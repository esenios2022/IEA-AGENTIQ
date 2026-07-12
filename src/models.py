import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    empresa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # FASE 2.2 — campos ya diseñados en material_subido_fabian/HANDOFF_CLAUDE_CODE.md,
    # nunca antes implementados. Todos opcionales o con default: agregar estos campos
    # no cambia el comportamiento de ningun llamador existente de POST /api/leads.
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pais: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan_interes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fuente: Mapped[str] = mapped_column(String(100), default="landing_web")
    estado: Mapped[str] = mapped_column(String(50), default="prospecto")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Campos agregados a pedido explicito (mensaje del Arquitecto Principal durante esta
    # misma fase): el Lead debe poder representar un PACIENTE potencial, no solo un
    # contacto generico — necesarios para el paso de clasificacion/seleccion de terapeuta
    # que esta fase prepara pero NO implementa (ver src/lead_qualification.py).
    tenant: Mapped[str] = mapped_column(String(100), default="ealumina")  # eAlumina primero; Terra Araras y otros clientes de IEA AGENTIQ despues, mismo modelo
    idioma: Mapped[str] = mapped_column(String(10), default="es")
    tipo_terapia: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ej. "ansiedad", "terapia de pareja", "duelo"
    disponibilidad: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ej. "tardes entre semana", "fines de semana"
    clasificacion_ia: Mapped[str | None] = mapped_column(Text, nullable=True)  # generada por el paso real de analisis IA, ver qualify_and_contact_lead()


class LeadInteraction(Base):
    """Un registro real por cada intento de contacto automatizado hacia un Lead — FASE 2.2."""

    __tablename__ = "lead_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    channel: Mapped[str] = mapped_column(String(50), default="whatsapp")
    direction: Mapped[str] = mapped_column(String(20), default="outbound")
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50))  # "sent" | "failed"
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    daily_budget_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClientAgent(Base):
    __tablename__ = "client_agents"
    __table_args__ = (UniqueConstraint("client_id", "agent_id", name="uq_client_agent"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    schedule_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schedule_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[str | None] = mapped_column(Text, nullable=True)


class UsageLog(Base):
    """One row per agent execution (lean executor or CrewAI), used for cost/budget tracking."""

    __tablename__ = "usage_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    model: Mapped[str] = mapped_column(String(100))
    tier: Mapped[str] = mapped_column(String(20))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResponseCache(Base):
    """Caches agent responses for 24h (TTL enforced at query time) to avoid re-paying for identical requests."""

    __tablename__ = "response_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    hash_prompt: Mapped[str] = mapped_column(String(64), index=True)
    response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KbArticle(Base):
    """Knowledge-base article for the RAG tool (brute-force cosine similarity, no pgvector dependency).

    `agent_id` NULL means a global article visible to every agent's KB search;
    a set `agent_id` scopes it to that agent only (e.g. a therapy technique's
    reference books, not mixed into the general support KB).
    """

    __tablename__ = "kb_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    tema: Mapped[str] = mapped_column(String(255))
    pregunta: Mapped[str] = mapped_column(Text)
    respuesta: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PatientCase(Base):
    """A named, persistent thread of work on one patient (for agents with `case_memory: true`).

    Every message sent while a case is open is saved to `CaseMessage` and
    replayed back to the model on the next message, so the agent keeps
    context across sessions days or weeks apart — unlike the default
    single-shot `run()` path used by every other agent.
    """

    __tablename__ = "patient_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    patient_label: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="abierto")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CaseMessage(Base):
    __tablename__ = "case_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_cases.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LibraryAsset(Base):
    """Biblioteca Inteligente de Marketing (FASE 2.3) — un recurso reutilizable
    (imagen, video, documento, prompt o plantilla) que los agentes de Marketing
    podran buscar antes de generar contenido nuevo (busqueda todavia no conectada
    a ningun agente en esta fase, ver src/tools/library_search.py).

    `client_id` NULL significa "Recursos Globales" (visible para todos los
    clientes), igual que el patron ya usado por KbArticle.client_id.
    """

    __tablename__ = "library_assets"
    __table_args__ = (
        Index("ix_library_assets_client_category_status", "client_id", "category", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_type: Mapped[str] = mapped_column(String(30))  # imagen | video | documento | audio | prompt | plantilla | otro
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # prompts/plantillas guardados como texto inline
    language: Mapped[str] = mapped_column(String(10), default="es")
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="borrador", index=True)  # borrador | en_revision | aprobado | archivado
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
