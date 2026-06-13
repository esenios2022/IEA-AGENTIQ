# IEA-AGENTIQ

**IEA-AGENTIQ** es una plataforma de agentes inteligentes basada en IA, diseñada para automatizar tareas, procesar información y ejecutar flujos de trabajo de manera autónoma.

## Descripción

Este proyecto implementa un sistema de agentes inteligentes (AI Agents) orientado a resolver tareas complejas mediante la combinación de modelos de lenguaje, herramientas externas y flujos de trabajo configurables.

## Stack Tecnológico

- **Backend**: Python + [FastAPI](https://fastapi.tiangolo.com/)
- **Base de datos**: PostgreSQL
- **Caching**: Redis

## Características

- Arquitectura modular basada en agentes
- API REST construida con FastAPI
- Persistencia de datos con PostgreSQL
- Caching y manejo de tareas con Redis
- Configuración flexible mediante archivos YAML
- Integración con herramientas y APIs externas
- Suite de pruebas para garantizar la calidad del código

## Estructura del proyecto

```
IEA-AGENTIQ/
├── src/            # Código fuente principal
├── docs/           # Documentación del proyecto
├── tests/          # Pruebas unitarias e integración
├── config/         # Archivos de configuración
├── requirements.txt
├── setup.py
├── config.yaml
└── README.md
```

## Instalación

Cloná el repositorio e instalá las dependencias:

```bash
git clone https://github.com/esenios2022/IEA-AGENTIQ.git
cd IEA-AGENTIQ
pip install -r requirements.txt
```

## Configuración

Copiá `.env.example` a `.env` y ajustá las credenciales de **PostgreSQL**, **Redis** y del panel de administración.

```bash
cp .env.example .env
```

## Uso

### Con Docker Compose (recomendado)

Levanta la app, PostgreSQL y Redis con un solo comando:

```bash
docker compose up --build
```

La landing queda disponible en `http://localhost:8000`.

### Local

Ejecutá el servidor de desarrollo de FastAPI:

```bash
uvicorn src.main:app --reload
```

### Panel de leads

Los contactos enviados desde el formulario quedan guardados en PostgreSQL y son visibles en `/admin/leads` (requiere las credenciales `ADMIN_USER` / `ADMIN_PASSWORD` definidas en `.env`).

## Pruebas

Para ejecutar la suite de pruebas:

```bash
pytest tests/
```

## Contribuciones

Las contribuciones son bienvenidas. Por favor leé [CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar un pull request.

## Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.
