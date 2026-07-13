"""Registro de conectores por plataforma — mismo patron que src/tools/registry.py.
Agregar Facebook/LinkedIn/YouTube despues es una entrada mas aca, nada mas."""

from src.connectors.instagram import InstagramConnector

CONNECTORS = {
    "instagram": InstagramConnector(),
}
