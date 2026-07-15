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
"""

import mimetypes
import uuid

from crewai.tools import BaseTool

from src import library, library_storage
from src.config import settings
from src.cost import record_usage
from src.database import SessionLocal

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
FORCED_STATUS = "borrador"
DEFAULT_CATEGORY = "Imágenes"


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
        return f"Imagen generada y guardada en la Biblioteca como borrador. asset_id={asset_id}, url={url}"
