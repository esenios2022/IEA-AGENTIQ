"""Assembles the list of CrewAI `BaseTool` instances for an agent definition.

Shared by both execution paths: the lean `agent_executor` (default, single
agent/task) and the CrewAI-based `crew_runtime` (fallback, multi-agent teams).
Keeping this in one place means a tool only needs to be registered once to be
usable from either executor.
"""

from src.composio_tools import get_toolkit_tools
from src.tools.knowledge_base import KnowledgeBaseTool
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


def _matching_tools(definition: dict, agent_id=None) -> list:
    tools = []
    seen_names = set()
    for spec in definition.get("tools") or []:
        name = spec.get("name", "")
        if name in seen_names:
            continue
        # Constructed fresh (not the shared registry singleton) so each agent's
        # knowledge-base search is scoped to its own uploaded documents.
        if name == "knowledge_base":
            tools.append(KnowledgeBaseTool(agent_id=str(agent_id) if agent_id else None))
            seen_names.add(name)
            continue
        tool = TOOL_REGISTRY.get(name)
        if tool is not None:
            tools.append(tool)
            seen_names.add(name)
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


def assemble_tools(definition: dict, user_id: str, agent_id=None) -> list:
    return (
        _matching_tools(definition, agent_id=agent_id)
        + _composio_tools(definition, user_id)
        + build_zapier_tools(definition.get("tools") or [])
    )
