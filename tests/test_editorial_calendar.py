"""FASE 3.1 — src.editorial_calendar. Mismo convenio que
tests/test_strategic_intelligence.py: Session MagicMock, se patchea
run_agent_service / library.create_asset en el límite del módulo. El
cálculo de fechas ancla, el parser del Coordinador y la tabla de
confianza son funciones puras reales, sin mocks."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src import editorial_calendar


def _client(**config):
    return MagicMock(id="client-1", name="eAlumina", config=config)


# --- _week_anchor_dates ---

def test_week_anchor_dates_are_7_days_apart():
    today = date(2026, 7, 13)
    dates = editorial_calendar._week_anchor_dates(today, 13)

    assert len(dates) == 13
    assert dates[0] == today
    assert dates[1] == date(2026, 7, 20)
    assert dates[-1] == date(2026, 10, 5)  # 12 semanas despues


# --- _batches ---

def test_batches_splits_13_weeks_into_5_5_3():
    dates = editorial_calendar._week_anchor_dates(date(2026, 7, 13), 13)
    batches = editorial_calendar._batches(dates, 5)

    assert [len(b) for b in batches] == [5, 5, 3]
    assert batches[0][0] == (1, dates[0])
    assert batches[-1][-1] == (13, dates[12])


def test_batches_single_batch_when_weeks_fit() :
    dates = editorial_calendar._week_anchor_dates(date(2026, 7, 13), 2)
    batches = editorial_calendar._batches(dates, 5)
    assert len(batches) == 1
    assert len(batches[0]) == 2


# --- _parse_coordinador_weeks ---

WELL_FORMED_TEXT = """Intro que el parser debe ignorar.

## SEMANA 1 (2026-07-13)
TEMA CENTRAL: Relaciones familiares
EVENTOS DESTACADOS: Luna creciente
ASPECTOS DE INTERÉS: Sol en Cáncer
EMOCIONES PREDOMINANTES: Calma
IDEAS DE CONTENIDO:
- Reel: Video corto sobre vínculos
- Carrusel: Tips de comunicación
- Video: Testimonio
- Email: Newsletter semanal
- Artículo: Blog post largo

