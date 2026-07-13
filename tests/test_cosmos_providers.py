"""FASE 3.0 — cálculos reales de src/cosmos/providers/*.py contra valores
de referencia conocidos e independientes (no solo mocks). Cada assert
está documentado con la fuente/derivación del valor esperado."""

from datetime import date, datetime, timedelta

from src.cosmos.providers.astronomy import (
    AstronomyEngineProvider,
    longitude_to_zodiac_sign,
)
from src.cosmos.providers.biodecoding import CuratedBiodecodingProvider
from src.cosmos.providers.dreamspell import ClassicDreamspellProvider
from src.cosmos.providers.maya import GMTCorrelationProvider, gregorian_to_jdn
from src.cosmos.providers.yoruba import TraditionalYorubaProvider


# --- Maya (Tzolkin/Haab clásico, correlación GMT 584283) ---

def test_gregorian_to_jdn_matches_known_julian_day_number():
    # JDN 2451545 para el 1 de enero de 2000 es una constante ampliamente
    # publicada y usada como época J2000 — punto de referencia independiente
    # de esta implementación.
    assert gregorian_to_jdn(2000, 1, 1) == 2451545


def test_gregorian_to_jdn_matches_maya_creation_epoch():
    # 11 de agosto de 3114 a.C. (proléptico gregoriano, año astronómico
    # -3113) es la fecha de creación 0.0.0.0.0 según la correlación GMT —
    # JDN 584283 exactamente, el mismo valor usado como GMT_CORRELATION.
    assert gregorian_to_jdn(-3113, 8, 11) == 584283


def test_maya_snapshot_at_2012_baktun_13_is_4_ajaw_3_kankin():
    # 21 de diciembre de 2012 = Long Count 13.0.0.0.0 = 4 Ajaw 3 K'ank'in
    # bajo la correlación GMT 584283 — la fecha maya más ampliamente
    # publicada y verificada que existe (el "fin del Baktun 13"), y la
    # única con año dentro del rango soportado por datetime.date (a
    # diferencia de la fecha de creación 0.0.0.0.0, en 3114 a.C.).
    provider = GMTCorrelationProvider()
    snapshot = provider.get_snapshot(date(2012, 12, 21))

    assert snapshot.long_count_days == 13 * 144000  # 13 baktunes exactos
    assert str(snapshot.tzolkin) == "4 Ajaw"
    assert str(snapshot.haab) == "3 K'ank'in"


def test_maya_snapshot_tzolkin_cycles_every_260_days():
    provider = GMTCorrelationProvider()
    start = date(2026, 7, 13)
    base = provider.get_snapshot(start)
    later = provider.get_snapshot(start + timedelta(days=260))

    assert base.tzolkin.number == later.tzolkin.number
    assert base.tzolkin.day_name == later.tzolkin.day_name


def test_maya_snapshot_haab_cycles_every_365_days():
    provider = GMTCorrelationProvider()
    start = date(2026, 7, 13)
    base = provider.get_snapshot(start)
    later = provider.get_snapshot(start + timedelta(days=365))

    assert base.haab.day == later.haab.day
    assert base.haab.month_name == later.haab.month_name


# --- Dreamspell (José Argüelles, 1987 — sistema moderno, no maya clásico) ---

def test_dreamspell_epoch_is_kin_1_red_magnetic_dragon():
    # 26 de julio de 1987 = Kin 1 (Dragón Rojo Magnético) — verificado por
    # búsqueda real contra fuentes Dreamspell independientes de este código.
    provider = ClassicDreamspellProvider()
    snapshot = provider.get_snapshot(date(1987, 7, 26))

    assert snapshot.kin.kin_number == 1
    assert snapshot.kin.tone == "Magnético"
    assert snapshot.kin.seal == "Dragón"
    assert snapshot.kin.seal_color == "Rojo"
    assert snapshot.wavespell.number == 1
    assert snapshot.wavespell.seed_seal == "Dragón"


