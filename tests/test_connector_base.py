"""src.connectors.base.resolve_composio_user_id — agregado 2026-08-13 junto con el
fix del bug real documentado en src/connectors/base.py: varios puntos de llamada
usaban el UUID crudo del Client para hablar con Composio en vez de su
Client.config["composio_user_id"] (identidad real bajo la que están las conexiones
activas). Unit tests con MagicMock, mismo estilo que tests/test_connector_instagram.py."""

from unittest.mock import MagicMock

import pytest

from src.connectors.base import resolve_composio_user_id


def test_resolve_composio_user_id_uses_config_override_when_present():
    client = MagicMock(id="11111111-1111-1111-1111-111111111111", config={"composio_user_id": "ealumina"})

    assert resolve_composio_user_id(client) == "ealumina"


def test_resolve_composio_user_id_falls_back_to_uuid_when_no_config():
    client = MagicMock(id="11111111-1111-1111-1111-111111111111", config=None)

    assert resolve_composio_user_id(client) == "11111111-1111-1111-1111-111111111111"


def test_resolve_composio_user_id_falls_back_to_uuid_when_config_has_no_override():
    client = MagicMock(id="11111111-1111-1111-1111-111111111111", config={"otra_clave": "x"})

    assert resolve_composio_user_id(client) == "11111111-1111-1111-1111-111111111111"


def test_resolve_composio_user_id_rejects_none_client():
    with pytest.raises(ValueError):
        resolve_composio_user_id(None)
