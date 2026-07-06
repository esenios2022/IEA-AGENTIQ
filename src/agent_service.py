"""Single orchestration entrypoint for running an agent.

Order of operations: cache lookup -> budget check -> tier selection -> route to
the lean executor or CrewAI -> record cost -> write cache. `main.py` and
`scheduler.py` call `run()` here instead of the executors directly.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent_executor import run_agent as run_lean_agent
from src.case_memory import append_message, get_case_history
from src.config import settings
from src.cost import BudgetDecision, check_budget, record_usage
from src.crew_runtime import run_crew
from src.llm_pricing import TIER_MODELS
from src.models import Agent, ResponseCache
from src.tiering import select_tier

LISA_CODE = "agent_032"

CACHE_TTL = timedelta(hours=24)


@dataclass
class RunOutcome:
    result: str
    cost_usd: float
    tier_used: str
    cached: bool


class AgentPausedError(PermissionError):
    pass


def _cache_key(agent_id, tier: str, extra_input: str | None) -> str:
    normalized = (extra_input or "").strip().lower()
    raw = f"{agent_id}:{tier}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_lookup(db: Session, agent_id, tier: str, extra_input: str | None) -> ResponseCache | None:
    key = _cache_key(agent_id, tier, extra_input)
    cutoff = datetime.utcnow() - CACHE_TTL
    return db.scalar(
        select(ResponseCache)
        .where(
            ResponseCache.agent_id == agent_id,
            ResponseCache.hash_prompt == key,
            ResponseCache.created_at >= cutoff,
        )
        .order_by(ResponseCache.created_at.desc())
    )


def _cache_write(db: Session, agent_id, tier: str, extra_input: str | None, response_text: str) -> None:
    key = _cache_key(agent_id, tier, extra_input)
    db.add(ResponseCache(agent_id=agent_id, hash_prompt=key, response=response_text))
    db.commit()


def _is_multi_step(definition: dict) -> bool:
    """Structural routing rule: teams (>1 sub-agent/task) go to CrewAI, everything else to the lean executor."""
    return len(definition.get("agents") or []) > 1 or len(definition.get("tasks") or []) > 1


def run(
    db: Session,
    agent: Agent,
    extra_input: str | None = None,
    user_id: str | None = None,
    client_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None = None,
    gemini_key: str | None = None,
    history: list[dict] | None = None,
) -> RunOutcome:
    definition = agent.definition or {}

    # Lisa Mawu uses Gemini: prefer caller-supplied key, then platform env var.
    # Either way cost is $0 to the Anthropic budget.
    is_lisa = agent.agent_code == LISA_CODE or agent.name == "Lisa Mawu"
    effective_gemini_key = gemini_key or (settings.gemini_api_key if is_lisa else None)
    if effective_gemini_key:
        from src.gemini_executor import run_gemini
        exec_result = run_gemini(agent, extra_input or "", effective_gemini_key, history=history)
        return RunOutcome(result=exec_result.text, cost_usd=0.0, tier_used="gemini-free", cached=False)

    decision = check_budget(db, agent)
    if decision == BudgetDecision.PAUSED:
        raise AgentPausedError(
            f"«{agent.name}» está pausado: superó su presupuesto diario (${agent.daily_budget_usd}). "
            "Se reactiva automáticamente mañana."
        )

    tier, _reason = select_tier(agent, extra_input)
    if decision == BudgetDecision.FORCE_ECONOMY:
        tier = "economy"

    # Case-based runs carry their own conversation memory, so identical text at two
    # different points in a patient's history must NOT be deduped by the response cache.
    if case_id is None:
        cached_row = _cache_lookup(db, agent.id, tier, extra_input)
        if cached_row is not None:
            record_usage(
                db,
                agent_id=agent.id,
                client_id=client_id,
                execution_id=None,
                model=TIER_MODELS[tier],
                tier=tier,
                input_tokens=0,
                output_tokens=0,
                cached=True,
                success=True,
                input_text=extra_input,
                result_text=cached_row.response,
            )
            return RunOutcome(result=cached_row.response, cost_usd=0.0, tier_used=tier, cached=True)

    case_history = get_case_history(db, case_id) if case_id is not None else None
    effective_history = case_history if case_id is not None else history

    execution_id = uuid.uuid4()
    try:
        if case_id is not None:
            exec_result = run_lean_agent(agent, tier, extra_input, user_id=user_id, history=effective_history)
        elif _is_multi_step(definition):
            exec_result = run_crew(agent, extra_input, user_id=user_id, tier=tier)
        else:
            exec_result = run_lean_agent(agent, tier, extra_input, user_id=user_id, history=effective_history)
    except Exception as exc:
        record_usage(
            db,
            agent_id=agent.id,
            client_id=client_id,
            execution_id=execution_id,
            model=TIER_MODELS[tier],
            tier=tier,
            input_tokens=0,
            output_tokens=0,
            success=False,
            error_message=str(exc),
            input_text=extra_input,
        )
        raise

    log = record_usage(
        db,
        agent_id=agent.id,
        client_id=client_id,
        execution_id=execution_id,
        model=exec_result.model,
        tier=tier,
        input_tokens=exec_result.input_tokens,
        output_tokens=exec_result.output_tokens,
        tool_calls=exec_result.tool_calls,
        success=True,
        input_text=extra_input,
        result_text=exec_result.text,
    )

    if case_id is not None:
        append_message(db, case_id, "user", extra_input or "", cost_usd=None)
        append_message(db, case_id, "assistant", exec_result.text, cost_usd=float(log.cost_usd))
    else:
        _cache_write(db, agent.id, tier, extra_input, exec_result.text)

    return RunOutcome(result=exec_result.text, cost_usd=float(log.cost_usd), tier_used=tier, cached=False)
