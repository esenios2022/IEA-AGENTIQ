# Despliegue IEA AGENTIQ (plataforma 100% funcional)

## Qué cambió
- **Backend nuevo** en `app/` (FastAPI): todos los endpoints reales — crear/editar/eliminar clientes y agentes, equipos, conocimiento (RAG básico), claves API en servidor, historial y reportes CSV reales, rentabilidad con precio de plan, ejecución de agentes con OpenAI/Anthropic/Gemini/Mistral/Ollama.
- **Frontend corregido** en `app/templates/plataforma.html`: todos los botones "(demo)" ahora llaman a la API real. Markdown renderizado en el chat, atribución de ejecuciones a cliente, filtro de razonamiento interno.
- Es **esquema-adaptativo**: al arrancar agrega a tu base (Supabase) solo las columnas que falten, sin borrar nada.

## Pasos en Railway (10 minutos)
1. En Railway: **New Service → Deploy from GitHub repo** → elegí `IEA-AGENTIQ`. (Recomendado: crear un servicio NUEVO primero para probar, sin tocar el actual.)
2. En Variables del servicio nuevo, copiá las del servicio viejo. Mínimo:
   - `DATABASE_URL` (la misma de siempre — así conservás los 41 agentes)
   - `ADMIN_USER` y `ADMIN_PASSWORD` (tu login de admin)
   - Las API keys de IA que uses: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY` u `OLLAMA_URL`
   - Opcional: `SECRET_KEY` (cualquier texto largo aleatorio)
3. Abrí `https://TU-SERVICIO.up.railway.app/plataforma` y verificá: login, agentes cargados, crear un cliente de prueba.
4. Si todo está bien: apuntá el dominio `iea-agentiq.up.railway.app` al servicio nuevo (Settings → Networking) y borrá el viejo.

## Local (opcional)
```
pip install -r requirements.txt
ADMIN_PASSWORD=miclave uvicorn app.main:app --reload
# http://localhost:8000/plataforma
```
