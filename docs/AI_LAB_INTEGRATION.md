# Integración con el AI LAB (FASE 2.1)

Este documento describe cómo IEA-AGENTIQ se conecta al **AI LAB
Service** (repositorio independiente `IEA-AGENTIQ-AI-LAB`, Sprint 26)
— la primera integración real entre el panel/control plane de
IEA-AGENTIQ y el motor de ejecución del AI LAB.

## Arquitectura

```
IEA-AGENTIQ (este repositorio, Railway)
        │
        │ src/ai_lab_client.py
        │ X-API-Key + X-Correlation-Id
        ▼
AI LAB Service (repositorio separado, FastAPI sobre PlatformBootstrap)
        │
        ▼
Workflow / Automation / Knowledge / Gateway / WhatsApp / Voice / Vision
```

IEA-AGENTIQ **no ejecuta IA directamente** contra el AI LAB — llama a
su API REST versionada (`/api/v1/*`) igual que cualquier otro cliente
externo lo haría. El AI LAB sigue siendo el único motor; este
repositorio administra empresas, usuarios, agentes y clientes, y
delega la ejecución de inteligencia al AI LAB cuando corresponde.

## `src/ai_lab_client.py`

El único cliente HTTP reutilizable hacia el AI LAB — cualquier
herramienta o endpoint nuevo que necesite hablar con el AI LAB debe
usar este cliente, nunca `requests` directo.

Incluye:
- **Autenticación**: header `X-API-Key`, leído de `settings.ai_lab_api_key`.
- **Correlation ID**: cada llamada genera un `X-Correlation-Id` real
  (`uuid4`), que el AI LAB Service's `CorrelationMiddleware` lee y
  propaga en sus propios logs — permite trazar una request de punta a
  punta entre los dos repositorios.
- **Retry**: hasta 2 reintentos con backoff (0.5s, 1s), solo ante
  errores de conexión/timeout o `5xx` — nunca ante `4xx` (esos son
  errores reales del llamador, reintentarlos no ayuda). Este repositorio
  no tenía ninguna librería ni convención de retry antes de esta
  integración — es un patrón genuinamente nuevo, no una reutilización.
- **Timeout**: 30s por defecto (cubre los tiempos reales medidos en el
  AI LAB Service: búsqueda de conocimiento ~2-4s, workflows ~2-5s).
- **Logging**: `print(f"[ai_lab_client] ...", flush=True)`, igual que
  el resto de este repositorio (que no usa el módulo `logging` en
  ningún lado).
- **Métricas**: un contador real y mínimo en memoria
  (`src.ai_lab_client.metrics`, `total_calls`/`total_errors`/
  `total_retries`/`average_latency_ms`) — este repositorio tampoco
  tenía ningún sistema de métricas propio.

## Configuración

Agregar a `.env` (o a las variables de entorno de Railway):

```bash
AI_LAB_BASE_URL=http://localhost:8000   # o la URL real del AI LAB Service desplegado
AI_LAB_API_KEY=<la misma API key configurada en el AI LAB Service, ver docs/AUTHENTICATION.md del repo AI LAB>
```

Ambas son opcionales (`None` por defecto) — si no están configuradas,
`AiLabClient` lanza `AiLabNotConfiguredError` de forma clara al primer
uso, en vez de fallar silenciosamente o con un error genérico de red.

## `AiLabKnowledgeSearchTool` — ejemplo de uso

La primera herramienta real construida sobre el cliente. Es
**aditiva**: `KnowledgeBaseTool` (el RAG propio de IEA-AGENTIQ, sobre
`KbArticle`) sigue funcionando exactamente igual, sin ningún cambio.
`AiLabKnowledgeSearchTool` es una fuente de conocimiento separada y
opcional — un agente la usa solo si su definición la incluye
explícitamente.

Para que un agente la use, agregar `"ai_lab_knowledge"` a su lista de
tools en la definición del agente:

```python
definition = {
    "tools": [
        {"name": "knowledge_base"},      # RAG propio de IEA-AGENTIQ, sin cambios
        {"name": "ai_lab_knowledge"},    # RAG del AI LAB (Qdrant, multi-tenant)
    ],
    ...
}
```

`src/tool_assembly.py::_matching_tools()` construye una instancia
nueva por agente, igual que ya hacía con `knowledge_base`, escopeada
al `tenant_id` real (el `user_id`/`Client.id` del cliente que está
corriendo el agente) — nunca la instancia compartida del registry.

Uso directo (fuera de un agente, para pruebas o debugging):

```python
from src.ai_lab_client import ai_lab_client

result = ai_lab_client.knowledge_search(
    tenant_id="acme",
    query="politica de vacaciones",
    max_results=5,
)
print(result["text"])       # contexto real recuperado del AI LAB
print(result["sources"])    # [{"chunk_id": ..., "score": ...}, ...]
```

## Verificación realizada (FASE 2.1)

