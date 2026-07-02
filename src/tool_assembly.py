"""Assembles the list of CrewAI `BaseTool` instances for an agent definition.

Shared by both execution paths: the lean `agent_executor` (default, single
agent/task) and the CrewAI-based `crew_runtime` (fallback, multi-agent teams).
Keeping this in one place means a tool only needs to be registered once to be
usable from either executor.
"""

from src.composio_tools import get_toolkit_tools
from src.tools.registry import TOOL_REGISTRY
from src.tools.zapier import build_zapier_tools

# Toolkit slugs Obatalá (or the master agent seed) can reference by name even
# without an explicit "composio" type.
KNOWN_COMPOSIO_TOOLKITS = {
    "gmail",
    "whatsapp",
    "googlesheets",
    "google_sheets",
    "slack",
    "notion",
    "hubspot",
    "linkedin",
}


def _matching_tools(definition: dict) -> list:
    tools = []
    for spec in definition.get("tools") or []:
        tool = TOOL_REGISTRY.get(spec.get("name", ""))
        if tool is not None and tool not in tools:
            tools.append(tool)
    return tools


def _composio_tools(definition: dict, user_id: str) -> list:
    toolkit_slugs = set()
    for spec in definition.get("tools") or []:
        name = (spec.get("name") or "").lower().replace(" ", "_")
        if spec.get("type") == "composio":
            toolkit_slugs.add(name)
        elif name in KNOWN_COMPOSIO_TOOLKITS:
            toolkit_slugs.add(name)

    if not toolkit_slugs:
        return []

    try:
        return list(get_toolkit_tools(user_id, list(toolkit_slugs)))
    except Exception as exc:
        print(f"[tool_assembly] Composio tools unavailable ({exc}), continuing without them", flush=True)
        return []


def assemble_tools(definition: dict, user_id: str) -> list:
    return (
        _matching_tools(definition)
        + _composio_tools(definition, user_id)
        + build_zapier_tools(definition.get("tools") or [])
    )
