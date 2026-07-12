"""FASE 2.4A — src.tools.library_save.LibrarySaveTool. Patches
`src.tools.library_save.library.create_asset` (module boundary), same
convention as tests/test_library_search_tool.py."""

from unittest.mock import MagicMock, patch

from src.tools.library_save import LibrarySaveTool


def test_run_saves_text_content_and_forces_borrador_status():
    fake_asset = MagicMock(id="asset-1", category="Emails", subcategory=None, status="borrador")
    tool = LibrarySaveTool(client_id="client-1", created_by_agent_id="agent-034")

    with patch("src.tools.library_save.library.create_asset", return_value=fake_asset) as mock_create:
        result = tool._run(
            title="Email de bienvenida",
            category="Emails",
            file_type="prompt",
            text_content="Hola {{nombre}}, bienvenido...",
            tags="bienvenida, email",
        )

    mock_create.assert_called_once()
    _, kwargs = mock_create.call_args
    assert kwargs["client_id"] == "client-1"
    assert kwargs["created_by_agent_id"] == "agent-034"
    assert kwargs["status"] == "borrador"  # forced, regardless of what's passed
    assert kwargs["tags"] == ["bienvenida", "email"]
    assert "asset_id=asset-1" in result
    assert "borrador" in result


def test_run_saves_source_url_as_storage_key():
    fake_asset = MagicMock(id="asset-2", category="Videos", subcategory=None, status="borrador")
    tool = LibrarySaveTool(client_id=None, created_by_agent_id="agent-033")

    with patch("src.tools.library_save.library.create_asset", return_value=fake_asset) as mock_create:
        tool._run(
            title="Reel producido",
            category="Videos",
            file_type="video",
            source_url="https://heygen.example.com/videos/abc123.mp4",
        )

    _, kwargs = mock_create.call_args
    assert kwargs["storage_key"] == "https://heygen.example.com/videos/abc123.mp4"


def test_run_rejects_when_no_content_or_url_given():
    tool = LibrarySaveTool(client_id="client-1", created_by_agent_id="agent-006")

    with patch("src.tools.library_save.library.create_asset") as mock_create:
        result = tool._run(title="Sin nada", category="Marca", file_type="imagen")

    mock_create.assert_not_called()
    assert "Error" in result
