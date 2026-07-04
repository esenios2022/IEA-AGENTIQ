"""RAG knowledge-base search: brute-force cosine similarity, no pgvector dependency.

Maps to the `supabase_knowledge_base` tool id in agents_config.json.
`KbArticle.agent_id` scopes articles: NULL is a global article visible to
every agent's search (María/Elías's short support FAQs); a set agent_id
scopes it to just that agent (e.g. Moisés's TQA manuals, Jeremías's
ThetaHealing books) so unrelated agents never surface each other's reference
material.

At the scale this platform targets, doing the similarity math in Python over
a capped SELECT is fast enough and avoids depending on the hosting Postgres
instance supporting `CREATE EXTENSION vector`. See `src.agent_executor` for
the zero-LLM-cost shortcut this module also powers (María/Elías: answer
straight from a high-confidence KB hit).
"""

import math

from crewai.tools import BaseTool
from sqlalchemy import or_, select

from src.database import SessionLocal
from src.embeddings import embed_text
from src.models import KbArticle

CANDIDATE_LIMIT = 2000
TOP_K = 3
SHORTCUT_SIMILARITY_THRESHOLD = 0.85


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_kb(query: str, agent_id=None, top_k: int = TOP_K) -> list[tuple[KbArticle, float]]:
    query_embedding = embed_text(query)

    db = SessionLocal()
    try:
        conditions = [KbArticle.embedding.isnot(None)]
        scope = KbArticle.agent_id.is_(None)
        if agent_id is not None:
            scope = or_(scope, KbArticle.agent_id == agent_id)
        conditions.append(scope)
        candidates = db.scalars(select(KbArticle).where(*conditions).limit(CANDIDATE_LIMIT)).all()
    finally:
        db.close()

    scored = [(article, _cosine_similarity(query_embedding, article.embedding)) for article in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def best_match(query: str, agent_id=None) -> tuple[KbArticle, float] | None:
    try:
        results = search_kb(query, agent_id=agent_id, top_k=1)
    except Exception:
        return None
    return results[0] if results else None


class KnowledgeBaseTool(BaseTool):
    name: str = "knowledge_base"
    description: str = (
        "Busca en la base de conocimiento (artículos y fragmentos de documentos cargados). "
        "Consultala ANTES de razonar desde cero — si hay un fragmento relevante, usalo como base "
        "de tu respuesta."
    )
    agent_id: str | None = None

    def _run(self, query: str) -> str:
        try:
            results = search_kb(query, agent_id=self.agent_id)
        except RuntimeError as exc:
            return f"Base de conocimiento no disponible: {exc}"
        except Exception as exc:
            return f"Error buscando en la base de conocimiento: {exc}"

        if not results:
            return "No se encontró ningún artículo relevante en la base de conocimiento."

        lines = []
        for article, score in results:
            lines.append(f"[{score:.2f}] {article.tema}: {article.pregunta} -> {article.respuesta}")
        return "\n".join(lines)
