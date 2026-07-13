"""
ComposioSocialProvider — envuelve src/composio_tools.py, reutiliza la
misma auth que ya usan Gmail/WhatsApp/etc en este repo en vez de duplicar
OAuth. No usa el path de tool-calling para agentes (composio.tools.get,
pensado para darle tools a un LLM) sino la ejecucion directa de una
accion puntual desde codigo de backend (composio.tools.execute) —
verificado contra el SDK real instalado (composio>=0.17.0) antes de
escribir esto, no asumido.

Mismo estilo print(f"[...] ...", flush=True) que el resto de src/ (sin
logging).
"""

from __future__ import annotations

from typing import Any

from src.composio_tools import get_composio, start_connection
from src.connectors.providers.base import SocialProvider, SocialProviderError


class ComposioSocialProvider(SocialProvider):
    def get_auth_url(self, user_id: str, platform: str) -> str:
        try:
            return start_connection(user_id=user_id, toolkit_slug=platform)
        except Exception as exc:
            raise SocialProviderError(f"No se pudo iniciar la conexión con Composio: {exc}") from exc

    def is_connected(self, user_id: str, platform: str) -> bool:
        try:
            composio = get_composio()
            result = composio.toolkits.connected_accounts.list(
                user_ids=[user_id],
                toolkit_slugs=[platform.upper()],
                statuses=["ACTIVE"],
            )
        except Exception as exc:
            print(f"[composio_provider] is_connected check failed for {platform}/{user_id}: {exc}", flush=True)
            return False
        return bool(getattr(result, "items", None))

    def call_action(self, user_id: str, action_slug: str, params: dict[str, Any]) -> dict[str, Any]:
        """Verificado contra una llamada real (2026-07-13, publicación real de eAlumina en
        Instagram): `tools.execute()` exige `dangerously_skip_version_check=True` para
        ejecución manual fuera del flujo de tool-calling de un agente, o falla con
        `ToolVersionRequiredError`. La respuesta real trae el payload de la API externa
        anidado en `response.data["data"]`, con `response.data["successful"]`/`["error"]`
        como envoltorio de Composio — no es un dict plano como se había asumido antes de
        probar contra la API real."""
        try:
            composio = get_composio()
            response = composio.tools.execute(
                action_slug,
                params,
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        except Exception as exc:
            raise SocialProviderError(f"Composio action {action_slug} falló: {exc}") from exc

        envelope = response.data if hasattr(response, "data") else response
        if not isinstance(envelope, dict):
            return {}
        if envelope.get("successful") is False or envelope.get("error"):
            raise SocialProviderError(f"Composio action {action_slug} devolvió error: {envelope.get('error')}")
        return envelope.get("data") or {}