## SEMANA 2 (2026-07-20)
TEMA CENTRAL: Sanación interior
EVENTOS DESTACADOS: Ninguno relevante
ASPECTOS DE INTERÉS: Venus en Virgo
EMOCIONES PREDOMINANTES: Introspección
IDEAS DE CONTENIDO:
- Reel: Meditación guiada
- Carrusel: Pasos para soltar
- Video: Entrevista
- Email: Tip semanal
- Artículo: Guía práctica
"""


def test_parse_coordinador_weeks_extracts_all_fields():
    anchor_dates = [date(2026, 7, 13), date(2026, 7, 20)]
    weeks = editorial_calendar._parse_coordinador_weeks(WELL_FORMED_TEXT, anchor_dates)

    assert len(weeks) == 2
    assert weeks[0]["week_number"] == 1
    assert weeks[0]["start_date"] == "2026-07-13"
    assert weeks[0]["tema_central"] == "Relaciones familiares"
    assert weeks[0]["aspectos_de_interes"] == "Sol en Cáncer"
    assert "Video corto sobre vínculos" in weeks[0]["ideas_de_contenido"]

    assert weeks[1]["week_number"] == 2
    assert weeks[1]["tema_central"] == "Sanación interior"
    assert weeks[1]["emociones_predominantes"] == "Introspección"


def test_parse_coordinador_weeks_tolerates_truncated_output():
    # Simula una respuesta cortada por max_tokens: solo llega la Semana 1
    # completa y la Semana 2 arranca pero sin campos — no debe explotar.
    truncated = WELL_FORMED_TEXT.split("## SEMANA 2")[0] + "## SEMANA 2 (2026-07-20)\nTEMA CENTRAL: Sana"
    anchor_dates = [date(2026, 7, 13), date(2026, 7, 20)]

    weeks = editorial_calendar._parse_coordinador_weeks(truncated, anchor_dates)

    assert len(weeks) == 2
    assert weeks[0]["tema_central"] == "Relaciones familiares"
    assert weeks[1]["tema_central"] == "Sana"
    assert weeks[1]["eventos_destacados"] is None  # nunca se inventa, se deja None


def test_parse_coordinador_weeks_returns_empty_list_when_format_not_followed():
    weeks = editorial_calendar._parse_coordinador_weeks("Un texto libre sin ningún encabezado de semana.", [date(2026, 7, 13)])
    assert weeks == []


# --- _confidence_table ---

def test_confidence_table_calculado_for_deterministic_sources():
    table = editorial_calendar._confidence_table(
        enabled_sources=["astronomia", "maya"],
        sections_ran={"astronomia", "maya"},
        ancestral_modules=[],
        ancestral_ran=False,
    )
    assert table["fuentes"]["Inteligencia Astronómica"] == "Calculado"
    assert table["fuentes"]["Inteligencia del Calendario Maya"] == "Calculado"
    assert table["nivel_global"] == "Alto"


def test_confidence_table_biodecoding_never_gets_a_percentage_label():
    table = editorial_calendar._confidence_table(
        enabled_sources=["biodecodificacion"],
        sections_ran={"biodecodificacion"},
        ancestral_modules=[],
        ancestral_ran=False,
    )
    label = table["fuentes"]["Inteligencia de Biodescodificación"]
    assert label == "Interpretación documental"
    assert "%" not in label


def test_confidence_table_missing_calculable_source_is_medio():
    table = editorial_calendar._confidence_table(
        enabled_sources=["astronomia", "maya"],
        sections_ran={"astronomia"},  # maya no corrio (agente no encontrado, etc.)
        ancestral_modules=[],
        ancestral_ran=False,
    )
    assert table["fuentes"]["Inteligencia del Calendario Maya"] == "No disponible"
    assert table["nivel_global"] == "Medio"


def test_confidence_table_tendencias_without_serper_key_is_medio():
    with patch.object(editorial_calendar.settings, "serper_api_key", None):
        table = editorial_calendar._confidence_table(
            enabled_sources=["tendencias"],
            sections_ran={"tendencias"},
            ancestral_modules=[],
            ancestral_ran=False,
        )
    assert "no disponible" in table["fuentes"]["Inteligencia de Tendencias Sociales"].lower()
    assert table["nivel_global"] == "Medio"


def test_confidence_table_tendencias_with_serper_key_is_alto():
    with patch.object(editorial_calendar.settings, "serper_api_key", "fake-key-for-test"):
        table = editorial_calendar._confidence_table(
            enabled_sources=["tendencias"],
            sections_ran={"tendencias"},
            ancestral_modules=[],
            ancestral_ran=False,
        )
    assert "configurada" in table["fuentes"]["Inteligencia de Tendencias Sociales"].lower()
    assert table["nivel_global"] == "Alto"


def test_confidence_table_ancestral_active_module():
    table = editorial_calendar._confidence_table(
        enabled_sources=[], sections_ran=set(), ancestral_modules=["chamanismo"], ancestral_ran=True,
    )
    assert table["fuentes"]["Inteligencia de Tradiciones Ancestrales"] == "Documental (módulo activo)"


def test_confidence_table_ancestral_not_configured():
    table = editorial_calendar._confidence_table(
        enabled_sources=[], sections_ran=set(), ancestral_modules=[], ancestral_ran=False,
    )
    assert table["fuentes"]["Inteligencia de Tradiciones Ancestrales"] == "No disponible"


# --- generate_editorial_calendar (orquestacion) ---

def test_generate_editorial_calendar_client_not_found():
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(ValueError, match="no encontrado"):
        editorial_calendar.generate_editorial_calendar(db, "missing")


def test_generate_editorial_calendar_only_runs_enabled_sources():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046", id="agent-coord-id")
    db.scalar.side_effect = [astronomia_agent, coordinador_agent]

    fake_outcome = MagicMock(result=WELL_FORMED_TEXT)

    with patch("src.editorial_calendar.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch("src.editorial_calendar.library.create_asset", return_value=MagicMock()) as create_mock:
        result = editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=2)

    assert run_mock.call_count == 2  # 1 especialista + coordinador
    kwargs = create_mock.call_args.kwargs
    assert kwargs["file_type"] == "calendario_editorial"
    assert kwargs["structured_content"]["weeks_requested"] == 2
    assert len(kwargs["structured_content"]["weeks"]) == 2
    assert "confidence" in kwargs["structured_content"]
    assert result is create_mock.return_value


def test_generate_editorial_calendar_batches_coordinador_calls_for_13_weeks():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046", id="agent-coord-id")
    db.scalar.side_effect = [astronomia_agent, coordinador_agent]

    fake_outcome = MagicMock(result=WELL_FORMED_TEXT)

    with patch("src.editorial_calendar.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch("src.editorial_calendar.library.create_asset", return_value=MagicMock()):
        editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=13)

    # 1 especialista + 3 lotes del coordinador (5+5+3 semanas, ver COORDINADOR_BATCH_WEEKS) = 4 llamadas
    assert run_mock.call_count == 4


def test_generate_editorial_calendar_raises_when_no_sections_generated():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])
    db.scalar.return_value = None

    with pytest.raises(ValueError, match="ninguna fuente"):
        editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=2)


def test_generate_editorial_calendar_raises_when_coordinador_missing():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    db.scalar.side_effect = [astronomia_agent, None]

    with patch("src.editorial_calendar.run_agent_service", return_value=MagicMock(result="ok")):
        with pytest.raises(RuntimeError, match="Coordinador"):
            editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=2)
