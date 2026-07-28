import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from secrets import compare_digest

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete as sa_delete, select, text, update as sa_update
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from src.agent_runtime import AgentRuntime
from src.agent_seed import load_master_config, sync_master_agents
from src.agent_service import AgentPausedError
from src.agent_service import run as run_agent_service
from src.architect_agent import get_obatala
from src.auth import get_current_client, hash_password, verify_password
from src.case_memory import create_case, get_case, get_case_history, list_cases
from src.composio_tools import start_connection
from src.config import settings
from src.database import Base, SessionLocal, engine, get_db
from src.document_ingest import ingest_document
from src.embeddings import embed_text
from src import editorial_calendar, instagram_comment_automation, library, library_storage, marketing_pipeline, social_publishing, strategic_intelligence
from src.connectors.base import PublishValidationError
from src.connectors.providers.base import SocialProviderError
from src.connectors.registry import CONNECTORS
from src.lead_qualification import qualify_and_contact_lead
from src.models import Agent, CaseMessage, Client, ClientAgent, KbArticle, Lead, LeadInteraction, PatientCase, ResponseCache, SocialPublication, UsageLog
from src.scheduler import start_scheduler
from src.schemas import (
    AgentOut,
    ArchitectCreateAgentRequest,
    ArchitectCreateAgentResponse,
    AssignedAgentOut,
    CaseMessageOut,
    CaseOut,
    CaseRunRequest,
    ClientLogin,
    ClientOut,
    ConnectToolkitResponse,
    CreateCaseRequest,
    CrewRunRequest,
    CrewRunResponse,
    ExecutionOut,
    KbArticleOut,
    LeadCreate,
    LeadInteractionOut,
    LeadOut,
    LibraryAssetOut,
    ProfitabilityByClientOut,
    ProfitabilityOut,
    UsageByAgentOut,
    UsageOut,
)
from src.usage_reports import agent_usage_summary, profitability_by_client, usage_by_agent, usage_by_department


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # creates lead_interactions (new table) for real, but never alters an existing table's columns
    # Safe column migrations — ADD COLUMN IF NOT EXISTS never fails on re-deploy
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS config JSONB")
        )
        # FASE 2.2 — leads already existed before these columns were added, same reasoning as clients.config above.
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS telefono VARCHAR(50)"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS ciudad VARCHAR(255)"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS pais VARCHAR(100)"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS plan_interes VARCHAR(255)"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS fuente VARCHAR(100) NOT NULL DEFAULT 'landing_web'"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS estado VARCHAR(50) NOT NULL DEFAULT 'prospecto'"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS notas TEXT"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tenant VARCHAR(100) NOT NULL DEFAULT 'ealumina'"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS idioma VARCHAR(10) NOT NULL DEFAULT 'es'"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tipo_terapia VARCHAR(255)"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS disponibilidad VARCHAR(255)"))
        conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS clasificacion_ia TEXT"))
        conn.commit()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="IEA-AGENTIQ", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

security = HTTPBasic(auto_error=False)


def require_admin(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)):
    if request.session.get("is_admin"):
        return
    if credentials is not None:
        valid_user = compare_digest(credentials.username, settings.admin_user)
        valid_password = compare_digest(credentials.password, settings.admin_password)
        if valid_user and valid_password:
            return
    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": "/login?as=admin"},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/config/providers")
def provider_config():
    """Tells the frontend which AI providers are configured server-side."""
    return {
        "gemini": bool(settings.gemini_api_key),
        "anthropic": bool(settings.anthropic_api_key),
    }


def _serve_static_html(filename: str) -> HTMLResponse:
    with open(f"src/templates/{filename}", encoding="utf-8") as f:
        content = f.read()
    # 2026-07-18 -- sin esto el navegador puede servir una version vieja de
    # /plataforma desde su cache local sin siquiera consultar al servidor
    # (confirmado real: un usuario seguia viendo el login embebido viejo
    # despues de que el fix de auth ya estaba deployado y funcionando).
    return HTMLResponse(content, headers={"Cache-Control": "no-store"})


@app.get("/")
def home():
    return _serve_static_html("index.html")


@app.post("/api/leads", response_model=LeadOut)
def create_lead(lead: LeadCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_lead = Lead(
        nombre=lead.nombre, email=lead.email, empresa=lead.empresa,
        telefono=lead.telefono, ciudad=lead.ciudad, pais=lead.pais, plan_interes=lead.plan_interes,
        fuente=lead.fuente, notas=lead.notas, tenant=lead.tenant, idioma=lead.idioma,
        tipo_terapia=lead.tipo_terapia, disponibilidad=lead.disponibilidad,
    )
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)

    # FASE 2.2 — automatico SOLO si se proveyo telefono. Ningun llamador existente de este
    # endpoint envia ese campo hoy, asi que esto no cambia el comportamiento para nadie que
    # ya lo use (Terra Araras u otros) — ver docs/AI_LAB_INTEGRATION.md.
    if db_lead.telefono:
        background_tasks.add_task(_run_lead_qualification, db_lead.id)

    return db_lead


def _run_lead_qualification(lead_id: int) -> None:
    """Corre en un BackgroundTask real de FastAPI — despues de responder al llamador, con su propia sesion de DB (la del request ya se cerro)."""
    db = SessionLocal()
    try:
        db_lead = db.get(Lead, lead_id)
        if db_lead is not None:
            qualify_and_contact_lead(db_lead, db)
    finally:
        db.close()


@app.post("/api/leads/{lead_id}/qualify", response_model=LeadInteractionOut)
def qualify_lead_now(lead_id: int, db: Session = Depends(get_db)):
    """Disparo manual/explicito del ciclo completo — para probar el flujo sobre un lead ya existente sin esperar al BackgroundTask, o para reintentar uno que fallo."""
    db_lead = db.get(Lead, lead_id)
    if db_lead is None:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    interaction = qualify_and_contact_lead(db_lead, db)
    if interaction is None:
        raise HTTPException(status_code=400, detail="El lead no tiene telefono — nada que contactar por WhatsApp.")
    return interaction


@app.get("/api/leads/{lead_id}/interactions", response_model=list[LeadInteractionOut])
def list_lead_interactions(lead_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(LeadInteraction).where(LeadInteraction.lead_id == lead_id).order_by(LeadInteraction.created_at.desc())
    ).all()


