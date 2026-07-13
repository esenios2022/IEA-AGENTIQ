"""FASE 2.4 — src.connectors.instagram.InstagramConnector. Unit tests
inject a MagicMock SocialProvider (never a real Composio call) and patch
src.library_storage.get_asset_url (module boundary), same conventions as
tests/test_library_search_tool.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.connectors.base import PublishValidationError
from src.connectors.instagram import InstagramConnector


def _asset(**overrides):
    defaults = dict(id="asset-1", title="Foto de campaña", file_type="imagen", storage_key="global/x.png")
    defaults.update(overrides)
    return MagicMock(**defaults)


def test_validate_content_rejects_non_media_asset():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset(file_type="prompt", storage_key="")

    with pytest.raises(PublishValidationError):
        connector.validate_content(asset, "un caption")


def test_validate_content_rejects_empty_caption():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset()

    with pytest.raises(PublishValidationError):
        connector.validate_content(asset, "   ")


def test_validate_content_rejects_caption_over_limit():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset()

    with pytest.raises(PublishValidationError):
        connector.validate_content(asset, "x" * 2201)


def test_validate_content_accepts_valid_image_and_warns_about_account_type():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset()

    warnings = connector.validate_content(asset, "Un caption válido")

    assert any("Business/Creator" in w for w in warnings)


def test_validate_content_warns_about_video_processing_time():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset(file_type="video")

    warnings = connector.validate_content(asset, "Un caption válido")

    assert any("procesar" in w for w in warnings)


def test_build_preview_never_raises_shows_warning_instead():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset(file_type="prompt", storage_key="")

    with patch("src.connectors.instagram.get_asset_url", return_value="https://cdn.example.com/x.png"):
        preview = connector.build_preview(asset, "caption")

    assert preview.warnings
    assert preview.platform == "instagram"


def test_build_preview_includes_media_url():
    connector = InstagramConnector(provider=MagicMock())
    asset = _asset()

    with patch("src.connectors.instagram.get_asset_url", return_value="https://cdn.example.com/x.png"):
        preview = connector.build_preview(asset, "caption valido")

    assert preview.media_url == "https://cdn.example.com/x.png"


def test_get_auth_url_delegates_to_provider():
    provider = MagicMock()
    provider.get_auth_url.return_value = "https://composio.example.com/auth"
    connector = InstagramConnector(provider=provider)

    url = connector.get_auth_url("client-1")

    assert url == "https://composio.example.com/auth"
    provider.get_auth_url.assert_called_once_with("client-1", "instagram")


def test_publish_calls_create_then_publish_container():
    provider = MagicMock()
    provider.call_action.side_effect = [{"id": "container-1"}, {"status": "published"}]
    connector = InstagramConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.instagram.get_asset_url", return_value="https://cdn.example.com/x.png"):
        result = connector.publish("client-1", asset, "caption valido")

    assert result == {"status": "published"}
    assert provider.call_action.call_count == 2
    first_call, second_call = provider.call_action.call_args_list
    assert first_call.args[1] == "INSTAGRAM_POST_IG_USER_MEDIA"
    assert second_call.args[1] == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH"
    assert second_call.args[2]["creation_id"] == "container-1"
