"""Runs a persisted agent definition as a live conversational assistant."""

from anthropic import Anthropic

from src.config import settings
from src.models import Agent

MODEL = "claude-sonnet-4-6"


def _system_prompt_for(agent: Agent) -> str:
    definition = agent.definition or {}
    instructions = definition.get("instructions") or {}
    if instructions.get("system_prompt"):
        return instructions["system_prompt"]
    prompts = definition.get("prompts") or {}
    if prompts.get("system"):
        return prompts["system"]
    return f"Eres {agent.name}. Rol: {agent.role}. {agent.description or ''}".strip()


class AgentRuntime:
    """Holds one live conversation with a single persisted agent."""

    def __init__(self, agent: Agent, api_key: str | None = None):
        self.agent = agent
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.system_prompt = _system_prompt_for(agent)
        self.conversation_history: list[dict[str, str]] = []

    def reply(self, user_message: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=self.system_prompt,
            messages=self.conversation_history,
        )
        assistant_message = response.content[0].text
        self.conversation_history.append({"role": "assistant", "content": assistant_message})
        return assistant_message
