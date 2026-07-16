"""
GeminiImageTool — 2026-07-14. Primera herramienta real de generación de
imágenes de la Biblioteca Inteligente de Marketing: genera con la cuenta
propia de IEA-AGENTIQ (no BYOK del cliente, confirmado por el usuario),
sube el binario real a storage S3-compatible y deja el resultado en la
Biblioteca como borrador — mismo patrón que LibrarySaveTool (nunca se
auto-aprueba lo que un agente genera).

Modelo usado: `gemini-2.5-flash-image` vía `generate_content()` — los
modelos Imagen dedicados (`imagen-4.0-*`) están restringidos ("no longer
available to new users") para keys nuevas, confirmado real ese mismo día
en gemini_executor.py. Este es el camino que sí funciona.

2026-07-16 — composición real del logo aprobado: un modelo de generación
de imagen por texto no reproduce de forma confiable un logo específico
(confirmado real: la primera corrida produjo un fondo abstracto genérico
sin ninguna relación con la marca). En vez de confiar en que el prompt
"describa" el logo, esta tool busca el logo real aprobado del cliente en
la Biblioteca (categoría Marca/Logos), le quita el fondo blanco de forma
programática (los 3 logos reales del cliente son JPEG opacos, sin canal
alfa) y lo compone sobre el fondo generado — así el resultado final
siempre tiene el logo real y exacto, nunca una aproximación de la IA.
"""

import io
import mimetypes
import uuid

from crewai.tools import BaseTool
from PIL import Image

from src import library, library_storage
from src.config import settings
from src.cost import record_usage
from src.database import SessionLocal

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
FORCED_STATUS = "borrador"
DEFAULT_CATEGORY = "Imágenes"
LOGO_WHITE_THRESHOLD = 245  # 0-255; píxeles con los 3 canales por encima de esto se vuelven transparentes
LOGO_WIDTH_RATIO = 0.42  # ancho del logo compuesto, relativo al ancho del canvas final
LOGO_BOTTOM_MARGIN_RATIO = 0.08  # margen inferior, relativo a la altura del canvas


def _remove_near_white_background(image: Image.Image, threshold: int = LOGO_WHITE_THRESHOLD) -> Image.Image:
    """Chroma-key simple sobre fondo blanco uniforme (confirmado real:
    los 3 logos del cliente tienen fondo (254,254,254) uniforme en las
    4 esquinas) — vuelve transparentes los píxeles cercanos al blanco,
    con una transición suave cerca del umbral para evitar un recorte
    con bordes duros."""
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            min_channel = min(r, g, b)
            if min_channel >= threshold:
                pixels[x, y] = (r, g, b, 0)
            elif min_channel >= threshold - 15:
                # transición suave en vez de un corte duro
                fade = int(255 * (threshold - min_channel) / 15)
                pixels[x, y] = (r, g, b, fade)
    return rgba


def _find_approved_logo(db, client_id: str | None):
    assets = library.search_assets(
        db, client_id=client_id, category="Marca", subcategory="Logos", status="aprobado", limit=5
    )
    for asset in assets:
        if "branco" in (asset.title or "").lower() or "1" in (asset.title or ""):
            return asset
    return assets[0] if assets else None


def _compose_logo_onto_background(background_bytes: bytes, logo_bytes: bytes) -> bytes:
    background = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
    logo = _remove_near_white_background(Image.open(io.BytesIO(logo_bytes)))

    target_width = int(background.width * LOGO_WIDTH_RATIO)
    scale = target_width / logo.width
    logo = logo.resize((target_width, int(logo.height * scale)), Image.LANCZOS)

    x = (background.width - logo.width) // 2
    y = int(background.height - logo.height - background.height * LOGO_BOTTOM_MARGIN_RATIO)
    background.alpha_composite(logo, (x, y))

    out = io.BytesIO()
    background.convert("RGB").save(out, format="PNG")
    return out.getvalue()


