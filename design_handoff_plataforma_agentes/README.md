# HANDOFF → CLAUDE CODE: IEA AGENTIQ — Plataforma de agentes funcionando de punta a punta

## Contexto
IEA AGENTIQ es una plataforma multi-tenant de agentes de IA (16 agentes con nombres humanos conectados a Orixás) que se vende como servicio a empresas (terapeutas, coaches, líderes — LATAM, ES/PT).

- **Repo**: https://github.com/esenios2022/IEA-AGENTIQ.git
- **Base de datos**: Supabase (proyecto `djyuotgzcwhqvoowvixv`, ya creado y enlazado)
- **Deploy**: Railway (ya subido, aún no funcional)
- **Fuente de verdad de los agentes**: `backend/agents_config.json` (v2 — NO tocar los prompts, ya son maestros y finales)

## Sobre los archivos de diseño en este paquete
Los archivos `.html` incluidos son **referencias de diseño hechas en HTML** (prototipos hi-fi con datos demo locales). NO son código de producción para copiar tal cual. La tarea es darles vida: conectar esa UI (o recrearla en el stack elegido) al backend real. La UI existente en HTML/JS vanilla es aceptable como frontend de producción si se conecta a la API — no es obligatorio migrarla a React.

## Fidelidad
**Hi-fi.** La plataforma (`IEA_AGENTIQ_Plataforma.html`) define exactamente el layout, colores (verde #0b4d3c, dorado #b08d57, crema #e6e1d4), secciones, roles (admin/cliente), bilingüe ES/PT, y toda la lógica de vistas. Respetar tal cual.

---

## MISIÓN GLOBAL (en orden)

### 1. Runtime de agentes (crear con código)
Los agentes se crean desde `backend/agents_config.json`. Implementar en `backend/app/`:
- **Executor**: dado un `agent_id` y una tarea, arma el mensaje con el `prompt` maestro del agente y ejecuta contra el LLM según `llm_routing`:
  - `default_tier: economy` → `claude-3-5-haiku-latest`
  - `standard` → `claude-sonnet-4` (o el sonnet vigente)
  - `premium` → `claude-opus` — SOLO agente Elías (agent_004) y solo si la tarea matchea `escalate_when`
  - `max_tokens` y `temperature` según `cost_policy.tiers` del JSON
- **Framework**: usar el SDK de Anthropic directo con tool-use nativo (más barato y controlable que CrewAI). Si ya hay CrewAI a medio integrar, reemplazar.
- Endpoint existente `POST /api/agents/{id}/run` debe ejecutar de verdad y escribir en `executions` + `execution_logs`.

### 2. Capa de TOOLS — programar TODAS las herramientas de cada agente
Cada agente declara sus tools en el JSON (campo `tools`). Implementar `backend/app/tools/` con un registro que mapea nombre → función ejecutable, expuesto al LLM como tool-use:

| Tool en JSON | Implementación |
|---|---|
| `composio_*` (gmail, whatsapp, linkedin, instagram, twitter, googlesheets, googledrive, calendar, googleads, metaads, analytics, searchconsole, apollo, buffer, canva, serpapi) | SDK `composio-core`: una **entity por agente** (`theo`, `maria`, `juan`...). Obtener acciones con `composio.get_tools(apps=[...], entity_id=agent_name)` y pasarlas al LLM. Las conexiones OAuth se dejan **preparadas**: crear las entities + integration configs por app, y exponer `GET /api/tools/connect/{agent}/{app}` que devuelve el link OAuth de Composio para que el admin conecte cada cuenta con un click. |
| `zapier_webhook` | POST a webhook URL (env `ZAPIER_WEBHOOK_URL_*`). Gratis, implementar primero. |
| `zapier_api`, `zapier_crm`, `zapier_scheduler`, `zapier_reporting`, `zapier_pm`, `zapier_accounting` | Zapier AI Actions (`ZAPIER_NLA_API_KEY`) o webhooks dedicados por flujo. |
| `supabase_query` | SQL parametrizado read-only sobre Supabase (service role). NUNCA tablas enteras: siempre agregaciones con LIMIT. |
| `supabase_storage` | Supabase Storage (bucket `agentiq`). |
| `supabase_knowledge_base` | RAG con pgvector: tabla `kb_articles(id, tema, pregunta, respuesta, embedding)`, búsqueda top_k=3. María la consulta ANTES de llamar al LLM: si hay match con similitud >0.85, responder el artículo tal cual (costo LLM = 0). |
| `web_search` | Serper.dev (`SERPER_API_KEY`) — más barato que SerpAPI. |
| `testing_tools` | checklists determinísticos en Python (sin LLM). |

**Regla**: si una tool no tiene API key configurada, el agente sigue funcionando y responde qué conexión falta (no crashear).

### 3. Medidor de consumo (crítico — vendemos servicio)
Todo lo que la UI muestra en «Consumo y saldo», «Rentabilidad» y «Analítica» debe salir de datos reales:
- Tabla `usage_log(id, agent_id, client_id, execution_id, model, input_tokens, output_tokens, cost_usd, tool_calls, created_at)` — escribir en CADA llamada al LLM (los tokens vienen en la respuesta del API).
- Cálculo de costo: tabla de precios por modelo en config (ej. Haiku $0.80/$4 por Mtok; Sonnet $3/$15; Opus $15/$75) — mantener en un solo lugar.
- Endpoints: `GET /api/usage?client=&agent=&period=` (día/mes/proyección×30), `GET /api/profitability` (por cliente: plan − consumo = margen).
- **Presupuesto diario** (`daily_budget_usd` en el JSON): middleware que suma el gasto del día por agente; al 80% fuerza tier economy; al 100% pausa el agente (status → `paused`) y notifica al admin.
- **Cache**: tabla `response_cache(hash_prompt, respuesta, created_at)` TTL 24h — consultar antes de cada llamada.

### 4. Conectar la UI de punta a punta
Reemplazar los datos demo (`const AGENTS`, `CONSUMO`, `CLIENTS`, `EXECS`...) por fetch a la API. Cada sección del menú lateral debe funcionar:
- **Inicio**: KPIs reales (`/api/agents`, `/api/clients`, `/api/executions?status=run`)
- **Chat de agentes**: enviar orden → `POST /api/agents/{id}/run` → stream/poll de logs
- **Agentes**: CRUD contra `/api/agents`; editar prompt/modelo/tools persiste en Supabase
- **Equipos**: CRUD de workforces
- **Clientes**: CRUD + asignación de agentes y features por cliente
- **Ejecuciones**: lista en vivo con pasos (`execution_logs`)
- **Herramientas**: estado real de cada conexión (conectada / falta key) + botón conectar (link OAuth Composio)
- **Rentabilidad / Analítica / Consumo y saldo**: desde `usage_log`
- **Catálogo**: contratación de agentes por cliente (escribe la relación cliente-agente)
- **Historial**: `usage_log` + `executions` agrupado por mes
- **Conexión & API**: guardar API keys propias del cliente (cifradas en Supabase, no localStorage en producción)
- **Conocimiento**: subir documentos → chunk → embedding → `kb_articles`
- **Funciones**: toggles por cliente persistidos
- **Ayuda**: estático, ya está

### 5. Multi-tenant y escala (16 agentes × 20+ empresas)
- Todas las tablas con `client_id`; RLS de Supabase activado.
- Los agentes se ejecutan por evento (webhook), sin workers en loop: en Railway un solo servicio FastAPI aguanta esto de sobra.
- Objetivo de costo verificable: equipo completo ≤ ~$1/día por cliente activo intensivo. Si `usage_log` muestra más, revisar batch/cache/tier.

### 6. Variables de entorno (Railway)
```
SUPABASE_URL, SUPABASE_KEY (service role), DATABASE_URL
ANTHROPIC_API_KEY
COMPOSIO_API_KEY
ZAPIER_NLA_API_KEY (y/o ZAPIER_WEBHOOK_URL_*)
SERPER_API_KEY
WHATSAPP_TOKEN (Meta Cloud API — prioridad: lo usan Juan y María)
```

### 7. Orden de implementación sugerido
1. Ejecutar `backend/migrations/001_create_tables.sql` + tablas nuevas (`usage_log`, `response_cache`, `kb_articles`) + `python import_agents.py`
2. Executor + medidor de consumo (con eso Chat y Ejecuciones ya viven)
3. Tools Supabase (query, storage, KB) — gratis, sin OAuth
4. Composio entities + link de conexión OAuth por agente/app
5. WhatsApp (Juan y María) + Zapier webhooks
6. Conectar todas las secciones de la UI
7. Presupuestos, cache y reporte semanal de Camila (cron de Railway)

## Archivos incluidos
- `IEA_AGENTIQ_Plataforma.html` — UI completa admin + cliente (referencia hi-fi, datos demo)
- `IEA_AGENTIQ_Landing_RESTAURADO.html` — landing pública
- `agents_config.json` — **fuente de verdad**: 16 agentes, prompts maestros, tools, routing, presupuestos, cost_policy
- `EQUIPO_ORIXAS_Y_CONEXION.md` — mapa del equipo + política de costos + guía Composio/Zapier
- `backend/` — FastAPI existente (models, schemas, database, main, import_agents, migración SQL)
