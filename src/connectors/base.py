"""
FASE 2.4 — interfaz generica de conector de red social. Cada plataforma
(Instagram ahora, Facebook/LinkedIn/YouTube despues) implementa esta
misma interfaz — src/social_publishing.py y las rutas admin nunca saben
nada especifico de una plataforma en particular, solo hablan contra esto.

Deliberadamente separado del "provider" (ver src/connectors/providers/
base.py): un SocialConnector sabe las REGLAS de una red social (limites
de caption, tipo de cuenta requerido, como armar la vista previa); un
SocialProvider sabe COMO hablar con un proveedor de API (Composio hoy,
Meta Graph API directa manana). Un conector recibe un provider inyectado,
nunca construye uno el mismo — asi cambiar de proveedor no toca ningun
conector.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.models import Client, LibraryAsset


class PublishValidationError(Exception):
    pass


def resolve_composio_user_id(client: Client) -> str:
    """Bug real (detectado 2026-08-13, revisando por qué `/admin/publicaciones` nunca
    llegaba a publicar en Instagram/Facebook para EALumina pese a tener las cuentas
    conectadas): un Client puede tener una identidad DISTINTA de su UUID en Composio
    (`Client.config["composio_user_id"]`) -- `src/marketing_pipeline.py:103` ya la
    resolvía bien para los agentes, pero `src/social_publishing.py::execute_publish()`
    y la ruta `GET /admin/clients/{client_id}/social-connect` en `src/main.py` seguían
    llamando a Composio con `str(client.id)` crudo. EALumina en producción tiene
    `composio_user_id="ealumina"`; bajo esa identidad están sus conexiones reales y
    activas de Instagram y Facebook, nunca bajo su UUID de la tabla `clients`.

    Verificado contra la API real de Composio (no simulado): con un UUID al azar,
    `ComposioSocialProvider().is_connected(uuid, "instagram"/"facebook")` devuelve
    `False` en ambos casos; con `"ealumina"` devuelve `True` en ambos (1 cuenta ACTIVE
    cada uno). Ver comentario con el mismo detalle en
    `src/social_publishing.py::execute_publish()`.

    Extraído a un único helper (en vez de repetir `(client.config or {}).get(...)` en
    3 puntos de llamada) para que el próximo conector (Facebook) lo use gratis."""
    if client is None:
        raise ValueError("resolve_composio_user_id() necesita un Client real, no None.")
    return (client.config or {}).get("composio_user_id") or str(client.id)


@dataclass
class PublishPreview:
    platform: str
    caption: str
    media_url: str | None
    file_type: str
    warnings: list[str] = field(default_factory=list)


class SocialConnector(ABC):
    platform: str

    @abstractmethod
    def get_auth_url(self, client_id: str) -> str:
        """Arranca el flujo de autenticacion para este cliente, devuelve la URL a la que redirigir."""

    @abstractmethod
    def is_connected(self, client_id: str) -> bool:
        """Verifica si el cliente ya tiene una cuenta conectada para esta plataforma."""

    @abstractmethod
    def validate_content(self, asset: LibraryAsset, caption: str) -> list[str]:
        """Devuelve advertencias (lista, puede estar vacia). Lanza PublishValidationError si hay un error duro que impide publicar."""

    @abstractmethod
    def build_preview(self, asset: LibraryAsset, caption: str) -> PublishPreview:
        """Arma la vista previa que ve el humano antes de aprobar."""

    @abstractmethod
    def publish(self, client_id: str, asset: LibraryAsset, caption: str) -> dict:
        """Publica de verdad. Construido y funcional, pero deliberadamente NO se llama desde
        ninguna ruta/boton esta fase — ver 'Explicitamente fuera de esta fase' en el plan."""
