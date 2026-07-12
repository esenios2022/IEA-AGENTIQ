"""
AiLabKnowledgeSearchTool — the AI LAB's real, Qdrant-backed, multi-tenant
RAG (`core.knowledge.search.KnowledgeSearch`, Sprint 13), reached over
the AI LAB Service's `/api/v1/knowledge/search` (Sprint 26).

Deliberately additive, not a replacement for `src.tools.knowledge_base.
KnowledgeBaseTool` — that one keeps serving `KbArticle` rows exactly as
it does today, zero changes. This is a second, separate knowledge
source an agent can be given in addition, so real usage data can
accumulate before anyone decides whether to unify or keep both. Maps
to the `ai_lab_knowledge` tool id in agent definitions.
"""

from crewai.tools import BaseTool

from src.ai_lab_client import AiLabNotConfiguredError, AiLabRequestError, ai_lab_client


class AiLabKnowledgeSearchTool(BaseTool):
    name: str = "ai_lab_knowledge"
    description: str = (
        "Busca en la base de conocimiento del AI LAB (RAG real sobre Qdrant, multi-tenant). "
        "Una fuente de conocimiento distinta y adicional a 'knowledge_base' — usala cuando "
        "necesites documentos o contenido cargado específicamente en el AI LAB."
    )
    tenant_id: str | None = None

    def _run(self, query: str) -> str:
        if not self.tenant_id:
            return "Búsqueda no disponible: no hay tenant_id configurado para este agente."

        try:
            result = ai_lab_client.knowledge_search(tenant_id=self.tenant_id, query=query)
        except AiLabNotConfiguredError:
            return "Búsqueda no disponible: falta configurar AI_LAB_BASE_URL."
        except AiLabRequestError as exc:
            return f"Error buscando en el AI LAB: {exc}"

        text = result.get("text", "")
        if not text:
            return "No se encontró contenido relevante en el AI LAB."
        return text
