# IEA AGENTIQ - Arquitectura de LLMs Modulares

## 🎯 SISTEMA FLEXIBLE DE LLMs

Ahora puedes usar **cualquier LLM** que quieras, cuando quieras:

### Soportados:
- ✅ **OpenAI** (GPT-4, GPT-3.5)
- ✅ **Anthropic** (Claude)
- ✅ **Ollama** (Local: Llama 2, Mistral, etc)
- ✅ **Mistral API**
- ✅ **Google Gemini**
- ✅ **HuggingFace**

---

## 🚀 CÓMO USAR

### 1. Instalar dependencias
```bash
# Mínimo (Ollama local)
pip install -r requirements.txt

# Máximo (todos los proveedores)
pip install -r requirements_full.txt
```

### 2. Configurar en `.env`
```env
# Solo los que usarás
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Usar en API
```bash
# Ejecutar agente con OpenAI
curl -X POST http://localhost:8000/api/agents/agent_001/run?llm_provider=openai

# Ejecutar con Ollama (default)
curl -X POST http://localhost:8000/api/agents/agent_001/run?llm_provider=ollama

# Ejecutar con Claude
curl -X POST http://localhost:8000/api/agents/agent_001/run?llm_provider=claude

# Ver providers disponibles
curl http://localhost:8000/api/llm/providers
```

---

## 📊 ARQUITECTURA

```
┌─────────────────────────┐
│  FastAPI Endpoint       │
│  /api/agents/{id}/run   │
└────────────┬────────────┘
             │ llm_provider=?
             ▼
┌─────────────────────────┐
│  LLMFactory             │
│  (Selector dinámico)    │
└────────────┬────────────┘
             │
    ┌────────┼────────┬─────────┬──────────┐
    ▼        ▼        ▼         ▼          ▼
 OpenAI  Claude   Ollama    Mistral    Gemini
```

---

## 🔧 CONFIGURACIÓN POR AGENTE

Próximamente: Cada agente puede tener su LLM preferido:

```json
{
  "id": "agent_001",
  "name": "Inteligencia en Negocios",
  "llm_provider": "openai",  // default para este agente
  "llm_model": "gpt-4"       // modelo específico
}
```

---

## 💡 EJEMPLOS DE USO

### Desarrollo Local
```bash
ollama run llama2  # Gratis, sin API keys
```

### Producción
```bash
# Usa OpenAI o Anthropic con mejor calidad
llm_provider=openai
llm_provider=claude
```

### Testing
```bash
# Prueba con Ollama antes de pasar a paid
```

---

## ¿PRÓXIMOS PASOS?

1. ✅ Importar agentes a Supabase: `python import_agents.py`
2. ✅ Configurar tu LLM preferido en `.env`
3. ✅ Ejecutar: `uvicorn app.main:app --reload`
4. ✅ Dashboard conectado y funcional

**¿Vamos?**