def test_dreamspell_day_out_of_time_is_july_25():
    provider = ClassicDreamspellProvider()
    snapshot = provider.get_snapshot(date(2026, 7, 25))
    assert snapshot.is_day_out_of_time is True

    not_dot = provider.get_snapshot(date(2026, 7, 24))
    assert not_dot.is_day_out_of_time is False


def test_dreamspell_kin_number_stays_in_valid_range():
    provider = ClassicDreamspellProvider()
    for probe in [date(1987, 7, 26), date(2000, 1, 1), date(2026, 7, 13), date(2050, 12, 31)]:
        snapshot = provider.get_snapshot(probe)
        assert 1 <= snapshot.kin.kin_number <= 260


# --- Yoruba (calendario tradicional de 4 días — sin odù por fecha, ver docstring) ---

def test_yoruba_never_assigns_an_odu():
    provider = TraditionalYorubaProvider()
    snapshot = provider.get_snapshot(date(2026, 7, 13))

    # Regla absoluta: nunca hay una noción de "odù" en la salida del provider.
    assert not hasattr(snapshot, "odu")
    assert snapshot.four_day_position.is_illustrative is True
    assert snapshot.four_day_position.day_name in ["Ògún", "Sàngó", "Ọbàtálá", "Òrìṣà"]


def test_yoruba_four_day_cycle_repeats_every_4_days():
    provider = TraditionalYorubaProvider()
    base = provider.get_snapshot(date(2026, 7, 13))
    later = provider.get_snapshot(date(2026, 7, 17))  # +4 días
    assert base.four_day_position.day_name == later.four_day_position.day_name


# --- Biodecodificación (base curada, nunca diagnóstico) ---

def test_biodecoding_disclaimer_always_present_and_non_diagnostic():
    provider = CuratedBiodecodingProvider()
    disclaimer = provider.get_disclaimer()
    assert "no un diagnóstico" in disclaimer.lower() or "no diagnóstico" in disclaimer.lower()

    categories = provider.get_categories()
    assert len(categories) > 0
    for category in categories:
        assert category.body_system
        assert category.symbolic_theme


# --- Astronomía (astronomy-engine — datos reales, no inventados) ---

def test_longitude_to_zodiac_sign_boundaries():
    assert longitude_to_zodiac_sign(0) == "Aries"
    assert longitude_to_zodiac_sign(29.9) == "Aries"
    assert longitude_to_zodiac_sign(30) == "Tauro"
    assert longitude_to_zodiac_sign(359.9) == "Piscis"
    assert longitude_to_zodiac_sign(360) == "Aries"  # wrap-around


def test_astronomy_snapshot_has_internally_consistent_real_values():
    provider = AstronomyEngineProvider()
    snapshot = provider.get_snapshot(datetime(2026, 7, 13, 12, 0, 0))

    assert 0 <= snapshot.moon_phase_angle < 360
    assert 0 <= snapshot.moon_illumination_fraction <= 1
    assert snapshot.moon_phase_name  # nunca vacío
    assert snapshot.sun_position.zodiac_sign in [
        "Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo",
        "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis",
    ]
    # 2026-07-13 el Sol real está en Cáncer (verificado: el Sol entra a Leo
    # recién a fines de julio) — chequeo contra el calendario zodiacal real,
    # no contra el propio código.
    assert snapshot.sun_position.zodiac_sign == "Cáncer"
    assert len(snapshot.planet_positions) == 5
    # Actividad solar: nunca inventada, siempre marcada explícitamente.
    assert "No disponible" in snapshot.solar_activity_note


def test_astronomy_solstices_and_equinoxes_are_real_calendar_dates():
    provider = AstronomyEngineProvider()
    # El solsticio de junio real cae siempre entre el 20 y 22 de junio.
    snapshot = provider.get_snapshot(datetime(2026, 6, 21, 0, 0, 0))
    event = snapshot.nearest_season_event
    assert event is not None
    assert event.date.month == 6
    assert 19 <= event.date.day <= 22
