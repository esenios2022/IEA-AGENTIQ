"""FASE 2.4 — src.connectors.instagram.InstagramConnector. Unit tests
inject a MagicMock SocialProvider (never a real Composio call) and patch
src.library_storage.get_asset_url (module boundary), same conventions as
tests/test_library_search_tool.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.connectors.base import PublishValidationError
from src.connectors.instagram import InstagramConnector
from src.connectors.providers.base import SocialProviderError


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


def test_publish_resolves_ig_user_id_then_creates_and_publishes_container():
    """FASE 2.5 — verificado contra la publicación real de eAlumina (2026-07-13):
    ig_user_id es obligatorio y se resuelve via INSTAGRAM_GET_USER_INFO antes de
    crear el contenedor."""
    provider = MagicMock()
    provider.call_action.side_effect = [
        {"id": "17841400000000000"},  # INSTAGRAM_GET_USER_INFO
        {"id": "container-1"},  # INSTAGRAM_POST_IG_USER_MEDIA
        {"id": "post-1"},  # INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH
    ]
    connector = InstagramConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.instagram.get_asset_url", return_value="https://cdn.example.com/x.png"):
        result = connector.publish("client-1", asset, "caption valido")

    assert result == {"id": "post-1"}
    assert provider.call_action.call_count == 3
    get_info_call, create_call, publish_call = provider.call_action.call_args_list
    assert get_info_call.args[1] == "INSTAGRAM_GET_USER_INFO"
    assert create_call.args[1] == "INSTAGRAM_POST_IG_USER_MEDIA"
    assert create_call.args[2]["ig_user_id"] == "17841400000000000"
    assert publish_call.args[1] == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH"
    assert publish_call.args[2]["creation_id"] == "container-1"
    assert publish_call.args[2]["ig_user_id"] == "17841400000000000"


def test_publish_rejects_url_with_query_params_before_calling_composio():
    """Instagram rechaza cualquier image_url con query string (presigned URLs de S3
    incluidas) — verificado contra el schema real de Composio. Falla rápido con un
    mensaje claro en vez de dejar que la API externa lo rechace de forma críptica."""
    provider = MagicMock()
    connector = InstagramConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.instagram.get_asset_url", return_value="https://cdn.example.com/x.png?X-Amz-Signature=abc"):
        with pytest.raises(PublishValidationError, match="parámetros de consulta"):
            connector.publish("client-1", asset, "caption valido")

    provider.call_action.assert_not_called()


def test_publish_raises_when_container_creation_has_no_id():
    provider = MagicMock()
    provider.call_action.side_effect = [{"id": "17841400000000000"}, {}]
    connector = InstagramConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.instagram.get_asset_url", return_value="https://cdn.example.com/x.png"):
        with pytest.raises(SocialProviderError, match="contenedor"):
            connector.publish("client-1", asset, "caption valido")
