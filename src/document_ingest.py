"""Multi-format document ingestion for agent-scoped knowledge bases.

Extracts text from PDF/DOCX/TXT/MD, chunks it by paragraph (hard-splitting
oversized paragraphs), embeds each chunk, and stores it as a `KbArticle`
scoped to the agent it was uploaded for — so Moisés's TQA manuals and
Jeremías's ThetaHealing books don't mix into each other's search results,
or into the general support KB (agent_id NULL).
"""

import io

from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy.orm import Session

from src.embeddings import embed_text
from src.models import KbArticle

CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150
SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt", "md"}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def extract_text(filename: str, content: bytes) -> str:
    ext = _extension(filename)
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "docx":
        doc = DocxDocument(io.BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")
    raise ValueError(f"Formato no soportado: .{ext} (usá PDF, DOCX, TXT o MD)")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(para) <= chunk_size:
            current = para
            continue
        start = 0
        while start < len(para):
            chunks.append(para[start : start + chunk_size])
            start += chunk_size - overlap
    if current:
        chunks.append(current)
    return chunks


def ingest_document(db: Session, *, agent_id, title: str, filename: str, content: bytes) -> int:
    text = extract_text(filename, content)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No se pudo extraer texto del documento.")

    for i, chunk in enumerate(chunks):
        try:
            embedding = embed_text(chunk)
        except Exception:
            embedding = None  # saved anyway; searchable once OPENAI_API_KEY is configured and re-indexed
        db.add(
            KbArticle(
                agent_id=agent_id,
                tema=title,
                pregunta=f"{title} — fragmento {i + 1}/{len(chunks)}",
                respuesta=chunk,
                embedding=embedding,
            )
        )
    db.commit()
    return len(chunks)
