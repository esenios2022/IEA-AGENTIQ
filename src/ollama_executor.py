"""Ollama executor — modelo local corriendo en esta máquina
(http://localhost:11434, confirmado real: qwen2.5:14b entre los modelos
ya descargados). Costo real $0 para la plataforma, no es una API paga,
es cómputo local. Sin tool-calling (igual reserva que Gemini) — ver
src/provider_routing.py, que solo enruta acá agentes sin tools
configuradas.

Solo alcanza al proceso que corre en ESTA máquina. Si el backend se
despliega en otro host (ej. Railway) o el servicio de Ollama no está
levantado, `is_ollama_reachable()` devuelve False rápido (timeout corto)
y `select_provider()` cae a Claude sin intentar la llamada real —
nunca debe colgar ni romper una corrida de producción por depender de
un servicio local que puede no estar."""

import requests

from src.agent_runtime import system_prompt_for
from src.exec_result import ExecResult
from src.models import Agent

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b"
OLLAMA_HEALTH_TIMEOUT_SECONDS = 1.5
OLLAMA_CHAT_TIMEOUT_SECONDS = 120


class OllamaUnavailableError(RuntimeError):
    pass


def is_ollama_reachable() -> bool:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_HEALTH_TIMEOUT_SECONDS)
        return response.ok
    except requests.RequestException:
        return False


def run_ollama(
    agent: Agent,
    user_message: str,
    history: list[dict] | None = None,
) -> ExecResult:
    messages = [{"role": "system", "content": system_prompt_for(agent)}]
    for msg in (history or []):
        role = "user" if msg.get("role") == "user" else "assistant"
        content = msg.get("content", "")
        if content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=OLLAMA_CHAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaUnavailableError(f"Ollama no disponible en {OLLAMA_BASE_URL}: {exc}") from exc

    data = response.json()
    text = (data.get("message") or {}).get("content", "")
    # prompt_eval_count / eval_count son el equivalente real de Ollama a
    # input/output tokens (confirmado contra una llamada real al endpoint
    # /api/chat) — no hay pricing que aplicarles (cómputo local, no API
    # paga), pero se guardan igual en UsageLog para comparar volumen real
    # de tokens entre proveedores.
    input_tokens = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)

    return ExecResult(text=text, model=OLLAMA_MODEL, input_tokens=input_tokens, output_tokens=output_tokens, tool_calls=0)
