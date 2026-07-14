"""ETAPA 4.1 — src.marketing_pipeline. Mismo convenio que
tests/test_editorial_calendar.py: Session MagicMock, se patchea
run_agent_service en el límite del módulo — no hay LLM real ni DB real
acá."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src import marketing_pipeline


def _client():
    return MagicMock(id="client-1", name="eAlumina")


# --- _build_prompt ---

def test_build_prompt_includes_previous_steps_as_context():
    client = _client()
    prompt = marketing_pipeline._build_prompt(client, "instrucción", [{"agent": "Daniel", "result": "hallazgos reales"}])
    assert "hallazgos reales" in prompt
    assert "Daniel" in prompt
    assert "library_search" in prompt  # BASE_INSTRUCTION siempre presente


def test_build_prompt_without_previous_steps_omits_material_section():
    client = _client()
    prompt = marketing_pipeline._build_prompt(client, "instrucción", [])
    assert "Material ya producido" not in prompt


# --- _saved_asset_since ---

def test_saved_asset_since_returns_asset_id_when_found():
    db = MagicMock()
    db.scalar.return_value = MagicMock(id="asset-123")
    result = marketing_pipeline._saved_asset_since(db, "agent-1", "client-1", MagicMock())
    assert result == "asset-123"


def test_saved_asset_since_returns_none_when_not_found():
    db = MagicMock()
    db.scalar.return_value = None
    result = marketing_pipeline._saved_asset_since(db, "agent-1", "client-1", MagicMock())
    assert result is None


# --- generate_weekly_marketing_content ---

def test_generate_weekly_marketing_content_client_not_found():
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(ValueError, match="no encontrado"):
        marketing_pipeline.generate_weekly_marketing_content(db, "missing")


def test_generate_weekly_marketing_content_raises_when_agent_missing():
    db = MagicMock()
    db.get.return_value = _client()
    db.scalar.return_value = None  # ningún agente encontrado

    with pytest.raises(RuntimeError, match="Daniel"):
        marketing_pipeline.generate_weekly_marketing_content(db, "client-1")


def test_generate_weekly_marketing_content_runs_all_6_agents_in_order():
    db = MagicMock()
    db.get.return_value = _client()
    agents = [MagicMock(agent_code=code, id=f"id-{code}") for code, _, _ in marketing_pipeline.PIPELINE]
    db.scalar.side_effect = agents

    fake_outcome = MagicMock(result="output", cost_usd=0.01)

    with patch("src.marketing_pipeline.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch.object(marketing_pipeline, "_saved_asset_since", return_value=uuid.uuid4()):
        result = marketing_pipeline.generate_weekly_marketing_content(db, "client-1")

    assert run_mock.call_count == 6
    assert [s["agent"] for s in result["steps"]] == ["Daniel", "Clara", "Ariel", "Valentina", "Marco", "Elena"]
    assert result["warnings"] == []
    assert all(s["saved_asset_id"] is not None for s in result["steps"])


def test_generate_weekly_marketing_content_passes_tier_override_to_every_call():
    db = MagicMock()
    db.get.return_value = _client()
    agents = [MagicMock(agent_code=code, id=f"id-{code}") for code, _, _ in marketing_pipeline.PIPELINE]
    db.scalar.side_effect = agents
    fake_outcome = MagicMock(result="output", cost_usd=0.01)

    with patch("src.marketing_pipeline.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch.object(marketing_pipeline, "_saved_asset_since", return_value=uuid.uuid4()):
        marketing_pipeline.generate_weekly_marketing_content(db, "client-1", tier_override="economy")

    for call in run_mock.call_args_list:
        assert call.kwargs["tier_override"] == "economy"


def test_generate_weekly_marketing_content_warns_when_an_agent_does_not_save():
    db = MagicMock()
    db.get.return_value = _client()
    agents = [MagicMock(agent_code=code, id=f"id-{code}") for code, _, _ in marketing_pipeline.PIPELINE]
    db.scalar.side_effect = agents

    fake_outcome = MagicMock(result="output", cost_usd=0.01)
    # Ariel (3er paso, index 2) no guarda nada esta vez -> None; el resto sí.
    side_effects = [uuid.uuid4(), uuid.uuid4(), None, uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    with patch("src.marketing_pipeline.run_agent_service", return_value=fake_outcome), \
         patch.object(marketing_pipeline, "_saved_asset_since", side_effect=side_effects):
        result = marketing_pipeline.generate_weekly_marketing_content(db, "client-1")

    assert len(result["warnings"]) == 1
    assert "Ariel" in result["warnings"][0]
    assert result["steps"][2]["saved_asset_id"] is None
    assert result["steps"][0]["saved_asset_id"] is not None
