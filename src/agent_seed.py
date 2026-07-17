"""Idempotent import/sync of the 16 master agents from src/data/agents_config.json.

Never runs automatically on boot (would silently mutate DB state on every
restart) — triggered explicitly via `POST /admin/agents/import` or
`scripts/import_agents.py`. Safe to re-run: upserts by `agent_code`, updates
prompt/tools/budget on existing rows, never touches `ClientAgent` assignments
or Composio connection state.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Agent

CONFIG_PATH = Path(__file__).parent / "data" / "agents_config.json"

# Ids that are intentionally generic/unconnected markers, not concrete tools —
# same convention Obatalá already uses for toolkits that need manual setup.
_NO_AUTO_MAPPING = {"composio_toolkit", "webhooks", "supabase_storage"}

# Agents whose prompt explicitly says "check the knowledge base before reasoning"
# (María, Elías) get the zero-LLM-cost shortcut in src.agent_executor.
_KB_SHORTCUT_AGENT_CODES = {"agent_002", "agent_004"}


def _map_tool(tool_id: str) -> dict | None:
    if tool_id in _NO_AUTO_MAPPING:
        return None
    if tool_id.startswith("composio_"):
        return {"name": tool_id[len("composio_") :], "type": "composio"}
    if tool_id.startswith("zapier_"):
        return {"name": tool_id, "type": "zapier_webhook", "config": {"url": None}}
    if tool_id == "supabase_query":
        return {"name": "postgres_query", "type": "postgres_query"}
    if tool_id == "web_search":
        return {"name": "web_search", "type": "web_search"}
    if tool_id == "supabase_knowledge_base":
        return {"name": "knowledge_base", "type": "knowledge_base"}
    if tool_id == "testing_tools":
        return {"name": "testing_tools", "type": "testing_tools"}
    if tool_id == "library_search":
        return {"name": "library_search", "type": "library_search"}
    if tool_id == "library_save":
        return {"name": "library_save", "type": "library_save"}
    if tool_id == "gemini_image":
        return {"name": "gemini_image", "type": "gemini_image"}
    # heygen_api queda deliberadamente afuera: no hay una HeyGenTool real
    # todavia (decision del usuario 2026-07-17: no forzarlo para el Reel de
    # b-roll) -- mapearlo sin una tool real detras lo sacaria de
    # unmapped_tools (pierde la nota de "no conectada" en el prompt) sin
    # darle al agente una tool que de verdad funcione.
    if tool_id == "runway_api":
        return {"name": "runway_api", "type": "runway_api"}
    return None


def _to_definition(cfg: dict) -> dict:
    tool_ids = cfg.get("tools") or []
    mapped_tools = [t for t in (_map_tool(tid) for tid in tool_ids) if t is not None]
    unmapped_tools = [tid for tid in tool_ids if _map_tool(tid) is None]

    system_prompt = cfg["prompt"]
    if unmapped_tools:
        system_prompt += (
            f"\n\nNOTA DE CONEXIÓN: {', '.join(unmapped_tools)} todavía no están conectadas — "
            "avisá que falta que el admin las configure desde el panel si las necesitás para una tarea."
        )

    return {
        "instructions": {"system_prompt": system_prompt},
        "agents": [
            {
                "name": cfg["name"],
                "role": cfg["role"],
                "goal": cfg["goal"],
                "backstory": system_prompt,
            }
        ],
        "tasks": [
            {
                "name": f"tarea_{cfg['name'].lower()}",
                "description": cfg["goal"],
                "agent": cfg["name"],
                "expected_output": "Resultado según el objetivo y el formato de salida definidos en el prompt.",
            }
        ],
        "tools": mapped_tools,
        "unmapped_tools": unmapped_tools,
        "llm_routing": {
            "default_tier": cfg["llm_routing"]["default_tier"],
            "escalate_to": cfg["llm_routing"]["escalate_to"],
            "escalate_keywords": cfg["llm_routing"].get("escalate_keywords", []),
        },
        "language": cfg.get("language", "es"),
        "orixa": cfg.get("orixa"),
        "orixa_dominio": cfg.get("orixa_dominio"),
        "group": cfg.get("group"),
        "knowledge_base_shortcut": cfg["id"] in _KB_SHORTCUT_AGENT_CODES,
        "case_memory": bool(cfg.get("case_memory", False)),
    }


@dataclass
class SyncResult:
    created: int
    updated: int
    total: int


def load_master_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def sync_master_agents(db: Session) -> SyncResult:
    config = load_master_config()
    created = 0
    updated = 0

    for cfg in config["agents"]:
        definition = _to_definition(cfg)
        existing = db.scalar(select(Agent).where(Agent.agent_code == cfg["id"]))

        if existing is None:
            db.add(
                Agent(
                    agent_code=cfg["id"],
                    name=cfg["name"],
                    role=cfg["role"],
                    description=cfg["goal"],
                    definition=definition,
                    daily_budget_usd=cfg.get("daily_budget_usd"),
                    status="active",
                )
            )
            created += 1
        else:
            existing.name = cfg["name"]
            existing.role = cfg["role"]
            existing.description = cfg["goal"]
            existing.definition = definition
            existing.daily_budget_usd = cfg.get("daily_budget_usd")
            updated += 1

    db.commit()
    return SyncResult(created=created, updated=updated, total=created + updated)
