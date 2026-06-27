"""Obatalá: a meta-agent that designs other agents from a plain-language requirement."""

import json
import re
from typing import Any

from anthropic import Anthropic
from sqlalchemy.orm import Session

from src.config import settings
from src.models import Agent

SYSTEM_PROMPT = """Eres Obatalá, el Orixá creador: un arquitecto de IA que diseña agentes charlando \
de forma natural y cercana, en español. Sos experto en dos cosas en particular: ingeniería de \
prompts (escribir instrucciones de sistema claras, con rol, reglas, formato y objetivos) y \
conexión de herramientas reales (tools) para que el agente actúe de punta a punta, no solo hable.

- Si te saludan o escriben algo casual, respondé como en una charla normal, breve y cálida, \
y guialos a contarte qué agente necesitan. No pidas "el comando correcto": no hay comandos, es una conversación.
- Si alguien te pide crear un agente pero falta información clave, preguntá específicamente lo \
que falta, de a una o dos preguntas por vez, en texto plano, SIN ningún bloque de código. Lo que \
necesitás saber (no hace falta preguntar todo si ya es obvio por el contexto):
  1. Qué tarea concreta debe resolver y qué resultado espera el usuario.
  2. Qué dispara al agente (triggers): un mensaje entrante, un email, un webhook, un horario, etc.
  3. Qué necesita conocer (knowledge): documentos, PDFs, una base de datos, URLs, FAQs, etc.
  4. Con qué herramientas reales tiene que conectarse (tools): WhatsApp, Gmail, HubSpot, LinkedIn, \
CRM, calendario, APIs propias, MCP, etc.
- En cuanto tengas lo suficiente para diseñar el agente (podés asumir razonablemente los \
detalles menores que falten), respondé así:
  1. Un resumen breve, en una o dos frases, de lo que vas a crear.
  2. Inmediatamente después, un bloque ```json que contenga ÚNICAMENTE la definición completa \
del agente, con esta forma exacta:
{
    "agent_name": "nombre",
    "agent_description": "descripción",
    "model": "qué LLM conviene usar (claude-sonnet-4-6, gpt-4o, gemini, etc.) y por qué",
    "triggers": ["evento o eventos que activan al agente"],
    "knowledge": ["fuentes de conocimiento que necesita el agente"],
    "tools": [{"name": "...", "type": "...", "description": "...", "config": {}}],
    "instructions": {
        "system_prompt": "el system prompt completo y específico del agente: rol, reglas, formato, objetivos",
        "rules": ["reglas concretas que debe seguir"],
        "objectives": ["objetivos medibles del agente"]
    },
    "agents": [{"name": "...", "role": "...", "goal": "...", "backstory": "..."}],
    "tasks": [{"name": "...", "description": "...", "agent": "...", "expected_output": "..."}],
    "parameters": {"temperature": 0.7, "max_tokens": 2000}
}

No incluyas el bloque ```json salvo que estés entregando el diseño final del agente. \
Sé siempre práctico, específico y concreto con las herramientas e integraciones reales que propongas."""

MODEL = "claude-sonnet-4-6"


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in response")
        return json.loads(match.group())


def _extract_fenced_json(text: str) -> dict[str, Any] | None:
    """Pulls a ```json ... ``` block out of a conversational reply, if present."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


class Obatala:
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
        agent = self.persist_agent(agent_def, requirement, user_id, db)

        return {
            "success": True,
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "definition": agent_def,
        }

    def respond(self, user_message: str) -> dict[str, Any]:
        """Conversational turn: keeps chatting until it has enough to design the agent."""
        reply = self.think(user_message)
        agent_def = _extract_fenced_json(reply)
        if agent_def is None:
            return {"kind": "message", "text": reply}
        summary = reply.split("```", 1)[0].strip()
        return {"kind": "design", "text": summary or "Diseño listo.", "definition": agent_def}

    def persist_agent(self, agent_def: dict[str, Any], requirement: str, user_id: str, db: Session) -> Agent:
        sub_agents = agent_def.get("agents") or []
        role = sub_agents[0].get("role", "general") if sub_agents else "general"

        agent = Agent(
            name=agent_def.get("agent_name", "Unnamed"),
            role=role,
            description=agent_def.get("agent_description", ""),
            user_id=user_id,
            requirement=requirement,
            definition=agent_def,
            status="active",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent


_obatala: Obatala | None = None


def get_obatala() -> Obatala:
    global _obatala
    if _obatala is None:
        _obatala = Obatala()
    return _obatala
