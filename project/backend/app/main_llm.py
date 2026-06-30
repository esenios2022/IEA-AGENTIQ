"""
Actualización de main.py para soportar múltiples LLMs
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .database import get_db, init_db
from .models import Agent, Client, Execution, Log, Lead
from .schemas import (
    AgentCreate, AgentUpdate, AgentResponse,
    ClientCreate, ClientResponse,
    ExecutionCreate, ExecutionResponse,
    LeadCreate, LeadResponse
)
from .llm_providers import LLMFactory

app = FastAPI(title="IEA AGENTIQ API")

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://iea-agentiq.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar BD
@app.on_event("startup")
def startup():
    init_db()
    print("✅ Database initialized")

# ==================== LLM CONFIG ====================

@app.get("/api/llm/providers")
def get_available_llms():
    """Obtener proveedores de LLM disponibles"""
    available = LLMFactory.get_available_providers()
    return {
        "available": available,
        "default": "ollama" if available.get("ollama") else "openai"
    }

# ==================== AGENTES ====================

@app.post("/api/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    """Crear nuevo agente"""
    db_agent = Agent(**agent.dict())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/api/agents", response_model=List[AgentResponse])
def list_agents(db: Session = Depends(get_db)):
    """Listar todos los agentes"""
    agents = db.query(Agent).all()
    return agents

@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Obtener detalles de un agente"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db)):
    """Editar un agente"""
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    for field, value in agent.dict(exclude_unset=True).items():
        setattr(db_agent, field, value)
    
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """Eliminar un agente"""
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db.delete(db_agent)
    db.commit()
    return {"message": "Agent deleted"}

# ==================== EJECUCIONES CON LLM ====================

@app.post("/api/agents/{agent_id}/run")
def run_agent(
    agent_id: str, 
    llm_provider: Optional[str] = Query("ollama"),
    db: Session = Depends(get_db)
):
    """Ejecutar un agente con LLM seleccionado"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Crear ejecución
    execution = Execution(
        agent_id=agent_id,
        status="running"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Obtener proveedor de LLM
    try:
        llm = LLMFactory.create(llm_provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validar credenciales
    if not llm.validate_credentials():
        raise HTTPException(
            status_code=400,
            detail=f"LLM provider '{llm_provider}' no está configurado"
        )
    
    # Agregar log
    log = Log(
        execution_id=execution.id,
        level="info",
        message=f"Iniciando ejecución con {llm_provider}"
    )
    db.add(log)
    db.commit()
    
    # Ejecutar agente
    try:
        result = llm.complete(
            prompt=agent.prompt or f"Eres un {agent.role}. Tu objetivo es: {agent.goal}"
        )
        
        execution.status = "completed"
        execution.result = {"output": result}
        execution.end_time = datetime.utcnow()
        
        log = Log(
            execution_id=execution.id,
            level="info",
            message=f"Ejecución completada exitosamente"
        )
        db.add(log)
        db.commit()
        
        return {
            "id": execution.id,
            "agent_id": agent_id,
            "status": "completed",
            "result": result,
            "llm_provider": llm_provider
        }
    
    except Exception as e:
        execution.status = "failed"
        execution.end_time = datetime.utcnow()
        
        log = Log(
            execution_id=execution.id,
            level="error",
            message=f"Error: {str(e)}"
        )
        db.add(log)
        db.commit()
        
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/executions/{execution_id}/logs")
def get_logs(execution_id: str, db: Session = Depends(get_db)):
    """Obtener logs de una ejecución"""
    logs = db.query(Log).filter(Log.execution_id == execution_id).all()
    return logs

# ==================== CLIENTES ====================

@app.post("/api/clients", response_model=ClientResponse)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    """Crear nuevo cliente"""
    db_client = Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.get("/api/clients", response_model=List[ClientResponse])
def list_clients(db: Session = Depends(get_db)):
    """Listar todos los clientes"""
    clients = db.query(Client).all()
    return clients

# ==================== LEADS ====================

@app.post("/api/leads", response_model=LeadResponse)
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    """Crear nuevo lead"""
    db_lead = Lead(**lead.dict())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead

@app.get("/api/leads", response_model=List[LeadResponse])
def list_leads(db: Session = Depends(get_db)):
    """Listar todos los leads"""
    leads = db.query(Lead).all()
    return leads

# ==================== HEALTH CHECK ====================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "IEA AGENTIQ API",
        "llm_providers": LLMFactory.get_available_providers()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