- **Cambios puramente aditivos** — confirmado línea por línea en el
  diff antes del commit: `src/config.py` (2 campos opcionales nuevos),
  `src/tool_assembly.py` (nuevo parámetro opcional `user_id` en
  `_matching_tools()`, nueva rama `if name == "ai_lab_knowledge"`),
  `src/tools/registry.py` (nueva entrada). Cero líneas eliminadas o
  modificadas de comportamiento existente.
- **`KnowledgeBaseTool` permanece completamente intacto** — cero
  cambios a `src/tools/knowledge_base.py` (confirmado por `git status`).
- **12 tests nuevos**: 7 en `tests/test_ai_lab_client.py` (auth,
  correlation id, retry en error de conexión, retry en `5xx`, sin
  retry en `4xx`, métricas) mockeando `requests` en el límite —
  la misma convención que este repositorio ya usa para mockear el SDK
  de Anthropic — y 5 en `tests/test_ai_lab_knowledge_tool.py`
  (incluyendo el escopeo real de `tenant_id` vía `_matching_tools()`).
- **Prueba real de punta a punta** (`tests/test_real_ai_lab_service.py`,
  se salta automáticamente si `AI_LAB_BASE_URL`/`AI_LAB_API_KEY` no
  están configurados): contenido real ingerido en el AI LAB
  (Qdrant/Postgres reales) y recuperado exitosamente desde
  `AiLabClient` corriendo en este repositorio — round trip real de
  ~2.17s, `X-Correlation-Id` real, autenticación real.

**Nota honesta sobre la suite de pruebas completa**: la suite completa
de IEA-AGENTIQ no pudo ejecutarse porque el PostgreSQL local requerido
por este repositorio no estaba disponible (puerto 5432). Esta
limitación pertenece al entorno de desarrollo y no a los cambios
implementados en esta fase. Las pruebas específicas del cliente AI LAB
y la integración end-to-end con un AI LAB Service real fueron
ejecutadas satisfactoriamente.

## Qué no se hizo en esta fase (alcance deliberado)

- No se migró ningún agente existente a ejecutar tareas vía Workflow/
  Automation del AI LAB — esta fase construyó y probó únicamente el
  cliente reutilizable y una herramienta de Knowledge Search como
  prueba real de conexión.
- No se tocó `KnowledgeBaseTool` ni sus datos (`KbArticle`) — decisión
  arquitectónica explícita: agregar, medir, comparar, decidir después.
- No se conectó eAlumina — depende de tener acceso al repositorio real
  de eAlumina, que este agente todavía no tiene.

---

# FASE 2.2 — Ciclo de adquisición de pacientes (Lead → WhatsApp → estado)

**Objetivo de negocio, no solo técnico**: el `Lead` representa un
**paciente potencial** para eAlumina, no un contacto genérico — esta
fase construye el primer eslabón real de un sistema de adquisición de
pacientes para los terapeutas registrados, operado desde IEA-AGENTIQ
mientras no hay acceso al repositorio real de eAlumina (ver FASE 2.1).

## El flujo real

```
Lead nuevo (con telefono)
        │
        ▼
POST /api/leads  ──BackgroundTask──►  qualify_and_contact_lead()
        │                                      │
        │                          1. Clasificación real (AI LAB, AIRuntime)
        │                             lead.clasificacion_ia
        │                                      │
        │                          2. Mensaje de bienvenida real (AI LAB)
        │                                      │
        │                          3. Envío real por WhatsApp (AI LAB, Evolution API)
        │                                      │
        │                          4. LeadInteraction registrada (sent | failed)
        │                                      │
        └──────────────────────────► lead.estado = "contactado" (si tuvo éxito)
```

Cada paso de IA (clasificación y mensaje) corre como un `RUN_AGENT`
real dentro del AI LAB (`AiLabClient.generate_message()` →
`POST /api/v1/workflow/run`) — **IEA-AGENTIQ no genera texto por su
cuenta en este flujo**, siguiendo la regla arquitectónica explícita
("IEA AGENTIQ NO ejecuta IA"). El envío usa
`AiLabClient.whatsapp_send()` → `POST /api/v1/whatsapp/send`, el mismo
`WhatsAppGateway` real (Evolution API) del AI LAB.

## Modelo de datos — el Lead como paciente potencial

Campos agregados a `Lead` en esta fase, más allá de los de FASE 2.1:

| Campo | Qué representa |
|---|---|
| `tenant` | A qué cliente de IEA AGENTIQ pertenece este paciente potencial — `"ealumina"` hoy, mismo modelo sirve para Terra Araras u otros sin cambios de código |
| `idioma` | Idioma del paciente (default `"es"`) — usado para generar el mensaje en el idioma correcto |
| `tipo_terapia` | Categoría de terapia buscada (ej. "ansiedad", "terapia de pareja") — si no viene declarada, la clasificación IA la infiere |
| `disponibilidad` | Disponibilidad declarada para sesión |
| `clasificacion_ia` | Resultado real del paso de análisis IA — texto libre, ver limitación de formato más abajo |

