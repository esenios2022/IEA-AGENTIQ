"""
SCRIPT DE SETUP COMPLETO
Ejecutar: python setup_complete.py
"""

import json
import sys
from pathlib import Path

# Agregar directorio al path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, init_db
from app.models import Agent, Tool

def setup_complete():
    print("🚀 SETUP COMPLETO DE IEA AGENTIQ")
    print("=" * 50)
    
    # 1. Inicializar BD
    print("\n1️⃣  Inicializando base de datos...")
    try:
        init_db()
        print("   ✅ BD inicializada")
    except Exception as e:
        print(f"   ⚠️  BD ya existía: {str(e)}")
    
    # 2. Importar agentes
    print("\n2️⃣  Importando 16 agentes...")
    try:
        with open("agents_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        db = SessionLocal()
        
        # Limpiar agentes existentes
        db.query(Agent).delete()
        db.query(Tool).delete()
        
        # Importar agentes
        agents_created = 0
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
            agents_created += 1
        
        # Importar herramientas
        tools_created = 0
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
            tools_created += 1
        
        db.commit()
        db.close()
        
        print(f"   ✅ {agents_created} agentes importados")
        print(f"   ✅ {tools_created} herramientas configuradas")
    
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False
    
    # 3. Crear archivo .env
    print("\n3️⃣  Configurando variables de entorno (.env)...")
    try:
        env_content = """# IEA AGENTIQ - CONFIGURACIÓN

# SUPABASE
DATABASE_URL=postgresql://postgres.djyuotgzcwhqvoowvixv:PASSWORD@db.djyuotgzcwhqvoowvixv.supabase.co:5432/postgres
SUPABASE_URL=https://djyuotgzcwhqvoowvixv.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_KEY

# LLM PROVIDERS (configura los que vayas a usar)

# OpenAI (GPT-4, GPT-3.5) - $
OPENAI_API_KEY=

# Anthropic (Claude) - $
ANTHROPIC_API_KEY=

# Google Gemini - $
GOOGLE_API_KEY=

# Mistral - $
MISTRAL_API_KEY=

# HuggingFace - $
HUGGINGFACE_API_KEY=

# Ollama (Local - GRATIS) ✅ RECOMENDADO PARA DESARROLLO
OLLAMA_BASE_URL=http://localhost:11434

# SERVER
DEBUG=True
SECRET_KEY=your_secret_key_change_in_production
FRONTEND_URL=http://localhost:5173
"""
        
        with open(".env", "w") as f:
            f.write(env_content)
        
        print("   ✅ .env creado (configura tus API keys)")
    except Exception as e:
        print(f"   ⚠️  {str(e)}")
    
    # 4. Mostrar instrucciones
    print("\n" + "=" * 50)
    print("✅ SETUP COMPLETADO")
    print("=" * 50)
    
    print("\n📋 PRÓXIMOS PASOS:")
    print("\n1. Configurar LLM en .env:")
    print("   - OPCIÓN A: Ollama (gratis, local)")
    print("   - OPCIÓN B: OpenAI (ChatGPT)")
    print("   - OPCIÓN C: Anthropic (Claude)")
    print("   - OPCIÓN D: Otra")
    
    print("\n2. Si usas Ollama:")
    print("   - Instalar desde: https://ollama.ai")
    print("   - ollama pull llama2")
    print("   - ollama serve (en otra terminal)")
    
    print("\n3. Ejecutar servidor:")
    print("   - uvicorn app.main_llm:app --reload")
    
    print("\n4. Abrir Dashboard:")
    print("   - http://localhost:5173/dashboard.html")
    
    print("\n5. Ver agentes disponibles:")
    print("   - curl http://localhost:8000/api/agents")
    
    print("\n6. Ejecutar un agente:")
    print("   - curl -X POST http://localhost:8000/api/agents/agent_001/run?llm_provider=ollama")
    
    print("\n" + "=" * 50)
    print("🎉 ¡Listo para usar!")
    print("=" * 50)

if __name__ == "__main__":
    setup_complete()
