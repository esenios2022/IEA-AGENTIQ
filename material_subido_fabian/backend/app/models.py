from sqlalchemy import Column, String, Text, Integer, JSON, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    goal = Column(Text)
    prompt = Column(Text)
    tools = Column(JSON, default=[])
    status = Column(String(50), default="active")
    group_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    executions = relationship("Execution", back_populates="agent", cascade="all, delete-orphan")

class Client(Base):
    __tablename__ = "clients"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    plan = Column(String(50), default="starter")
    agents_count = Column(Integer, default=0)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    executions = relationship("Execution", back_populates="client", cascade="all, delete-orphan")

class ClientAgent(Base):
    __tablename__ = "client_agents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

class Execution(Base):
    __tablename__ = "executions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    client_id = Column(String, ForeignKey("clients.id"))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String(50), default="running")
    result = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="executions")
    client = relationship("Client", back_populates="executions")
    logs = relationship("Log", back_populates="execution", cascade="all, delete-orphan")

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("executions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(20), default="info")
    message = Column(Text)
    
    execution = relationship("Execution", back_populates="logs")

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Tool(Base):
    __tablename__ = "tools"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    type = Column(String(50))
    config = Column(JSON, default={})
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
