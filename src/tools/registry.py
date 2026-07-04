"""Single lookup table for tools referenced by name in an agent's definition.

Merges every non-Composio, non-Zapier tool (those are dynamic, assembled
separately in `src.tool_assembly`) into one dict, keyed by the name used in
`definition["tools"][*]["name"]`.
"""

from src.tools.google_calendar import TOOL_REGISTRY as _GOOGLE_CALENDAR_TOOLS
from src.tools.knowledge_base import KnowledgeBaseTool
from src.tools.postgres_query import PostgresQueryTool
from src.tools.testing_tools import ChecklistTool
from src.tools.web_search import SerperSearchTool

TOOL_REGISTRY = {
    **_GOOGLE_CALENDAR_TOOLS,
    "postgres_query": PostgresQueryTool(),
    "testing_tools": ChecklistTool(),
    "web_search": SerperSearchTool(),
    "knowledge_base": KnowledgeBaseTool(),
}
