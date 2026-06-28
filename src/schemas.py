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
