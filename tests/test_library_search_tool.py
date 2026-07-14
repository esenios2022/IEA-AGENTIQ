"""FASE 2.3/2.4A — src.tools.library_search.LibrarySearchTool. Patches
`src.tools.library_search.library.search_assets` and `library_storage.
get_asset_url` (module boundary), same convention as
tests/test_ai_lab_knowledge_tool.py patching the AI LAB client."""

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.tools.library_search import LibrarySearchTool, _current_week


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


# --- ETAPA 4.1 (Integración Cosmos → Marketing): current_week ---

def test_current_week_picks_most_recent_started_week():
    today = date.today().isoformat()
    past = (date.today() - timedelta(days=7)).isoformat()
    future = (date.today() + timedelta(days=7)).isoformat()
    weeks = [
        {"week_number": 1, "start_date": past, "tema_central": "vieja"},
        {"week_number": 2, "start_date": today, "tema_central": "actual"},
        {"week_number": 3, "start_date": future, "tema_central": "futura"},
    ]
    assert _current_week({"weeks": weeks})["tema_central"] == "actual"


def test_current_week_falls_back_to_first_when_all_future():
    future1 = (date.today() + timedelta(days=7)).isoformat()
    future2 = (date.today() + timedelta(days=14)).isoformat()
    weeks = [{"week_number": 1, "start_date": future1}, {"week_number": 2, "start_date": future2}]
    assert _current_week({"weeks": weeks})["start_date"] == future1


def test_current_week_returns_none_when_no_weeks_or_no_structured_content():
    assert _current_week({"weeks": []}) is None
    assert _current_week(None) is None


def test_run_includes_current_week_for_calendario_editorial_assets():
    fake_asset = _fake_asset(
        file_type="calendario_editorial",
        storage_key="",
        text_content="texto largo " * 50,
        structured_content={"weeks": [{"week_number": 1, "start_date": date.today().isoformat(), "tema_central": "Tema semana"}]},
        status="aprobado",
    )
    tool = LibrarySearchTool(client_id="client-1")

    with patch("src.tools.library_search.library.search_assets", return_value=[fake_asset]):
        result = tool._run("calendario editorial")

    payload = json.loads(result)
    assert payload[0]["current_week"]["tema_central"] == "Tema semana"


def test_run_does_not_include_current_week_for_other_file_types():
    fake_asset = _fake_asset(status="aprobado", storage_key="")  # file_type="imagen" por default
    tool = LibrarySearchTool(client_id="client-1")

    with patch("src.tools.library_search.library.search_assets", return_value=[fake_asset]):
        result = tool._run("logo")

    payload = json.loads(result)
    assert "current_week" not in payload[0]
