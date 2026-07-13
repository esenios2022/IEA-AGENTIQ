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

FASE 2.5 — publish() corregido tras la primera publicacion real (eAlumina,
2026-07-13, ver https://www.instagram.com/p/Dat8-fYII4N/): la version
original nunca habia sido ejercitada contra la API real y tenia 2 bugs
reales, no detectables sin probar en vivo: (1) faltaba `ig_user_id`,
parametro obligatorio de INSTAGRAM_POST_IG_USER_MEDIA/_PUBLISH — ahora se
resuelve via INSTAGRAM_GET_USER_INFO antes de cada publish(); (2) Instagram
rechaza cualquier image_url/video_url con query string (presigned URLs de
S3 incluidas) — ahora se valida ANTES de llamar a Composio, con un error
claro en vez de dejar que la API externa lo rechace de forma críptica.
"""

from __future__ import annotations

from urllib.parse import urlparse

from src.connectors.base import PublishPreview, PublishValidationError, SocialConnector
from src.connectors.providers.base import SocialProvider, SocialProviderError
from src.connectors.providers.composio_provider import ComposioSocialProvider
from src.library_storage import LibraryStorageError, get_asset_url
from src.models import LibraryAsset

MAX_CAPTION_LENGTH = 2200
SUPPORTED_FILE_TYPES = {"imagen", "video"}

GET_USER_INFO_ACTION = "INSTAGRAM_GET_USER_INFO"
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

    def _resolve_ig_user_id(self, client_id: str) -> str:
        info = self.provider.call_action(client_id, GET_USER_INFO_ACTION, {})
        ig_user_id = info.get("id")
        if not ig_user_id:
            raise SocialProviderError("No se pudo resolver el ig_user_id de la cuenta conectada.")
        return ig_user_id

    def publish(self, client_id: str, asset: LibraryAsset, caption: str) -> dict:
        """FASE 2.5 — ahora sí conectado a un botón real (POST /admin/publicaciones/{id}/publish)."""
        self.validate_content(asset, caption)
        media_url = get_asset_url(asset.storage_key)

        if urlparse(media_url).query:
            raise PublishValidationError(
                "La URL del recurso tiene parámetros de consulta (típico de una presigned URL) — "
                "Instagram las rechaza. Configurá LIBRARY_S3_PUBLIC_BASE_URL con un bucket público real "
                "antes de publicar este recurso."
            )

        ig_user_id = self._resolve_ig_user_id(client_id)

        media_type = "REELS" if asset.file_type == "video" else "IMAGE"
        container = self.provider.call_action(
            client_id,
            CREATE_CONTAINER_ACTION,
            {
                "ig_user_id": ig_user_id,
                "media_type": media_type,
                "image_url" if media_type == "IMAGE" else "video_url": media_url,
                "caption": caption,
            },
        )
        container_id = container.get("id")
        if not container_id:
            raise SocialProviderError(f"No se pudo crear el contenedor de media: {container}")

        result = self.provider.call_action(
            client_id, PUBLISH_CONTAINER_ACTION, {"ig_user_id": ig_user_id, "creation_id": container_id},
        )
        if not result.get("id"):
            raise SocialProviderError(f"La publicación no devolvió un id válido: {result}")
        return result
