"""Aggregation queries over `usage_log`, backing the admin/portal consumption UI."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.cost import get_daily_spend
from src.models import Agent, Client, UsageLog

PERIOD_DELTAS = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}


def _period_start(period: str, now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return now - PERIOD_DELTAS.get(period, PERIOD_DELTAS["day"])


def usage_by_agent(db: Session, period: str = "day", client_id=None) -> tuple[list[dict], float]:
    start = _period_start(period)

    query = (
        select(
            UsageLog.agent_id,
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("spend"),
            func.count().label("runs"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("tokens_in"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("tokens_out"),
        )
        .where(UsageLog.created_at >= start)
        .group_by(UsageLog.agent_id)
    )
    if client_id is not None:
        query = query.where(UsageLog.client_id == client_id)

    rows = db.execute(query).all()
    spend_by_agent = {row.agent_id: row for row in rows}

    agents_query = select(Agent)
    if client_id is not None:
        agents_query = agents_query.where(Agent.id.in_(spend_by_agent.keys()))
    agents = db.scalars(agents_query.order_by(Agent.name)).all()

    results = []
    total = 0.0
    for agent in agents:
        row = spend_by_agent.get(agent.id)
        spend_period = float(row.spend) if row else 0.0
        total += spend_period
        results.append(
            {
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "agent_code": agent.agent_code,
                "status": agent.status,
                "daily_budget_usd": agent.daily_budget_usd,
                "spend_today_usd": get_daily_spend(db, agent.id),
                "spend_period_usd": spend_period,
                "runs": int(row.runs) if row else 0,
                "tokens_in": int(row.tokens_in) if row else 0,
                "tokens_out": int(row.tokens_out) if row else 0,
            }
        )
    return results, total


def agent_usage_summary(db: Session, agent_id, period: str = "month") -> dict:
    start = _period_start(period)
    row = db.execute(
        select(
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("spend"),
            func.count().label("runs"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("tokens_in"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("tokens_out"),
        ).where(UsageLog.agent_id == agent_id, UsageLog.created_at >= start)
    ).one()
    return {
        "spend_today_usd": get_daily_spend(db, agent_id),
        "spend_period_usd": float(row.spend),
        "runs": int(row.runs),
        "tokens_in": int(row.tokens_in),
        "tokens_out": int(row.tokens_out),
    }


def profitability_by_client(db: Session, period: str = "month") -> tuple[list[dict], float]:
    start = _period_start(period)

    query = (
        select(
            UsageLog.client_id,
            func.coalesce(func.sum(UsageLog.cost_usd), 0).label("spend"),
            func.count().label("runs"),
        )
        .where(UsageLog.created_at >= start, UsageLog.client_id.isnot(None))
        .group_by(UsageLog.client_id)
    )
    rows = db.execute(query).all()
    spend_by_client = {row.client_id: row for row in rows}

    clients = db.scalars(select(Client).where(Client.id.in_(spend_by_client.keys())).order_by(Client.name)).all()

    results = []
    total = 0.0
    for client in clients:
        row = spend_by_client[client.id]
        spend = float(row.spend)
        total += spend
        results.append(
            {
                "client_id": str(client.id),
                "client_name": client.name,
                "spend_period_usd": spend,
                "runs": int(row.runs),
            }
        )
    return results, total
