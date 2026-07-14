"""FASE 3.1/3.2A — src.editorial_calendar. Mismo convenio que
tests/test_strategic_intelligence.py: Session MagicMock, se patchea
run_agent_service / library.create_asset en el límite del módulo. El
cálculo de fechas ancla, el parser del Coordinador, la tabla de confianza
y el armado del marketing_brief son funciones puras reales, sin mocks."""

from datetime import date, timedelta
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


def test_batches_single_batch_when_weeks_fit():
    dates = editorial_calendar._week_anchor_dates(date(2026, 7, 13), 2)
    batches = editorial_calendar._batches(dates, 5)
    assert len(batches) == 1
    assert len(batches[0]) == 2


# --- _split_list_field ---

def test_split_list_field_splits_on_commas_and_trims():
    assert editorial_calendar._split_list_field("a, b ,  c") == ["a", "b", "c"]


def test_split_list_field_empty_for_none_or_blank():
    assert editorial_calendar._split_list_field(None) == []
    assert editorial_calendar._split_list_field("") == []


# --- _build_marketing_brief ---

def test_build_marketing_brief_derives_canales_from_populated_ideas_fields():
    week = {
        "tema_central": "Tema",
        "audiencia": "Adultos",
        "objetivo_principal": "educar",
        "llamado_a_la_accion": "Reservá",
        "prioridad": "ALTA",
        "ideas_instagram": "algo",
        "ideas_facebook": None,
        "ideas_linkedin": "algo",
        "ideas_youtube": None,
        "ideas_email": "algo",
    }
    brief = editorial_calendar._build_marketing_brief(week)

    assert brief == {
        "tema": "Tema",
        "audiencia": "Adultos",
        "objetivo": "educar",
        "cta": "Reservá",
        "canales": ["Instagram", "LinkedIn", "Email"],
        "urgencia": "ALTA",
    }


def test_build_marketing_brief_empty_canales_when_no_ideas_populated():
    week = {"tema_central": "Tema", "audiencia": None, "objetivo_principal": None, "llamado_a_la_accion": None, "prioridad": None}
    brief = editorial_calendar._build_marketing_brief(week)
    assert brief["canales"] == []


# --- _parse_coordinador_weeks (esquema extendido FASE 3.2A: 16 campos) ---

WELL_FORMED_TEXT = """Intro que el parser debe ignorar.

## SEMANA 1 (2026-07-13)
TEMA CENTRAL: Relaciones familiares
EVENTOS DESTACADOS: Luna creciente
ASPECTOS DE INTERÉS: Sol en Cáncer
EMOCIONES PREDOMINANTES: Calma
PRIORIDAD: ALTA
OBJETIVO PRINCIPAL: captar pacientes
AUDIENCIA: Adultos 30-50
HASHTAGS: #familia, #vinculos, #sanacion
PALABRAS CLAVE: relaciones, limites, reconciliacion
TERAPIAS RELACIONADAS: ThetaHealing, Terapia Multidimensional
LLAMADO A LA ACCIÓN: Reservá tu sesión
IDEAS INSTAGRAM: Reel sobre vínculos
IDEAS FACEBOOK: Post de comunidad
IDEAS LINKEDIN: Artículo profesional
IDEAS YOUTUBE: Video largo
IDEAS EMAIL: Newsletter semanal

## SEMANA 2 (2026-07-20)
TEMA CENTRAL: Sanación interior
EVENTOS DESTACADOS: Ninguno relevante
ASPECTOS DE INTERÉS: Venus en Virgo
EMOCIONES PREDOMINANTES: Introspección
PRIORIDAD: MEDIA
OBJETIVO PRINCIPAL: educar
AUDIENCIA: Mujeres 25-45
HASHTAGS: #sanacion, #bienestar
PALABRAS CLAVE: introspeccion, calma
TERAPIAS RELACIONADAS: EMF Balancing Technique
LLAMADO A LA ACCIÓN: Agendá tu consulta
IDEAS INSTAGRAM: Carrusel de tips
IDEAS FACEBOOK: Post breve
IDEAS LINKEDIN: Nota profesional
IDEAS YOUTUBE: Short
IDEAS EMAIL: Tip semanal
"""


def test_parse_coordinador_weeks_extracts_all_fields():
    anchor_dates = [date(2026, 7, 13), date(2026, 7, 20)]
    weeks = editorial_calendar._parse_coordinador_weeks(WELL_FORMED_TEXT, anchor_dates)

    assert len(weeks) == 2
    week1 = weeks[0]
    assert week1["week_number"] == 1
    assert week1["start_date"] == "2026-07-13"
    assert week1["tema_central"] == "Relaciones familiares"
    assert week1["aspectos_de_interes"] == "Sol en Cáncer"
    assert week1["prioridad"] == "ALTA"
    assert week1["objetivo_principal"] == "captar pacientes"
    assert week1["audiencia"] == "Adultos 30-50"
    assert week1["hashtags"] == ["#familia", "#vinculos", "#sanacion"]
    assert week1["palabras_clave"] == ["relaciones", "limites", "reconciliacion"]
    assert week1["terapias_relacionadas"] == ["ThetaHealing", "Terapia Multidimensional"]
    assert week1["llamado_a_la_accion"] == "Reservá tu sesión"
    assert week1["ideas_instagram"] == "Reel sobre vínculos"
    assert week1["ideas_facebook"] == "Post de comunidad"
    assert week1["ideas_linkedin"] == "Artículo profesional"
    assert week1["ideas_youtube"] == "Video largo"
    assert week1["ideas_email"] == "Newsletter semanal"
    assert week1["marketing_brief"]["canales"] == ["Instagram", "Facebook", "LinkedIn", "YouTube", "Email"]
    assert week1["marketing_brief"]["urgencia"] == "ALTA"

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
    assert weeks[1]["hashtags"] == []  # campo lista faltante -> lista vacia, nunca inventada


