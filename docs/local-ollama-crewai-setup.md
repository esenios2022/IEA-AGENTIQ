# Entorno local: CrewAI + Ollama (referencia)

Configuración local verificada por el usuario, a usar como referencia cuando se creen agentes
para ejecución **local** en su PC (Windows), en contraste con agentes pensados para una
**plataforma/servicio** (con API keys, deploy remoto, etc.).

## Entorno verificado (PC local, Windows 11)

- Usuario: `paint`, directorio: `C:\Users\paint`
- Python 3.12.10
- Virtual environment: `C:\Users\paint\venv` (activar con `C:\Users\paint\venv\Scripts\Activate.ps1`)
- pip 26.1.1
- CrewAI 1.14.7 (`crewai`, `crewai-cli`, `crewai-core`, `crewai-tools`)
- `langchain-ollama` 1.1.0, `langchain-core` 1.4.8
- Ollama v0.6.2 corriendo en `http://localhost:11434`

## Modelos disponibles en Ollama

- `hermes3:latest` (4.7 GB) — **probado y funcionando**
- `gemma3:4b` (3.3 GB)
- `llama3.2:latest` (2.0 GB)

## Script de conexión verificado

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="hermes3",
    base_url="http://localhost:11434",
    temperature=0.7
)

response = llm.invoke("Hola, ¿cómo estás?")
print(response.content)
```

## Puntos clave para diseñar agentes "locales"

- Todo corre en `C:\Users\paint`, sin necesidad de API keys (Ollama es local) ni internet.
- Modelo por defecto a usar: `hermes3` vía `http://localhost:11434`.
- Conectar Python↔Ollama con `langchain-ollama`.
- CrewAI 1.14.7 tiene limitaciones conocidas con la validación de LLM — tenerlo en cuenta al
  definir agentes/tasks.
- Scripts se ejecutan desde PowerShell, con el venv activado antes de correr cualquier script.

## Cuándo aplica esta config vs. una plataforma remota

- **Local (este documento)**: agentes que deben correr en el PC del usuario, sin servicios
  externos, usando Ollama + CrewAI tal como está instalado arriba.
- **Plataforma/remoto**: si el agente se va a desplegar en un servicio (cloud, API con keys,
  contenedor remoto, etc.), esta configuración de Ollama local NO aplica directamente — habrá
  que definir el LLM provider, credenciales y entorno de ejecución correspondientes al deploy
  real, no asumir `localhost:11434`.
