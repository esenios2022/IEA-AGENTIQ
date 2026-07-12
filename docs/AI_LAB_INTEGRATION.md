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
