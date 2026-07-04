# Entry point de compatibilidad: Railway puede arrancar 'src.main:app'.
# Reexporta la app nueva definida en app/main.py, para que el servicio
# existente tome el backend v1.0 sin reconfigurar nada.
from app.main import app  # noqa: F401
