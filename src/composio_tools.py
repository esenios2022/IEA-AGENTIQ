"""Real third-party tools (Gmail, WhatsApp, Sheets, etc.) via Composio, for CrewAI agents."""

from composio import Composio
from composio_crewai import CrewAIProvider

from src.config import settings

_composio: Composio | None = None


def get_composio() -> Composio:
    global _composio
    if _composio is None:
        if not settings.composio_api_key:
            raise RuntimeError("COMPOSIO_API_KEY no está configurada.")
        _composio = Composio(provider=CrewAIProvider(), api_key=settings.composio_api_key)
    return _composio


def get_toolkit_tools(user_id: str, toolkit_slugs: list[str]) -> list:
    """CrewAI-ready tools for the given toolkits, scoped to whatever account user_id has connected."""
    if not toolkit_slugs:
        return []
    composio = get_composio()
    return composio.tools.get(user_id=user_id, toolkits=[slug.upper() for slug in toolkit_slugs])


def start_connection(user_id: str, toolkit_slug: str) -> str:
    """Kicks off a Composio-hosted auth flow; returns the URL to send the user to.

    `toolkits.authorize(user_id, toolkit)` (the previous implementation) hits an
    endpoint Composio has since retired — confirmed against a real API key
    (2026-07-12), it now fails with ComposioLegacyConnectedAccountsEndpointRetiredError.
    The current flow needs an `auth_config_id` (one per toolkit, created in the
    Composio dashboard) rather than just the toolkit slug — resolved here via
    `auth_configs.list(toolkit_slug=...)` before calling `connected_accounts.link()`.
    """
    composio = get_composio()
    auth_configs = composio.auth_configs.list(toolkit_slug=toolkit_slug.lower())
    items = getattr(auth_configs, "items", None) or []
    if not items:
        raise RuntimeError(
            f"No hay un auth_config configurado para el toolkit '{toolkit_slug}' en Composio — "
            "hay que crearlo desde el dashboard de Composio antes de poder conectar esta integración."
        )
    auth_config_id = items[0].id
    request = composio.toolkits.connected_accounts.link(user_id=user_id, auth_config_id=auth_config_id)
    return request.redirect_url