@app.get("/admin/leads")
def list_leads(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    leads = db.scalars(select(Lead).order_by(Lead.created_at.desc())).all()
    return templates.TemplateResponse(request, "admin_leads.html", {"leads": leads})


@app.get("/admin/knowledge")
def list_knowledge_page(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    articles = db.scalars(select(KbArticle).order_by(KbArticle.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "admin_knowledge.html",
        {"articles": articles, "openai_configured": bool(settings.openai_api_key)},
    )


@app.post("/admin/knowledge")
def create_knowledge_article(
    tema: str = Form(...),
    pregunta: str = Form(...),
    respuesta: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    embedding = None
    try:
        embedding = embed_text(f"{tema}\n{pregunta}")
    except Exception as exc:
        print(f"[main] no se pudo generar embedding para el artículo nuevo: {exc}", flush=True)

    db.add(KbArticle(tema=tema, pregunta=pregunta, respuesta=respuesta, embedding=embedding))
    db.commit()
    return RedirectResponse(url="/admin/knowledge", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/knowledge/{article_id}/delete")
def delete_knowledge_article(
    article_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    article = db.get(KbArticle, article_id)
    if article is not None:
        db.delete(article)
        db.commit()
    return RedirectResponse(url="/admin/knowledge", status_code=status.HTTP_303_SEE_OTHER)


LIBRARY_MAX_UPLOAD_MB = 200


@app.get("/admin/biblioteca")
def list_library_page(
    request: Request,
    client_id: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    file_type: str | None = None,
    language: str | None = None,
    library_status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    assets = library.search_assets(
        db,
        client_id=client_id,
        category=category,
        subcategory=subcategory,
        file_type=file_type,
        language=language,
        status=library_status,
        query=q,
        limit=200,
    )
    clients = db.scalars(select(Client).order_by(Client.name)).all()
    folder_tree = library.get_folder_tree(db, client_id=client_id)
    return templates.TemplateResponse(
        request,
        "admin_biblioteca.html",
        {
            "assets": assets,
            "clients": clients,
            "folder_tree": folder_tree,
            "filters": {
                "client_id": client_id,
                "category": category,
                "subcategory": subcategory,
                "file_type": file_type,
                "language": language,
                "status": library_status,
                "q": q,
            },
        },
    )


@app.post("/admin/biblioteca/upload")
async def upload_library_asset(
    title: str = Form(...),
    description: str | None = Form(None),
    client_id: str | None = Form(None),
    category: str = Form(...),
    subcategory: str | None = Form(None),
    file_type: str = Form(...),
    language: str = Form("es"),
    tags: str | None = Form(None),
    author: str | None = Form(None),
    text_content: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    if not file and not text_content:
        raise HTTPException(status_code=400, detail="Subí un archivo o escribí el contenido de texto")

    storage_key = ""
    mime_type = None
    file_extension = None
    file_size_bytes = None

    if file and file.filename:
        content = await file.read()
        if len(content) > LIBRARY_MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"El archivo supera el límite de {LIBRARY_MAX_UPLOAD_MB}MB")
        mime_type = file.content_type or library_storage.guess_content_type(file.filename)
        file_extension = file.filename.rsplit(".", 1)[-1] if "." in file.filename else None
        file_size_bytes = len(content)
        storage_key = library_storage.build_storage_key(client_id, category, subcategory, file.filename)
        try:
            library_storage.upload_asset(content, storage_key, content_type=mime_type)
        except library_storage.LibraryStorageNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=f"Storage no configurado: {exc}") from exc
        except library_storage.LibraryStorageError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    library.create_asset(
        db,
        client_id=client_id or None,
        category=category,
        subcategory=subcategory,
        title=title,
        description=description,
        file_type=file_type,
        mime_type=mime_type,
        file_extension=file_extension,
        file_size_bytes=file_size_bytes,
        storage_key=storage_key,
        text_content=text_content,
        language=language,
        tags=tag_list,
        author=author,
    )
    return RedirectResponse(url="/admin/biblioteca?uploaded=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/biblioteca/{asset_id}/edit")
def edit_library_asset(
    asset_id: str,
    title: str = Form(...),
    description: str | None = Form(None),
    category: str = Form(...),
    subcategory: str | None = Form(None),
    language: str = Form("es"),
    tags: str | None = Form(None),
    author: str | None = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    asset = library.update_asset_metadata(
        db,
        asset_id,
        title=title,
        description=description,
        category=category,
        subcategory=subcategory or None,
        language=language,
        tags=tag_list,
        author=author,
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return RedirectResponse(url="/admin/biblioteca?edited=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/biblioteca/{asset_id}/status")
def set_library_asset_status(
    asset_id: str,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    try:
        asset = library.transition_asset_status(db, asset_id, new_status)
    except library.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if asset is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return RedirectResponse(url="/admin/biblioteca?status_saved=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/biblioteca/{asset_id}/delete")
def delete_library_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    library.delete_asset(db, asset_id)
    return RedirectResponse(url="/admin/biblioteca?deleted=1", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/biblioteca/{asset_id}/file")
def get_library_asset_file(
    asset_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    asset = library.get_asset(db, asset_id)
    if asset is None or not asset.storage_key:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    try:
        url = library_storage.get_asset_url(asset.storage_key)
    except library_storage.LibraryStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


# Sufijos reales observados en los titulos que produce el pipeline de
# marketing (ver marketing_pipeline.py) y los scripts de campana -- se
# usan solo para emparejar imagen<->texto de la misma pieza por titulo,
# nunca para decidir nada mas.
_BIBLIOTECA_TITLE_SUFFIXES = [
    " - foto limpia sin logo", " - imagen", " - foto", " - caption",
    " - copy", " - texto", " - video", " - story", " - post",
]


def _biblioteca_pair_base_title(title: str) -> str:
    lowered = title.strip().lower()
    for suffix in _BIBLIOTECA_TITLE_SUFFIXES:
        if lowered.endswith(suffix):
            return lowered[: -len(suffix)].strip()
    return lowered


@app.get("/admin/biblioteca/{asset_id}/preview")
def preview_library_asset(
    request: Request,
    asset_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Vista previa tipo 'como quedaria publicado': empareja este recurso
    con su contraparte imagen/texto (mismo cliente, mismo titulo base sin
    sufijo) para mostrar los dos juntos, en vez de tener que abrir cada
    fila de la Biblioteca por separado."""
    asset = library.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    base_title = _biblioteca_pair_base_title(asset.title)
    candidates = library.search_assets(db, client_id=str(asset.client_id) if asset.client_id else None, limit=200)
    pair = None
    for other in candidates:
        if other.id == asset.id:
            continue
        if _biblioteca_pair_base_title(other.title) != base_title:
            continue
        if asset.file_type in ("imagen", "video") and other.text_content:
            pair = other
            break
        if asset.text_content and other.file_type in ("imagen", "video"):
            pair = other
            break

    image_asset = asset if asset.file_type in ("imagen", "video") else pair
    text_asset = asset if asset.text_content else pair

    image_url = None
    if image_asset is not None and image_asset.storage_key:
        try:
            image_url = library_storage.get_asset_url(image_asset.storage_key)
        except library_storage.LibraryStorageError:
            image_url = None

    return templates.TemplateResponse(
        request,
        "admin_biblioteca_preview.html",
        {
            "asset": asset,
            "image_asset": image_asset,
            "text_asset": text_asset,
            "image_url": image_url,
            "is_video": image_asset.file_type == "video" if image_asset else False,
        },
    )


@app.post("/admin/biblioteca/clients/{client_id}/extra-categories")
def set_library_client_extra_categories(
    client_id: str,
    extra_categories: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    categories = [line.strip() for line in extra_categories.splitlines() if line.strip()]
    cfg = dict(client.config or {})
    cfg["library_extra_categories"] = categories
    client.config = cfg
    db.commit()
    return RedirectResponse(url=f"/admin/biblioteca?client_id={client_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/publicaciones")
def list_publications_page(
    request: Request,
    client_id: str | None = None,
    platform: str | None = None,
    pub_status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    stmt = select(SocialPublication).order_by(SocialPublication.created_at.desc())
    if client_id:
        stmt = stmt.where(SocialPublication.client_id == client_id)
    if platform:
        stmt = stmt.where(SocialPublication.platform == platform)
    if pub_status:
        stmt = stmt.where(SocialPublication.status == pub_status)
    publications = db.scalars(stmt).all()

    clients = db.scalars(select(Client).order_by(Client.name)).all()
    approved_assets = library.search_assets(db, client_id=client_id, status="aprobado", limit=200)
    return templates.TemplateResponse(
        request,
        "admin_publicaciones.html",
        {
            "publications": publications,
            "clients": clients,
            "approved_assets": approved_assets,
            "platforms": list(CONNECTORS),
            "filters": {"client_id": client_id, "platform": platform, "status": pub_status},
        },
    )


@app.post("/admin/publicaciones/prepare")
def prepare_publication_route(
    client_id: str = Form(...),
    library_asset_id: str = Form(...),
    platform: str = Form(...),
    caption: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    try:
        social_publishing.prepare_publication(
            db, client_id=client_id, library_asset_id=library_asset_id, platform=platform, caption=caption,
        )
    except (ValueError, PublishValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/admin/publicaciones?prepared=1", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/publicaciones/{publication_id}/preview")
def preview_publication_route(
    publication_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    preview = social_publishing.get_preview(db, publication_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return {
        "platform": preview.platform,
        "caption": preview.caption,
        "media_url": preview.media_url,
        "file_type": preview.file_type,
        "warnings": preview.warnings,
    }


@app.post("/admin/publicaciones/{publication_id}/legal-review")
def request_legal_review_route(
    publication_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    try:
        publication = social_publishing.request_legal_review(db, publication_id)
    except social_publishing.InvalidPublicationTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if publication is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return RedirectResponse(url="/admin/publicaciones?legal_reviewed=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/publicaciones/{publication_id}/approve")
def approve_publication_route(
    publication_id: str,
    approved_by: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    try:
        publication = social_publishing.approve_publication(db, publication_id, approved_by)
    except social_publishing.InvalidPublicationTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if publication is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return RedirectResponse(url="/admin/publicaciones?approved=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/publicaciones/{publication_id}/reject")
def reject_publication_route(
    publication_id: str,
    reason: str | None = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    try:
        publication = social_publishing.reject_publication(db, publication_id, reason)
    except social_publishing.InvalidPublicationTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if publication is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return RedirectResponse(url="/admin/publicaciones?rejected=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/publicaciones/{publication_id}/publish")
def publish_publication_route(
    publication_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    try:
        publication = social_publishing.execute_publish(db, publication_id)
    except social_publishing.PublishExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if publication is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return RedirectResponse(url="/admin/publicaciones?published=1", status_code=status.HTTP_303_SEE_OTHER)


# --- Webhook de comentarios de Instagram: camino para cuando tengamos una
# App de Meta propia con webhook entrante real (ver
# src/instagram_comment_automation.py — hoy la automatizacion real corre por
# POLLING desde scheduler.py, porque Composio no tiene ningun trigger de
# Instagram; este endpoint queda listo para el dia que eso cambie, sin tocar
# la logica de matching/respuesta).


@app.get("/webhooks/instagram")
def instagram_webhook_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge") or ""
    if (
        mode == "subscribe"
        and token
        and settings.instagram_webhook_verify_token
        and compare_digest(token, settings.instagram_webhook_verify_token)
    ):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verificación de webhook fallida")


@app.post("/webhooks/instagram")
async def instagram_webhook_receive(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    if settings.meta_app_secret:
        signature = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.meta_app_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if not compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="Firma X-Hub-Signature-256 inválida")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload no es JSON válido")
    background_tasks.add_task(instagram_comment_automation.process_webhook_payload, payload)
    return {"status": "ok"}


@app.post("/admin/publicaciones/test-publish")
def test_publish_route(
    client_id: str = Form(...),
    library_asset_id: str = Form(...),
    platform: str = Form(...),
    caption: str = Form(...),
    approved_by: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """'Publicar en modo prueba' — bypassea revisión legal a propósito
    (validación técnica del pipeline, no contenido de campaña real)."""
    try:
        publication = social_publishing.prepare_test_publication(
            db, client_id=client_id, library_asset_id=library_asset_id,
            platform=platform, caption=caption, approved_by=approved_by,
        )
        social_publishing.execute_publish(db, publication.id)
    except (ValueError, PublishValidationError, social_publishing.PublishExecutionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/admin/publicaciones?test_published=1", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/clients/{client_id}/social-connect")
def connect_client_social_platform(
    client_id: str,
    platform: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    connector = CONNECTORS.get(platform)
    if connector is None:
        raise HTTPException(status_code=400, detail=f"Plataforma no soportada: '{platform}'.")
    try:
        url = connector.get_auth_url(str(client.id))
    except SocialProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@app.get("/architect-chat")
def architect_chat_page(request: Request):
    return templates.TemplateResponse(request, "architect_chat.html")


@app.get("/plataforma")
def plataforma_page(request: Request):
    # 2026-07-18 -- plataforma.html trae su PROPIO formulario de login
    # embebido (visualmente distinto al de /login) que se muestra/oculta
    # via JS despues de un fetch a /api/auth/me. Sin este chequeo del lado
    # del servidor, cualquiera que entre a /plataforma sin sesion ve ese
    # formulario -- si ya paso por /login, es un segundo login redundante
    # y visualmente distinto, confirmado real por el usuario. Redirigir
    # antes de servir el HTML garantiza un unico login, siempre.
    if not (request.session.get("is_admin") or request.session.get("client_id")):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return _serve_static_html("plataforma.html")


@app.get("/dashboard")
def dashboard_page():
    """Old, unwired duplicate of /plataforma — redirect there instead of maintaining two demo shells."""
    return RedirectResponse(url="/plataforma", status_code=status.HTTP_302_FOUND)


@app.get("/api/architect/status")
def architect_status():
    architect = get_obatala()
    return {
        "status": "active",
        "model": "claude-sonnet-4-6",
        "api_key_configured": bool(settings.anthropic_api_key),
    }


@app.post("/api/architect/create-agent", response_model=ArchitectCreateAgentResponse)
def architect_create_agent(payload: ArchitectCreateAgentRequest, db: Session = Depends(get_db)):
    architect = get_obatala()
    architect.reset_conversation()
    try:
        return architect.create_agent(payload.requirement, payload.user_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/agents", response_model=list[AgentOut])
def list_agents_api(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agents = db.scalars(select(Agent).order_by(Agent.name)).all()
    return [_agent_out(a) for a in agents]


@app.get("/api/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_out(agent)


@app.post("/api/agents", response_model=AgentOut)
def create_agent_api(
    name: str = Form(...),
    role: str = Form(""),
    description: str = Form(""),
    group: str = Form("General"),
    system_prompt: str = Form(""),
    default_tier: str = Form("economy"),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    definition = {
        "group": group,
        "instructions": {"system_prompt": system_prompt},
        "llm_routing": {"default_tier": default_tier},
    }
    agent = Agent(
        name=name,
        role=role or name,
        description=description,
        definition=definition,
        status="active",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _agent_out(agent)


@app.post("/api/agents/{agent_id}/update")
def update_agent_api(
    agent_id: str,
    name: str = Form(None),
    description: str = Form(None),
    system_prompt: str = Form(None),
    default_tier: str = Form(None),
    group: str = Form(None),
    agent_status: str = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    definition = dict(agent.definition or {})
    if name is not None:
        agent.name = name
    if description is not None:
        agent.description = description
    if agent_status is not None:
        agent.status = agent_status
    if group is not None:
        definition["group"] = group
    if system_prompt is not None:
        instructions = dict(definition.get("instructions") or {})
        instructions["system_prompt"] = system_prompt
        definition["instructions"] = instructions
    if default_tier is not None:
        routing = dict(definition.get("llm_routing") or {})
        routing["default_tier"] = default_tier
        definition["llm_routing"] = routing
    agent.definition = definition
    db.commit()
    return {"success": True}


@app.post("/api/agents/{agent_id}/group")
def update_agent_group(
    agent_id: str,
    group: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    definition = dict(agent.definition or {})
    definition["group"] = group
    agent.definition = definition
    db.commit()
    return {"success": True}


@app.get("/api/clients", response_model=list[ClientOut])
def list_clients_api(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    clients = db.scalars(select(Client).order_by(Client.name)).all()
    return [_client_out(c, db) for c in clients]


def _executions_query(db: Session, client_id=None, limit: int = 50) -> list[ExecutionOut]:
    query = select(UsageLog).order_by(UsageLog.created_at.desc()).limit(limit)
    if client_id is not None:
        query = query.where(UsageLog.client_id == client_id)
    logs = db.scalars(query).all()

    agent_names = {a.id: a.name for a in db.scalars(select(Agent)).all()}
    client_names = {c.id: c.name for c in db.scalars(select(Client)).all()}
    return [_execution_out(log, agent_names, client_names) for log in logs]


@app.get("/api/executions", response_model=list[ExecutionOut])
def list_executions_api(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    return _executions_query(db)


@app.get("/api/me/executions", response_model=list[ExecutionOut])
def list_my_executions_api(request: Request, db: Session = Depends(get_db)):
    client = get_current_client(request, db)
    return _executions_query(db, client_id=client.id)


def _library_asset_out(asset, agent_names: dict) -> LibraryAssetOut:
    url = library_storage.get_asset_url(asset.storage_key) if asset.storage_key else None
    return LibraryAssetOut(
        id=str(asset.id),
        category=asset.category,
        subcategory=asset.subcategory,
        title=asset.title,
        description=asset.description,
        file_type=asset.file_type,
        mime_type=asset.mime_type,
        text_content=asset.text_content,
        url=url,
        status=asset.status,
        agent_name=agent_names.get(asset.created_by_agent_id) if asset.created_by_agent_id else None,
        created_at=asset.created_at.isoformat(),
    )


@app.get("/api/me/biblioteca", response_model=list[LibraryAssetOut])
def list_my_biblioteca_api(request: Request, db: Session = Depends(get_db)):
    """Piezas reales (imagenes, video, textos) que el equipo del cliente
    aprobo para la campana -- lo que faltaba para que un cliente pueda ver
    lo que sus agentes produjeron antes de publicarlo (confirmado real:
    el cliente no tenia ninguna forma de ver esto en /plataforma)."""
    client = get_current_client(request, db)
    # search_assets() por defecto filtra status="aprobado" -- sin status=None
    # el cliente nunca ve lo que esta en borrador (justo lo que mas necesita
    # revisar antes de aprobarlo, ej. el Reel del Dia 3), confirmado real
    # via un test de browser que devolvia 0 videos y "0 en borrador".
    assets = library.search_assets(db, client_id=str(client.id), status=None, limit=200)
    agent_names = {a.id: a.name for a in db.scalars(select(Agent)).all()}
    return [_library_asset_out(a, agent_names) for a in assets]


@app.get("/admin/agents")
def list_agents_page(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agents = db.scalars(select(Agent).order_by(Agent.created_at.desc())).all()
    groups: dict[str, list[Agent]] = {}
    for agent in agents:
        definition = agent.definition or {}
        group_name = definition.get("group") if agent.agent_code else None
        groups.setdefault(group_name or agent.user_id or "Sin grupo", []).append(agent)
    return templates.TemplateResponse(request, "admin_agents.html", {"groups": groups, "agents": agents})


@app.post("/admin/agents/import")
def import_master_agents(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    result = sync_master_agents(db)
    return RedirectResponse(
        url=f"/admin/agents?imported={result.created}&updated={result.updated}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _delete_agent_cascade(db: Session, agent: Agent) -> None:
    """Remove all FK-dependent rows before deleting an agent."""
    db.execute(sa_delete(UsageLog).where(UsageLog.agent_id == agent.id))
    db.execute(sa_update(ResponseCache).where(ResponseCache.agent_id == agent.id).values(agent_id=None))
    db.execute(sa_update(KbArticle).where(KbArticle.agent_id == agent.id).values(agent_id=None))
    for case in db.scalars(select(PatientCase).where(PatientCase.agent_id == agent.id)).all():
        db.execute(sa_delete(CaseMessage).where(CaseMessage.case_id == case.id))
    db.execute(sa_delete(PatientCase).where(PatientCase.agent_id == agent.id))
    db.execute(sa_delete(ClientAgent).where(ClientAgent.agent_id == agent.id))
    db.delete(agent)


@app.post("/admin/agents/{agent_id}/delete")
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    _delete_agent_cascade(db, agent)
    db.commit()
    return RedirectResponse(url="/admin/agents?deleted=1&kept=0", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/agents/cleanup")
def cleanup_non_master_agents(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Delete all agents whose agent_code is NOT in the master JSON config."""
    config = load_master_config()
    valid_codes = {cfg["id"] for cfg in config["agents"]}
    all_agents = db.scalars(select(Agent)).all()
    deleted = 0
    kept = 0
    for agent in all_agents:
        if agent.agent_code in valid_codes:
            kept += 1
        else:
            _delete_agent_cascade(db, agent)
            deleted += 1
    db.commit()
    return RedirectResponse(
        url=f"/admin/agents?deleted={deleted}&kept={kept}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/admin/agents/reset-all")
def reset_all_agents(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Delete EVERY agent unconditionally, then reimport the 37 masters fresh."""
    all_agents = db.scalars(select(Agent)).all()
    for agent in all_agents:
        _delete_agent_cascade(db, agent)
    db.flush()
    result = sync_master_agents(db)
    db.commit()
    return RedirectResponse(
        url=f"/admin/agents?imported={result.created}&updated={result.updated}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/admin/agents/set-budget-all")
def set_budget_all_agents(
    daily_budget_usd: float = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    all_agents = db.scalars(select(Agent)).all()
    budget = daily_budget_usd if daily_budget_usd > 0 else None
    for agent in all_agents:
        agent.daily_budget_usd = budget
        if agent.status == "paused" and budget:
            agent.status = "active"
    db.commit()
    return RedirectResponse(
        url=f"/admin/agents?budget_updated={len(all_agents)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/admin/usage")
def usage_page(
    request: Request,
    period: str = "day",
    client_id: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    rows, total = usage_by_agent(db, period=period)
    clients_rows, clients_total = profitability_by_client(db, period="month")
    department_rows, department_total = ([], 0.0)
    if client_id:
        department_rows, department_total = usage_by_department(db, client_id, period=period)
    all_clients = db.scalars(select(Client).order_by(Client.name)).all()
    return templates.TemplateResponse(
        request,
        "admin_usage.html",
        {
            "rows": rows,
            "total": total,
            "period": period,
            "clients_rows": clients_rows,
            "clients_total": clients_total,
            "all_clients": all_clients,
            "selected_client_id": client_id,
            "department_rows": department_rows,
            "department_total": department_total,
        },
    )


@app.get("/api/usage", response_model=UsageOut)
def api_usage(
    period: str = "day",
    client: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    rows, total = usage_by_agent(db, period=period, client_id=client)
    return UsageOut(period=period, by_agent=[UsageByAgentOut(**row) for row in rows], total_usd=total)


@app.get("/api/me/usage", response_model=UsageOut)
def api_my_usage(
    request: Request,
    period: str = "day",
    db: Session = Depends(get_db),
):
    client = get_current_client(request, db)
    rows, total = usage_by_agent(db, period=period, client_id=client.id)
    return UsageOut(period=period, by_agent=[UsageByAgentOut(**row) for row in rows], total_usd=total)


@app.get("/api/profitability", response_model=ProfitabilityOut)
def api_profitability(
    period: str = "month",
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    rows, total = profitability_by_client(db, period=period)
    return ProfitabilityOut(period=period, by_client=[ProfitabilityByClientOut(**row) for row in rows], total_usd=total)


@app.get("/admin/agents/{agent_id}")
def agent_detail_page(
    agent_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    definition_json = json.dumps(agent.definition or {}, indent=2, ensure_ascii=False)
    usage = agent_usage_summary(db, agent.id, period="month")
    kb_articles = db.scalars(
        select(KbArticle).where(KbArticle.agent_id == agent.id).order_by(KbArticle.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "admin_agent_detail.html",
        {
            "agent": agent,
            "definition_json": definition_json,
            "usage": usage,
            "kb_articles": kb_articles,
            "case_memory": bool((agent.definition or {}).get("case_memory")),
        },
    )


@app.post("/admin/agents/{agent_id}")
def update_agent_definition(
    agent_id: str,
    definition_json: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        definition = json.loads(definition_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {exc}") from exc

    agent.definition = definition
    if definition.get("agent_name"):
        agent.name = definition["agent_name"]
    db.commit()
    return RedirectResponse(url=f"/admin/agents/{agent_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/agents/{agent_id}/set-budget")
def set_agent_budget(
    agent_id: str,
    daily_budget_usd: float = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.daily_budget_usd = daily_budget_usd if daily_budget_usd > 0 else None
    if agent.status == "paused" and daily_budget_usd > 0:
        agent.status = "active"
    db.commit()
    return RedirectResponse(url=f"/admin/agents/{agent_id}?budget_saved=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/agents/{agent_id}/knowledge/upload")
async def upload_agent_knowledge(
    agent_id: str,
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    content = await file.read()
    try:
        chunks = ingest_document(db, agent_id=agent.id, title=title, filename=file.filename or "", content=content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/admin/agents/{agent_id}?uploaded={chunks}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/agents/{agent_id}/knowledge/{article_id}/delete")
def delete_agent_knowledge_article(
    agent_id: str,
    article_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    article = db.get(KbArticle, article_id)
    if article is not None and str(article.agent_id) == agent_id:
        db.delete(article)
        db.commit()
    return RedirectResponse(url=f"/admin/agents/{agent_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/agents/{agent_id}/connect")
def connect_agent_toolkit(
    agent_id: str,
    toolkit: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        url = start_connection(user_id=agent_id, toolkit_slug=toolkit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo iniciar la conexión con Composio: {exc}") from exc
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@app.post("/api/agents/{agent_id}/run", response_model=CrewRunResponse)
def run_agent_with_crew(
    agent_id: str,
    payload: CrewRunRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        outcome = run_agent_service(
            db, agent, payload.input,
            gemini_key=payload.gemini_key,
            history=payload.history,
        )
    except AgentPausedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error ejecutando el agente: {exc}") from exc
    return CrewRunResponse(
        result=outcome.result, cost_usd=outcome.cost_usd, tier_used=outcome.tier_used, cached=outcome.cached
    )


def _tool_names(definition: dict) -> list[str]:
    return [t.get("name", "") for t in (definition.get("tools") or []) if t.get("name")]


def _assigned_agent_out(agent: Agent) -> AssignedAgentOut:
    definition = agent.definition or {}
    return AssignedAgentOut(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        agent_code=agent.agent_code,
        orixa=definition.get("orixa"),
        group=definition.get("group"),
        status=agent.status,
        daily_budget_usd=agent.daily_budget_usd,
        tools=_tool_names(definition),
        case_memory=bool(definition.get("case_memory")),
    )


def _agent_out(agent: Agent) -> AgentOut:
    definition = agent.definition or {}
    instructions = definition.get("instructions") or {}
    routing = definition.get("llm_routing") or {}
    return AgentOut(
        id=str(agent.id),
        agent_code=agent.agent_code,
        name=agent.name,
        role=agent.role,
        description=agent.description,
        status=agent.status,
        daily_budget_usd=agent.daily_budget_usd,
        orixa=definition.get("orixa"),
        group=definition.get("group"),
        tools=_tool_names(definition),
        system_prompt=instructions.get("system_prompt"),
        default_tier=routing.get("default_tier"),
        case_memory=bool(definition.get("case_memory")),
        created_at=agent.created_at.isoformat(),
    )


def _execution_out(log: UsageLog, agent_names: dict, client_names: dict) -> ExecutionOut:
    return ExecutionOut(
        id=str(log.id),
        agent_id=str(log.agent_id),
        agent_name=agent_names.get(log.agent_id, "?"),
        client_id=str(log.client_id) if log.client_id else None,
        client_name=client_names.get(log.client_id) if log.client_id else None,
        status="done" if log.success else "err",
        tier=log.tier,
        cost_usd=float(log.cost_usd),
        cached=log.cached,
        input_text=log.input_text,
        result_text=log.result_text,
        error_message=log.error_message,
        created_at=log.created_at.isoformat(),
    )


def _client_out(client: Client, db: Session) -> ClientOut:
    rows = db.scalars(
        select(Agent).join(ClientAgent, ClientAgent.agent_id == Agent.id).where(ClientAgent.client_id == client.id)
    ).all()
    return ClientOut(
        id=str(client.id),
        name=client.name,
        email=client.email,
        config=client.config,
        agents=[_assigned_agent_out(a) for a in rows],
    )


@app.post("/api/clients/{client_id}/config")
def update_client_config(
    client_id: str,
    industry: str = Form(None),
    services: str = Form(None),
    tone: str = Form(None),
    whatsapp: str = Form(None),
    instagram: str = Form(None),
    website: str = Form(None),
    notes: str = Form(None),
    features: str = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    cfg = dict(client.config or {})
    if industry is not None:
        cfg["industry"] = industry
    if services is not None:
        cfg["services"] = services
    if tone is not None:
        cfg["tone"] = tone
    if whatsapp is not None:
        cfg["whatsapp"] = whatsapp
    if instagram is not None:
        cfg["instagram"] = instagram
    if website is not None:
        cfg["website"] = website
    if notes is not None:
        cfg["notes"] = notes
    if features is not None:
        try:
            cfg["features"] = json.loads(features)
        except Exception:
            pass
    client.config = cfg
    db.commit()
    return {"success": True, "config": cfg}


@app.post("/api/auth/login", response_model=ClientOut)
def login(payload: ClientLogin, request: Request, db: Session = Depends(get_db)):
    client = db.scalar(select(Client).where(Client.email == payload.email))
    if client is None or not verify_password(payload.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    request.session["client_id"] = str(client.id)
    return _client_out(client, db)


@app.post("/api/auth/admin-login")
def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    valid_user = compare_digest(username, settings.admin_user)
    valid_password = compare_digest(password, settings.admin_password)
    if not (valid_user and valid_password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    request.session["is_admin"] = True
    return {"success": True}


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"success": True}


@app.get("/api/auth/me")
def auth_me(request: Request, db: Session = Depends(get_db)):
    if request.session.get("is_admin"):
        return {"role": "admin", "username": settings.admin_user}
    client_id = request.session.get("client_id")
    if client_id:
        client = db.get(Client, client_id)
        if client:
            return {"role": "client", **_client_out(client, db).model_dump()}
    raise HTTPException(status_code=401, detail="No autenticado")


@app.get("/api/me", response_model=ClientOut)
def me(request: Request, db: Session = Depends(get_db)):
    client = get_current_client(request, db)
    return _client_out(client, db)


@app.get("/login")
def login_page(request: Request):
    default_tab = "admin" if request.query_params.get("as") == "admin" else "client"
    return templates.TemplateResponse(
        request, "login.html", {"default_tab": default_tab}, headers={"Cache-Control": "no-store"}
    )


@app.get("/portal")
def portal_page(request: Request):
    return templates.TemplateResponse(request, "portal.html")


@app.get("/admin/clients")
def list_clients_page(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    clients = db.scalars(select(Client).order_by(Client.created_at.desc())).all()
    agents = db.scalars(select(Agent).order_by(Agent.name)).all()
    clients_with_agents = [(c, _client_out(c, db).agents) for c in clients]
    return templates.TemplateResponse(
        request,
        "admin_clients.html",
        {"clients_with_agents": clients_with_agents, "agents": agents},
    )


@app.post("/api/clients", response_model=ClientOut)
def create_client_api(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    industry: str = Form(None),
    services: str = Form(None),
    tone: str = Form(None),
    whatsapp: str = Form(None),
    instagram: str = Form(None),
    website: str = Form(None),
    notes: str = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    if db.scalar(select(Client).where(Client.email == email)):
        raise HTTPException(status_code=409, detail="Ya existe un cliente con ese email")
    cfg: dict = {}
    if industry:
        cfg["industry"] = industry
    if services:
        cfg["services"] = services
    if tone:
        cfg["tone"] = tone
    if whatsapp:
        cfg["whatsapp"] = whatsapp
    if instagram:
        cfg["instagram"] = instagram
    if website:
        cfg["website"] = website
    if notes:
        cfg["notes"] = notes
    client = Client(name=name, email=email, password_hash=hash_password(password), config=cfg or None)
    db.add(client)
    db.commit()
    db.refresh(client)
    return _client_out(client, db)


@app.post("/admin/clients")
def create_client(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    agent_ids: list[str] = Form([]),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = Client(name=name, email=email, password_hash=hash_password(password))
    db.add(client)
    db.commit()
    db.refresh(client)

    for agent_id in agent_ids:
        db.add(ClientAgent(client_id=client.id, agent_id=agent_id))
    db.commit()

    return RedirectResponse(url="/admin/clients", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/clients/{client_id}")
def client_detail_page(
    client_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    agents = db.scalars(select(Agent).order_by(Agent.name)).all()
    assigned_ids = {str(a.id) for a in _client_out(client, db).agents}
    schedule_links = {
        str(link.agent_id): link
        for link in db.scalars(select(ClientAgent).where(ClientAgent.client_id == client.id)).all()
    }
    return templates.TemplateResponse(
        request,
        "admin_client_detail.html",
        {"client": client, "agents": agents, "assigned_ids": assigned_ids, "schedule_links": schedule_links},
    )


@app.post("/admin/clients/{client_id}")
def update_client(
    client_id: str,
    name: str = Form(...),
    password: str | None = Form(None),
    agent_ids: list[str] = Form([]),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    client.name = name
    if password:
        client.password_hash = hash_password(password)
    db.query(ClientAgent).filter(ClientAgent.client_id == client.id).delete()
    for agent_id in agent_ids:
        db.add(ClientAgent(client_id=client.id, agent_id=agent_id))
    db.commit()

    return RedirectResponse(url=f"/admin/clients/{client_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/clients/{client_id}/api-keys")
def set_client_api_keys(
    client_id: str,
    gemini_key: str = Form(""),
    anthropic_key: str = Form(""),
    openai_key: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    config = dict(client.config or {})
    api_keys = dict(config.get("api_keys", {}))
    for field, val in [("gemini", gemini_key), ("anthropic", anthropic_key), ("openai", openai_key)]:
        if val.strip():
            api_keys[field] = val.strip()
    config["api_keys"] = api_keys
    client.config = config
    db.commit()
    return RedirectResponse(url=f"/admin/clients/{client_id}?keys_saved=1", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/clients/{client_id}/generate-strategic-report")
def generate_strategic_report_route(
    client_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Departamento de Inteligencia Estratégica y Contextual (FASE 3.0) —
    dispara la corrida completa (especialistas habilitados + Coordinador
    Cosmos) y guarda el informe en la Biblioteca del cliente."""
    try:
        asset = strategic_intelligence.generate_strategic_report(db, client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(
        url=f"/admin/biblioteca?client_id={client_id}&generated_report={asset.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/admin/clients/{client_id}/generate-editorial-calendar")
def generate_editorial_calendar_route(
    client_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """FASE 3.1 — Calendario Editorial Inteligente: corre el Departamento
    Cosmos sobre 13 semanas (90 días) y guarda el calendario editorial en
    la Biblioteca del cliente, listo para que Marketing lo reutilice."""
    try:
        asset = editorial_calendar.generate_editorial_calendar(db, client_id, auto_provider=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(
        url=f"/admin/biblioteca?client_id={client_id}&generated_report={asset.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/admin/clients/{client_id}/cosmos-calendar-schedule")
def set_cosmos_calendar_schedule(
    client_id: str,
    enabled: str | None = Form(None),
    frequency: str = Form("weekly"),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """FASE 3.2A — prende/apaga la regeneración automática (deslizante) del
    Calendario Editorial para este cliente. Apagado por default — nada
    recurrente ni de costo real se activa solo, el admin lo prende
    explícitamente por cliente."""
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    client.cosmos_calendar_enabled = enabled is not None
    client.cosmos_calendar_frequency = frequency
    if client.cosmos_calendar_enabled:
        if client.cosmos_calendar_next_run_at is None:
            delta = timedelta(days=1) if frequency == "daily" else timedelta(days=7)
            client.cosmos_calendar_next_run_at = datetime.utcnow() + delta
    else:
        client.cosmos_calendar_next_run_at = None
    db.commit()
    return RedirectResponse(url=f"/admin/clients/{client_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/clients/{client_id}/generate-weekly-marketing")
def generate_weekly_marketing_route(
    client_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """ETAPA 4.1 — Integración Cosmos → Marketing: corre Daniel → Clara →
    Ariel → Valentina → Marco → Elena en cadena, cada uno leyendo la
    semana vigente del Calendario Editorial (library_search) y guardando
    su pieza en la Biblioteca como borrador (library_save). Disparo
    manual únicamente — el disparo automático semanal es ETAPA 4.2."""
    try:
        result = marketing_pipeline.generate_weekly_marketing_content(db, client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    saved_count = sum(1 for step in result["steps"] if step["saved_asset_id"])
    return RedirectResponse(
        url=(
            f"/admin/biblioteca?client_id={client_id}"
            f"&marketing_pieces={saved_count}&marketing_warnings={len(result['warnings'])}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/admin/clients/{client_id}/api-keys/delete")
def delete_client_api_key(
    client_id: str,
    provider: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    config = dict(client.config or {})
    api_keys = dict(config.get("api_keys", {}))
    api_keys.pop(provider, None)
    config["api_keys"] = api_keys
    client.config = config
    db.commit()
    return RedirectResponse(url=f"/admin/clients/{client_id}?keys_saved=1", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/api/me/connect", response_model=ConnectToolkitResponse)
def connect_my_toolkit(toolkit: str, request: Request, db: Session = Depends(get_db)):
    client = get_current_client(request, db)
    try:
        url = start_connection(user_id=str(client.id), toolkit_slug=toolkit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo iniciar la conexión con Composio: {exc}") from exc
    return ConnectToolkitResponse(redirect_url=url)


@app.post("/api/me/agents/{agent_id}/run", response_model=CrewRunResponse)
def run_my_agent(
    agent_id: str,
    payload: CrewRunRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client = get_current_client(request, db)
    link = db.scalar(
        select(ClientAgent).where(ClientAgent.client_id == client.id, ClientAgent.agent_id == agent_id)
    )
    if link is None:
        raise HTTPException(status_code=403, detail="Este agente no está asignado a tu cuenta")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    client_api_keys = (client.config or {}).get("api_keys", {})
    try:
        outcome = run_agent_service(
            db, agent, payload.input,
            user_id=str(client.id), client_id=client.id,
            gemini_key=payload.gemini_key or client_api_keys.get("gemini"),
            history=payload.history,
        )
    except AgentPausedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error ejecutando el agente: {exc}") from exc
    return CrewRunResponse(
        result=outcome.result, cost_usd=outcome.cost_usd, tier_used=outcome.tier_used, cached=outcome.cached
    )


def _case_out(case: PatientCase) -> CaseOut:
    return CaseOut(
        id=str(case.id),
        agent_id=str(case.agent_id),
        client_id=str(case.client_id) if case.client_id else None,
        patient_label=case.patient_label,
        status=case.status,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat(),
    )


def _require_case_access(case: PatientCase, request: Request, db: Session) -> None:
    """Admin can access any case; a client can only access their own."""
    if request.session.get("is_admin"):
        return
    client = get_current_client(request, db)
    if case.client_id != client.id:
        raise HTTPException(status_code=403, detail="No tenés acceso a este caso")


@app.get("/api/agents/{agent_id}/cases", response_model=list[CaseOut])
def list_agent_cases(
    agent_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    return [_case_out(c) for c in list_cases(db, agent_id=agent_id)]


@app.post("/api/agents/{agent_id}/cases", response_model=CaseOut)
def create_agent_case(
    agent_id: str,
    payload: CreateCaseRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    case = create_case(db, agent_id=agent_id, client_id=None, patient_label=payload.patient_label)
    return _case_out(case)


@app.get("/api/me/agents/{agent_id}/cases", response_model=list[CaseOut])
def list_my_agent_cases(agent_id: str, request: Request, db: Session = Depends(get_db)):
    client = get_current_client(request, db)
    link = db.scalar(select(ClientAgent).where(ClientAgent.client_id == client.id, ClientAgent.agent_id == agent_id))
    if link is None:
        raise HTTPException(status_code=403, detail="Este agente no está asignado a tu cuenta")
    return [_case_out(c) for c in list_cases(db, agent_id=agent_id, client_id=client.id)]


@app.post("/api/me/agents/{agent_id}/cases", response_model=CaseOut)
def create_my_agent_case(agent_id: str, payload: CreateCaseRequest, request: Request, db: Session = Depends(get_db)):
    client = get_current_client(request, db)
    link = db.scalar(select(ClientAgent).where(ClientAgent.client_id == client.id, ClientAgent.agent_id == agent_id))
    if link is None:
        raise HTTPException(status_code=403, detail="Este agente no está asignado a tu cuenta")
    case = create_case(db, agent_id=agent_id, client_id=client.id, patient_label=payload.patient_label)
    return _case_out(case)


@app.get("/api/cases/{case_id}/messages", response_model=list[CaseMessageOut])
def get_case_messages(case_id: str, request: Request, db: Session = Depends(get_db)):
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    _require_case_access(case, request, db)
    history = db.scalars(
        select(CaseMessage).where(CaseMessage.case_id == case_id).order_by(CaseMessage.created_at)
    ).all()
    return [
        CaseMessageOut(
            role=m.role,
            content=m.content,
            cost_usd=float(m.cost_usd) if m.cost_usd is not None else None,
            created_at=m.created_at.isoformat(),
        )
        for m in history
    ]


@app.post("/api/cases/{case_id}/message", response_model=CrewRunResponse)
def send_case_message(case_id: str, payload: CaseRunRequest, request: Request, db: Session = Depends(get_db)):
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    _require_case_access(case, request, db)
    agent = db.get(Agent, case.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    user_id = str(case.client_id) if case.client_id else "admin"
    try:
        outcome = run_agent_service(
            db, agent, payload.message, user_id=user_id, client_id=case.client_id, case_id=case.id
        )
    except AgentPausedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error ejecutando el agente: {exc}") from exc
    return CrewRunResponse(
        result=outcome.result, cost_usd=outcome.cost_usd, tier_used=outcome.tier_used, cached=outcome.cached
    )


@app.get("/admin/clients/{client_id}/agents/{agent_id}/schedule")
def schedule_form_page(
    client_id: str,
    agent_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    link = db.scalar(
        select(ClientAgent).where(ClientAgent.client_id == client_id, ClientAgent.agent_id == agent_id)
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Este agente no está asignado a este cliente")
    client = db.get(Client, client_id)
    agent = db.get(Agent, agent_id)
    return templates.TemplateResponse(
        request, "admin_schedule.html", {"client": client, "agent": agent, "link": link}
    )


@app.post("/admin/clients/{client_id}/agents/{agent_id}/schedule")
def schedule_save(
    client_id: str,
    agent_id: str,
    frequency: str = Form(...),
    instruction: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    link = db.scalar(
        select(ClientAgent).where(ClientAgent.client_id == client_id, ClientAgent.agent_id == agent_id)
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Este agente no está asignado a este cliente")

    if frequency == "none":
        link.schedule_frequency = None
        link.next_run_at = None
    else:
        link.schedule_frequency = frequency
        link.schedule_input = instruction or None
        if link.next_run_at is None:
            link.next_run_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/admin/clients/{client_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/agentes/{agent_id}")
def agent_public_chat_page(agent_id: str, request: Request, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return templates.TemplateResponse(request, "agent_public_chat.html", {"agent": agent})


@app.websocket("/api/agents/{agent_id}/chat")
async def agent_chat_socket(agent_id: str, websocket: WebSocket, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    runtime = AgentRuntime(agent)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message")
            if not message:
                continue
            try:
                reply = runtime.reply(message)
                await websocket.send_json({"type": "message", "content": reply})
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": f"Error: {exc}"})
    except WebSocketDisconnect:
        pass


@app.websocket("/api/architect/chat")
async def architect_chat_socket(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    architect = get_obatala()
    architect.reset_conversation()
    try:
        while True:
            data = await websocket.receive_json()
            requirement = data.get("requirement")
            if not requirement:
                continue

            try:
                await websocket.send_json({"type": "status", "message": "Pensando..."})
                result = architect.respond(requirement)

                if result["kind"] == "message":
                    await websocket.send_json({"type": "message", "content": result["text"]})
                    continue

                agent = architect.persist_agent(result["definition"], requirement, "demo_user", db)
                await websocket.send_json({"type": "design", "content": result["text"]})
                await websocket.send_json(
                    {"type": "complete", "message": f"Agente «{agent.name}» creado y guardado."}
                )
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": f"Error: {exc}"})
    except WebSocketDisconnect:
        pass
