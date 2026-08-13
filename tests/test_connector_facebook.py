"""src.connectors.facebook.FacebookConnector (Bug 3, 2026-08-13). Unit tests inject
a MagicMock SocialProvider (never a real Composio call) and patch
src.connectors.facebook.get_asset_url and src.connectors.facebook.requests.post
(module boundary), same conventions as tests/test_connector_instagram.py. The real
Graph API POST calls (photos/feed) bypass the provider entirely (see module
docstring for why), so they're mocked at `requests.post`, not at the provider."""

from unittest.mock import MagicMock, patch

import pytest

from src.connectors.base import PublishValidationError
from src.connectors.facebook import FacebookConnector
from src.connectors.providers.base import SocialProviderError


def _asset(**overrides):
    defaults = dict(id="asset-1", title="Foto de campaña", file_type="imagen", storage_key="global/x.png")
    defaults.update(overrides)
    return MagicMock(**defaults)


def _http_response(json_data, status_code=200):
    response = MagicMock(status_code=status_code)
    response.json.return_value = json_data
    return response


def test_validate_content_rejects_non_image_asset():
    connector = FacebookConnector(provider=MagicMock())
    asset = _asset(file_type="video", storage_key="")

    with pytest.raises(PublishValidationError):
        connector.validate_content(asset, "un mensaje")


def test_validate_content_rejects_empty_caption():
    connector = FacebookConnector(provider=MagicMock())
    asset = _asset()

    with pytest.raises(PublishValidationError):
        connector.validate_content(asset, "   ")


def test_validate_content_rejects_message_over_limit():
    connector = FacebookConnector(provider=MagicMock())
    asset = _asset()

    with pytest.raises(PublishValidationError):
        connector.validate_content(asset, "x" * 63207)


def test_validate_content_accepts_valid_image_and_warns_about_page_permissions():
    connector = FacebookConnector(provider=MagicMock())
    asset = _asset()

    warnings = connector.validate_content(asset, "Un mensaje válido")

    assert any("Página" in w for w in warnings)


def test_get_auth_url_delegates_to_provider():
    provider = MagicMock()
    provider.get_auth_url.return_value = "https://composio.example.com/auth"
    connector = FacebookConnector(provider=provider)

    url = connector.get_auth_url("ealumina")

    assert url == "https://composio.example.com/auth"
    provider.get_auth_url.assert_called_once_with("ealumina", "facebook")


def test_is_connected_delegates_to_provider():
    provider = MagicMock()
    provider.is_connected.return_value = True
    connector = FacebookConnector(provider=provider)

    assert connector.is_connected("ealumina") is True
    provider.is_connected.assert_called_once_with("ealumina", "facebook")


def test_build_preview_never_raises_shows_warning_instead():
    connector = FacebookConnector(provider=MagicMock())
    asset = _asset(file_type="video", storage_key="")

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png"):
        preview = connector.build_preview(asset, "mensaje")

    assert preview.warnings
    assert preview.platform == "facebook"


def test_build_preview_includes_media_url():
    connector = FacebookConnector(provider=MagicMock())
    asset = _asset()

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png"):
        preview = connector.build_preview(asset, "mensaje valido")

    assert preview.media_url == "https://cdn.example.com/x.png"


