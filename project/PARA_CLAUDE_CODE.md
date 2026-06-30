# 🤖 INSTRUCCIONES PARA CLAUDE CODE — IEA AGENTIQ

## TU TAREA
Hacer que la plataforma IEA AGENTIQ funcione completamente. Tenemos el frontend diseñado. Necesitás crear el backend, conectar Supabase y desplegar todo.

---

## REPOSITORIO
**GitHub:** `https://github.com/esenios2022/IEA-AGENTIQ`
**Rama activa:** `claude/inspiring-dirac-68hil7`

---

## SUPABASE (ya está configurado)
```
URL: https://djyuotgzcwhqvoowvixv.supabase.co
Project ID: djyuotgzcwhqvoowvixv
Región: sa-east-1 (São Paulo)
```
Las keys las encontrás en: https://supabase.com/dashboard/project/djyuotgzcwhqvoowvixv/settings/api

---

## PASO 1: CREAR TABLAS EN SUPABASE
Ir a Supabase SQL Editor y ejecutar:

```sql
-- Agentes
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  "orixá" TEXT,
  role TEXT,
  goal TEXT,
  group_name TEXT,
  status TEXT DEFAULT 'active',
  modelo TEXT DEFAULT 'ollama/mistral',
  prompt TEXT,
  tools JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Clientes
CREATE TABLE IF NOT EXISTS clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  email TEXT UNIQUE,
  plan TEXT DEFAULT 'Inicial',
  pais TEXT,
  lang TEXT DEFAULT 'es',
  agents TEXT[] DEFAULT '{}',
  features JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ejecuciones
CREATE TABLE IF NOT EXISTS executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT REFERENCES agents(id),
  client_id UUID REFERENCES clients(id),
  task TEXT,
  status TEXT DEFAULT 'pending',
  result TEXT,
  tokens_used INTEGER DEFAULT 0,
  cost_usd DECIMAL(10,6) DEFAULT 0,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

-- Leads (de la landing)
CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre_completo TEXT,
  email TEXT,
  telefono TEXT,
  empresa TEXT,
  ciudad TEXT,
  pais TEXT,
  plan_interes TEXT,
  fuente TEXT DEFAULT 'landing_web',
  estado TEXT DEFAULT 'prospecto',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Herramientas configuradas
CREATE TABLE IF NOT EXISTS tools_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tool_name TEXT UNIQUE NOT NULL,
  api_key TEXT,
  enabled BOOLEAN DEFAULT false,
  config JSONB DEFAULT '{}'
);

-- Políticas RLS (permisivas para desarrollo)
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "all_agents" ON agents FOR ALL USING (true);
CREATE POLICY "all_clients" ON clients FOR ALL USING (true);
CREATE POLICY "all_executions" ON executions FOR ALL USING (true);
CREATE POLICY "all_leads" ON leads FOR ALL USING (true);
```

---

## PASO 2: IMPORTAR LOS 16 AGENTES

