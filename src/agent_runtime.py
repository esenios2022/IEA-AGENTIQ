"""Runs a persisted agent definition as a live conversational assistant."""

from anthropic import Anthropic

from src.config import settings
from src.models import Agent

MODEL = "claude-sonnet-4-6"

# 2026-07-18 -- principios comunes a los 46 agentes, agregados una sola vez
# aca (no en cada prompt de agents_config.json) porque system_prompt_for()
# es el unico punto por el que pasa el prompt final tanto del chat
# interactivo (AgentRuntime) como del pipeline en lote (agent_executor).
# Adaptados de un framework externo (ADAPTA.ORG) a pedido del usuario --
# se tomaron los 4 principios con impacto real en un producto de agentes
# que ejecutan tareas (no las reglas de estilo de superficie del original,
# que apuntaban a como escribe un asistente conversacional, no a como
# ejecuta un agente de fondo).
COMMON_PRINCIPLES = """PRINCIPIOS DE TRABAJO (aplican a toda tarea, ademas de tus instrucciones especificas):
1) VERIFICACION: antes de afirmar que algo se guardo, se genero o funciono, confirmalo de verdad -- no lo asumas por falta de error. Si no podes verificar, decilo explicitamente en vez de darlo por hecho.
2) SIN COMPLACENCIA: si un pedido tiene una falla logica o va a perjudicar el resultado del cliente, decilo con claridad y proponé una alternativa mejor, en vez de ejecutar sin cuestionar.
3) CONSECUENCIAS: antes de una accion con efecto real (publicar, gastar, enviar, borrar), pensa que pasa despues y a quien mas afecta; si hay riesgo, señalalo antes de actuar, aunque no te lo hayan pedido.
4) PATRONES REPETIDOS: si la misma tarea vuelve a aparecer, no la resuelvas de cero cada vez -- proponé guardarla como plantilla o proceso reutilizable.
5) EXPERTISE REAL: sos un experto real en el rol específico que tu identidad describe, no un asistente genérico. Respondé y decidí con el criterio de un profesional experimentado en esa función precisa (no "marketing en general", sino tu especialidad puntual) -- eso incluye tomar decisiones concretas (horarios, formatos, prioridades) en vez de devolvérselas al usuario cuando la respuesta cae dentro de tu expertise."""


def system_prompt_for(agent: Agent) -> str:
    definition = agent.definition or {}
    instructions = definition.get("instructions") or {}
    if instructions.get("system_prompt"):
        base = instructions["system_prompt"]
    else:
        prompts = definition.get("prompts") or {}
        if prompts.get("system"):
            base = prompts["system"]
        else:
            base = f"Eres {agent.name}. Rol: {agent.role}. {agent.description or ''}".strip()
    return f"{base}\n\n{COMMON_PRINCIPLES}"


class AgentRuntime:
    """Holds one live conversation with a single persisted agent."""

    def __init__(self, agent: Agent, api_key: str | None = None):
        self.agent = agent
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.system_prompt = system_prompt_for(agent)
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
