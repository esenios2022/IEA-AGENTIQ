import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.agent_seed import sync_master_agents
from src.database import SessionLocal
from src.llm_pricing import calculate_cost_usd
from src.models import Agent, Client, LibraryAsset, ResponseCache, UsageLog
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
    from src.agent_seed import load_master_config

    expected_total = len(load_master_config()["agents"])

    result1 = sync_master_agents(db)
    assert result1.total == expected_total
    assert result1.created + result1.updated == expected_total

    result2 = sync_master_agents(db)
    assert result2.created == 0
    assert result2.updated == expected_total

    count = db.query(Agent).filter(Agent.agent_code.isnot(None)).count()
    assert count == expected_total


def test_agent_service_cache_and_budget(db, test_agent):
    import time

    import src.agent_service as agent_service

    def _slow_fake_response(*args, **kwargs):
        # Simula tiempo real de red/inferencia — sin esto, la llamada mockeada
        # es tan instantánea que duration_ms redondea a 0.00 (Numeric(10,2))
        # y no distingue una ejecución real de una omitida.
        time.sleep(0.01)
        return _fake_response()

    with patch("src.agent_executor.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.side_effect = _slow_fake_response

        outcome1 = agent_service.run(db, test_agent, extra_input="hola", user_id="tester")
        assert outcome1.cached is False
        assert outcome1.cost_usd > 0
        assert mock_anthropic.return_value.messages.create.call_count == 1
        # Modo Producción — cada ejecución real registra su tiempo de ejecución (UsageLog.duration_ms)
        log1 = db.query(UsageLog).filter(UsageLog.agent_id == test_agent.id, UsageLog.cached.is_(False)).one()
        assert log1.duration_ms > 0
        # 2026-07-14 — provider explícito, nunca inferido de tier/model en tiempo de consulta
        assert log1.provider == "claude"

        outcome2 = agent_service.run(db, test_agent, extra_input="hola", user_id="tester")
        assert outcome2.cached is True
        assert outcome2.cost_usd == 0.0
        assert mock_anthropic.return_value.messages.create.call_count == 1
        # un cache hit no ejecuta nada real -> duration_ms=0, nunca inventado
        log2 = db.query(UsageLog).filter(UsageLog.agent_id == test_agent.id, UsageLog.cached.is_(True)).one()
        assert log2.duration_ms == 0

        mock_anthropic.return_value.messages.create.return_value = _fake_response(text="urgente atendido")
        agent_service.run(db, test_agent, extra_input="esto es urgente", user_id="tester")

        with pytest.raises(agent_service.AgentPausedError):
            agent_service.run(db, test_agent, extra_input="otra tarea distinta", user_id="tester")


def test_agent_service_gemini_byok_records_real_tokens_but_zero_platform_cost(db, test_agent):
    """Modo Producción — antes esta rama no llamaba record_usage() en
    absoluto: una corrida real en Gemini quedaba invisible para
    /admin/usage. Ahora sí se registra, con cost_usd=0 (BYOK, lo paga la
    cuenta del cliente) pero tokens/tiempo reales."""
    import src.agent_service as agent_service
    from src.exec_result import ExecResult

    fake_exec_result = ExecResult(text="Respuesta real de Gemini.", model="gemini-flash-latest", input_tokens=20, output_tokens=180)

    with patch("src.gemini_executor.run_gemini", return_value=fake_exec_result):
        outcome = agent_service.run(db, test_agent, extra_input="hola", user_id="tester", gemini_key="fake-key")

    assert outcome.cost_usd == 0.0
    assert outcome.tier_used == "gemini-byok"

    log = db.query(UsageLog).filter(UsageLog.agent_id == test_agent.id, UsageLog.tier == "gemini-byok").one()
    assert log.model == "gemini-flash-latest"
    assert log.input_tokens == 20
    assert log.output_tokens == 180
    assert float(log.cost_usd) == 0.0
    assert log.duration_ms >= 0
    assert log.provider == "gemini"


def test_agent_service_gemini_platform_key_records_real_cost(db, test_agent):
    """2026-07-14 — cuando la key es la propia de IEA-AGENTIQ (no BYOK del
    cliente), platform_cost=True hace que el gasto real en Gemini entre al
    cost-tracking de la plataforma (provider=gemini, cost_usd>0), en vez de
    quedar invisible en $0 como en el caso BYOK."""
    import src.agent_service as agent_service
    from src.exec_result import ExecResult

    fake_exec_result = ExecResult(text="Calendario real.", model="gemini-flash-latest", input_tokens=1000, output_tokens=1000)

    with patch("src.gemini_executor.run_gemini", return_value=fake_exec_result):
        outcome = agent_service.run(
            db, test_agent, extra_input="generá el calendario", user_id="tester", gemini_key="platform-key", platform_cost=True
        )

    assert outcome.cost_usd > 0.0

    log = db.query(UsageLog).filter(UsageLog.agent_id == test_agent.id, UsageLog.tier == "gemini-platform").one()
    assert log.provider == "gemini"
    assert float(log.cost_usd) == pytest.approx((1000 * 1.50 + 1000 * 9.00) / 1_000_000)


def test_agent_service_populates_content_asset_id_when_agent_saves_to_library(db, test_agent):
    """2026-07-14 — si el agente guarda un LibraryAsset durante su ejecución
    (vía library_save), el UsageLog de esa misma ejecución debe quedar
    vinculado a ese asset — necesario para responder "cuánto costó esta
    publicación" sin adivinar."""
    import src.agent_service as agent_service

    client = Client(name="Cliente de prueba content_asset_id", email=f"asset-link-{uuid.uuid4()}@test.local", password_hash="x")
    db.add(client)
    db.commit()
    db.refresh(client)

    try:
        with patch("src.agent_executor.Anthropic") as mock_anthropic:
            def _save_asset_then_respond(*args, **kwargs):
                asset = LibraryAsset(
                    client_id=client.id,
                    category="Documentación",
                    subcategory=None,
                    title="Pieza de prueba",
                    file_type="texto",
                    storage_key="",
                    created_by_agent_id=test_agent.id,
                    status="borrador",
                )
                db.add(asset)
                db.commit()
                return _fake_response()

            mock_anthropic.return_value.messages.create.side_effect = _save_asset_then_respond
            agent_service.run(db, test_agent, extra_input="guardá algo", user_id="tester", client_id=client.id)

        log = db.query(UsageLog).filter(UsageLog.agent_id == test_agent.id, UsageLog.client_id == client.id).one()
        saved_asset = db.query(LibraryAsset).filter(LibraryAsset.client_id == client.id).one()
        assert log.content_asset_id == saved_asset.id
    finally:
        db.query(UsageLog).filter(UsageLog.client_id == client.id).delete()
        db.query(LibraryAsset).filter(LibraryAsset.client_id == client.id).delete()
        db.delete(client)
        db.commit()


def test_usage_by_department_groups_by_agent_definition_group(db, test_agent):
    from src.cost import record_usage
    from src.models import Client
    from src.usage_reports import usage_by_department

    client = Client(name="Cliente de prueba departamento", email=f"dept-test-{uuid.uuid4()}@test.local", password_hash="x")
    db.add(client)
    db.commit()
    db.refresh(client)
    try:
        record_usage(
            db, agent_id=test_agent.id, client_id=client.id, execution_id=uuid.uuid4(),
            model="claude-haiku-4-5-20251001", tier="economy", input_tokens=100, output_tokens=50,
        )

        rows, total = usage_by_department(db, client.id, period="day")

        assert total > 0
        # test_agent no tiene "group" en su definition -> cae en el fallback, nunca se inventa un departamento
        assert rows[0]["department"] == "Sin departamento"
        assert rows[0]["runs"] == 1
    finally:
        db.query(UsageLog).filter(UsageLog.client_id == client.id).delete()
        db.delete(client)
        db.commit()


def test_postgres_query_tool_guards():
    tool = PostgresQueryTool()
    assert "no se permiten" in tool.run(query="DELETE FROM agents").lower() or "error" in tool.run(
        query="DELETE FROM agents"
    ).lower()
    assert "no permitida" in tool.run(query="SELECT * FROM pg_shadow").lower()

    result = tool.run(query="SELECT COUNT(*) FROM agents")
    assert "error" not in result.lower()
