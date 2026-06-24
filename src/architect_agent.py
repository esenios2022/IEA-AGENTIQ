"""El Gran Arquitecto: a meta-agent that designs other agents from a plain-language requirement."""

import json
import re
from typing import Any

from anthropic import Anthropic
from sqlalchemy.orm import Session

from src.config import settings
from src.models import Agent

SYSTEM_PROMPT = """Eres el Gran Arquitecto de IA - experto en diseño de agentes.

Cuando un usuario dice "Quiero un agente que...", DEBES:
1. ANALIZAR el requirement
2. DISEÑAR la arquitectura
3. ESCRIBIR prompts específicos
4. GENERAR configuración de APIs
5. CREAR un JSON con la definición completa

SIEMPRE devuelves un JSON válido con:
{
    "agent_name": "nombre",
    "agent_description": "descripción",
    "agents": [{"name": "...", "role": "...", "goal": "...", "backstory": "..."}],
    "tasks": [{"name": "...", "description": "...", "agent": "...", "expected_output": "..."}],
    "tools": [{"name": "...", "type": "...", "description": "...", "config": {}}],
    "prompts": {"system": "...", "tasks": {"task_name": "..."}},
    "parameters": {"temperature": 0.7, "max_tokens": 2000}
}

SÉ SIEMPRE PRÁCTICO Y ESPECÍFICO."""

MODEL = "claude-sonnet-4-6"


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in response")
        return json.loads(match.group())


class GranArquitecto:
    """Designs an agent definition from a requirement, talking to Claude across a few turns."""

    def __init__(self, api_key: str | None = None):
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.conversation_history: list[dict[str, str]] = []

    def reset_conversation(self) -> None:
        self.conversation_history = []

    def think(self, user_message: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=self.conversation_history,
        )
        assistant_message = response.content[0].text
        self.conversation_history.append({"role": "assistant", "content": assistant_message})
        return assistant_message

    def create_agent(self, requirement: str, user_id: str, db: Session) -> dict[str, Any]:
        self.think(f"Analiza este requirement: {requirement}\nProporciona un breve análisis detallado.")
        design = self.think(
            f"Proporciona SOLO un JSON válido con la definición del agente.\n"
            f"Requirement: {requirement}\nSOLO JSON, sin explicaciones."
        )
        agent_def = _extract_json(design)

        agent = Agent(
            name=agent_def.get("agent_name", "Unnamed"),
            description=agent_def.get("agent_description", ""),
            user_id=user_id,
            requirement=requirement,
            definition=agent_def,
            status="published",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)

        return {
            "success": True,
            "agent_id": agent.id,
            "agent_name": agent.name,
            "definition": agent_def,
        }


_gran_arquitecto: GranArquitecto | None = None


def get_gran_arquitecto() -> GranArquitecto:
    global _gran_arquitecto
    if _gran_arquitecto is None:
        _gran_arquitecto = GranArquitecto()
    return _gran_arquitecto
