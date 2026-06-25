from contextlib import asynccontextmanager
from secrets import compare_digest

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.architect_agent import get_gran_arquitecto
from src.config import settings
from src.database import Base, engine, get_db
from src.models import Agent, Lead
from src.schemas import ArchitectCreateAgentRequest, ArchitectCreateAgentResponse, LeadCreate, LeadOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="IEA-AGENTIQ", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    valid_user = compare_digest(credentials.username, settings.admin_user)
    valid_password = compare_digest(credentials.password, settings.admin_password)
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
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


@app.get("/architect-chat")
def architect_chat_page(request: Request):
    return templates.TemplateResponse(request, "architect_chat.html")


@app.get("/plataforma")
def plataforma_page():
    return _serve_static_html("plataforma.html")


@app.get("/dashboard")
def dashboard_page():
    return _serve_static_html("dashboard.html")


@app.get("/api/architect/status")
def architect_status():
    architect = get_gran_arquitecto()
    return {
        "status": "active",
        "model": "claude-sonnet-4-6",
        "api_key_configured": bool(settings.anthropic_api_key),
    }


@app.post("/api/architect/create-agent", response_model=ArchitectCreateAgentResponse)
def architect_create_agent(payload: ArchitectCreateAgentRequest, db: Session = Depends(get_db)):
    architect = get_gran_arquitecto()
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


@app.websocket("/api/architect/chat")
async def architect_chat_socket(websocket: WebSocket):
    await websocket.accept()
    architect = get_gran_arquitecto()
    architect.reset_conversation()
    try:
        while True:
            data = await websocket.receive_json()
            requirement = data.get("requirement")
            if not requirement:
                continue

            await websocket.send_json({"type": "status", "message": "Analizando..."})
            analysis = architect.think(f"Analiza: {requirement}\n\nBreve análisis.")
            await websocket.send_json({"type": "analysis", "content": analysis})

            await websocket.send_json({"type": "status", "message": "Diseñando..."})
            design = architect.think(
                f"JSON del agente.\nRequirement: {requirement}\nSOLO JSON."
            )
            await websocket.send_json({"type": "design", "content": design})

            await websocket.send_json({"type": "complete", "message": "Listo"})
    except WebSocketDisconnect:
        pass
