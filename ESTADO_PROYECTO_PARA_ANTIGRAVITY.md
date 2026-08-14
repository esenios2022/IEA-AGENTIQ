# Estado real de IEA AGENTIQ — para Antigravity

Este documento resume, con evidencia verificada (no supuesta), dónde está
parado el proyecto a 2026-08-14. Es la continuación de una auditoría previa
más una serie de fixes reales ya aplicados. Léelo entero antes de tocar
código — evita repetir trabajo de diagnóstico ya hecho.

## 0. Qué es este proyecto

Plataforma SaaS multi-agente (40 agentes de IA con nombre y rol fijo, ej.
Ariel = Social Media Manager, Clara = Marketing Strategy, Elías = Legal
Advisor). Primer cliente real en producción: **EALumina**
(`ealumina.com`), plataforma que conecta pacientes con terapeutas reales.
Instagram real: `@ealumina4444`, con Facebook Page también conectada.

- Repo: este mismo (`IEA-AGENTIQ`)
- Deploy: Railway, proyecto `charismatic-friendship`, servicio
  `IEA-AGENTIQ`, entorno `production` → `https://iea-agentiq.up.railway.app`
- Stack: FastAPI + SQLAlchemy + Postgres + Jinja2 (admin panel
  server-rendered) + CrewAI (orquestación) + Composio (integraciones
  externas)
- Verificar: `pytest tests/` (237 passed, 3 skipped a esta fecha)

## 1. Auditoría completa previa (leer primero)

Existe un documento de auditoría exhaustivo del sistema completo, hecho el
2026-08-13, que cubre: gestión de agentes, onboarding de clientes,
pipeline de marketing, facturación (inexistente), base de conocimiento
(RAG, rota por falta de `OPENAI_API_KEY`), agentes de terapia (sin
integraciones reales), aislamiento multi-tenant, infraestructura, y UX del
panel admin. Hallazgo central: **de 40 agentes definidos, solo 2
integraciones externas estuvieron conectadas alguna vez en toda la
historia del proyecto** (Instagram y Facebook de EALumina) — el resto son
definiciones sin herramientas reales detrás.

Ese documento vive fuera de este repo (carpeta temporal de la sesión que lo
generó). Si no lo tenés a mano, pedile el resumen a quien te haya dado este
archivo, o volvé a auditar esas mismas áreas antes de asumir que ya
funcionan.

## 2. Lo que se arregló DESPUÉS de esa auditoría (ya en producción)

Todo esto está commiteado y deployado, verificado contra producción real,
no solo contra tests:

1. **`3684f67`** — El publicador (`/admin/publicaciones`) usaba el UUID del
   cliente para buscar la conexión de Instagram/Facebook en Composio, en
   vez de `client.config["composio_user_id"]` (donde está la conexión
   real). Corregido con un helper único
   (`src/connectors/base.py::resolve_composio_user_id`). Se agregó también
   el conector de Facebook completo (`src/connectors/facebook.py`), que no
   existía.

2. **`9a9e98f`** — El panel `/admin/agents` mostraba 40+ tarjetas
   idénticas sin ninguna señal de actividad real. Ahora cada tarjeta
   muestra corridas reales (UsageLog), última ejecución, y piezas dejadas
   en la Biblioteca — verificado: de las tarjetas reales, la mayoría
   nunca corrió, el resto tiene entre 1 y 10 corridas reales.

3. **`38d4085`** — El chat en vivo de un agente (`/agentes/{agent_id}`,
   websocket) usaba `AgentRuntime` (charla pura, sin `tools` en absoluto).
   Ahora pasa por `agent_service.run()`, el mismo motor que el pipeline
   por lotes — **verificado real**: log muestra `Using Tool:
   library_search` ejecutándose de verdad en una conversación con
   historial. De paso se corrigió un bug real en el caché de respuestas
   (`src/agent_service.py`) que ignoraba `history` por completo y podía
   devolver respuestas viejas fuera de contexto.

