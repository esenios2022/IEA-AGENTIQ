# 🤖 HANDOFF PARA CLAUDE CODE — IEA AGENTIQ

## 📌 QUÉ ES ESTE PROYECTO

**Nombre:** IEA AGENTIQ — Arquitectura de la Creación  
**Tipo:** Plataforma SaaS de agentes de IA para empresas y terapeutas  
**Stack:** HTML/JS frontend + FastAPI backend + Supabase (PostgreSQL)  
**Repo GitHub:** `esenios2022/iea-agentiq`  

---

## 🎯 TU TAREA (hacé todo esto en orden)

### 1. DESCARGAR LOS ARCHIVOS DE CLAUDE DESIGN
Los archivos principales están en el proyecto de Claude Design. Necesitás:
- `IEA_AGENTIQ_Plataforma.html` — plataforma admin + cliente (archivo principal)
- `IEA_AGENTIQ_Landing_RESTAURADO.html` — landing page de ventas
- `frontend/Setup_Supabase.html` — setup de base de datos
- `frontend/Dashboard_Agentiq.html` — dashboard de agentes
- `logo_iea_agentiq.jpg` — logo de la empresa
- `flor_agentiq.png` — símbolo de la flor de la vida

---

### 2. CONFIGURAR SUPABASE

**URL del proyecto:** `https://djyuotgzcwhqvoowvixv.supabase.co`  
**Project ID:** `djyuotgzcwhqvoowvixv`  
**Región:** sa-east-1 (São Paulo)

#### 2a. Crear las tablas (ejecutar en Supabase SQL Editor)

```sql
-- Tabla de agentes
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

-- Tabla de clientes
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

-- Tabla de ejecuciones
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

-- Tabla de herramientas configuradas
CREATE TABLE IF NOT EXISTS tools_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tool_name TEXT UNIQUE NOT NULL,
  api_key TEXT,
  enabled BOOLEAN DEFAULT false,
  config JSONB DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de API keys del sistema
CREATE TABLE IF NOT EXISTS api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider TEXT UNIQUE NOT NULL,
  api_key TEXT,
  base_url TEXT,
  enabled BOOLEAN DEFAULT false,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de leads (ya existe como ealumina_clientes_maestro)
-- Si no existe, crearla:
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
  notas TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar RLS (Row Level Security) básico
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE executions ENABLE ROW LEVEL SECURITY;

-- Política pública de lectura para agentes (el frontend los necesita)
CREATE POLICY "agents_public_read" ON agents FOR SELECT USING (true);
CREATE POLICY "agents_auth_write" ON agents FOR ALL USING (true);
CREATE POLICY "clients_auth_all" ON clients FOR ALL USING (true);
CREATE POLICY "executions_auth_all" ON executions FOR ALL USING (true);
```

#### 2b. Importar los 16 agentes
Ejecutar este SQL en Supabase SQL Editor:

