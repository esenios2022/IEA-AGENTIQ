"""src.composio_tools.start_connection. Verificado en vivo contra la API
real de Composio (2026-07-12) antes de escribir este fix: toolkits.
authorize() está retirado, connected_accounts.link() + auth_config_id
es el flujo correcto actual. Estos tests mockean el cliente Composio
(módulo get_composio), no llaman a la API real."""

from unittest.mock import MagicMock, patch

import pytest

from src.composio_tools import start_connection


def test_start_connection_resolves_auth_config_and_links():
    fake_composio = MagicMock()
    fake_composio.auth_configs.list.return_value = MagicMock(items=[MagicMock(id="ac_123")])
    fake_composio.toolkits.connected_accounts.link.return_value = MagicMock(redirect_url="https://connect.composio.dev/link/abc")

    with patch("src.composio_tools.get_composio", return_value=fake_composio):
        url = start_connection(user_id="client-1", toolkit_slug="instagram")

    assert url == "https://connect.composio.dev/link/abc"
    fake_composio.auth_configs.list.assert_called_once_with(toolkit_slug="instagram")
    fake_composio.toolkits.connected_accounts.link.assert_called_once_with(user_id="client-1", auth_config_id="ac_123")


def test_start_connection_raises_clear_error_when_no_auth_config():
    fake_composio = MagicMock()
    fake_composio.auth_configs.list.return_value = MagicMock(items=[])

    with patch("src.composio_tools.get_composio", return_value=fake_composio):
        with pytest.raises(RuntimeError, match="auth_config"):
            start_connection(user_id="client-1", toolkit_slug="tiktok")

    fake_composio.toolkits.connected_accounts.link.assert_not_called()
