"""
LibrarySaveTool — FASE 2.4A. El único camino por el que un agente puede
dejar contenido nuevo en la Biblioteca Inteligente de Marketing.

Regla dura, no negociable: TODO lo que guarda esta tool queda en
status="borrador", sin excepción — un agente nunca puede aprobar su
propio contenido. Solo un humano, desde el panel /admin/biblioteca,
puede moverlo a en_revision -> aprobado (ver src/library.py::
transition_asset_status).

Para archivos binarios reales (imagen/video generado por una API externa
como HeyGen/Runway/Canva) se guarda `source_url` (el link que devolvió
esa API) en vez de subir bytes — library_storage.get_asset_url()
reconoce URLs externas y las devuelve tal cual. Para texto (prompts,
guiones, copy, briefs) se usa `text_content` directamente.
"""

from crewai.tools import BaseTool

from src import library
from src.database import SessionLocal

FORCED_STATUS = "borrador"


class LibrarySaveTool(BaseTool):
    name: str = "library_save"
    description: str = (
        "Guarda un recurso nuevo (texto, prompt, guion, copy, o un link a un archivo generado "
        "por otra herramienta) en la Biblioteca Inteligente de Marketing. Usala DESPUÉS de haber "
        "buscado con library_search y no haber encontrado nada aprobado que sirva. El recurso "
        "SIEMPRE queda en estado 'borrador' — nunca se aprueba automáticamente, un humano tiene "
        "que revisarlo antes de que otro agente pueda reutilizarlo."
    )
    client_id: str | None = None
    created_by_agent_id: str | None = None

    def _run(
        self,
        title: str,
        category: str,
        file_type: str,
        text_content: str | None = None,
        source_url: str | None = None,
        subcategory: str | None = None,
        description: str | None = None,
        language: str = "es",
        tags: str | None = None,
    ) -> str:
        if not text_content and not source_url:
            return "Error: falta text_content (para texto/prompts) o source_url (para un archivo ya generado)."

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

        db = SessionLocal()
        try:
            asset = library.create_asset(
                db,
                client_id=self.client_id,
                category=category,
                subcategory=subcategory,
                title=title,
                description=description,
                file_type=file_type,
                mime_type=None,
                file_extension=None,
                file_size_bytes=None,
                storage_key=source_url or "",
                text_content=text_content,
                language=language,
                tags=tag_list,
                created_by_agent_id=self.created_by_agent_id,
                status=FORCED_STATUS,
            )
        finally:
            db.close()

        return (
            f"Guardado en la Biblioteca como borrador. asset_id={asset.id}, "
            f"categoria={asset.category}/{asset.subcategory or ''}, estado={asset.status}. "
            "Falta revisión y aprobación humana antes de que pueda reutilizarse."
        )
