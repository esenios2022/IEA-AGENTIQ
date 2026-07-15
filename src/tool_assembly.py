"""Assembles the list of CrewAI `BaseTool` instances for an agent definition.

Shared by both execution paths: the lean `agent_executor` (default, single
agent/task) and the CrewAI-based `crew_runtime` (fallback, multi-agent teams).
Keeping this in one place means a tool only needs to be registered once to be
usable from either executor.
"""

from src.composio_tools import get_toolkit_tools
from src.tools.ai_lab_knowledge import AiLabKnowledgeSearchTool
from src.tools.gemini_image_tool import GeminiImageTool
from src.tools.knowledge_base import KnowledgeBaseTool
from src.tools.library_save import LibrarySaveTool
from src.tools.library_search import LibrarySearchTool
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


def _matching_tools(definition: dict, agent_id=None, user_id=None) -> list:
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
        # Same reasoning as knowledge_base above — each agent's AI LAB search
        # is scoped to its own tenant (Client.id), never the shared singleton.
        if name == "ai_lab_knowledge":
            tools.append(AiLabKnowledgeSearchTool(tenant_id=str(user_id) if user_id else None))
            seen_names.add(name)
            continue
        # FASE 2.3/2.4A — each agent's Biblioteca search is scoped to its own
        # Client.id, never the shared singleton. Connected to Ariel/Marco/
        # Valentina/Elena in src/data/agents_config.json (FASE 2.4A).
        if name == "library_search":
            tools.append(LibrarySearchTool(client_id=str(user_id) if user_id else None))
            seen_names.add(name)
            continue
        # FASE 2.4A — scoped by BOTH client_id (tenant isolation) and
        # agent_id (so LibraryAsset.created_by_agent_id is real, not
        # guessed) — same "fresh instance, never the shared singleton"
        # reasoning as library_search/knowledge_base above.
        if name == "library_save":
            tools.append(LibrarySaveTool(client_id=str(user_id) if user_id else None, created_by_agent_id=str(agent_id) if agent_id else None))
            seen_names.add(name)
            continue
        # 2026-07-14 — misma razón que library_save: el UsageLog que graba
        # (agent_id) y el LibraryAsset que crea (created_by_agent_id,
        # client_id) tienen que ser reales, nunca el singleton compartido.
        if name == "gemini_image":
            tools.append(GeminiImageTool(client_id=str(user_id) if user_id else None, created_by_agent_id=str(agent_id) if agent_id else None))
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
        _matching_tools(definition, agent_id=agent_id, user_id=user_id)
        + _composio_tools(definition, user_id)
        + build_zapier_tools(definition.get("tools") or [])
    )
