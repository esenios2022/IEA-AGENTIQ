"""Turns a persisted agent definition into a real CrewAI crew and runs it.

Fallback execution path for multi-agent/multi-task "team" definitions (the
kind Obatalá can design). Single agent/single task definitions — including
all 16 master agents — run through the cheaper `src.agent_executor` instead;
see `src.agent_service` for the routing decision.
"""

import concurrent.futures

from crewai import LLM, Agent as CrewAgent
from crewai import Crew, Task

from src.exec_result import ExecResult
from src.llm_pricing import TIER_MAX_TOKENS, TIER_MODELS, TIER_TEMPERATURE
from src.models import Agent
from src.tool_assembly import assemble_tools

KICKOFF_TIMEOUT_SECONDS = 240


def _llm_for_tier(tier: str) -> LLM:
    model = TIER_MODELS.get(tier, TIER_MODELS["standard"])
    return LLM(
        model=f"anthropic/{model}",
        max_tokens=TIER_MAX_TOKENS.get(tier, 2048),
        temperature=TIER_TEMPERATURE.get(tier, 0.5),
    )


def build_crew(
    agent: Agent, extra_input: str | None = None, user_id: str | None = None, tier: str = "standard"
) -> Crew:
    definition = agent.definition or {}
    composio_user_id = user_id or str(agent.id)
    shared_tools = assemble_tools(definition, composio_user_id)
    crew_llm = _llm_for_tier(tier)
    context_block = (
        f"\n\nDATOS REALES DE ESTE CASO (usalos tal cual, no inventes otros nombres ni datos):\n{extra_input}"
        if extra_input
        else ""
    )

    crew_agents: dict[str, CrewAgent] = {}
    for spec in definition.get("agents") or []:
        crew_agents[spec.get("name", "agente")] = CrewAgent(
            role=spec.get("role", agent.role),
            goal=spec.get("goal", agent.description or ""),
            backstory=spec.get("backstory", ""),
            tools=shared_tools,
            llm=crew_llm,
            verbose=False,
        )
    if not crew_agents:
        crew_agents["principal"] = CrewAgent(
            role=agent.role,
            goal=agent.description or agent.requirement or "",
            backstory="",
            tools=shared_tools,
            llm=crew_llm,
            verbose=False,
        )

    fallback_agent = next(iter(crew_agents.values()))
    crew_tasks: list[Task] = []
    for spec in definition.get("tasks") or []:
        crew_tasks.append(
            Task(
                description=spec.get("description", "") + context_block,
                expected_output=spec.get("expected_output", "Resultado de la tarea."),
                agent=crew_agents.get(spec.get("agent"), fallback_agent),
            )
        )
    if not crew_tasks:
        crew_tasks.append(
            Task(
                description=(agent.requirement or agent.description or f"Cumplí tu objetivo como {agent.role}.")
                + context_block,
                expected_output="Resultado de la tarea.",
                agent=fallback_agent,
            )
        )

    return Crew(agents=list(crew_agents.values()), tasks=crew_tasks, verbose=False)


def run_crew(
    agent: Agent, extra_input: str | None = None, user_id: str | None = None, tier: str = "standard"
) -> ExecResult:
    """Fallback path for multi-agent/multi-task definitions. See module docstring."""
    print(f"[crew_runtime] building crew for agent {agent.id} (tier={tier})", flush=True)
    crew = build_crew(agent, extra_input, user_id=user_id, tier=tier)

    print(f"[crew_runtime] kicking off crew (timeout={KICKOFF_TIMEOUT_SECONDS}s)", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(crew.kickoff)
        try:
            result = future.result(timeout=KICKOFF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutError(
                f"CrewAI no respondió en {KICKOFF_TIMEOUT_SECONDS}s. "
                "Puede ser un problema de red o un modelo/LLM mal configurado."
            ) from exc

    print("[crew_runtime] kickoff finished", flush=True)
    usage = result.token_usage
    return ExecResult(
        text=str(result),
        model=TIER_MODELS.get(tier, TIER_MODELS["standard"]),
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        tool_calls=0,
    )