4. **`844b6c5`** + **`055fa80`** — Intento de arreglar que el chat en vivo
   funcione contra producción real (no solo en tests). Se encontraron y
   corrigieron dos problemas reales de infraestructura (`--proxy-headers`
   para que Uvicorn resuelva bien la IP/host detrás del proxy de Railway;
   cambio de la librería `websockets` a `wsproto` porque la primera
   rechazaba con 403 cualquier conexión real, verificado en logs). **Estos
   dos fixes son correctos y están deployados, pero NO resolvieron el
   problema de fondo** — ver sección 3.

## 3. PROBLEMA ABIERTO, sin resolver — el más urgente para Antigravity

**Ningún websocket real (ni el chat de agentes, ni `/api/architect/chat`)
funciona hoy contra la URL pública de producción.** Verificado con dos
librerías Python distintas (`websocket-client` y `websockets`), con y sin
headers de Origin explícitos: todas las conexiones reales son rechazadas
con `403 Forbidden`, header `server: railway-hikari` — es decir, **el
rechazo pasa en el borde de Railway, no en la aplicación**.

Esto es un problema conocido y documentado por otros usuarios de Railway
(foro oficial "Railway Central Station"), no algo exclusivo de este
proyecto: `railway-hikari` (su proxy de borde) tiene reportes reales de
rechazar conexiones websocket con 403 (a veces con el mensaje
`host_not_allowed`) y de matar conexiones largas, independientemente de
cómo esté armado el backend.

**Confirmado que el código de la app está bien**: usando `TestClient` de
FastAPI (que ejercita la misma lógica ASGI sin pasar por el proxy de
Railway) todo funciona perfectamente, incluida la ejecución real de
herramientas dentro del chat.

**Dos caminos reales, ninguno ejecutado todavía:**

1. Contactar soporte de Railway con la evidencia de este documento (es su
   plataforma la que está rechazando la conexión).
2. Reescribir el chat de websocket a **Server-Sent Events (SSE)** —
   arquitectura que no depende de la parte de Railway que está fallando.
   Requiere tocar `src/main.py::agent_chat_socket` (y el equivalente de
   `architect_chat_socket`) y el JavaScript de
   `src/templates/agent_public_chat.html` (y `architect_chat.html`). No
   es una línea, es una reescritura real del mecanismo de transporte,
   pero el motor de ejecución de abajo (`agent_service.run()`) no cambia
   nada.

**Pedido concreto para Antigravity**: evaluar la opción 2 (SSE) —
diseñarla e implementarla si tiene sentido, o proponer una alternativa
mejor si la conoce. Verificar cualquier fix SIEMPRE contra la URL pública
real (`https://iea-agentiq.up.railway.app`), nunca solo con `TestClient`
ni solo localmente — ese fue exactamente el error que hizo que este
problema pasara desapercibido en la auditoría anterior.

## 4. Reglas de la casa (no romper estos patrones ya validados)

- Nunca reportar algo como "arreglado" sin verificarlo contra el sistema
  real (API real, servidor real desplegado, no un mock ni un supuesto).
- `client.config["composio_user_id"]` es la identidad real en Composio,
  casi nunca coincide con el UUID del cliente — usar siempre
  `resolve_composio_user_id()`.
- Cero nombres de cliente hardcodeados — todo parametrizado por
  `client_id`.
- Comentarios explican el *por qué*, no el *qué*, con fecha y evidencia
  concreta cuando documentan un fix real (mirar los commits de arriba
  como referencia de tono).
- `print(f"[modulo] ...", flush=True)` para diagnóstico, no `logging`.
- No tocar `agents_config.json`, `instagram_comment_automation.py`, ni la
  lógica interna de Composio sin que te lo pidan explícitamente.
- Commit local está bien; pushear/deployar a producción es una decisión
  del usuario, no asumirla en automático salvo que te lo pidan.
