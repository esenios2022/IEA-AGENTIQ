"""Embedding generation for the knowledge-base RAG tool.

Anthropic has no embeddings API, so this is the one deliberate exception to
the otherwise Anthropic-only stack: OpenAI's `text-embedding-3-small` is
cheap (~$0.02/Mtok) and avoids adding a heavier local model dependency.
"""

from openai import OpenAI

from src.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY no está configurada.")
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def embed_text(text: str) -> list[float]:
    client = _get_client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding
