"""FASE 2.4 — src.connectors.providers.composio_provider.ComposioSocialProvider.
Patches src.composio_tools (module boundary) and src.connectors.providers.
composio_provider.get_composio, same convention as tests/test_ai_lab_client.py
mocking requests."""

from unittest.mock import MagicMock, patch

import pytest

from src.connectors.providers.base import SocialProviderError
from src.connectors.providers.composio_provider import ComposioSocialProvider


def test_get_auth_url_delegates_to_start_connection():
    provider = ComposioSocialProvider()
    with patch("src.connectors.providers.composio_provider.start_connection", return_value="https://composio.example.com/auth") as mock_start:
        url = provider.get_auth_url("client-1", "instagram")

    assert url == "https://composio.example.com/auth"
    mock_start.assert_called_once_with(user_id="client-1", toolkit_slug="instagram")


def test_get_auth_url_wraps_failures():
    provider = ComposioSocialProvider()
    with patch("src.connectors.providers.composio_provider.start_connection", side_effect=RuntimeError("boom")):
        with pytest.raises(SocialProviderError):
            provider.get_auth_url("client-1", "instagram")


def test_is_connected_true_when_active_account_found():
    provider = ComposioSocialProvider()
    fake_composio = MagicMock()
    fake_composio.toolkits.connected_accounts.list.return_value = MagicMock(items=[MagicMock()])

    with patch("src.connectors.providers.composio_provider.get_composio", return_value=fake_composio):
        assert provider.is_connected("client-1", "instagram") is True

    fake_composio.toolkits.connected_accounts.list.assert_called_once_with(
        user_ids=["client-1"], toolkit_slugs=["INSTAGRAM"], statuses=["ACTIVE"],
    )


def test_is_connected_false_when_no_accounts():
    provider = ComposioSocialProvider()
    fake_composio = MagicMock()
    fake_composio.toolkits.connected_accounts.list.return_value = MagicMock(items=[])

    with patch("src.connectors.providers.composio_provider.get_composio", return_value=fake_composio):
        assert provider.is_connected("client-1", "instagram") is False


def test_is_connected_false_on_error_not_raised():
    provider = ComposioSocialProvider()
    with patch("src.connectors.providers.composio_provider.get_composio", side_effect=RuntimeError("no key")):
        assert provider.is_connected("client-1", "instagram") is False


def test_call_action_executes_and_returns_dict():
    provider = ComposioSocialProvider()
    fake_composio = MagicMock()
    fake_composio.tools.execute.return_value = {"id": "container-1"}

    with patch("src.connectors.providers.composio_provider.get_composio", return_value=fake_composio):
        result = provider.call_action("client-1", "INSTAGRAM_POST_IG_USER_MEDIA", {"caption": "hola"})

    assert result == {"id": "container-1"}
    fake_composio.tools.execute.assert_called_once_with("INSTAGRAM_POST_IG_USER_MEDIA", {"caption": "hola"}, user_id="client-1")


def test_call_action_wraps_failures():
    provider = ComposioSocialProvider()
    fake_composio = MagicMock()
    fake_composio.tools.execute.side_effect = RuntimeError("boom")

    with patch("src.connectors.providers.composio_provider.get_composio", return_value=fake_composio):
        with pytest.raises(SocialProviderError):
            provider.call_action("client-1", "INSTAGRAM_POST_IG_USER_MEDIA", {})
