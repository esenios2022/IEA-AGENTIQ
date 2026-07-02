"""Daily budget enforcement and usage recording — the platform's cost ledger."""

import enum
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.llm_pricing import calculate_cost_usd
from src.models import Agent, UsageLog

BUDGET_WARN_RATIO = 0.8


class BudgetDecision(enum.Enum):
    OK = "ok"
    FORCE_ECONOMY = "force_economy"
    PAUSED = "paused"


def _today_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def get_daily_spend(db: Session, agent_id, now: datetime | None = None) -> float:
    start, end = _today_bounds(now)
    total = db.scalar(
        select(func.coalesce(func.sum(UsageLog.cost_usd), 0)).where(
            UsageLog.agent_id == agent_id,
            UsageLog.created_at >= start,
            UsageLog.created_at < end,
        )
    )
    return float(total or 0)


def check_budget(db: Session, agent: Agent) -> BudgetDecision:
    """Compares today's spend against the agent's daily_budget_usd.

    Self-healing: a `paused` agent is re-activated the moment a fresh check
    finds today's spend back under budget (i.e. the day rolled over) — no
    separate reactivation job needed.
    """
    if not agent.daily_budget_usd or agent.daily_budget_usd <= 0:
        if agent.status == "paused":
            agent.status = "active"
        return BudgetDecision.OK

    spend = get_daily_spend(db, agent.id)
    ratio = spend / agent.daily_budget_usd

    if ratio >= 1.0:
        if agent.status != "paused":
            agent.status = "paused"
            db.commit()
        return BudgetDecision.PAUSED

    if agent.status == "paused":
        agent.status = "active"
        db.commit()

    if ratio >= BUDGET_WARN_RATIO:
        return BudgetDecision.FORCE_ECONOMY

    return BudgetDecision.OK


def record_usage(
    db: Session,
    *,
    agent_id,
    client_id,
    execution_id: uuid.UUID | None,
    model: str,
    tier: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int = 0,
    cached: bool = False,
    success: bool = True,
    error_message: str | None = None,
) -> UsageLog:
    cost_usd = 0.0 if cached else calculate_cost_usd(model, input_tokens, output_tokens)
    log = UsageLog(
        agent_id=agent_id,
        client_id=client_id,
        execution_id=execution_id or uuid.uuid4(),
        model=model,
        tier=tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        cached=cached,
        success=success,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
