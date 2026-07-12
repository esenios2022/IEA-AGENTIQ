"""FASE 2.4A — src.agent_seed._map_tool. Confirms library_search/
library_save map to real tool definitions instead of falling through to
the "NOTA DE CONEXIÓN: todavía no están conectadas" unmapped-tool path
— a silent-failure risk found during this phase's implementation (the
Biblioteca tools would otherwise never reach src.tool_assembly's
_matching_tools())."""

from src.agent_seed import _map_tool


def test_library_search_maps_to_itself():
    assert _map_tool("library_search") == {"name": "library_search", "type": "library_search"}


def test_library_save_maps_to_itself():
    assert _map_tool("library_save") == {"name": "library_save", "type": "library_save"}


def test_unmapped_tool_still_returns_none():
    assert _map_tool("heygen_api") is None
