"""Enrutamiento dinámico de proveedor para agentes sin herramientas
(hoy, los 8 del Departamento de Inteligencia Estratégica y Contextual —
Cosmos y sus especialistas).

Regla dura, no negociable: un agente con `tools` configuradas en su
`definition` SOLO puede correr en Claude — el ejecutor de Gemini
(`src/gemini_executor.py`) no manda `tools=` a la API, es chat puro.
Enrutarlo a Gemini de todos modos no degrada la calidad, directamente
ejecuta sin ninguna de sus herramientas y sin avisar.

Para un agente sin tools, el orden de preferencia es:
1. Gemini BYOK (key propia del cliente, guardada en
   `client.config["api_keys"]["gemini"]` vía el panel de admin) — costo
   real $0 para la plataforma (lo paga la cuenta de Google del cliente).
   Se prioriza primero porque representa una elección deliberada del
   cliente/admin, y su calidad (Gemini Flash) ya está validada en la
   comparación real del 2026-07-14.
2. Ollama local (2026-07-19, ver src/ollama_executor.py) — costo real
   $0 siempre (cómputo local, no es una API paga). Solo se ofrece si
   `is_ollama_reachable()` confirma que el servicio realmente responde
   ahora mismo (timeout corto) — si el backend corre en un host donde
   Ollama no está disponible (ej. Railway en producción), esto se
   detecta acá y cae a Claude sin intentar la llamada real.
3. Claude — fallback final, siempre disponible. Nunca se usa la key
   propia de Gemini de IEA-AGENTIQ acá: al precio real de
   `gemini-flash-latest` ($1.50/$9.00 por Mtok, ver llm_pricing.py) contra
   Claude Haiku economy ($1.00/$5.00 por Mtok), y con el consumo ~3.7x
   mayor de tokens de salida que Gemini mostró en la comparación real del
   2026-07-14 (ver memoria de esa fecha), pagar con la key de la
   plataforma sale más caro que Claude, no más barato — confirmado real,
   no negociado a la baja.
"""

from dataclasses import dataclass

from src.models import Agent, Client
from src.ollama_executor import is_ollama_reachable


@dataclass
class ProviderDecision:
    provider: str  # "claude" | "gemini" | "ollama"
    gemini_key: str | None
    platform_cost: bool
    reason: str


def select_provider(
    agent: Agent,
    client: Client | None,
    requested_gemini_key: str | None = None,
) -> ProviderDecision:
    """No hace ninguna llamada de red salvo el health check corto de Ollama
    (solo si no hay key BYOK de Gemini) — no llama nunca a la API real de
    ningún proveedor."""
    has_tools = bool((agent.definition or {}).get("tools"))

    if has_tools:
        if requested_gemini_key:
            raise ValueError(
                f"«{agent.name}» tiene herramientas configuradas; no puede enrutarse a "
                "Gemini (el ejecutor de Gemini no soporta tool-calling)."
            )
        return ProviderDecision("claude", None, True, "agente usa herramientas, Gemini no soporta tool-calling")

    byok_key = requested_gemini_key or ((client.config or {}).get("api_keys", {}).get("gemini") if client else None)
    if byok_key:
        return ProviderDecision(
            "gemini", byok_key, False, "sin herramientas + key BYOK del cliente disponible: costo $0 a la plataforma"
        )

    if is_ollama_reachable():
        return ProviderDecision("ollama", None, False, "sin key BYOK de Gemini, Ollama local disponible: costo $0")

    return ProviderDecision("claude", None, True, "sin key de Gemini del cliente ni Ollama disponible, usa tier de Claude")
