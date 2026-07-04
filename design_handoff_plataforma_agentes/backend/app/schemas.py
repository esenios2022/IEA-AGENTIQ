from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ==================== AGENTES ====================

class AgentCreate(BaseModel):
    name: str
    role: str
    goal: Optional[str] = None
    prompt: Optional[str] = None
    tools: Optional[List[str]] = []
    group_name: Optional[str] = None

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    status: Optional[str] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    role: str
    goal: Optional[str]
    prompt: Optional[str]
    tools: List[str]
    status: str
    group_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== CLIENTES ====================

class ClientCreate(BaseModel):
    name: str
    email: str
    plan: Optional[str] = "starter"

class ClientResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    agents_count: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== EJECUCIONES ====================

class ExecutionCreate(BaseModel):
    agent_id: str
    client_id: Optional[str] = None

class ExecutionResponse(BaseModel):
    id: str
    agent_id: str
    client_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    result: dict
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== LOGS ====================

class LogResponse(BaseModel):
    id: str
    execution_id: str
    timestamp: datetime
    level: str
    message: str
    
    class Config:
        from_attributes = True

# ==================== LEADS ====================

class LeadCreate(BaseModel):
    email: str
    name: Optional[str] = None
    message: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
