"""
InstagramConnector — primer conector real (FASE 2.4). Reglas propias de
Instagram (caption, tipo de media, tipo de cuenta) viven aca; el "como
hablar con la API" vive en el provider inyectado (Composio por defecto).

Action slugs verificados contra la documentacion real de Composio antes
de escribir esto (docs.composio.dev/toolkits/instagram, julio 2026):
INSTAGRAM_POST_IG_USER_MEDIA (crea el contenedor: imagen/video/Reel/
carrusel) + INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH (publica el contenedor,
hace polling automatico — video/Reel tarda 30-120s en procesar). Las
acciones viejas (INSTAGRAM_CREATE_MEDIA_CONTAINER/INSTAGRAM_CREATE_POST)
estan deprecadas, no se usan.

Limitacion real conocida, no resuelta aca: la API de Instagram solo
acepta cuentas Business o Creator, nunca personales — este connector no
puede verificar el tipo de cuenta del lado nuestro antes de publicar
(el propio publish() fallaria recien contra la API real si la cuenta es
personal); se deja como advertencia informativa en build_preview.
"""

from __future__ import annotations

from src.connectors.base import PublishPreview, PublishValidationError, SocialConnector
from src.connectors.providers.base import SocialProvider
from src.connectors.providers.composio_provider import ComposioSocialProvider
from src.library_storage import LibraryStorageError, get_asset_url
from src.models import LibraryAsset

MAX_CAPTION_LENGTH = 2200
SUPPORTED_FILE_TYPES = {"imagen", "video"}

CREATE_CONTAINER_ACTION = "INSTAGRAM_POST_IG_USER_MEDIA"
PUBLISH_CONTAINER_ACTION = "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH"


class InstagramConnector(SocialConnector):
    platform = "instagram"

    def __init__(self, provider: SocialProvider | None = None) -> None:
        self.provider = provider or ComposioSocialProvider()

    def get_auth_url(self, client_id: str) -> str:
        return self.provider.get_auth_url(client_id, self.platform)

    def is_connected(self, client_id: str) -> bool:
        return self.provider.is_connected(client_id, self.platform)

    def validate_content(self, asset: LibraryAsset, caption: str) -> list[str]:
        warnings: list[str] = []

        if asset.file_type not in SUPPORTED_FILE_TYPES or not asset.storage_key:
            raise PublishValidationError(
                f"Instagram necesita una imagen o video real — el recurso '{asset.title}' es de tipo "
                f"'{asset.file_type}' sin archivo asociado."
            )
        if not caption or not caption.strip():
            raise PublishValidationError("Falta el caption de la publicación.")
        if len(caption) > MAX_CAPTION_LENGTH:
            raise PublishValidationError(f"El caption supera el límite de Instagram ({MAX_CAPTION_LENGTH} caracteres).")

        warnings.append(
            "No se puede verificar desde acá si la cuenta de Instagram conectada es Business/Creator "
            "(requisito real de la API, las cuentas personales son rechazadas) — confirmalo manualmente."
        )
        if asset.file_type == "video":
            warnings.append("Los videos/Reels tardan 30–120s en procesar del lado de Instagram antes de poder publicarse.")

        return warnings

    def build_preview(self, asset: LibraryAsset, caption: str) -> PublishPreview:
        try:
            warnings = self.validate_content(asset, caption)
        except PublishValidationError as exc:
            warnings = [f"⚠ {exc}"]

        media_url = None
        if asset.storage_key:
            try:
                media_url = get_asset_url(asset.storage_key)
            except LibraryStorageError as exc:
                warnings.append(f"No se pudo generar la URL del recurso: {exc}")

        return PublishPreview(platform=self.platform, caption=caption, media_url=media_url, file_type=asset.file_type, warnings=warnings)

    def publish(self, client_id: str, asset: LibraryAsset, caption: str) -> dict:
        """Implementado, nunca invocado desde ninguna ruta esta fase."""
        self.validate_content(asset, caption)
        media_url = get_asset_url(asset.storage_key)

        media_type = "REELS" if asset.file_type == "video" else "IMAGE"
        container = self.provider.call_action(
            client_id,
            CREATE_CONTAINER_ACTION,
            {"media_type": media_type, "image_url" if media_type == "IMAGE" else "video_url": media_url, "caption": caption},
        )
        container_id = container.get("id") or container.get("data", {}).get("id")
        return self.provider.call_action(client_id, PUBLISH_CONTAINER_ACTION, {"creation_id": container_id})
