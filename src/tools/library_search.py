"""
LibrarySearchTool — busca en la Biblioteca Inteligente de Marketing
antes de generar contenido nuevo (FASE 2.3, mejorada en FASE 2.4A para
devolver datos reutilizables: asset_id, URL, tipo de archivo y estado —
sin esto un agente podía saber que un recurso existía pero no tenía
forma de tomarlo y reutilizarlo).

Conectada a Daniel, Clara, Ariel, Marco, Valentina y Elena (ver src/data/
agents_config.json) — siempre junto con library_save (búsqueda sin
guardado no cierra el ciclo de reutilización).

Solo devuelve recursos con status="aprobado" — borradores y contenido en
revision no deben sugerirse para reutilización.

ETAPA 4.1 (Integración Cosmos → Marketing): cuando el recurso encontrado
es un calendario_editorial, además de los campos genéricos se agrega
`current_week` con TODOS los campos de la semana vigente (no un recorte
a 300 caracteres) — sin esto, "leer el Calendario Editorial mediante
LibrarySearchTool" no le daría a un agente de Marketing nada usable
(marketing_brief, ideas por plataforma, hashtags, etc. quedaban fuera
del texto truncado).
"""

import json
from datetime import date

from crewai.tools import BaseTool

from src import library, library_storage
from src.database import SessionLocal


def _current_week(structured_content: dict | None) -> dict | None:
    """Semana vigente del calendario editorial: la de start_date más
    reciente que ya empezó, o la primera si todas son futuras. Nunca
    inventa datos — si no hay semanas parseadas, devuelve None."""
    weeks = (structured_content or {}).get("weeks") or []
    if not weeks:
        return None
    today = date.today().isoformat()
    past_or_current = [w for w in weeks if w.get("start_date") and w["start_date"] <= today]
    return past_or_current[-1] if past_or_current else weeks[0]


class LibrarySearchTool(BaseTool):
    name: str = "library_search"
    description: str = (
        "Busca en la Biblioteca Inteligente de Marketing (imágenes, videos, documentos, prompts, "
        "plantillas y el Calendario Editorial vigente, todos ya aprobados) ANTES de generar contenido "
        "nuevo. Devuelve, por cada resultado, asset_id, url, tipo de archivo y estado — usá esos datos "
        "para reutilizar el recurso en vez de generar uno nuevo con library_save. Si el resultado es un "
        "calendario_editorial, incluye current_week con el plan completo de la semana vigente (tema, "
        "prioridad, objetivo, audiencia, hashtags, ideas por plataforma, marketing_brief)."
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
                entry = {
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
                if asset.file_type == "calendario_editorial":
                    entry["current_week"] = _current_week(asset.structured_content)
                payload.append(entry)
        finally:
            db.close()

        if not payload:
            return "No se encontró ningún recurso aprobado relevante en la Biblioteca. Podés generar contenido nuevo y guardarlo con library_save."
        return json.dumps(payload, ensure_ascii=False)