def test_publish_resolves_page_then_creates_photo_and_feed_post():
    """Ruta feliz: GET /me/accounts vía el provider (token de usuario) resuelve el
    access_token de Página; POST /{page_id}/photos y POST /{page_id}/feed van
    directo a graph.facebook.com (vía requests, no vía el provider) con ESE token."""
    provider = MagicMock()
    provider.proxy.return_value = {
        "data": [{"id": "page-1", "name": "EALumina", "access_token": "page-token-abc"}]
    }
    connector = FacebookConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png"), \
         patch("src.connectors.facebook.requests.post") as mock_post:
        mock_post.side_effect = [
            _http_response({"id": "photo-1"}),
            _http_response({"id": "post-1"}),
        ]
        result = connector.publish("ealumina", asset, "mensaje válido")

    assert result == {"id": "post-1"}
    provider.proxy.assert_called_once_with("ealumina", "facebook", "/me/accounts", "GET")
    assert mock_post.call_count == 2

    photos_call, feed_call = mock_post.call_args_list
    assert photos_call.args[0] == "https://graph.facebook.com/page-1/photos"
    assert photos_call.kwargs["params"]["url"] == "https://cdn.example.com/x.png"
    assert photos_call.kwargs["params"]["published"] == "false"
    assert photos_call.kwargs["params"]["access_token"] == "page-token-abc"

    assert feed_call.args[0] == "https://graph.facebook.com/page-1/feed"
    assert feed_call.kwargs["params"]["message"] == "mensaje válido"
    assert feed_call.kwargs["params"]["access_token"] == "page-token-abc"
    assert '"media_fbid": "photo-1"' in feed_call.kwargs["params"]["attached_media"]


def test_publish_rejects_url_with_query_params_before_resolving_page():
    provider = MagicMock()
    connector = FacebookConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png?X-Amz-Signature=abc"):
        with pytest.raises(PublishValidationError, match="parámetros de consulta"):
            connector.publish("ealumina", asset, "mensaje válido")

    provider.proxy.assert_not_called()


def test_publish_raises_when_no_pages_found():
    provider = MagicMock()
    provider.proxy.return_value = {"data": []}
    connector = FacebookConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png"):
        with pytest.raises(SocialProviderError, match="ninguna Página"):
            connector.publish("ealumina", asset, "mensaje válido")


def test_publish_raises_when_graph_api_returns_error():
    provider = MagicMock()
    provider.proxy.return_value = {"data": [{"id": "page-1", "access_token": "page-token-abc"}]}
    connector = FacebookConnector(provider=provider)
    asset = _asset()

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png"), \
         patch("src.connectors.facebook.requests.post") as mock_post:
        mock_post.return_value = _http_response({"error": {"message": "Invalid parameter", "code": 100}})
        with pytest.raises(SocialProviderError, match="Invalid parameter"):
            connector.publish("ealumina", asset, "mensaje válido")


def test_publish_carousel_creates_multiple_photos_then_one_feed_post():
    provider = MagicMock()
    provider.proxy.return_value = {"data": [{"id": "page-1", "access_token": "page-token-abc"}]}
    connector = FacebookConnector(provider=provider)
    assets = [_asset(id="a1", title="Foto 1"), _asset(id="a2", title="Foto 2"), _asset(id="a3", title="Foto 3")]

    with patch("src.connectors.facebook.get_asset_url", return_value="https://cdn.example.com/x.png"), \
         patch("src.connectors.facebook.requests.post") as mock_post:
        mock_post.side_effect = [
            _http_response({"id": "photo-1"}),
            _http_response({"id": "photo-2"}),
            _http_response({"id": "photo-3"}),
            _http_response({"id": "post-1"}),
        ]
        result = connector.publish_carousel("ealumina", assets, "mensaje del carrusel")

    assert result == {"id": "post-1"}
    assert mock_post.call_count == 4
    feed_call = mock_post.call_args_list[-1]
    attached = feed_call.kwargs["params"]["attached_media"]
    assert '"media_fbid": "photo-1"' in attached
    assert '"media_fbid": "photo-2"' in attached
    assert '"media_fbid": "photo-3"' in attached


def test_publish_carousel_rejects_too_few_assets():
    connector = FacebookConnector(provider=MagicMock())

    with pytest.raises(PublishValidationError, match="entre 2 y 10"):
        connector.publish_carousel("ealumina", [_asset()], "mensaje")


def test_publish_carousel_rejects_non_image_asset():
    connector = FacebookConnector(provider=MagicMock())
    assets = [_asset(), _asset(file_type="video")]

    with pytest.raises(PublishValidationError, match="no es una imagen"):
        connector.publish_carousel("ealumina", assets, "mensaje")
