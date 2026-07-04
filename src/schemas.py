from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    nombre: str
    email: EmailStr
    empresa: str | None = None


class LeadOut(LeadCreate):
    id: int

    model_config = {"from_attributes": True}


class ArchitectCreateAgentRequest(BaseModel):
    requirement: str
    user_id: str = "demo_user"


class ArchitectCreateAgentResponse(BaseModel):
    success: bool
    agent_id: str
    agent_name: str
    definition: dict


class AgentDefinitionUpdate(BaseModel):
    definition: dict


class CrewRunRequest(BaseModel):
    input: str | None = None


class CrewRunResponse(BaseModel):
    result: str
    cost_usd: float = 0.0
    tier_used: str | None = None
    cached: bool = False


class ClientLogin(BaseModel):
    email: EmailStr
    password: str


class AssignedAgentOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    agent_code: str | None = None
    orixa: str | None = None
    group: str | None = None
    status: str = "active"
    daily_budget_usd: float | None = None
    tools: list[str] = []
    case_memory: bool = False


class ClientOut(BaseModel):
    id: str
    name: str
    email: str
    agents: list[AssignedAgentOut] = []


class AgentOut(BaseModel):
    id: str
    agent_code: str | None = None
    name: str
    role: str
    description: str | None = None
    status: str
    daily_budget_usd: float | None = None
    orixa: str | None = None
    group: str | None = None
    tools: list[str] = []
    system_prompt: str | None = None
    default_tier: str | None = None
    case_memory: bool = False
    created_at: str


class CreateCaseRequest(BaseModel):
    patient_label: str


class CaseOut(BaseModel):
    id: str
    agent_id: str
    client_id: str | None = None
    patient_label: str
    status: str
    created_at: str
    updated_at: str


class CaseMessageOut(BaseModel):
    role: str
    content: str
    cost_usd: float | None = None
    created_at: str


class CaseRunRequest(BaseModel):
    message: str


class KbArticleOut(BaseModel):
    id: str
    tema: str
    pregunta: str
    respuesta: str
    indexed: bool
    created_at: str


class ExecutionOut(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    client_id: str | None = None
    client_name: str | None = None
    status: str
    tier: str
    cost_usd: float
    cached: bool
    input_text: str | None = None
    result_text: str | None = None
    error_message: str | None = None
    created_at: str


class ConnectToolkitResponse(BaseModel):
    redirect_url: str


class UsageByAgentOut(BaseModel):
    agent_id: str
    agent_name: str
    agent_code: str | None = None
    status: str
    daily_budget_usd: float | None = None
    spend_today_usd: float
    spend_period_usd: float
    runs: int
    tokens_in: int
    tokens_out: int


class UsageOut(BaseModel):
    period: str
    by_agent: list[UsageByAgentOut]
    total_usd: float


class ProfitabilityByClientOut(BaseModel):
    client_id: str
    client_name: str
    spend_period_usd: float
    runs: int


class ProfitabilityOut(BaseModel):
    period: str
    by_client: list[ProfitabilityByClientOut]
    total_usd: float