```sql
INSERT INTO agents (id, name, "orixá", role, goal, group_name, status, modelo, tools, prompt) VALUES
('SL','Sales Lead','Oxum','Cierre de Ventas','Cierre de ventas y conversión de clientes terapeutas y líderes.','Máquina de Adquisición','active','ollama/mistral','["WhatsApp (API oficial)","Email (Gmail)","CRM","Agenda","LinkedIn"]','Eres Sales Lead (Oxum). Rol: Cierre de Ventas. Tu objetivo es: Cierre de ventas y conversión de clientes terapeutas y líderes.'),
('GS','Growth Scout','Oxóssi','Prospección Activa','Prospección activa de nuevos clientes y nichos de mercado.','Máquina de Adquisición','active','ollama/llama3.2','["LinkedIn","Búsqueda Web","CRM","Email (Gmail)"]','Eres Growth Scout (Oxóssi). Prospección B2B activa.'),
('SA','SEO Architect','Obatalá','Posicionamiento SEO','Posicionamiento orgánico y claridad estratégica de marca.','Máquina de Contenido','active','ollama/mistral','["Búsqueda Web","Archivos","Generación de Contenido"]','Eres SEO Architect (Obatalá). Especialista en posicionamiento orgánico.'),
('RM','Resource Manager','Ogum','Gestión Financiera','Gestión de presupuestos, finanzas y flujo de caja.','Máquina de Operaciones','active','ollama/gemma2','["Archivos","Email (Gmail)","CRM"]','Eres Resource Manager (Ogum). Gestor financiero y de presupuestos.'),
('CC','Client Care','Iemanjá','Soporte al Cliente','Soporte al cliente y atención a la comunidad.','Máquina de Atención','active','ollama/llama3.2','["WhatsApp (API oficial)","Email (Gmail)","CRM","Agenda"]','Eres Client Care (Iemanjá). Atención al cliente 24/7.'),
('CG','Compliance Guard','Xangó','Legal y Ética','Legal, contratos y ética de la plataforma.','Máquina de Cumplimiento','active','ollama/mistral','["Archivos","Email (Gmail)","Búsqueda Web"]','Eres Compliance Guard (Xangó). Especialista legal y normativo.'),
('BC','Brand Catalyst','Iansã','Marketing y Redes','Publicidad, redes sociales y campañas virales.','Máquina de Contenido','active','ollama/llama3.2','["LinkedIn","Generación de Contenido","Búsqueda Web"]','Eres Brand Catalyst (Iansã). Estratega de marca y campañas.'),
('SH','Systems Healer','Obaluaiê','Soporte Técnico','Soporte técnico, estabilidad y mantenimiento.','Máquina de Operaciones','active','ollama/phi3','["Archivos","Email (Gmail)"]','Eres Systems Healer (Obaluaiê). Soporte técnico y estabilidad.'),
('CF','Creative Flow','Logun Edé','Creación de Contenido','Creación de contenido, copy persuasivo y material gráfico.','Máquina de Contenido','active','ollama/mistral','["Generación de Contenido","Archivos","Búsqueda Web"]','Eres Creative Flow (Logun Edé). Creador de contenido y copy.'),
('OL','Operations Lead','Ossaim','Automatización','Logística, automatización y procesos internos.','Máquina de Operaciones','active','ollama/gemma2','["CRM","Archivos","Email (Gmail)","Agenda"]','Eres Operations Lead (Ossaim). Automatización y operaciones.'),
('PC','Project Core','Oduduwa','Gestión de Proyectos','Gestión general y liderazgo de proyectos estratégicos.','Máquina de Operaciones','active','ollama/llama3.2','["Agenda","CRM","Email (Gmail)","Archivos"]','Eres Project Core (Oduduwa). Gerente de proyectos.'),
('GK','Gatekeeper AI','Exu','Seguridad y APIs','Seguridad, APIs y control del tráfico de información.','Máquina de Cumplimiento','active','ollama/phi3','["Archivos"]','Eres Gatekeeper AI (Exu). Seguridad y control de accesos.'),
('IX','Innovation Nexus','Oxumaré','I+D y Tecnología','I+D, nuevas tecnologías y escalabilidad.','Máquina de Análisis','active','ollama/deepseek-r1','["Búsqueda Web","Archivos","Generación de Contenido"]','Eres Innovation Nexus (Oxumaré). Investigación y desarrollo.'),
('KA','Knowledge Anchor','Orunmilá','Formación','Formación, capacitación y gestión de bases de conocimiento.','Máquina de Operaciones','active','ollama/llama3.2','["Archivos","Generación de Contenido","Email (Gmail)"]','Eres Knowledge Anchor (Orunmilá). Formación y conocimiento.'),
('WA','Wisdom Auditor','Nanã','Control de Calidad','Control de calidad, auditoría y mejora continua.','Máquina de Calidad','active','ollama/mistral','["Archivos","CRM","Email (Gmail)"]','Eres Wisdom Auditor (Nanã). Auditoría y calidad.'),
('GH','Global Harmony','Oxalá','Relaciones Institucionales','Relaciones institucionales y expansión global.','Máquina de Estrategia','active','ollama/llama3.2','["LinkedIn","Email (Gmail)","CRM","Agenda"]','Eres Global Harmony (Oxalá). Relaciones y expansión global.')
ON CONFLICT (id) DO UPDATE SET
  name=EXCLUDED.name, "orixá"=EXCLUDED."orixá", role=EXCLUDED.role,
  goal=EXCLUDED.goal, group_name=EXCLUDED.group_name, modelo=EXCLUDED.modelo,
  tools=EXCLUDED.tools, prompt=EXCLUDED.prompt, updated_at=NOW();
```

---

### 3. PUSH AL REPOSITORIO GITHUB

```bash
# Clonar el repo existente
git clone https://github.com/esenios2022/iea-agentiq.git
cd iea-agentiq

# Copiar los archivos del proyecto de Claude Design
# (Los archivos están en la carpeta del proyecto descargado)
cp /ruta/descarga/IEA_AGENTIQ_Plataforma.html ./frontend/
cp /ruta/descarga/IEA_AGENTIQ_Landing_RESTAURADO.html ./frontend/
cp /ruta/descarga/frontend/Dashboard_Agentiq.html ./frontend/
cp /ruta/descarga/frontend/Setup_Supabase.html ./frontend/
cp /ruta/descarga/logo_iea_agentiq.jpg ./assets/
cp /ruta/descarga/flor_agentiq.png ./assets/
cp /ruta/descarga/HANDOFF_CLAUDE_CODE.md ./

# Commit y push
git add .
git commit -m "feat: 16 agentes Orixás + CRUD clientes + 27 herramientas + modelos locales Ollama"
git push origin main
```