def test_parse_coordinador_weeks_returns_empty_list_when_format_not_followed():
    weeks = editorial_calendar._parse_coordinador_weeks("Un texto libre sin ningún encabezado de semana.", [date(2026, 7, 13)])
    assert weeks == []


# --- _run_coordinador_batches (retry real de produccion: el Coordinador a
# veces ignora el formato pedido y vuelve a su formato de 7 preguntas) ---

def test_run_coordinador_batches_retries_on_malformed_output_then_succeeds():
    db = MagicMock()
    client = _client()
    coordinador = MagicMock(id="coord-1")
    dates = [date(2026, 7, 13), date(2026, 7, 20)]

    bad_output = MagicMock(result="Informe en el formato viejo de 7 preguntas, sin encabezados de semana.")
    good_output = MagicMock(result=WELL_FORMED_TEXT)

    with patch("src.editorial_calendar.run_agent_service", side_effect=[bad_output, good_output]) as run_mock:
        weeks = editorial_calendar._run_coordinador_batches(db, coordinador, [("Fuente", "texto")], client, dates, "client-1")

    assert run_mock.call_count == 2
    assert len(weeks) == 2
    second_call_prompt = run_mock.call_args_list[1].args[2]
    assert editorial_calendar.RETRY_PREFIX in second_call_prompt


def test_run_coordinador_batches_raises_after_max_attempts_never_saves_partial_calendar():
    db = MagicMock()
    client = _client()
    coordinador = MagicMock(id="coord-1")
    dates = [date(2026, 7, 13), date(2026, 7, 20)]

    bad_output = MagicMock(result="Informe en el formato viejo de 7 preguntas, sin encabezados de semana.")

    with patch("src.editorial_calendar.run_agent_service", return_value=bad_output) as run_mock:
        with pytest.raises(RuntimeError, match="no devolvió el formato"):
            editorial_calendar._run_coordinador_batches(db, coordinador, [("Fuente", "texto")], client, dates, "client-1")

    assert run_mock.call_count == editorial_calendar.MAX_COORDINADOR_ATTEMPTS


# --- _archive_calendar ---

def test_archive_calendar_marks_archived_and_returns_previous_version():
    db = MagicMock()
    current = MagicMock(structured_content={"calendar_version": 3}, status="aprobado")

    previous_version = editorial_calendar._archive_calendar(db, current)

    assert previous_version == 3
    assert current.status == "archivado"
    db.commit.assert_not_called()  # se confirma junto con el nuevo asset, no acá (ver docstring)


def test_archive_calendar_returns_none_when_no_current():
    db = MagicMock()
    assert editorial_calendar._archive_calendar(db, None) is None


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


# --- generate_editorial_calendar (cold start) ---

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
    # 3er valor: la busqueda de _get_current_calendar (no hay calendario previo) -> version 1
    db.scalar.side_effect = [astronomia_agent, coordinador_agent, None]

    fake_outcome = MagicMock(result=WELL_FORMED_TEXT)

    with patch("src.editorial_calendar.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch("src.editorial_calendar.library.create_asset", return_value=MagicMock()) as create_mock:
        result = editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=2)

    assert run_mock.call_count == 2  # 1 especialista + coordinador (batch de 2 cabe en COORDINADOR_BATCH_WEEKS=2)
    kwargs = create_mock.call_args.kwargs
    assert kwargs["file_type"] == "calendario_editorial"
    assert kwargs["structured_content"]["weeks_requested"] == 2
    assert len(kwargs["structured_content"]["weeks"]) == 2
    assert kwargs["structured_content"]["calendar_version"] == 1
    assert "v1" in kwargs["tags"]
    assert "confidence" in kwargs["structured_content"]
    assert result is create_mock.return_value


def test_generate_editorial_calendar_batches_coordinador_calls_for_13_weeks():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046", id="agent-coord-id")
    db.scalar.side_effect = [astronomia_agent, coordinador_agent, None]

    fake_outcome = MagicMock(result=WELL_FORMED_TEXT)

    with patch("src.editorial_calendar.run_agent_service", return_value=fake_outcome) as run_mock, \
         patch("src.editorial_calendar.library.create_asset", return_value=MagicMock()):
        editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=13)

    # 1 especialista + 7 lotes del coordinador (13 semanas / COORDINADOR_BATCH_WEEKS=2 -> 7 lotes) = 8 llamadas
    assert run_mock.call_count == 8


