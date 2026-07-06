"""Gemini executor — uses the client's own Google Gemini API key.

Cost is charged to the client's Google account, not the platform.
Supports conversation history and Google Search grounding (real-time web access).
"""

from src.agent_runtime import system_prompt_for
from src.exec_result import ExecResult
from src.models import Agent

GEMINI_MODEL = "gemini-2.0-flash-latest"


def run_gemini(
    agent: Agent,
    user_message: str,
    api_key: str,
    history: list[dict] | None = None,
    use_search: bool = True,
) -> ExecResult:
    import google.generativeai as genai
    from google.generativeai import types as gtypes

    genai.configure(api_key=api_key)

    tools = []
    if use_search:
        tools.append(gtypes.Tool(google_search=gtypes.GoogleSearch()))

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_prompt_for(agent),
        tools=tools if tools else None,
    )

    gemini_history = []
    for msg in (history or []):
        role = "user" if msg.get("role") == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg.get("content", "")]})

    chat = model.start_chat(history=gemini_history)
    response = chat.send_message(user_message)

    text = response.text or ""
    return ExecResult(text=text, model=GEMINI_MODEL, input_tokens=0, output_tokens=0, tool_calls=0)