---

### 4. CONECTAR FRONTEND CON SUPABASE

En `IEA_AGENTIQ_Plataforma.html`, agregar en `<head>`:
```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
```

Y al inicio del script, después de las variables:
```javascript
// Conexión Supabase
const SUPA_URL = localStorage.getItem('k_surl') || 'https://djyuotgzcwhqvoowvixv.supabase.co';
const SUPA_KEY = localStorage.getItem('k_skey') || '';
let sb = null;
if (SUPA_URL && SUPA_KEY && window.supabase) {
  sb = window.supabase.createClient(SUPA_URL, SUPA_KEY);
}

// Cargar agentes desde Supabase (si está conectado)
async function loadFromSupabase() {
  if (!sb) return;
  try {
    const { data } = await sb.from('agents').select('*');
    if (data && data.length) {
      data.forEach(a => {
        AGENTS[a.id] = {
          n: a.name, orixá: a['orixá'] || '', grupo: a.group_name,
          modelo: a.modelo || 'ollama/mistral', idioma: 'PT/ES',
          estado: a.status || 'activo', d: a.goal || '',
          prompt: a.prompt || '', tools: JSON.parse(a.tools || '[]')
        };
      });
    }
  } catch(e) { console.warn('Supabase:', e.message); }
}
```

---

### 5. VARIABLES DE ENTORNO (para el backend FastAPI)

Crear archivo `.env` en la raíz:
```env
# Base de datos
SUPABASE_URL=https://djyuotgzcwhqvoowvixv.supabase.co
SUPABASE_ANON_KEY=TU_ANON_KEY
SUPABASE_SERVICE_KEY=TU_SERVICE_ROLE_KEY

# LLMs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OLLAMA_BASE_URL=http://localhost:11434

# Comunicación
WHATSAPP_TOKEN=EAA...
WHATSAPP_PHONE_ID=...
GMAIL_CLIENT_ID=...
LINKEDIN_TOKEN=AQV...

# CRM
HUBSPOT_API_KEY=...
NOTION_TOKEN=secret_...
ZAPIER_WEBHOOK_URL=...
APOLLO_API_KEY=...
SERPER_API_KEY=...
```

---

## 📂 ESTRUCTURA DE ARCHIVOS FINAL

```
iea-agentiq/
├── frontend/
│   ├── IEA_AGENTIQ_Plataforma.html    ← PLATAFORMA PRINCIPAL
│   ├── IEA_AGENTIQ_Landing.html       ← LANDING DE VENTAS
│   ├── Dashboard_Agentiq.html         ← DASHBOARD AGENTES
│   └── Setup_Supabase.html            ← SETUP BD
├── assets/
│   ├── logo_iea_agentiq.jpg
│   └── flor_agentiq.png
├── backend/                           ← FastAPI (ya existente)
│   ├── main.py
│   └── ...
├── .env                               ← Variables de entorno
├── HANDOFF_CLAUDE_CODE.md             ← ESTE ARCHIVO
└── README.md
```

---

## ✅ CHECKLIST DE VERIFICACIÓN

- [ ] Tablas creadas en Supabase
- [ ] 16 agentes importados (verificar en Table Editor)
- [ ] Archivos pusheados a GitHub
- [ ] `.env` configurado con las keys
- [ ] Ollama corriendo en localhost:11434
- [ ] Frontend abre y muestra los agentes
- [ ] Conexión & API Keys configurada en la plataforma

---

## 💡 NOTAS IMPORTANTES

1. **Modelos locales gratuitos**: Los agentes usan Ollama por defecto (`ollama/mistral`, `ollama/llama3.2`, etc.). Para usarlos, Ollama tiene que estar corriendo: `ollama serve`

2. **Para probar un agente**: Entrar como Admin → Agentes → seleccionar agente → cambiar modelo a `ollama/mistral` → Guardar

3. **Supabase anon key vs service role**: 
   - `anon key` → para el frontend (lectura pública)
   - `service role key` → para el backend (acceso total, SECRETO)

4. **Los clientes demo**: Centro Aurora, Instituto Theta, Luz Interior son datos de prueba. Para producción, crear clientes reales desde el panel Admin → Clientes.
