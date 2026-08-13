"""Registro de conectores por plataforma — mismo patron que src/tools/registry.py.
Agregar LinkedIn/YouTube despues es una entrada mas aca, nada mas.

2026-08-13 — "facebook" agregado (Bug 3 del plan de cierre de ciclo): la Pagina de
Facebook de EALumina ya estaba conectada en Composio, pero no habia conector que
la usara desde el panel. Ver src/connectors/facebook.py para el detalle real de
por que el token de Pagina se resuelve aparte del de Instagram."""

from src.connectors.facebook import FacebookConnector
from src.connectors.instagram import InstagramConnector

CONNECTORS = {
    "instagram": InstagramConnector(),
    "facebook": FacebookConnector(),
}
