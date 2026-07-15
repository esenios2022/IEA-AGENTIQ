"""2026-07-14 — src.tools.gemini_image_tool.GeminiImageTool. Same
convention as tests/test_library_save_tool.py and
tests/test_gemini_executor.py: patches `google.genai.Client` directly
(the import is local to _run(), not a module-level attribute), plus
library/library_storage/cost at the module boundary — no real network,
no real S3, no real DB write."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.tools import gemini_image_tool
from src.tools.gemini_image_tool import GeminiImageTool


def _fake_gemini_response(image_bytes=b"fake-png-bytes", mime_type="image/png", input_tokens=50, output_tokens=1290):
    part = SimpleNamespace(inline_data=SimpleNamespace(data=image_bytes, mime_type=mime_type))
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    usage = SimpleNamespace(prompt_token_count=input_tokens, candidates_token_count=output_tokens)
    return SimpleNamespace(candidates=[candidate], usage_metadata=usage)


def test_run_rejects_when_gemini_api_key_not_configured():
    tool = GeminiImageTool(client_id="client-1", created_by_agent_id="agent-015")

    with patch.object(gemini_image_tool.settings, "gemini_api_key", None):
        result = tool._run(prompt="un colibrí dorado", title="Colibrí")

    assert "Error" in result
    assert "GEMINI_API_KEY" in result


def test_run_generates_uploads_and_saves_asset_as_borrador():
    fake_asset = MagicMock(id="asset-img-1")
    tool = GeminiImageTool(client_id="client-1", created_by_agent_id="agent-015")

    with patch.object(gemini_image_tool.settings, "gemini_api_key", "fake-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("src.tools.gemini_image_tool.library_storage.upload_asset") as mock_upload, \
         patch("src.tools.gemini_image_tool.library_storage.get_asset_url", return_value="https://storage.example/img.png"), \
         patch("src.tools.gemini_image_tool.library.create_asset", return_value=fake_asset) as mock_create, \
         patch("src.tools.gemini_image_tool.record_usage") as mock_record:
        mock_client_cls.return_value.models.generate_content.return_value = _fake_gemini_response()

        result = tool._run(prompt="un colibrí dorado sobre flores", title="Colibrí dorado")

    mock_upload.assert_called_once()
    upload_args, upload_kwargs = mock_upload.call_args
    assert upload_args[0] == b"fake-png-bytes"
    assert upload_kwargs.get("content_type") == "image/png"

    mock_create.assert_called_once()
    _, create_kwargs = mock_create.call_args
    assert create_kwargs["client_id"] == "client-1"
    assert create_kwargs["created_by_agent_id"] == "agent-015"
    assert create_kwargs["file_type"] == "imagen"
    assert create_kwargs["status"] == "borrador"  # forced, never auto-approved
    assert create_kwargs["file_size_bytes"] == len(b"fake-png-bytes")

    mock_record.assert_called_once()
    _, record_kwargs = mock_record.call_args
    assert record_kwargs["provider"] == "gemini"
    assert record_kwargs["platform_cost"] is True
    assert record_kwargs["content_asset_id"] == "asset-img-1"
    assert record_kwargs["input_tokens"] == 50
    assert record_kwargs["output_tokens"] == 1290

    assert "asset_id=asset-img-1" in result
    assert "borrador" in result


def test_run_returns_error_when_gemini_returns_no_image():
    tool = GeminiImageTool(client_id="client-1", created_by_agent_id="agent-015")
    empty_response = SimpleNamespace(candidates=[], usage_metadata=None)

    with patch.object(gemini_image_tool.settings, "gemini_api_key", "fake-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("src.tools.gemini_image_tool.library.create_asset") as mock_create:
        mock_client_cls.return_value.models.generate_content.return_value = empty_response
        result = tool._run(prompt="algo imposible", title="Nada")

    mock_create.assert_not_called()
    assert "Error" in result


def test_run_returns_clear_error_when_storage_not_configured():
    tool = GeminiImageTool(client_id="client-1", created_by_agent_id="agent-015")

    with patch.object(gemini_image_tool.settings, "gemini_api_key", "fake-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch(
             "src.tools.gemini_image_tool.library_storage.upload_asset",
             side_effect=gemini_image_tool.library_storage.LibraryStorageNotConfiguredError("no s3 configured"),
         ), \
         patch("src.tools.gemini_image_tool.library.create_asset") as mock_create:
        mock_client_cls.return_value.models.generate_content.return_value = _fake_gemini_response()
        result = tool._run(prompt="un colibrí dorado", title="Colibrí")

    mock_create.assert_not_called()
    assert "Error" in result
    assert "almacenamiento" in result.lower()


def test_run_skips_usage_recording_when_no_agent_id_bound():
    fake_asset = MagicMock(id="asset-img-2")
    tool = GeminiImageTool(client_id="client-1", created_by_agent_id=None)

    with patch.object(gemini_image_tool.settings, "gemini_api_key", "fake-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("src.tools.gemini_image_tool.library_storage.upload_asset"), \
         patch("src.tools.gemini_image_tool.library_storage.get_asset_url", return_value="https://storage.example/img.png"), \
         patch("src.tools.gemini_image_tool.library.create_asset", return_value=fake_asset), \
         patch("src.tools.gemini_image_tool.record_usage") as mock_record:
        mock_client_cls.return_value.models.generate_content.return_value = _fake_gemini_response()
        tool._run(prompt="un colibrí dorado", title="Colibrí")

    mock_record.assert_not_called()
