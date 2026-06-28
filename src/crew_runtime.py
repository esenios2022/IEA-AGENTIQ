"""Turns a persisted agent definition into a real CrewAI crew and runs it."""

from crewai import Agent as CrewAgent
from crewai import Crew, Task

from src.models import Agent

CREW_LLM = "anthropic/claude-sonnet-4-6"


def build_crew(agent: Agent) -> Crew:
    definition = agent.definition or {}

    crew_agents: dict[str, CrewAgent] = {}
    for spec in definition.get("agents") or []:
        crew_agents[spec.get("name", "agente")] = CrewAgent(
            role=spec.get("role", agent.role),
            goal=spec.get("goal", agent.description or ""),
            backstory=spec.get("backstory", ""),
            llm=CREW_LLM,
            verbose=True,
        )
    if not crew_agents:
        crew_agents["principal"] = CrewAgent(
            role=agent.role,
            goal=agent.description or agent.requirement or "",
            backstory="",
            llm=CREW_LLM,
            verbose=True,
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

    return Crew(agents=list(crew_agents.values()), tasks=crew_tasks, verbose=True)


def run_crew(agent: Agent, extra_input: str | None = None) -> str:
    crew = build_crew(agent)
    result = crew.kickoff(inputs={"input": extra_input} if extra_input else None)
    return str(result)
