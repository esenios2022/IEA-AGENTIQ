"""
LibrarySearchTool — busca en la Biblioteca Inteligente de Marketing
antes de generar contenido nuevo (FASE 2.3, mejorada en FASE 2.4A para
devolver datos reutilizables: asset_id, URL, tipo de archivo y estado —
sin esto un agente podía saber que un recurso existía pero no tenía
forma de tomarlo y reutilizarlo).

Conectada a Ariel, Marco, Valentina y Elena (ver src/data/
agents_config.json) — siempre junto con library_save (búsqueda sin
guardado no cierra el ciclo de reutilización).

Solo devuelve recursos con status="aprobado" — borradores y contenido en
revision no deben sugerirse para reutilización.
"""

import json

from crewai.tools import BaseTool

from src import library, library_storage
from src.database import SessionLocal


class LibrarySearchTool(BaseTool):
    name: str = "library_search"
    description: str = (
        "Busca en la Biblioteca Inteligente de Marketing (imágenes, videos, documentos, prompts "
        "y plantillas ya aprobados) ANTES de generar contenido nuevo. Devuelve, por cada resultado, "
        "asset_id, url, tipo de archivo y estado — usá esos datos para reutilizar el recurso en vez "
        "de generar uno nuevo con library_save."
    )
    client_id: str | None = None

    def _run(self, query: str) -> str:
        db = SessionLocal()
        try:
            results = library.search_assets(db, client_id=self.client_id, query=query, status="aprobado", limit=5)

            payload = []
            for asset in results:
                url = None
                if asset.storage_key:
                    try:
                        url = library_storage.get_asset_url(asset.storage_key)
                    except library_storage.LibraryStorageError:
                        url = None
                payload.append(
                    {
                        "asset_id": str(asset.id),
                        "title": asset.title,
                        "category": asset.category,
                        "subcategory": asset.subcategory,
                        "file_type": asset.file_type,
                        "language": asset.language,
                        "status": asset.status,
                        "url": url,
                        "text_content": (asset.text_content[:300] if asset.text_content else None),
                    }
                )
        finally:
            db.close()

        if not payload:
            return "No se encontró ningún recurso aprobado relevante en la Biblioteca. Podés generar contenido nuevo y guardarlo con library_save."
        return json.dumps(payload, ensure_ascii=False)
