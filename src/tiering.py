"""Deterministic (zero-LLM-cost) tier selection for an agent run.

Each master agent carries a short, hand-curated `escalate_keywords` list in
`definition["llm_routing"]` (derived from the free-text `escalate_when` in
agents_config.json). We do a cheap substring check against the run's input
instead of asking the model to judge its own tier — that would cost an extra
LLM call and defeats the point of cost-conscious routing.
"""

from src.llm_pricing import DEFAULT_TIER
from src.models import Agent

TIER_ORDER = ["economy", "standard", "premium"]


def select_tier(agent: Agent, extra_input: str | None) -> tuple[str, str]:
    """Returns (tier, reason)."""
    definition = agent.definition or {}
    routing = definition.get("llm_routing") or {}

    default_tier = routing.get("default_tier", DEFAULT_TIER)
    if default_tier not in TIER_ORDER:
        default_tier = DEFAULT_TIER

    escalate_to = routing.get("escalate_to")
    keywords = routing.get("escalate_keywords") or []

    if escalate_to in TIER_ORDER and keywords and extra_input:
        haystack = extra_input.lower()
        for keyword in keywords:
            if keyword.lower() in haystack:
                return escalate_to, f"escalado por palabra clave: «{keyword}»"

    return default_tier, "tier por defecto del agente"


def downgrade_to_economy(tier: str) -> str:
    return "economy"
