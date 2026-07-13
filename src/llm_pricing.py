"""Single source of truth for tier -> model mapping and USD cost calculation.

Pricing must be kept in sync with https://docs.anthropic.com/en/docs/about-claude/pricing
whenever Anthropic changes it — this is the only place it should live.
"""

TIER_MODELS = {
    "economy": "claude-haiku-4-5-20251001",
    "standard": "claude-sonnet-4-6",
    "premium": "claude-opus-4-8",
}

TIER_MAX_TOKENS = {
    "economy": 1024,
    "standard": 2048,
    "premium": 4096,
}

TIER_TEMPERATURE = {
    "economy": 0.3,
    "standard": 0.5,
    # "premium" (claude-opus-4-8) intentionally omitted: the API rejects an
    # explicit temperature for this model ("temperature is deprecated for
    # this model", confirmed via a real call) — see agent_executor.py, which
    # only sends temperature when TIER_TEMPERATURE.get(tier) is not None.
}

# USD per million tokens: (input, output)
PRICING_USD_PER_MTOK = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
}

DEFAULT_TIER = "economy"


def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = PRICING_USD_PER_MTOK.get(model, PRICING_USD_PER_MTOK[TIER_MODELS["standard"]])
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def next_tier(tier: str) -> str:
    """Escalation ladder: economy -> standard -> premium (clamped at premium)."""
    order = ["economy", "standard", "premium"]
    idx = order.index(tier) if tier in order else 0
    return order[min(idx + 1, len(order) - 1)]
