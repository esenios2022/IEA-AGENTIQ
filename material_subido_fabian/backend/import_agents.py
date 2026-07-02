"""
Script para importar agentes desde agents_config.json a Supabase
Ejecutar: python import_agents.py
"""

import json
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Agent, Tool
import sys
import os

# Agregar directorio app al path
sys.path.insert(0, os.path.dirname(__file__))

def import_agents():
    """Importar agentes desde JSON a Supabase"""
    
    with open("agents_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    db = SessionLocal()
    
    try:
        # Limpiar agentes existentes (opcional)
        db.query(Agent).delete()
        
        # Importar agentes
        for agent_data in config["agents"]:
            agent = Agent(
                id=agent_data["id"],
                name=agent_data["name"],
                role=agent_data["role"],
                goal=agent_data["goal"],
                prompt=agent_data["prompt"],
                tools=agent_data["tools"],
                group_name=agent_data["group"],
                status=agent_data["status"]
            )
            db.add(agent)
        
        # Importar herramientas
        for tool_name, tool_data in config["tools_config"].items():
            tool = Tool(
                name=tool_name,
                description=tool_data.get("type"),
                type=tool_data.get("type"),
                config={
                    "provider": tool_data.get("provider"),
                    "requires_api_key": tool_data.get("requires_api_key")
                },
                status=tool_data.get("status", "pending")
            )
            db.add(tool)
        
        db.commit()
        print(f"✅ {len(config['agents'])} agentes importados")
        print(f"✅ {len(config['tools_config'])} herramientas configuradas")
        print("✅ Agentes listos en Supabase")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    import_agents()
