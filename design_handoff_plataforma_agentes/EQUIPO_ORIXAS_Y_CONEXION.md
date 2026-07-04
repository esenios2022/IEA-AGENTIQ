# IEA AGENTIQ — Equipo de Agentes v2 (Orixás Primordiales)

## El equipo (16 agentes)

| Nombre | Orixá | Función | Tier por defecto |
|---|---|---|---|
| Theo | Oxalá | Inteligencia de Negocios | economy |
| María | Iemanjá | Atención al Cliente | economy |
| Camila | Obá | Finanzas y Contabilidad (audita el gasto de todo el equipo) | economy |
| Elías | Xangô | Legal y Cumplimiento | standard (único con acceso a premium) |
| Lucas | Oxóssi | Prospección LinkedIn | economy |
| Ariel | Oxum | Redes Sociales | standard |
| Santiago | Ogum | Automatización de Flujos | economy |
| Bruno | Ibeji | Gestión de Proyectos | economy |
| Noa | Logunedé | Recursos Humanos | economy |
| Clara | Iansã | Estrategia de Marketing / Ads | standard |
| Juan | Exú | Ventas y WhatsApp | economy |
| Sofía | Nanã | Análisis de Datos | economy |
| Rafael | Ossain | SEO | economy |
| Gabriel | Oxumaré | Integraciones | economy |
| Valentina | Ewá | Diseño | economy |
| Miguel | Obaluaiê | Calidad (QA) | economy |

Todo está en `backend/agents_config.json` (v2). Importar a Supabase:

```bash
cd backend
python import_agents.py
```

## Política de costo mínimo (ya embebida en cada prompt)

1. **Ruteo por tiers**: economy (Haiku / gpt-4o-mini) por defecto; standard solo cuando el prompt lo justifica; premium solo Elías (legal de alto riesgo).
2. **Cache 24h** de respuestas repetidas (tabla `response_cache` en Supabase).
3. **Batch obligatorio**: calificar 50 leads = 1 llamada, no 50.
4. **Eventos, no polling**: los agentes despiertan por webhook (Composio triggers / Zapier), nunca por loops.
5. **Presupuesto diario por agente** (`daily_budget_usd`): al 80% degrada a economy, al 100% pausa y notifica.
6. **RAG top_k=3** con pgvector en Supabase — contexto mínimo, nunca documentos enteros.
7. **Camila audita**: reporte semanal de costo por agente + recomendaciones de recorte.

Costo estimado del equipo completo: presupuesto tope ~$26/día; en operación normal con estas reglas, mucho menos.

## Conexión de tools (para Railway)

### Variables de entorno en Railway
```
SUPABASE_URL=...
SUPABASE_KEY=...          # service_role para el backend
DATABASE_URL=...          # ya la tienen
COMPOSIO_API_KEY=...      # https://app.composio.dev → Settings → API Keys
ZAPIER_NLA_API_KEY=...    # https://actions.zapier.com (Zapier AI Actions)
ANTHROPIC_API_KEY=...     # tier economy/standard/premium
OPENAI_API_KEY=...        # opcional, fallback economy
SERPAPI_KEY=...           # búsqueda web (opcional al inicio)
```

### Composio (recomendado como capa principal)
1. Crear cuenta en composio.dev y obtener API key.
2. Crear una **entity** por agente (`theo`, `maria`, `juan`, ...) — así cada agente tiene sus propias conexiones OAuth.
3. Conectar apps por entity: Gmail, Google Calendar, Sheets, Drive, LinkedIn, Instagram, Twitter/X, Google Ads, Meta Ads, Search Console.
4. En el backend: `pip install composio-core` y pasar las tools al ejecutor del agente según el campo `tools` del JSON.

### Zapier
- **Webhooks (gratis)**: usar Zaps con "Webhooks by Zapier" apuntando a `POST /api/agents/{id}/run` en Railway — así un lead nuevo, un mensaje de WhatsApp o un formulario dispara al agente correcto.
- **Zapier AI Actions**: para acciones en apps que Composio no cubra.

### WhatsApp
Opciones: WhatsApp Business Cloud API (Meta, oficial) vía Composio/directo, o Twilio. María y Juan lo necesitan primero — priorizar esta conexión.

## Orden de encendido recomendado (menor costo, mayor impacto)
1. Supabase + import de agentes (ya casi listo)
2. Juan + María con WhatsApp → ventas y atención funcionando
3. Santiago + Gabriel → webhooks Zapier/Composio conectando todo
4. Lucas (LinkedIn) + Clara (ads con presupuesto test)
5. El resto del equipo