```sql
INSERT INTO agents (id, name, "orixá", role, goal, group_name, status, modelo, tools, prompt) VALUES
('SL','Sales Lead','Oxum','Cierre de Ventas','Cierre de ventas y conversión de clientes terapeutas.','Máquina de Adquisición','active','ollama/mistral','["WhatsApp","Email","CRM","Agenda","LinkedIn"]','Eres Sales Lead (Oxum). Especialista en cierre de ventas B2B para terapeutas y líderes.'),
('GS','Growth Scout','Oxóssi','Prospección Activa','Prospección activa de nuevos clientes y nichos de mercado.','Máquina de Adquisición','active','ollama/llama3.2','["LinkedIn","Búsqueda Web","CRM","Email"]','Eres Growth Scout (Oxóssi). Prospector B2B activo.'),
('SA','SEO Architect','Obatalá','Posicionamiento SEO','Posicionamiento orgánico y claridad estratégica de marca.','Máquina de Contenido','active','ollama/mistral','["Búsqueda Web","Archivos","Generación Contenido"]','Eres SEO Architect (Obatalá). Especialista en SEO y posicionamiento.'),
('RM','Resource Manager','Ogum','Gestión Financiera','Gestión de presupuestos, finanzas y flujo de caja.','Máquina de Operaciones','active','ollama/gemma2','["Archivos","Email","CRM"]','Eres Resource Manager (Ogum). Gestor financiero y de presupuestos.'),
('CC','Client Care','Iemanjá','Soporte al Cliente','Soporte al cliente y atención a la comunidad.','Máquina de Atención','active','ollama/llama3.2','["WhatsApp","Email","CRM","Agenda"]','Eres Client Care (Iemanjá). Atención al cliente 24/7.'),
('CG','Compliance Guard','Xangó','Legal y Ética','Legal, contratos y ética de la plataforma.','Máquina de Cumplimiento','active','ollama/mistral','["Archivos","Email","Búsqueda Web"]','Eres Compliance Guard (Xangó). Asesor legal y normativo.'),
('BC','Brand Catalyst','Iansã','Marketing y Redes','Publicidad, redes sociales y campañas virales.','Máquina de Contenido','active','ollama/llama3.2','["LinkedIn","Generación Contenido","Búsqueda Web"]','Eres Brand Catalyst (Iansã). Estratega de marca y campañas.'),
('SH','Systems Healer','Obaluaiê','Soporte Técnico','Soporte técnico, estabilidad y mantenimiento.','Máquina de Operaciones','active','ollama/phi3','["Archivos","Email"]','Eres Systems Healer (Obaluaiê). Soporte técnico y estabilidad.'),
('CF','Creative Flow','Logun Edé','Creación de Contenido','Creación de contenido, copy persuasivo y material gráfico.','Máquina de Contenido','active','ollama/mistral','["Generación Contenido","Archivos","Búsqueda Web"]','Eres Creative Flow (Logun Edé). Creador de contenido y copy.'),
('OL','Operations Lead','Ossaim','Automatización','Logística, automatización y procesos internos.','Máquina de Operaciones','active','ollama/gemma2','["CRM","Archivos","Email","Agenda"]','Eres Operations Lead (Ossaim). Automatización y operaciones.'),
('PC','Project Core','Oduduwa','Gestión de Proyectos','Gestión general y liderazgo de proyectos estratégicos.','Máquina de Operaciones','active','ollama/llama3.2','["Agenda","CRM","Email","Archivos"]','Eres Project Core (Oduduwa). Gerente de proyectos.'),
('GK','Gatekeeper AI','Exu','Seguridad y APIs','Seguridad, APIs y control del tráfico de información.','Máquina de Cumplimiento','active','ollama/phi3','["Archivos"]','Eres Gatekeeper AI (Exu). Seguridad y control de accesos.'),
('IX','Innovation Nexus','Oxumaré','I+D y Tecnología','I+D, nuevas tecnologías y escalabilidad.','Máquina de Análisis','active','ollama/deepseek-r1','["Búsqueda Web","Archivos","Generación Contenido"]','Eres Innovation Nexus (Oxumaré). Investigación y desarrollo.'),
('KA','Knowledge Anchor','Orunmilá','Formación','Formación, capacitación y bases de conocimiento.','Máquina de Operaciones','active','ollama/llama3.2','["Archivos","Generación Contenido","Email"]','Eres Knowledge Anchor (Orunmilá). Formación y conocimiento.'),
('WA','Wisdom Auditor','Nanã','Control de Calidad','Control de calidad, auditoría y mejora continua.','Máquina de Calidad','active','ollama/mistral','["Archivos","CRM","Email"]','Eres Wisdom Auditor (Nanã). Auditoría y calidad.'),
('GH','Global Harmony','Oxalá','Relaciones Institucionales','Relaciones institucionales y expansión global.','Máquina de Estrategia','active','ollama/llama3.2','["LinkedIn","Email","CRM","Agenda"]','Eres Global Harmony (Oxalá). Relaciones y expansión global.')
ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, updated_at=NOW();
```

---

## PASO 3: BACKEND FastAPI

Actualizar `src/main.py` con estas rutas nuevas:

```python
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import os, json
from datetime import datetime

app = FastAPI(title="IEA AGENTIQ API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPA_URL, SUPA_KEY) if SUPA_URL and SUPA_KEY else None

# ── AGENTES ──────────────────────────────
@app.get("/api/agents")
async def get_agents():
    if not sb: return {"agents": [], "error": "Supabase no configurado"}
    r = sb.table("agents").select("*").execute()
    return {"agents": r.data}

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    if not sb: raise HTTPException(404)
    r = sb.table("agents").select("*").eq("id", agent_id).single().execute()
    return r.data

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, data: dict):
    if not sb: raise HTTPException(500)
    r = sb.table("agents").update(data).eq("id", agent_id).execute()
    return r.data

@app.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, task: str = "Ejecutar tarea", llm_provider: str = "ollama"):
    if not sb: raise HTTPException(500)
    # Crear ejecución
    exec_data = {"agent_id": agent_id, "task": task, "status": "running"}
    r = sb.table("executions").insert(exec_data).execute()
    exec_id = r.data[0]["id"] if r.data else None
    # Aquí iría la lógica real del agente (CrewAI, LangChain, etc.)
    # Por ahora devolvemos la ejecución creada
    return {"execution_id": exec_id, "status": "running", "agent_id": agent_id}

@app.get("/api/agents/{agent_id}/executions")
async def get_agent_executions(agent_id: str):
    if not sb: return {"executions": []}
    r = sb.table("executions").select("*").eq("agent_id", agent_id).order("started_at", desc=True).limit(20).execute()
    return {"executions": r.data}

# WebSocket para logs en tiempo real
@app.websocket("/ws/agent/{agent_id}")
async def agent_ws(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "log", "agent": agent_id, "msg": f"Recibido: {data}", "ts": str(datetime.now())}))
    except:
        pass

# ── CLIENTES ──────────────────────────────
@app.get("/api/clients")
async def get_clients():
    if not sb: return {"clients": []}
    r = sb.table("clients").select("*").execute()
    return {"clients": r.data}

@app.post("/api/clients")
async def create_client(data: dict):
    if not sb: raise HTTPException(500)
    r = sb.table("clients").insert(data).execute()
    return r.data[0] if r.data else {}

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, data: dict):
    if not sb: raise HTTPException(500)
    r = sb.table("clients").update(data).eq("id", client_id).execute()
    return r.data

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str):
    if not sb: raise HTTPException(500)
    sb.table("clients").delete().eq("id", client_id).execute()
    return {"ok": True}

# ── LEADS (desde landing) ──────────────────
@app.post("/api/leads")
async def create_lead(data: dict):
    if not sb: raise HTTPException(500)
    data["fuente"] = data.get("fuente", "landing_web")
    data["estado"] = "prospecto"
    r = sb.table("leads").insert(data).execute()
    return {"ok": True, "id": r.data[0]["id"] if r.data else None}

@app.get("/api/leads")
async def get_leads():
    if not sb: return {"leads": []}
    r = sb.table("leads").select("*").order("created_at", desc=True).execute()
    return {"leads": r.data}

# ── EJECUCIONES ──────────────────────────────
@app.get("/api/executions")
async def get_executions():
    if not sb: return {"executions": []}
    r = sb.table("executions").select("*").order("started_at", desc=True).limit(50).execute()
    return {"executions": r.data}

@app.get("/")
async def root():
    return {"status": "IEA AGENTIQ API running", "version": "2.0"}
```

---

## PASO 4: VARIABLES DE ENTORNO

Crear `.env` en la raíz del repo:

```env
SUPABASE_URL=https://djyuotgzcwhqvoowvixv.supabase.co
SUPABASE_ANON_KEY=TU_ANON_KEY_AQUI
SUPABASE_SERVICE_KEY=TU_SERVICE_ROLE_KEY_AQUI

# LLMs locales (gratis)
OLLAMA_BASE_URL=http://localhost:11434

# LLMs cloud (opcionales)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Herramientas (agregar cuando estén listas)
WHATSAPP_TOKEN=
GMAIL_CLIENT_ID=
LINKEDIN_TOKEN=
SERPER_API_KEY=
```

---

## PASO 5: ACTUALIZAR requirements.txt

```txt
fastapi==0.115.0
uvicorn==0.32.0
supabase==2.10.0
python-dotenv==1.0.1
websockets==13.1
httpx==0.27.2
pydantic==2.9.2
```

---

## PASO 6: CONECTAR EL FRONTEND A LA API

