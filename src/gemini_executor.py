"""Gemini executor — uses the client's own Google Gemini API key.

Cost is charged to the client's Google account, not the platform.
Supports full conversation history so Lisa remembers prior turns.
"""

from src.agent_runtime import system_prompt_for
from src.exec_result import ExecResult
from src.models import Agent

GEMINI_MODEL = "gemini-2.5-flash"

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
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_prompt_for(agent),
    )

    gemini_history = []
    for msg in (history or []):
        role = "user" if msg.get("role") == "user" else "model"
        content = msg.get("content", "")
        if role == "model":
            content = _clean_assistant_msg(content)
        if content.strip():
            gemini_history.append({"role": role, "parts": [content]})

    chat = model.start_chat(history=gemini_history)
    response = chat.send_message(user_message)

    text = response.text or ""
    return ExecResult(text=text, model=GEMINI_MODEL, input_tokens=0, output_tokens=0, tool_calls=0)
