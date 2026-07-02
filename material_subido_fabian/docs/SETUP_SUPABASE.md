# IEA AGENTIQ - SETUP SUPABASE

## 🎯 CONFIGURACIÓN PASO A PASO

### PASO 1: Obtener API Keys

1. Ve a: https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv/settings/api

2. Copia estas 2 keys:
   - **anon (public)** - Para landing/frontend
   - **service_role (secret)** - Para backend Python

3. Abre `backend/.env` y agrega:
```env
SUPABASE_URL=https://djyuotgzcwhqvoowvixv.supabase.co
SUPABASE_ANON_KEY=tu_anon_key_aqui
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key_aqui
```

---

### PASO 2: Crear tablas en Supabase

1. Ve a: https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv/sql/new

2. Click **New Query**

3. Copia TODO esto:

```sql
-- IEA AGENTIQ TABLES

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

CREATE TABLE IF NOT EXISTS client_agents (
  id TEXT PRIMARY KEY,
  client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
  agent_id TEXT REFERENCES agents(id) ON DELETE CASCADE,
  assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  execution_id TEXT REFERENCES executions(id) ON DELETE CASCADE,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  level VARCHAR(20) DEFAULT 'info',
  message TEXT
);

CREATE TABLE IF NOT EXISTS tools (
  id TEXT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT,
  type VARCHAR(50),
  config JSONB DEFAULT '{}'::jsonb,
  status VARCHAR(50) DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  name VARCHAR(255),
  message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

4. Click **Run** (ejecutar)

5. ✅ Verás las 7 tablas creadas

---

### PASO 3: Importar agentes

En tu terminal:
```bash
cd backend
pip install supabase
python setup_supabase.py
```

Esto automáticamente:
- ✅ Conecta a Supabase
- ✅ Importa 16 agentes
- ✅ Configura 9 herramientas
- ✅ Verifica la conexión

---

### PASO 4: Ejecutar servidor

```bash
uvicorn app.main:app --reload
```

---

## ✅ VERIFICACIÓN

Abre en navegador:
```
http://localhost:8000/api/agents
```

Deberías ver los 16 agentes en JSON.

---

## 🎉 ¡LISTO!

Ahora tu plataforma está:
- ✅ Conectada a Supabase
- ✅ Con 16 agentes cargados
- ✅ Backend funcionando
- ✅ Lista para usar cualquier LLM

¿Preguntas?