En `IEA_AGENTIQ_Plataforma.html`, al inicio del `<script>`, agregar:

```javascript
// Config API (cambiar en producción)
const API_BASE = localStorage.getItem('api_base') || 'http://localhost:8000';
const SUPA_URL = 'https://djyuotgzcwhqvoowvixv.supabase.co';
const SUPA_ANON = localStorage.getItem('supa_anon') || '';

// Cargar agentes desde Supabase
async function syncFromSupabase() {
  if (!SUPA_ANON) return;
  try {
    const r = await fetch(`${SUPA_URL}/rest/v1/agents?select=*`, {
      headers: { 'apikey': SUPA_ANON, 'Authorization': 'Bearer ' + SUPA_ANON }
    });
    const data = await r.json();
    if (Array.isArray(data)) {
      data.forEach(a => {
        AGENTS[a.id] = {
          n: a.name, orixá: a['orixá'] || '', grupo: a.group_name,
          modelo: a.modelo || 'ollama/mistral', idioma: 'PT/ES',
          estado: a.status || 'activo', d: a.goal || '',
          prompt: a.prompt || '', tools: a.tools || []
        };
      });
      render();
    }
  } catch(e) { console.warn('Supabase sync:', e.message); }
}

// Guardar lead desde landing
async function enviarLead(datos) {
  try {
    await fetch(`${API_BASE}/api/leads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos)
    });
  } catch(e) { console.warn('Lead error:', e); }
}
```

---

## PASO 7: DESPLEGAR EN VERCEL (frontend) + RAILWAY/RENDER (backend)

### Frontend (Vercel):
```bash
# Desde la raíz del repo
vercel --prod
# O conectar el repo en vercel.com y auto-deploy en cada push
```

### Backend (Railway o Render):
```bash
# En Railway: New Project → Deploy from GitHub → esenios2022/IEA-AGENTIQ
# Variables de entorno: agregar las del .env
# Start command: uvicorn src.main:app --host 0.0.0.0 --port $PORT
```

---

## ESTRUCTURA FINAL DEL REPO

```
IEA-AGENTIQ/
├── frontend/
│   ├── IEA_AGENTIQ_Plataforma.html    ← PLATAFORMA PRINCIPAL
│   ├── IEA_AGENTIQ_Landing.html       ← LANDING DE VENTAS
│   ├── Dashboard_Agentiq.html         ← DASHBOARD AGENTES
│   └── Setup_Supabase.html            ← SETUP BD
├── assets/
│   ├── logo_iea_agentiq.jpg
│   └── flor_agentiq.png
├── src/
│   ├── main.py                        ← API FastAPI (actualizado)
│   ├── database.py
│   ├── models.py
│   └── config.py
├── .env                               ← Keys (NO pushear)
├── .gitignore                         ← incluir .env
├── requirements.txt                   ← actualizado
├── Dockerfile
├── docker-compose.yml
└── PARA_CLAUDE_CODE.md                ← ESTE ARCHIVO
```

---

## CHECKLIST FINAL

- [ ] Tablas creadas en Supabase SQL Editor
- [ ] 16 agentes importados (verificar en Table Editor)
- [ ] `src/main.py` actualizado con las nuevas rutas
- [ ] `.env` configurado con SUPABASE_URL y SUPABASE_SERVICE_KEY
- [ ] `requirements.txt` actualizado
- [ ] Frontend HTML subido a `frontend/`
- [ ] Backend corriendo: `uvicorn src.main:app --reload`
- [ ] Probar: `GET http://localhost:8000/api/agents`
- [ ] Desplegar en Railway/Render
- [ ] Conectar dominio

---

## NOTAS IMPORTANTES

1. **Ollama para pruebas locales gratuitas:** 
   ```bash
   ollama serve
   ollama pull mistral
   ollama pull llama3.2
   ```

2. **Para que los agentes ejecuten REALMENTE** (no solo demo), integrar CrewAI o LangChain en el endpoint `/api/agents/{id}/run`. El scaffolding ya está listo.

3. **Supabase anon key** → para el frontend (lectura pública)  
   **Supabase service key** → solo para el backend (NUNCA publicar)

4. **Los modelos locales Ollama** no necesitan API key. Los cloud (OpenAI, Claude, Gemini) sí.
