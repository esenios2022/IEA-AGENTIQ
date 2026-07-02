import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.agent_seed import sync_master_agents
from src.database import SessionLocal
from src.llm_pricing import calculate_cost_usd
from src.models import Agent, ResponseCache, UsageLog
from src.tiering import select_tier
from src.tools.postgres_query import PostgresQueryTool


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_agent(db):
    agent = Agent(
        id=uuid.uuid4(),
        name="TestAgent",
        role="Tester",
        description="Agente de prueba",
        definition={
            "instructions": {"system_prompt": "Sos un agente de prueba."},
            "tasks": [{"description": "Decí hola", "expected_output": "Un saludo"}],
            "tools": [],
            "llm_routing": {"default_tier": "economy", "escalate_to": "premium", "escalate_keywords": ["urgente"]},
        },
        daily_budget_usd=0.0002,
        status="active",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    yield agent
    db.query(UsageLog).filter(UsageLog.agent_id == agent.id).delete()
    db.query(ResponseCache).filter(ResponseCache.agent_id == agent.id).delete()
    db.delete(agent)
    db.commit()


def _fake_response(text="Hola!", input_tokens=50, output_tokens=20):
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp.content = [block]
    return resp


def test_calculate_cost_usd_basic():
    cost = calculate_cost_usd("claude-sonnet-4-6", 1000, 500)
    assert cost == pytest.approx(0.0105)


def test_select_tier_default_and_escalation(test_agent):
    tier, _ = select_tier(test_agent, "consulta normal")
    assert tier == "economy"

    tier, reason = select_tier(test_agent, "esto es urgente")
    assert tier == "premium"
    assert "urgente" in reason


def test_sync_master_agents_is_idempotent(db):
    result1 = sync_master_agents(db)
    assert result1.total == 16
    assert result1.created + result1.updated == 16

    result2 = sync_master_agents(db)
    assert result2.created == 0
    assert result2.updated == 16

    count = db.query(Agent).filter(Agent.agent_code.isnot(None)).count()
    assert count == 16


def test_agent_service_cache_and_budget(db, test_agent):
    import src.agent_service as agent_service

    with patch("src.agent_executor.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = _fake_response()

        outcome1 = agent_service.run(db, test_agent, extra_input="hola", user_id="tester")
        assert outcome1.cached is False
        assert outcome1.cost_usd > 0
        assert mock_anthropic.return_value.messages.create.call_count == 1

        outcome2 = agent_service.run(db, test_agent, extra_input="hola", user_id="tester")
        assert outcome2.cached is True
        assert outcome2.cost_usd == 0.0
        assert mock_anthropic.return_value.messages.create.call_count == 1

        mock_anthropic.return_value.messages.create.return_value = _fake_response(text="urgente atendido")
        agent_service.run(db, test_agent, extra_input="esto es urgente", user_id="tester")

        with pytest.raises(agent_service.AgentPausedError):
            agent_service.run(db, test_agent, extra_input="otra tarea distinta", user_id="tester")


def test_postgres_query_tool_guards():
    tool = PostgresQueryTool()
    assert "no se permiten" in tool.run(query="DELETE FROM agents").lower() or "error" in tool.run(
        query="DELETE FROM agents"
    ).lower()
    assert "no permitida" in tool.run(query="SELECT * FROM pg_shadow").lower()

    result = tool.run(query="SELECT COUNT(*) FROM agents")
    assert "error" not in result.lower()
