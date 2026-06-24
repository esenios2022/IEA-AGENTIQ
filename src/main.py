from contextlib import asynccontextmanager
from secrets import compare_digest

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.database import Base, engine, get_db
from src.models import Agent, Client, Execution, Lead
from src.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    ClientCreate,
    ClientOut,
    ExecutionCreate,
    ExecutionOut,
    LeadCreate,
    LeadOut,
)


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


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


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


@app.get("/api/agents", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.scalars(select(Agent)).all()


@app.get("/api/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post("/api/agents", response_model=AgentOut)
def create_agent(
    agent: AgentCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    db_agent = Agent(**agent.model_dump())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


@app.put("/api/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str,
    agent: AgentUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    db_agent = db.get(Agent, agent_id)
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in agent.model_dump(exclude_unset=True).items():
        setattr(db_agent, field, value)
    db.commit()
    db.refresh(db_agent)
    return db_agent


@app.delete("/api/agents/{agent_id}")
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    db_agent = db.get(Agent, agent_id)
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"ok": True}


@app.get("/api/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    return db.scalars(select(Client)).all()


@app.post("/api/clients", response_model=ClientOut)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    db_client = Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@app.get("/api/executions", response_model=list[ExecutionOut])
def list_executions(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    return db.scalars(select(Execution).order_by(Execution.started_at.desc())).all()


@app.post("/api/executions", response_model=ExecutionOut)
def create_execution(execution: ExecutionCreate, db: Session = Depends(get_db)):
    db_execution = Execution(**execution.model_dump())
    db.add(db_execution)
    db.commit()
    db.refresh(db_execution)
    return db_execution
