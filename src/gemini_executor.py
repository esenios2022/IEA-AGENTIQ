"""Gemini executor — uses the client's own Google Gemini API key.

Cost is charged to the client's Google account, not the platform.
Supports full conversation history so Lisa remembers prior turns.

Modo Producción (2026-07-15) — reescrito con el SDK `google-genai` (el
`google.generativeai` viejo está deprecado por Google y, confirmado real
con una key nueva, `gemini-2.5-flash` ya devuelve 404 "no longer
available to new users" en ese SDK viejo — el camino BYOK de Gemini
estaba roto para cualquier key nueva, no solo "deprecado"). Se usa
`gemini-flash-latest` (alias que Google mantiene apuntando al modelo
flash vigente) en vez de fijar una versión — confirmado real que
`gemini-2.5-flash`/`gemini-2.0-flash` fijos ya no están disponibles para
keys nuevas. Se capturan tokens reales de `usage_metadata` (antes
quedaban hardcodeados en 0, lo que rompía cualquier medición de costo
real para agentes corriendo en Gemini).
"""

from src.agent_runtime import system_prompt_for
from src.exec_result import ExecResult
from src.models import Agent

GEMINI_MODEL = "gemini-flash-latest"

_META_PREFIXES = ("[tier:", "[🟢 Gemini", "[⚠️")


def _clean_assistant_msg(text: str) -> str:
    """Strip the cost/tier metadata prefix the UI prepends to assistant messages."""
    if text.startswith(_META_PREFIXES):
        body_start = text.find("\n\n")
        if body_start != -1:
            return text[body_start + 2:]
    return text


def run_gemini(
    agent: Agent,
    user_message: str,
    api_key: str,
    history: list[dict] | None = None,
) -> ExecResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    gemini_history = []
    for msg in (history or []):
        role = "user" if msg.get("role") == "user" else "model"
        content = msg.get("content", "")
        if role == "model":
            content = _clean_assistant_msg(content)
        if content.strip():
            gemini_history.append(types.Content(role=role, parts=[types.Part(text=content)]))

    chat = client.chats.create(
        model=GEMINI_MODEL,
        config=types.GenerateContentConfig(system_instruction=system_prompt_for(agent)),
        history=gemini_history,
    )
    response = chat.send_message(user_message)

    usage = response.usage_metadata
    input_tokens = (usage.prompt_token_count or 0) if usage else 0
    output_tokens = ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0

    text = response.text or ""
    return ExecResult(text=text, model=GEMINI_MODEL, input_tokens=input_tokens, output_tokens=output_tokens, tool_calls=0)
