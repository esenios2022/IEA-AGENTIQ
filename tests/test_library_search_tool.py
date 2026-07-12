"""FASE 2.3 — src.tools.library_search.LibrarySearchTool. Patches
`src.tools.library_search.library.search_assets` (module boundary),
same convention as tests/test_ai_lab_knowledge_tool.py patching the AI
LAB client."""

from unittest.mock import MagicMock, patch

from src.tools.library_search import LibrarySearchTool


def test_run_formats_results():
    fake_asset = MagicMock(
        category="Marca", subcategory="Logos", title="Logo principal",
        file_type="imagen", language="es", text_content=None, description="Logo oficial en fondo transparente",
    )
    tool = LibrarySearchTool(client_id="client-1")

    with patch("src.tools.library_search.library.search_assets", return_value=[fake_asset]) as mock_search:
        result = tool._run("logo")

    mock_search.assert_called_once()
    _, kwargs = mock_search.call_args
    assert kwargs["client_id"] == "client-1"
    assert kwargs["status"] == "aprobado"
    assert "Logo principal" in result
    assert "Marca/Logos" in result


def test_run_returns_message_when_no_results():
    tool = LibrarySearchTool(client_id=None)

    with patch("src.tools.library_search.library.search_assets", return_value=[]):
        result = tool._run("algo que no existe")

    assert "No se encontró" in result
