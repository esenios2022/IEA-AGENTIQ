"""Turns a persisted agent definition into a real CrewAI crew and runs it."""

import concurrent.futures

from crewai import Agent as CrewAgent
from crewai import Crew, Task

from src.models import Agent
from src.tools.google_calendar import TOOL_REGISTRY

CREW_LLM = "anthropic/claude-sonnet-4-6"
KICKOFF_TIMEOUT_SECONDS = 240


def _matching_tools(definition: dict) -> list:
    tools = []
    for spec in definition.get("tools") or []:
        tool = TOOL_REGISTRY.get(spec.get("name", ""))
        if tool is not None and tool not in tools:
            tools.append(tool)
    return tools


def build_crew(agent: Agent) -> Crew:
    definition = agent.definition or {}
    shared_tools = _matching_tools(definition)

    crew_agents: dict[str, CrewAgent] = {}
    for spec in definition.get("agents") or []:
        crew_agents[spec.get("name", "agente")] = CrewAgent(
            role=spec.get("role", agent.role),
            goal=spec.get("goal", agent.description or ""),
            backstory=spec.get("backstory", ""),
            tools=shared_tools,
            llm=CREW_LLM,
            verbose=False,
        )
    if not crew_agents:
        crew_agents["principal"] = CrewAgent(
            role=agent.role,
            goal=agent.description or agent.requirement or "",
            backstory="",
            tools=shared_tools,
            llm=CREW_LLM,
            verbose=False,
        )

    fallback_agent = next(iter(crew_agents.values()))
    crew_tasks: list[Task] = []
    for spec in definition.get("tasks") or []:
        crew_tasks.append(
            Task(
                description=spec.get("description", ""),
                expected_output=spec.get("expected_output", "Resultado de la tarea."),
                agent=crew_agents.get(spec.get("agent"), fallback_agent),
            )
        )
    if not crew_tasks:
        crew_tasks.append(
            Task(
                description=agent.requirement or agent.description or f"Cumplí tu objetivo como {agent.role}.",
                expected_output="Resultado de la tarea.",
                agent=fallback_agent,
            )
        )

    return Crew(agents=list(crew_agents.values()), tasks=crew_tasks, verbose=False)


def run_crew(agent: Agent, extra_input: str | None = None) -> str:
    print(f"[crew_runtime] building crew for agent {agent.id}", flush=True)
    crew = build_crew(agent)
    inputs = {"input": extra_input} if extra_input else None

    print(f"[crew_runtime] kicking off crew (timeout={KICKOFF_TIMEOUT_SECONDS}s)", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(crew.kickoff, inputs=inputs)
        try:
            result = future.result(timeout=KICKOFF_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutError(
                f"CrewAI no respondió en {KICKOFF_TIMEOUT_SECONDS}s. "
                "Puede ser un problema de red o un modelo/LLM mal configurado."
            ) from exc

    print("[crew_runtime] kickoff finished", flush=True)
    return str(result)
