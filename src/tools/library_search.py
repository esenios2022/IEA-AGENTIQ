"""
LibrarySearchTool — busca en la Biblioteca Inteligente de Marketing
(FASE 2.3) antes de generar contenido nuevo. Construida y registrada,
pero NO referenciada por ningun agente todavia (ver src/data/
agents_config.json, que no se toca en esta fase) — queda lista para que
una fase futura la conecte a los agentes del Departamento de Marketing.

Solo devuelve recursos con status="aprobado" — borradores y contenido en
revision no deben sugerirse para reutilizacion.
"""

from crewai.tools import BaseTool

from src import library
from src.database import SessionLocal


class LibrarySearchTool(BaseTool):
    name: str = "library_search"
    description: str = (
        "Busca en la Biblioteca Inteligente de Marketing (imágenes, videos, documentos, prompts "
        "y plantillas ya aprobados) ANTES de generar contenido nuevo, para reutilizar material "
        "existente en vez de duplicar trabajo."
    )
    client_id: str | None = None

    def _run(self, query: str) -> str:
        db = SessionLocal()
        try:
            results = library.search_assets(db, client_id=self.client_id, query=query, status="aprobado", limit=5)
        finally:
            db.close()

        if not results:
            return "No se encontró ningún recurso aprobado relevante en la Biblioteca."

        lines = []
        for asset in results:
            location = f"{asset.category}/{asset.subcategory}" if asset.subcategory else asset.category
            snippet = asset.text_content or asset.description or ""
            if snippet:
                snippet = snippet[:200]
            lines.append(f"[{location}] {asset.title} ({asset.file_type}, {asset.language}): {snippet}")
        return "\n".join(lines)
