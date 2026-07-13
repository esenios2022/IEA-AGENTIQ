"""
FASE 2.4 — interfaz generica de proveedor de API detras de un
SocialConnector. Un connector (ej. InstagramConnector) no sabe si esta
hablando con Composio o con la API directa de Meta — solo llama estos
tres metodos. Cambiar de proveedor = escribir una clase nueva que
implemente esto, sin tocar ningun connector.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SocialProviderError(Exception):
    pass


class SocialProvider(ABC):
    @abstractmethod
    def get_auth_url(self, user_id: str, platform: str) -> str:
        """Arranca el flujo de autenticacion, devuelve la URL a la que redirigir."""

    @abstractmethod
    def is_connected(self, user_id: str, platform: str) -> bool:
        """Verifica contra el proveedor real si user_id tiene una cuenta activa conectada."""

    @abstractmethod
    def call_action(self, user_id: str, action_slug: str, params: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta una accion puntual (no via un agente/LLM, una llamada directa de backend)."""
