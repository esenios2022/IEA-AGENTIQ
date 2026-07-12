"""Single lookup table for tools referenced by name in an agent's definition.

Merges every non-Composio, non-Zapier tool (those are dynamic, assembled
separately in `src.tool_assembly`) into one dict, keyed by the name used in
`definition["tools"][*]["name"]`.
"""

from src.tools.ai_lab_knowledge import AiLabKnowledgeSearchTool
from src.tools.google_calendar import TOOL_REGISTRY as _GOOGLE_CALENDAR_TOOLS
from src.tools.knowledge_base import KnowledgeBaseTool
from src.tools.library_save import LibrarySaveTool
from src.tools.library_search import LibrarySearchTool
from src.tools.postgres_query import PostgresQueryTool
from src.tools.testing_tools import ChecklistTool
from src.tools.web_search import SerperSearchTool

TOOL_REGISTRY = {
    **_GOOGLE_CALENDAR_TOOLS,
    "postgres_query": PostgresQueryTool(),
    "testing_tools": ChecklistTool(),
    "web_search": SerperSearchTool(),
    "knowledge_base": KnowledgeBaseTool(),
    # "ai_lab_knowledge" is intentionally absent here — like knowledge_base,
    # it needs to be constructed fresh per agent (scoped by tenant_id), see
    # src/tool_assembly.py::_matching_tools(). This entry exists only so
    # `TOOL_REGISTRY.get("ai_lab_knowledge")` never silently returns None for
    # callers that don't go through _matching_tools.
    "ai_lab_knowledge": AiLabKnowledgeSearchTool(),
    # Same story as ai_lab_knowledge — "library_search" needs a fresh
    # instance scoped by client_id, see _matching_tools(). Placeholder only
    # so this key never silently returns None for callers outside
    # _matching_tools; the real, scoped instance used by Ariel/Marco/
    # Valentina/Elena (FASE 2.4A) is built there.
    "library_search": LibrarySearchTool(),
    # "library_save" (FASE 2.4A) needs a fresh instance scoped by BOTH
    # client_id and created_by_agent_id — same placeholder-only story.
    "library_save": LibrarySaveTool(),
}