class GeminiImageTool(BaseTool):
    name: str = "gemini_image"
    description: str = (
        "Genera una imagen real con Gemini a partir de una descripción y la guarda en la Biblioteca "
        "Inteligente de Marketing. Usala cuando necesites una pieza visual nueva (no hay ninguna "
        "aprobada reutilizable encontrada con library_search). El resultado SIEMPRE queda en estado "
        "'borrador' — un humano tiene que revisarlo antes de que otro agente pueda reutilizarlo."
    )
    client_id: str | None = None
    created_by_agent_id: str | None = None

    def _run(
        self,
        prompt: str,
        title: str,
        subcategory: str | None = None,
        description: str | None = None,
    ) -> str:
        if not settings.gemini_api_key:
            return "Error: GEMINI_API_KEY no está configurada en la plataforma — no se puede generar la imagen."

        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(model=GEMINI_IMAGE_MODEL, contents=prompt)

        image_bytes: bytes | None = None
        mime_type = "image/png"
        for part in (response.candidates[0].content.parts if response.candidates else []):
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and inline_data.data:
                image_bytes = inline_data.data
                mime_type = inline_data.mime_type or mime_type
                break

        if image_bytes is None:
            return "Error: Gemini no devolvió ninguna imagen para ese prompt — probá reformularlo."

        usage = response.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        output_tokens = (usage.candidates_token_count or 0) if usage else 0

        logo_composed = False
        compose_db = SessionLocal()
        try:
            logo_asset = _find_approved_logo(compose_db, self.client_id)
            if logo_asset is not None:
                try:
                    logo_bytes = library_storage.download_asset(logo_asset.storage_key)
                    image_bytes = _compose_logo_onto_background(image_bytes, logo_bytes)
                    mime_type = "image/png"
                    logo_composed = True
                except (library_storage.LibraryStorageError, OSError) as exc:
                    print(f"[gemini_image_tool] no se pudo componer el logo real ({exc}), sigo sin él", flush=True)
        finally:
            compose_db.close()

        extension = (mimetypes.guess_extension(mime_type) or ".png").lstrip(".")
        filename = f"{uuid.uuid4()}.{extension}"
        storage_key = library_storage.build_storage_key(self.client_id, DEFAULT_CATEGORY, subcategory, filename)

        try:
            library_storage.upload_asset(image_bytes, storage_key, content_type=mime_type)
        except library_storage.LibraryStorageNotConfiguredError:
            return (
                "Error: el almacenamiento S3-compatible de la Biblioteca no está configurado "
                "(LIBRARY_S3_BUCKET/LIBRARY_S3_ACCESS_KEY_ID/LIBRARY_S3_SECRET_ACCESS_KEY) — "
                "la imagen se generó pero no se pudo guardar. Avisá al admin."
            )
        except library_storage.LibraryStorageError as exc:
            return f"Error subiendo la imagen al almacenamiento: {exc}"

        db = SessionLocal()
        try:
            asset = library.create_asset(
                db,
                client_id=self.client_id,
                category=DEFAULT_CATEGORY,
                subcategory=subcategory,
                title=title,
                description=description,
                file_type="imagen",
                mime_type=mime_type,
                file_extension=extension,
                file_size_bytes=len(image_bytes),
                storage_key=storage_key,
                text_content=prompt,
                created_by_agent_id=self.created_by_agent_id,
                status=FORCED_STATUS,
            )

            asset_id = asset.id

            if self.created_by_agent_id:
                record_usage(
                    db,
                    agent_id=self.created_by_agent_id,
                    client_id=self.client_id,
                    execution_id=None,
                    model=GEMINI_IMAGE_MODEL,
                    tier="gemini-platform",
                    provider="gemini",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=True,
                    input_text=prompt,
                    platform_cost=True,
                    content_asset_id=asset_id,
                )
        finally:
            db.close()

        # asset_id (no asset.id) porque la sesión ya cerró arriba -- accederlo
        # tras db.close() dispara un lazy-load contra una sesión cerrada
        # (DetachedInstanceError), confirmado real en la verificación end-to-end.
        url = library_storage.get_asset_url(storage_key)
        logo_note = " Logo real de la marca compuesto sobre el fondo generado." if logo_composed else ""
        return f"Imagen generada y guardada en la Biblioteca como borrador. asset_id={asset_id}, url={url}.{logo_note}"
