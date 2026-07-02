import json
from contextlib import asynccontextmanager
from datetime import datetime
from secrets import compare_digest

from fastapi import Depends, FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from src.agent_runtime import AgentRuntime
from src.agent_seed import sync_master_agents
from src.agent_service import AgentPausedError
from src.agent_service import run as run_agent_service
from src.architect_agent import get_obatala
from src.auth import get_current_client, hash_password, verify_password
from src.composio_tools import start_connection
from src.config import settings
from src.database import Base, engine, get_db
from src.embeddings import embed_text
from src.models import Agent, Client, ClientAgent, KbArticle, Lead
from src.scheduler import start_scheduler
from src.schemas import (
    ArchitectCreateAgentRequest,
    ArchitectCreateAgentResponse,
    AssignedAgentOut,
    ClientLogin,
    ClientOut,
    ConnectToolkitResponse,
    CrewRunRequest,
    CrewRunResponse,
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
    """Old static mockup, superseded by the real (Jinja, connected) admin/portal UI."""
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/dashboard")
def dashboard_page():
    """Old static mockup, superseded by the real (Jinja, connected) admin/portal UI."""
    return RedirectResponse(url="/admin/agents", status_code=status.HTTP_302_FOUND)


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


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


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
    return templates.TemplateResponse(
        request, "admin_agent_detail.html", {"agent": agent, "definition_json": definition_json, "usage": usage}
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
        outcome = run_agent_service(db, agent, payload.input)
    except AgentPausedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error ejecutando el agente: {exc}") from exc
    return CrewRunResponse(
        result=outcome.result, cost_usd=outcome.cost_usd, tier_used=outcome.tier_used, cached=outcome.cached
    )


def _client_out(client: Client, db: Session) -> ClientOut:
    rows = db.scalars(
        select(Agent).join(ClientAgent, ClientAgent.agent_id == Agent.id).where(ClientAgent.client_id == client.id)
    ).all()
    return ClientOut(
        id=str(client.id),
        name=client.name,
        email=client.email,
        agents=[AssignedAgentOut(id=str(a.id), name=a.name, description=a.description) for a in rows],
    )


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
    agent_ids: list[str] = Form([]),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    client.name = name
    db.query(ClientAgent).filter(ClientAgent.client_id == client.id).delete()
    for agent_id in agent_ids:
        db.add(ClientAgent(client_id=client.id, agent_id=agent_id))
    db.commit()

    return RedirectResponse(url=f"/admin/clients/{client_id}", status_code=status.HTTP_303_SEE_OTHER)


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
    try:
        outcome = run_agent_service(db, agent, payload.input, user_id=str(client.id), client_id=client.id)
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