def test_generate_editorial_calendar_increments_version_when_previous_exists():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046", id="agent-coord-id")
    previous_asset = MagicMock(structured_content={"calendar_version": 4}, status="aprobado")
    db.scalar.side_effect = [astronomia_agent, coordinador_agent, previous_asset]

    fake_outcome = MagicMock(result=WELL_FORMED_TEXT)

    with patch("src.editorial_calendar.run_agent_service", return_value=fake_outcome), \
         patch("src.editorial_calendar.library.create_asset", return_value=MagicMock()) as create_mock:
        editorial_calendar.generate_editorial_calendar(db, "client-1", weeks=2)

    assert create_mock.call_args.kwargs["structured_content"]["calendar_version"] == 5
    assert previous_asset.status == "archivado"


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


# --- roll_editorial_calendar (calendario deslizante, FASE 3.2A) ---

def _asset_with_weeks(weeks: list[dict], version: int = 1) -> MagicMock:
    return MagicMock(structured_content={"weeks": weeks, "calendar_version": version}, status="aprobado")


def test_roll_editorial_calendar_delegates_to_cold_start_when_no_current():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    with patch("src.editorial_calendar._get_current_calendar", return_value=None), \
         patch("src.editorial_calendar.generate_editorial_calendar", return_value=MagicMock()) as gen_mock:
        result = editorial_calendar.roll_editorial_calendar(db, "client-1")

    gen_mock.assert_called_once()
    assert result is gen_mock.return_value


def test_roll_editorial_calendar_delegates_to_cold_start_when_all_weeks_expired():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    today = date.today()
    week1_start = (today - timedelta(weeks=20)).isoformat()  # muy vieja -> weeks_to_advance >= len(existing_weeks)
    current = _asset_with_weeks([{"week_number": 1, "start_date": week1_start, "raw_text": "vieja"}])

    with patch("src.editorial_calendar._get_current_calendar", return_value=current), \
         patch("src.editorial_calendar.generate_editorial_calendar", return_value=MagicMock()) as gen_mock:
        result = editorial_calendar.roll_editorial_calendar(db, "client-1")

    gen_mock.assert_called_once()
    assert result is gen_mock.return_value


def test_roll_editorial_calendar_advances_and_regenerates_only_new_weeks():
    db = MagicMock()
    db.get.return_value = _client(intelligence_sources=["astronomia"])

    today = date.today()
    week1_start = date.fromisoformat((today - timedelta(days=7)).isoformat())  # weeks_to_advance = 1
    existing_weeks = [
        {"week_number": i, "start_date": (week1_start + timedelta(weeks=i - 1)).isoformat(), "raw_text": f"semana vieja {i}"}
        for i in range(1, 14)
    ]
    current = _asset_with_weeks(existing_weeks, version=1)

    astronomia_agent = MagicMock(agent_code="agent_038")
    coordinador_agent = MagicMock(agent_code="agent_046", id="agent-coord-id")
    db.scalar.side_effect = [astronomia_agent, coordinador_agent]

    fake_new_week_text = (
        "## SEMANA 1 (2099-01-01)\n"
        "TEMA CENTRAL: Nueva semana\n"
        "EVENTOS DESTACADOS: algo\n"
        "ASPECTOS DE INTERÉS: algo\n"
        "EMOCIONES PREDOMINANTES: algo\n"
        "PRIORIDAD: ALTA\n"
        "OBJETIVO PRINCIPAL: educar\n"
        "AUDIENCIA: adultos\n"
        "HASHTAGS: a, b\n"
        "PALABRAS CLAVE: x, y\n"
        "TERAPIAS RELACIONADAS: ThetaHealing\n"
        "LLAMADO A LA ACCIÓN: reservá\n"
        "IDEAS INSTAGRAM: idea ig\n"
        "IDEAS FACEBOOK: idea fb\n"
        "IDEAS LINKEDIN: idea li\n"
        "IDEAS YOUTUBE: idea yt\n"
        "IDEAS EMAIL: idea email\n"
    )
    fake_outcome = MagicMock(result=fake_new_week_text)

    with patch("src.editorial_calendar._get_current_calendar", return_value=current), \
         patch("src.editorial_calendar.run_agent_service", return_value=fake_outcome), \
         patch("src.editorial_calendar.library.create_asset", return_value=MagicMock()) as create_mock:
        editorial_calendar.roll_editorial_calendar(db, "client-1")

    kwargs = create_mock.call_args.kwargs
    weeks = kwargs["structured_content"]["weeks"]
    assert len(weeks) == 13  # 12 arrastradas + 1 nueva
    assert weeks[0]["raw_text"] == "semana vieja 2"  # la semana 1 vieja se descarto
    assert weeks[0]["week_number"] == 1  # renumerada
    assert weeks[-1]["week_number"] == 13
    assert weeks[-1]["tema_central"] == "Nueva semana"
    assert kwargs["structured_content"]["calendar_version"] == 2  # incrementado desde 1
    assert current.status == "archivado"
