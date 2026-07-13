"""Registro de proveedores por especialista — mismo patrón que
src/tools/registry.py y src/connectors/registry.py. Swappear un proveedor
(ej. otra fuente astronómica) es cambiar esta entrada, sin tocar
agentes, prompts ni el orquestador."""

from src.cosmos.providers.astronomy import AstronomyEngineProvider
from src.cosmos.providers.biodecoding import CuratedBiodecodingProvider
from src.cosmos.providers.dreamspell import ClassicDreamspellProvider
from src.cosmos.providers.maya import GMTCorrelationProvider
from src.cosmos.providers.yoruba import TraditionalYorubaProvider

DEFAULT_PROVIDERS = {
    "astronomia": AstronomyEngineProvider(),
    "astrologia": AstronomyEngineProvider(),  # Astrología reutiliza los mismos datos reales de Astronomía
    "maya": GMTCorrelationProvider(),
    "dreamspell": ClassicDreamspellProvider(),
    "yoruba": TraditionalYorubaProvider(),
    "biodecodificacion": CuratedBiodecodingProvider(),
    # "ancestral" no tiene un provider único acá — se resuelve por módulo,
    # ver src/cosmos/providers/ancestral.py::get_active_modules().
    # "tendencias" no usa un provider de este departamento — reutiliza la
    # tool web_search ya existente (SerperSearchTool), asignada directo al
    # agente en agents_config.json, sin capa extra.
}