**Deliberadamente NO implementado en esta fase — preparado, no
construido**: selección real de terapeuta. `AutomationRuntime`/
`WorkflowRuntime` podrían orquestar ese paso, pero necesita un
directorio real de terapeutas (idioma, especialidad, disponibilidad,
modalidad) que hoy vive en eAlumina — un repositorio al que este
agente todavía no tiene acceso (mismo bloqueo que motivó FASE 2.1 en
vez de una integración directa con eAlumina). Los campos de arriba
existen específicamente para que ese paso futuro tenga con qué
trabajar sin volver a tocar el modelo de datos.

## Canal de disparo — solo teléfono, por ahora

La automatización se dispara únicamente si el `Lead` trae `telefono`.
Esto es intencional para esta primera versión — según feedback
explícito del Arquitecto Principal, canales adicionales (Instagram DM,
formularios web dedicados, LinkedIn, Google Maps) son un paso futuro
real, no simulado aquí.

## Cómo probar el flujo completo

```bash
# 1. Levantar el AI LAB Service real (repo IEA-AGENTIQ-AI-LAB)
#    export AI_LAB_SERVICE_API_KEY=... && python -m service.server

# 2. En este repo, configurar .env:
#    AI_LAB_BASE_URL=http://localhost:8000
#    AI_LAB_API_KEY=<misma key>

# 3. Crear un lead con telefono — dispara la automatizacion automaticamente
curl -X POST http://localhost:8000/api/leads \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Maria",
    "email": "maria@example.com",
    "telefono": "5511999999999",
    "plan_interes": "ansiedad",
    "pais": "Brasil",
    "ciudad": "Sao Paulo",
    "disponibilidad": "tardes entre semana"
  }'

# 4. Ver el resultado real (clasificacion_ia, estado) en /admin/leads,
#    o consultar las interacciones registradas:
curl http://localhost:8000/api/leads/<id>/interactions

# 5. Para reintentar manualmente sin crear un lead nuevo:
curl -X POST http://localhost:8000/api/leads/<id>/qualify
```

Tests automatizados: `tests/test_lead_qualification.py` (5 unitarios,
mockean `ai_lab_client`) y `tests/test_real_lead_qualification.py`
(real, contra un AI LAB Service corriendo de verdad — se salta
automáticamente si `AI_LAB_BASE_URL`/`AI_LAB_API_KEY` no están
configurados).

## Verificación real realizada en esta fase

- **Loop completo probado contra infraestructura real**, no simulada:
  2 llamadas reales al AI LAB (clasificación + mensaje, ~2.4-5.8s cada
  una con `llama3.2` local) y un intento real de envío por WhatsApp.
- **Hallazgo honesto sobre el formato de clasificación**: el modelo
  local (`llama3.2`) no siempre respeta el formato estricto pedido
  (`tipo_terapia: X | urgencia: Y`) — en una corrida real devolvió
  `"Terapia de pareja: baja | urgencia: baja"`, un formato cercano
  pero no exacto. Funciona como texto libre legible para un humano
  revisando `/admin/leads`, pero **no es apto todavía para parsear
  programáticamente** (ej. para alimentar un futuro motor de selección
  de terapeuta automático) sin validación/reintento adicional — un
  hallazgo real, no una suposición, y un paso pendiente real si se
  quiere clasificación estructurada confiable.
- **El envío de WhatsApp falló en la prueba real** con el mismo
  hallazgo ya documentado en el AI LAB desde el Sprint 21: sin un
  número de WhatsApp emparejado (QR) en el entorno de Evolution API,
  el envío da timeout real. El código lo maneja correctamente —
  registra un `LeadInteraction` con `status="failed"` y deja
  `lead.estado` sin cambios, en vez de fallar silenciosamente o romper
  la creación del lead.
- **12 tests nuevos** (7 unitarios de `AiLabClient` + 5 de
  `lead_qualification`) más 2 reales (integración completa contra AI
  LAB real, y el ya existente de FASE 2.1) — 21 passed, 3 skipped
  (reales, se saltan sin un AI LAB Service corriendo).
- Misma limitación de entorno que FASE 2.1: la suite completa de
  IEA-AGENTIQ (`test_main.py`) no pudo ejecutarse por falta de
  PostgreSQL local (puerto 5432) en este entorno de desarrollo.

## Próximos pasos recomendados (no construidos en esta fase)

1. **Agente "Cazador de Pacientes"** (sugerido explícitamente por el
   Arquitecto Principal) — separado del agente de clasificación actual:
   uno recibe leads pasivamente, otro saldría a buscar pacientes
   activamente (redes sociales, Google Maps, formularios). Requiere su
   propio diseño, no es una extensión trivial de este flujo.
2. **Canales adicionales de entrada**: Instagram DM, formulario web
   dedicado, LinkedIn.
3. **Selección real de terapeuta** — bloqueada hasta tener acceso al
   directorio real de terapeutas de eAlumina.
4. **Clasificación estructurada confiable** — validar/reintentar el
   formato de `clasificacion_ia`, o pedir un modelo más grande
   (`model_hint`) para ese paso específico.
5. **Agenda real** — el último eslabón del flujo que describió el
   Arquitecto Principal (Lead → ... → terapeuta → agenda) no está
   construido; depende de 3 (selección de terapeuta) primero.
