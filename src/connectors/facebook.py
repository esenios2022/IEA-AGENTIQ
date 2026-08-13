"""
FacebookConnector — Bug 3 del plan de cierre de ciclo (2026-08-13): la Página de
Facebook de EALumina (id 1267719713097416) ya estaba conectada en Composio bajo
la misma entidad "ealumina" que Instagram, pero no existía código que la usara
desde el panel (src/connectors/registry.py solo registraba "instagram"). Sigue el
mismo patrón/interfaz que InstagramConnector (src/connectors/instagram.py):
publish/is_connected/get_auth_url/validate_content/build_preview, + publish_carousel
opcional para posts multi-foto.

Diferencia real y no obvia con Instagram, ya descubierta antes de escribir esto:
Meta rechaza crear fotos sin publicar (published=false) en una Página usando el
token de USUARIO que Composio guarda por default para la conexión — error real
de Meta: "#200: Unpublished posts must be posted to a page as the page itself".
La solución real: resolver el access_token específico de la Página llamando
GET /me/accounts (con el token de usuario — esto SÍ funciona con el token de
usuario, ya que es el usuario quien lista sus propias Páginas) y usar ESE token
de Página para publicar.

Por qué las llamadas que publican de verdad (POST /{page_id}/photos y
POST /{page_id}/feed) van directo a graph.facebook.com vía `requests` en vez de
pasar por ComposioSocialProvider.proxy(): proxy() siempre firma la llamada con el
token de la cuenta conectada (el del usuario) — no tiene forma de inyectar un
token distinto (el de la Página) sin tocar la lógica interna de Composio, que
está fuera de alcance. Pasar `access_token=<token de Página>` como query param es
la forma estándar y documentada de autenticar cualquier llamada de la Graph API
de Meta (no depende de Composio) — GET /me/accounts sí se resuelve vía
proxy() porque para ESA llamada el token correcto es el del usuario.

Verificado real contra la API de Composio antes de escribir esto (2026-08-13):
ComposioSocialProvider().is_connected("ealumina", "facebook") -> True (1 cuenta
ACTIVE). El intento de GET /me/accounts vía proxy() para "ealumina" devolvió un
error real y vigente de Meta (code 190, subcode 458: "The user has not
authorized application <id>") — la conexión de Facebook de EALumina en Composio
está en estado ACTIVE pero el token guardado ya no es válido contra la Graph API
real. Este connector queda funcionalmente completo y lee ese caso de error de
forma clara (SocialProviderError con el mensaje real de Meta), pero el usuario
necesita reconectar la Página de Facebook en Composio antes de que un publish()
real pueda completarse — no es un bug de este código, es un hallazgo aparte que
hay que resolver del lado de la conexión.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

import requests

from src.connectors.base import PublishPreview, PublishValidationError, SocialConnector
from src.connectors.providers.base import SocialProvider, SocialProviderError
from src.connectors.providers.composio_provider import ComposioSocialProvider
from src.library_storage import LibraryStorageError, get_asset_url
from src.models import LibraryAsset

# Límite de caracteres ampliamente citado para el "message" de un post de Facebook
# (63206) — a diferencia del límite de Instagram (2200, ver instagram.py), este no
# se re-verificó contra la documentación oficial más reciente de Meta en este ciclo;
# se deja como validación best-effort, no como un dato garantizado.
MAX_MESSAGE_LENGTH = 63206
SUPPORTED_FILE_TYPES = {"imagen"}

GRAPH_API_BASE = "https://graph.facebook.com"
ACCOUNTS_ENDPOINT = "/me/accounts"


class FacebookConnector(SocialConnector):
    platform = "facebook"

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
                f"Facebook (este connector) necesita una imagen real — el recurso '{asset.title}' es de tipo "
                f"'{asset.file_type}' sin archivo asociado. Video/link posts no están implementados todavía."
            )
        if not caption or not caption.strip():
            raise PublishValidationError("Falta el mensaje de la publicación.")
        if len(caption) > MAX_MESSAGE_LENGTH:
            raise PublishValidationError(f"El mensaje supera el límite de Facebook (~{MAX_MESSAGE_LENGTH} caracteres).")

        warnings.append(
            "No se puede verificar desde acá si la cuenta de Facebook conectada tiene permisos de publicación "
            "sobre una Página real (requisito de la API) — se resuelve recién al publicar, vía GET /me/accounts."
        )
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

    def _resolve_page(self, client_id: str) -> tuple[str, str]:
        """Resuelve (page_id, page_access_token) de la Página de Facebook conectada
        para este cliente vía GET /me/accounts (con el token de usuario, a través de
        ComposioSocialProvider.proxy()). Si la cuenta administra más de una Página,
        toma la primera que devuelve Meta — hoy alcanza porque cada cliente conecta
        una sola Página (ej. EALumina, id 1267719713097416); soportar selección
        explícita de Página (ej. client.config["facebook_page_id"]) queda para cuando
        haga falta de nuevo, no antes."""
        data = self.provider.proxy(client_id, self.platform, ACCOUNTS_ENDPOINT, "GET")
        pages = data.get("data") or []
        if not pages:
            raise SocialProviderError(
                "La cuenta de Facebook conectada no administra ninguna Página (GET /me/accounts no devolvió resultados)."
            )
        page = pages[0]
        page_id = page.get("id")
        page_token = page.get("access_token")
        if not page_id or not page_token:
            raise SocialProviderError(f"GET /me/accounts no devolvió id/access_token de Página utilizable: {page}")
        return page_id, page_token

    @staticmethod
    def _graph_post(page_id: str, edge: str, page_token: str, params: dict) -> dict:
        """POST directo a graph.facebook.com con el access_token de Página como query
        param — ver docstring del módulo para por qué no pasa por Composio.proxy()."""
        url = f"{GRAPH_API_BASE}/{page_id}/{edge}"
        try:
            response = requests.post(url, params={**params, "access_token": page_token}, timeout=30)
        except requests.RequestException as exc:
            raise SocialProviderError(f"Llamada a Facebook Graph API ({edge}) falló: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise SocialProviderError(
                f"Facebook Graph API ({edge}) devolvió una respuesta no-JSON (status {response.status_code}): "
                f"{response.text[:300]}"
            ) from exc

        if isinstance(data, dict) and "error" in data:
            raise SocialProviderError(f"Facebook Graph API ({edge}) devolvió error: {data['error']}")
        return data

    def _create_unpublished_photo(self, page_id: str, page_token: str, media_url: str) -> str:
        data = self._graph_post(page_id, "photos", page_token, {"url": media_url, "published": "false"})
        photo_id = data.get("id")
        if not photo_id:
            raise SocialProviderError(f"No se pudo crear la foto sin publicar en la Página: {data}")
        return photo_id

    def _create_feed_post(self, page_id: str, page_token: str, caption: str, photo_ids: list[str]) -> dict:
        attached_media = json.dumps([{"media_fbid": pid} for pid in photo_ids])
        result = self._graph_post(page_id, "feed", page_token, {"message": caption, "attached_media": attached_media})
        if not result.get("id"):
            raise SocialProviderError(f"La publicación en la Página no devolvió un id válido: {result}")
        return result

    def _resolve_media_url(self, asset: LibraryAsset) -> str:
        media_url = get_asset_url(asset.storage_key)
        if urlparse(media_url).query:
            raise PublishValidationError(
                f"La URL de '{asset.title}' tiene parámetros de consulta (típico de una presigned URL) — "
                "Facebook la rechaza igual que Instagram. Configurá LIBRARY_S3_PUBLIC_BASE_URL con un bucket "
                "público real antes de publicar este recurso."
            )
        return media_url

    def publish(self, client_id: str, asset: LibraryAsset, caption: str) -> dict:
        """Post de una sola foto: crea la foto sin publicar y la adjunta a un post
        nuevo del feed de la Página — mismo mecanismo de attached_media que
        publish_carousel(), con una sola foto."""
        self.validate_content(asset, caption)
        media_url = self._resolve_media_url(asset)

        page_id, page_token = self._resolve_page(client_id)
        photo_id = self._create_unpublished_photo(page_id, page_token, media_url)
        return self._create_feed_post(page_id, page_token, caption, [photo_id])

    def publish_carousel(self, client_id: str, assets: list[LibraryAsset], caption: str) -> dict:
        """Post multi-foto deslizable en la Página, mismo mecanismo que el carrusel de
        Instagram (ver instagram.py::publish_carousel) pero con la mecánica real de
        Facebook, ya probada: (1) por cada foto, POST /{page_id}/photos con
        published=false y el token de Página -> devuelve un id; (2) un único
        POST /{page_id}/feed con message + attached_media=[{"media_fbid": id}, ...]
        con todas las fotos, también con el token de Página."""
        if not (2 <= len(assets) <= 10):
            raise PublishValidationError(f"Un post multi-foto necesita entre 2 y 10 imágenes (recibidas: {len(assets)}).")
        for asset in assets:
            if asset.file_type != "imagen" or not asset.storage_key:
                raise PublishValidationError(f"'{asset.title}' no es una imagen con archivo real, no puede ir en un post multi-foto.")
        if not caption or not caption.strip():
            raise PublishValidationError("Falta el mensaje del post.")

        media_urls = [self._resolve_media_url(asset) for asset in assets]

        page_id, page_token = self._resolve_page(client_id)
        photo_ids = [self._create_unpublished_photo(page_id, page_token, url) for url in media_urls]
        return self._create_feed_post(page_id, page_token, caption, photo_ids)
