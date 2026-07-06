import json
from contextlib import asynccontextmanager
from datetime import datetime
from secrets import compare_digest

from fastapi import (
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
from fastapi.responses import HTMLResponse, RedirectResponse
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
from src.database import Base, engine, get_db
from src.document_ingest import ingest_document
from src.embeddings import embed_text
from src.models import Agent, CaseMessage, Client, ClientAgent, KbArticle, Lead, PatientCase, ResponseCache, UsageLog
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
    LeadOut,
    ProfitabilityByClientOut,
    ProfitabilityOut,
    UsageByAgentOut,
    UsageOut,
)
from src.usage_reports import agent_usage_summary, profitability_by_client, usage_by_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Safe column migrations — ADD COLUMN IF NOT EXISTS never fails on re-deploy
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS config JSONB")
        )
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


def _serve_static_html(filename: str) -> HTMLResponse:
    with open(f"src/templates/{filename}", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/")
def home():
    return _serve_static_html("index.html")


@app.post("/api/leads", response_model=LeadOut)
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    db_lead = Lead(nombre=lead.nombre, email=lead.email, empresa=lead.empresa)
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead


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


@app.get("/architect-chat")
def architect_chat_page(request: Request):
    return templates.TemplateResponse(request, "architect_chat.html")


@app.get("/plataforma")
def plataforma_page():
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
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    rows, total = usage_by_agent(db, period=period)
    clients_rows, clients_total = profitability_by_client(db, period="month")
    return templates.TemplateResponse(
        request,
        "admin_usage.html",
        {"rows": rows, "total": total, "period": period, "clients_rows": clients_rows, "clients_total": clients_total},
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
    return templates.TemplateResponse(request, "login.html", {"default_tab": default_tab})


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
