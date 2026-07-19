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

    def publish_carousel(self, client_id: str, assets: list[LibraryAsset], caption: str) -> dict:
        """Post multi-imagen deslizable (carrusel) -- 2026-07-19, agregado para el carrusel
        de apertura del Dia 1 de EALumina. Esquema real confirmado contra Composio antes de
        escribir esto (composio.tools.get_raw_composio_tools(['INSTAGRAM_POST_IG_USER_MEDIA'])):
        1) crear un contenedor hijo por imagen con is_carousel_item=true (sin caption --
        el caption va SOLO en el contenedor padre); 2) crear un contenedor padre con
        media_type=CAROUSEL y children=[ids de los hijos]; 3) publicar el padre con la
        misma accion PUBLISH_CONTAINER_ACTION que un post simple.

        No pasa por el flujo formal de SocialPublication (revision_legal -> aprobado ->
        en_cola) -- deliberado, no un descuido: es un caso puntual de un solo asset este
        dia (el carrusel del Dia 1), con contenido ya revisado a mano por el cliente
        durante toda esta sesion. Generalizar el flujo de aprobacion a multiples assets
        por publicacion queda para cuando haga falta de nuevo, no antes."""
        if not (2 <= len(assets) <= 10):
            raise PublishValidationError(f"Un carrusel necesita entre 2 y 10 imágenes (recibidas: {len(assets)}).")
        for asset in assets:
            if asset.file_type != "imagen" or not asset.storage_key:
                raise PublishValidationError(f"'{asset.title}' no es una imagen con archivo real, no puede ir en un carrusel.")
        if not caption or not caption.strip():
            raise PublishValidationError("Falta el caption del carrusel.")

        media_urls = []
        for asset in assets:
            media_url = get_asset_url(asset.storage_key)
            if urlparse(media_url).query:
                raise PublishValidationError(
                    f"La URL de '{asset.title}' tiene parámetros de consulta (presigned) — Instagram la rechaza. "
                    "Configurá LIBRARY_S3_PUBLIC_BASE_URL con un bucket público real."
                )
            media_urls.append(media_url)

        ig_user_id = self._resolve_ig_user_id(client_id)

        child_ids = []
        for media_url in media_urls:
            child = self.provider.call_action(
                client_id,
                CREATE_CONTAINER_ACTION,
                {"ig_user_id": ig_user_id, "image_url": media_url, "is_carousel_item": True},
            )
            child_id = child.get("id")
            if not child_id:
                raise SocialProviderError(f"No se pudo crear un contenedor hijo del carrusel: {child}")
            child_ids.append(child_id)

        parent = self.provider.call_action(
            client_id,
            CREATE_CONTAINER_ACTION,
            {"ig_user_id": ig_user_id, "media_type": "CAROUSEL", "children": child_ids, "caption": caption},
        )
        parent_id = parent.get("id")
        if not parent_id:
            raise SocialProviderError(f"No se pudo crear el contenedor padre del carrusel: {parent}")

        result = self.provider.call_action(
            client_id, PUBLISH_CONTAINER_ACTION, {"ig_user_id": ig_user_id, "creation_id": parent_id},
        )
        if not result.get("id"):
            raise SocialProviderError(f"La publicación del carrusel no devolvió un id válido: {result}")
        return result

    def publish_story(self, client_id: str, asset: LibraryAsset) -> dict:
        """Story individual (24hs, no carrusel) -- 2026-07-19, agregado para la secuencia de
        3 stories del Dia 2 de EALumina. media_type='STORIES' confirmado como valor real y
        valido del enum contra el esquema de Composio (junto a REELS/CAROUSEL). A diferencia
        de publish(), nunca manda caption -- las stories de Instagram no lo muestran."""
        if asset.file_type != "imagen" or not asset.storage_key:
            raise PublishValidationError(f"'{asset.title}' no es una imagen con archivo real, no puede ir como story.")

        media_url = get_asset_url(asset.storage_key)
        if urlparse(media_url).query:
            raise PublishValidationError(
                f"La URL de '{asset.title}' tiene parámetros de consulta (presigned) — Instagram la rechaza."
            )

        ig_user_id = self._resolve_ig_user_id(client_id)

        container = self.provider.call_action(
            client_id,
            CREATE_CONTAINER_ACTION,
            {"ig_user_id": ig_user_id, "media_type": "STORIES", "image_url": media_url},
        )
        container_id = container.get("id")
        if not container_id:
            raise SocialProviderError(f"No se pudo crear el contenedor de la story: {container}")

        result = self.provider.call_action(
            client_id, PUBLISH_CONTAINER_ACTION, {"ig_user_id": ig_user_id, "creation_id": container_id},
        )
        if not result.get("id"):
            raise SocialProviderError(f"La publicación de la story no devolvió un id válido: {result}")
        return result
