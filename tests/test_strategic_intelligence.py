"""FASE 3.0 — src.strategic_intelligence (orquestación del Departamento
Cosmos). Mismo convenio que tests/test_social_publishing.py: Session
MagicMock, se patchea run_agent_service y library.create_asset en el
límite del módulo — no hay LLM real ni DB real acá. Los datos "duros" de
cada especialista (astronomía, maya, etc.) SÍ corren de verdad (son
funciones puras, ya cubiertas por tests/test_cosmos_providers.py) porque
strategic_intelligence.py los llama directamente, sin mockearlos."""

from unittest.mock import MagicMock, patch

import pytest

from src import strategic_intelligence


def _client(**config):
    return MagicMock(id="client-1", name="eAlumina", config=config)


def test_generate_strategic_report_client_not_found():
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(ValueError, match="no encontrado"):
        strategic_intelligence.generate_strategic_report(db, "missing")


def test_generate_strategic_report_only_runs_enabled_sources():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia", "maya"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    maya_agent = MagicMock(agent_code="agent_040")
    coordinador_agent = MagicMock(agent_code="agent_046")
    db.scalar.side_effect = [astronomia_agent, maya_agent, coordinador_agent]

    fake_outcome = MagicMock(result="análisis de prueba")

    with patch("src.strategic_intelligence.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch("src.strategic_intelligence.library.create_asset", return_value=MagicMock()):
        strategic_intelligence.generate_strategic_report(db, "client-1")

    # 2 especialistas habilitados + 1 Coordinador — dreamspell/yoruba/etc.
    # (no habilitados) nunca deben correr.
    assert run_mock.call_count == 3


def test_generate_strategic_report_raises_when_no_sections_generated():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])
    db.scalar.return_value = None  # ningún agente encontrado en la DB

    with pytest.raises(ValueError, match="ninguna fuente"):
        strategic_intelligence.generate_strategic_report(db, "client-1")


def test_generate_strategic_report_skips_ancestral_when_no_modules_configured():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046")
    # Solo 2 valores: si el código llamara a db.scalar() una 3ra vez (p.ej.
    # para buscar el agente ancestral sin querer) esta lista se agota y
    # el test falla con StopIteration.
    db.scalar.side_effect = [astronomia_agent, coordinador_agent]

    with patch("src.strategic_intelligence.run_agent_service", return_value=MagicMock(result="ok")) as run_mock, \
         patch("src.strategic_intelligence.library.create_asset", return_value=MagicMock()):
        strategic_intelligence.generate_strategic_report(db, "client-1")

    assert run_mock.call_count == 2  # astronomía + coordinador, nunca ancestral


def test_generate_strategic_report_runs_ancestral_when_modules_configured():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"], ancestral_modules=["chamanismo"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    ancestral_agent = MagicMock(agent_code="agent_043")
    coordinador_agent = MagicMock(agent_code="agent_046")
    db.scalar.side_effect = [astronomia_agent, ancestral_agent, coordinador_agent]

    with patch("src.strategic_intelligence.run_agent_service", return_value=MagicMock(result="ok")) as run_mock, \
         patch("src.strategic_intelligence.library.create_asset", return_value=MagicMock()):
        strategic_intelligence.generate_strategic_report(db, "client-1")

    assert run_mock.call_count == 3


def test_generate_strategic_report_saves_library_asset_with_coordinador_output():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046", id="agent-coord-id")
    db.scalar.side_effect = [astronomia_agent, coordinador_agent]

    outcomes = [MagicMock(result="analisis astronomico"), MagicMock(result="informe final del coordinador")]
    fake_asset = MagicMock()

    with patch("src.strategic_intelligence.run_agent_service", side_effect=outcomes), \
         patch("src.strategic_intelligence.library.create_asset", return_value=fake_asset) as create_mock:
        result = strategic_intelligence.generate_strategic_report(db, "client-1")

    assert result is fake_asset
    kwargs = create_mock.call_args.kwargs
    assert kwargs["file_type"] == "informe"
    assert kwargs["status"] == "aprobado"
    assert kwargs["text_content"] == "informe final del coordinador"
    assert "astronomia" in kwargs["tags"]
    assert kwargs["created_by_agent_id"] == "agent-coord-id"


def test_generate_strategic_report_raises_when_coordinador_missing():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    db.scalar.side_effect = [astronomia_agent, None]  # coordinador no encontrado

    with patch("src.strategic_intelligence.run_agent_service", return_value=MagicMock(result="ok")):
        with pytest.raises(RuntimeError, match="Coordinador"):
            strategic_intelligence.generate_strategic_report(db, "client-1")
