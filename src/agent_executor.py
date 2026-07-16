"""Lean, cost-conscious executor: native Anthropic tool-use, no CrewAI overhead.

Default execution path for single agent / single task definitions — which is
every one of the 16 master agents. CrewAI (`src.crew_runtime`) stays as the
fallback for multi-agent "team" definitions Obatalá can design; see
`src.agent_service` for the routing decision between the two.

Cost optimizations specific to going through the Anthropic SDK directly
(not available/easy through CrewAI):
- Prompt caching (`cache_control: ephemeral`) on the system prompt, which is
  long and reused verbatim across every run of a given agent.
- Exact per-call token accounting straight from the API response, rather than
  relying on a crew-level aggregate.
"""

import concurrent.futures

from anthropic import Anthropic

from src.agent_runtime import system_prompt_for
from src.config import settings
from src.exec_result import ExecResult
from src.llm_pricing import TIER_MAX_TOKENS, TIER_MODELS, TIER_TEMPERATURE
from src.models import Agent
from src.tool_assembly import assemble_tools
from src.tools.knowledge_base import SHORTCUT_SIMILARITY_THRESHOLD, best_match

EXEC_TIMEOUT_SECONDS = 240
MAX_TOOL_ITERATIONS = 8


def _tool_to_anthropic_schema(tool) -> dict:
    schema = tool.args_schema.model_json_schema()
    schema.pop("title", None)
    return {
        "name": tool.name,
        "description": tool.description[:4000],
        "input_schema": schema,
    }


def _run_tool(tools_by_name: dict, name: str, tool_input: dict) -> str:
    tool = tools_by_name.get(name)
    if tool is None:
        return f"Error: la herramienta «{name}» no está disponible."
    try:
        result = tool.run(**tool_input)
        return str(result)
    except Exception as exc:
        return f"Error ejecutando «{name}»: {exc}"


def _initial_task_text(agent: Agent, extra_input: str | None) -> str:
    definition = agent.definition or {}
    tasks = definition.get("tasks") or []
    base = tasks[0].get("description") if tasks else None
    base = base or agent.requirement or agent.description or f"Cumplí tu objetivo como {agent.role}."
    if extra_input:
        base += f"\n\nDATOS REALES DE ESTE CASO (usalos tal cual, no inventes otros nombres ni datos):\n{extra_input}"
    return base


def _run_loop(
    agent: Agent,
    tier: str,
    extra_input: str | None,
    user_id: str,
    history: list[dict] | None = None,
    composio_user_id: str | None = None,
) -> ExecResult:
    model = TIER_MODELS.get(tier, TIER_MODELS["standard"])
    max_tokens = TIER_MAX_TOKENS.get(tier, 2048)
    temperature = TIER_TEMPERATURE.get(tier)  # None (e.g. "premium") -> omitido, ver llm_pricing.py

    definition = agent.definition or {}

    if definition.get("knowledge_base_shortcut") and extra_input:
        match = best_match(extra_input, agent_id=agent.id)
        if match is not None:
            article, score = match
            if score >= SHORTCUT_SIMILARITY_THRESHOLD:
                return ExecResult(text=article.respuesta, model=model, input_tokens=0, output_tokens=0, tool_calls=1)

    tools = assemble_tools(definition, user_id, agent_id=agent.id, composio_user_id=composio_user_id)
    tools_by_name = {t.name: t for t in tools}
    anthropic_tools = [_tool_to_anthropic_schema(t) for t in tools]

    system_prompt = system_prompt_for(agent)
    client = Anthropic(api_key=settings.anthropic_api_key)

    if history:
        # Continuing an open case: prior turns carry the framing already, so the new
        # message goes in as-is rather than re-wrapped in the task/objective template.
        messages: list[dict] = list(history) + [{"role": "user", "content": extra_input or "Continuá."}]
    else:
        messages = [{"role": "user", "content": _initial_task_text(agent, extra_input)}]

    input_tokens = 0
    output_tokens = 0
    tool_calls = 0
    final_text = ""

    for _ in range(MAX_TOOL_ITERATIONS):
        create_kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        if temperature is not None:
            create_kwargs["temperature"] = temperature
        if anthropic_tools:
            create_kwargs["tools"] = anthropic_tools
        response = client.messages.create(**create_kwargs)
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        text_parts = [block.text for block in response.content if block.type == "text"]
        final_text = "\n".join(text_parts).strip() or final_text

        if response.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_calls += 1
            output = _run_tool(tools_by_name, block.name, block.input or {})
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        messages.append({"role": "user", "content": tool_results})
    else:
        final_text = final_text or "El agente alcanzó el máximo de pasos de herramientas sin terminar."

    return ExecResult(
        text=final_text,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
    )


def run_agent(
    agent: Agent,
    tier: str,
    extra_input: str | None = None,
    user_id: str | None = None,
    history: list[dict] | None = None,
    composio_user_id: str | None = None,
) -> ExecResult:
    resolved_user_id = user_id or str(agent.id)
    print(f"[agent_executor] running agent {agent.id} (tier={tier})", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_loop, agent, tier, extra_input, resolved_user_id, history, composio_user_id)
        try:
            return future.result(timeout=EXEC_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutError(
                f"El agente no respondió en {EXEC_TIMEOUT_SECONDS}s. "
                "Puede ser un problema de red o un modelo/LLM mal configurado."
            ) from exc
