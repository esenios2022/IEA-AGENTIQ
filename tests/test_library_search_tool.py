"""FASE 2.3/2.4A — src.tools.library_search.LibrarySearchTool. Patches
`src.tools.library_search.library.search_assets` and `library_storage.
get_asset_url` (module boundary), same convention as
tests/test_ai_lab_knowledge_tool.py patching the AI LAB client."""

import json
from unittest.mock import MagicMock, patch

from src.tools.library_search import LibrarySearchTool


def _fake_asset(**overrides):
    defaults = dict(
        id="asset-1", category="Marca", subcategory="Logos", title="Logo principal",
        file_type="imagen", language="es", text_content=None, storage_key="global/Marca/Logos/x.png",
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def test_run_returns_structured_json_with_asset_id_url_type_status():
    fake_asset = _fake_asset(status="aprobado")
    tool = LibrarySearchTool(client_id="client-1")

    with patch("src.tools.library_search.library.search_assets", return_value=[fake_asset]) as mock_search, \
         patch("src.tools.library_search.library_storage.get_asset_url", return_value="https://cdn.example.com/logo.png"):
        result = tool._run("logo")

    mock_search.assert_called_once()
    _, kwargs = mock_search.call_args
    assert kwargs["client_id"] == "client-1"
    assert kwargs["status"] == "aprobado"

    payload = json.loads(result)
    assert len(payload) == 1
    item = payload[0]
    assert item["asset_id"] == "asset-1"
    assert item["url"] == "https://cdn.example.com/logo.png"
    assert item["file_type"] == "imagen"
    assert item["status"] == "aprobado"


def test_run_handles_text_only_assets_without_storage_key():
    fake_asset = _fake_asset(file_type="prompt", storage_key="", text_content="Sos un asistente...", status="aprobado")
    tool = LibrarySearchTool(client_id=None)

    with patch("src.tools.library_search.library.search_assets", return_value=[fake_asset]):
        result = tool._run("prompt de bienvenida")

    payload = json.loads(result)
    assert payload[0]["url"] is None
    assert payload[0]["text_content"] == "Sos un asistente..."


def test_run_returns_message_when_no_results():
    tool = LibrarySearchTool(client_id=None)

    with patch("src.tools.library_search.library.search_assets", return_value=[]):
        result = tool._run("algo que no existe")

    assert "No se encontró" in result
    assert "library_save" in result
