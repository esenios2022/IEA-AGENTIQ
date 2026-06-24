import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    nombre: str
    email: EmailStr
    empresa: str | None = None


class LeadOut(LeadCreate):
    id: int

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    id: str
    name: str
    orixa: str | None = None
    role: str | None = None
    goal: str | None = None
    group_name: str | None = None
    status: str = "active"
    modelo: str = "ollama/mistral"
    prompt: str | None = None
    tools: list[str] = []


class AgentUpdate(BaseModel):
    name: str | None = None
    orixa: str | None = None
    role: str | None = None
    goal: str | None = None
    group_name: str | None = None
    status: str | None = None
    modelo: str | None = None
    prompt: str | None = None
    tools: list[str] | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    orixa: str | None = None
    role: str | None = None
    goal: str | None = None
    group_name: str | None = None
    status: str
    modelo: str
    prompt: str | None = None
    tools: list[str] = []

    model_config = {"from_attributes": True}


class ClientCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    plan: str = "Inicial"
    pais: str | None = None
    lang: str = "es"
    agents: list[str] = []
    features: dict = {}


class ClientOut(ClientCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionCreate(BaseModel):
    agent_id: str | None = None
    client_id: uuid.UUID | None = None
    task: str | None = None


class ExecutionOut(BaseModel):
    id: uuid.UUID
    agent_id: str | None = None
    client_id: uuid.UUID | None = None
    task: str | None = None
    status: str
    result: str | None = None
    tokens_used: int
    cost_usd: float
    started_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}
