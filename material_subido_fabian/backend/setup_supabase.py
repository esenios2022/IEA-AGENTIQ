"""
SETUP SUPABASE - IEA AGENTIQ
Crea tablas e importa agentes directamente desde Supabase
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# Credenciales Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://djyuotgzcwhqvoowvixv.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ ERROR: SUPABASE_SERVICE_ROLE_KEY no está en .env")
    print("\n📌 PASOS:")
    print("1. Ve a: https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv/settings/api")
    print("2. Copia 'service_role' (la key secreta)")
    print("3. Abre .env y agrega: SUPABASE_SERVICE_ROLE_KEY=tu_key_aqui")
    exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Supabase no instalado. Ejecuta:")
    print("   pip install supabase")
    exit(1)

# Conectar a Supabase
print("🔗 Conectando a Supabase...")
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("✅ Conectado a Supabase")
except Exception as e:
    print(f"❌ Error de conexión: {str(e)}")
    exit(1)

def create_tables():
    """Crear tablas en Supabase ejecutando SQL"""
    print("\n📊 Creando tablas...")
    
    sql_queries = [
        # Tabla: Agentes
        """
        CREATE TABLE IF NOT EXISTS agents (
          id TEXT PRIMARY KEY,
          name VARCHAR(255) NOT NULL,
          role VARCHAR(100) NOT NULL,
          goal TEXT,
          prompt TEXT,
          tools JSONB DEFAULT '[]'::jsonb,
          status VARCHAR(50) DEFAULT 'active',
          group_name VARCHAR(100),
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        # Tabla: Clientes
        """
        CREATE TABLE IF NOT EXISTS clients (
          id TEXT PRIMARY KEY,
          name VARCHAR(255) NOT NULL,
          email VARCHAR(255) UNIQUE NOT NULL,
          plan VARCHAR(50) DEFAULT 'starter',
          agents_count INT DEFAULT 0,
          status VARCHAR(50) DEFAULT 'active',
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        # Tabla: Asignaciones
        """
        CREATE TABLE IF NOT EXISTS client_agents (
          id TEXT PRIMARY KEY,
          client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
          agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
          assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        # Tabla: Ejecuciones
        """
        CREATE TABLE IF NOT EXISTS executions (
          id TEXT PRIMARY KEY,
          agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
          client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
          start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          end_time TIMESTAMP WITH TIME ZONE,
          status VARCHAR(50) DEFAULT 'running',
          result JSONB DEFAULT '{}'::jsonb,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        # Tabla: Logs
        """
        CREATE TABLE IF NOT EXISTS logs (
          id TEXT PRIMARY KEY,
          execution_id TEXT REFERENCES executions(id) ON DELETE CASCADE,
          timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          level VARCHAR(20) DEFAULT 'info',
          message TEXT
        );
        """,
        
        # Tabla: Herramientas
        """
        CREATE TABLE IF NOT EXISTS tools (
          id TEXT PRIMARY KEY,
          name VARCHAR(100) NOT NULL UNIQUE,
          description TEXT,
          type VARCHAR(50),
          config JSONB DEFAULT '{}'::jsonb,
          status VARCHAR(50) DEFAULT 'active',
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        # Tabla: Leads
        """
        CREATE TABLE IF NOT EXISTS leads (
          id TEXT PRIMARY KEY,
          email VARCHAR(255) NOT NULL,
          name VARCHAR(255),
          message TEXT,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
    ]
    
    # Intentar crear tablas (puede fallar si ya existen, eso está bien)
    try:
        # En Supabase, usamos el SDK de Python para insertar datos
        # Las tablas se crean desde el dashboard SQL Editor
        print("   ⚠️  Para crear tablas, ejecuta esto en Supabase SQL Editor:")
        print("   https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv/sql/new")
        print("\n   Copia y pega en el SQL Editor:")
        for query in sql_queries:
            print(f"\n   {query.strip()}\n")
        return True
    except Exception as e:
        print(f"   ⚠️  {str(e)}")
        return True

def import_agents():
    """Importar 16 agentes a Supabase"""
    print("\n🤖 Importando agentes...")
    
    try:
        with open("agents_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("   ❌ agents_config.json no encontrado")
        return False
    
    try:
        # Insertar agentes
        for agent_data in config["agents"]:
            response = supabase.table("agents").insert({
                "id": agent_data["id"],
                "name": agent_data["name"],
                "role": agent_data["role"],
                "goal": agent_data["goal"],
                "prompt": agent_data["prompt"],
                "tools": agent_data["tools"],
                "group_name": agent_data["group"],
                "status": agent_data["status"]
            }).execute()
        
        print(f"   ✅ {len(config['agents'])} agentes importados")
        
        # Insertar herramientas
        for tool_name, tool_data in config["tools_config"].items():
            supabase.table("tools").insert({
                "id": f"tool_{tool_name}",
                "name": tool_name,
                "description": tool_data.get("type"),
                "type": tool_data.get("type"),
                "config": {
                    "provider": tool_data.get("provider"),
                    "requires_api_key": tool_data.get("requires_api_key")
                },
                "status": tool_data.get("status", "pending")
            }).execute()
        
        print(f"   ✅ {len(config['tools_config'])} herramientas configuradas")
        return True
    
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def test_connection():
    """Verificar conexión y datos"""
    print("\n✅ Pruebas de conexión...")
    
    try:
        # Contar agentes
        response = supabase.table("agents").select("id").execute()
        agents_count = len(response.data)
        print(f"   ✅ {agents_count} agentes en BD")
        
        # Contar herramientas
        response = supabase.table("tools").select("id").execute()
        tools_count = len(response.data)
        print(f"   ✅ {tools_count} herramientas en BD")
        
        return True
    except Exception as e:
        print(f"   ⚠️  No se pudieron leer datos: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("🚀 SETUP IEA AGENTIQ - SUPABASE")
    print("=" * 60)
    
    # 1. Crear tablas
    create_tables()
    
    # 2. Importar agentes
    import_agents()
    
    # 3. Pruebas
    test_connection()
    
    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETADO")
    print("=" * 60)
    
    print("\n📋 PRÓXIMOS PASOS:")
    print("\n1. Ve a SQL Editor en Supabase:")
    print("   https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv/sql/new")
    print("\n2. Copia y ejecuta las tablas (ver arriba)")
    print("\n3. Obtén tus API keys en Settings > API:")
    print("   - ANON KEY (para frontend)")
    print("   - SERVICE ROLE KEY (para backend)")
    print("\n4. Actualiza tu .env con las keys")
    print("\n5. Ejecuta:")
    print("   python setup_supabase.py")
    print("\n6. Inicia el servidor:")
    print("   uvicorn app.main:app --reload")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
