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


class ClientOut(BaseModel):
    id: str
    name: str
    email: str
    agents: list[AssignedAgentOut] = []


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
