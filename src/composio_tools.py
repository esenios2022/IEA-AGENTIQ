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
    """Kicks off a Composio-hosted auth flow; returns the URL to send the user to."""
    composio = get_composio()
    request = composio.toolkits.authorize(user_id=user_id, toolkit=toolkit_slug.lower())
    return request.redirect_url
