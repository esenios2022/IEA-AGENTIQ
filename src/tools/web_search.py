"""Web search via Serper.dev — cheaper than SerpAPI, per the platform's cost policy.

Maps to the `web_search` tool id in agents_config.json.
"""

import requests
from crewai.tools import BaseTool

from src.config import settings

SEARCH_URL = "https://google.serper.dev/search"
REQUEST_TIMEOUT_SECONDS = 15
MAX_RESULTS = 5


class SerperSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Busca en la web información actual (mercado, competencia, normativa, tendencias)."

    def _run(self, query: str) -> str:
        if not settings.serper_api_key:
            return "Búsqueda no disponible: falta configurar SERPER_API_KEY."

        try:
            response = requests.post(
                SEARCH_URL,
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": query},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return f"Error buscando en la web: {exc}"

        data = response.json()
        results = data.get("organic", [])[:MAX_RESULTS]
        if not results:
            return "Sin resultados."

        lines = []
        for item in results:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            lines.append(f"- {title}: {snippet} ({link})")
        return "\n".join(lines)
