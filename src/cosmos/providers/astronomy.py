"""
FASE 3.0 (Departamento Cosmos) — proveedor de hechos astronómicos reales,
calculados (nunca inventados por un LLM). Interfaz `AstronomyProvider`
desacoplada de la implementación concreta — pedido explícito del usuario
("no debe depender de una única librería... debe permitir agregar
proveedores sin modificar la arquitectura"), mismo patrón ya usado en
FASE 2.4 para SocialConnector/SocialProvider. `AstronomyEngineProvider`
es la primera implementación real (astronomy-engine, MIT, sin archivo de
efemérides grande); Swiss Ephemeris u otra fuente = otra clase después,
sin tocar el resto (agentes, orquestador).

Verificado contra la librería real (2026-07-13) antes de escribir esto:
Time.Make/MoonPhase/Illumination/Seasons/SunPosition/GeoVector+Ecliptic/
SearchGlobalSolarEclipse/SearchLunarEclipse — no asumido de memoria.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

ZODIAC_SIGNS = [
    "Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo",
    "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis",
]

# (límite inferior, límite superior, nombre) del ángulo de fase lunar 0-360
MOON_PHASE_NAMES = [
    (0, 22.5, "luna nueva"), (22.5, 67.5, "luna creciente"), (67.5, 112.5, "cuarto creciente"),
    (112.5, 157.5, "gibosa creciente"), (157.5, 202.5, "luna llena"), (202.5, 247.5, "gibosa menguante"),
    (247.5, 292.5, "cuarto menguante"), (292.5, 337.5, "luna menguante"), (337.5, 360.001, "luna nueva"),
]

PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
PLANET_LABELS_ES = {"Mercury": "Mercurio", "Venus": "Venus", "Mars": "Marte", "Jupiter": "Júpiter", "Saturn": "Saturno"}


def longitude_to_zodiac_sign(longitude: float) -> str:
    """Zodíaco tropical estándar (0°=Aries), convención astronómica/astrológica
    establecida — no una correspondencia inventada."""
    return ZODIAC_SIGNS[int(longitude % 360 // 30) % 12]


def _moon_phase_name(phase_angle: float) -> str:
    for lo, hi, name in MOON_PHASE_NAMES:
        if lo <= phase_angle < hi:
            return name
    return "luna nueva"


@dataclass
class PlanetPosition:
    body: str
    ecliptic_longitude: float
    zodiac_sign: str


@dataclass
class SeasonEvent:
    name: str
    date: datetime
    days_away: int


@dataclass
class EclipseEvent:
    kind: str
    date: datetime
    days_away: int


@dataclass
class AstronomySnapshot:
    date: datetime
    moon_phase_angle: float
    moon_phase_name: str
    moon_illumination_fraction: float
    sun_position: PlanetPosition
    planet_positions: list[PlanetPosition]
    nearest_season_event: SeasonEvent | None
    upcoming_solar_eclipse: EclipseEvent | None
    upcoming_lunar_eclipse: EclipseEvent | None
    solar_activity_note: str  # best-effort; nunca inventado, dice explícitamente si no está disponible


class AstronomyProvider(ABC):
    @abstractmethod
    def get_snapshot(self, date: datetime) -> AstronomySnapshot: ...


class AstronomyEngineProvider(AstronomyProvider):
    """Primera implementación real, vía `astronomy-engine` (pip). "Actividad
    solar" (manchas solares reales) no la calcula esta librería — queda
    explícitamente marcada como no disponible en vez de inventarse."""

    def get_snapshot(self, date: datetime) -> AstronomySnapshot:
        import astronomy

        time = astronomy.Time.Make(date.year, date.month, date.day, date.hour, date.minute, date.second)

        phase_angle = astronomy.MoonPhase(time)
        illum = astronomy.Illumination(astronomy.Body.Moon, time)

        sun_lon = astronomy.SunPosition(time).elon
        sun_position = PlanetPosition("Sol", sun_lon, longitude_to_zodiac_sign(sun_lon))

        planet_positions = []
        for name in PLANETS:
            body = getattr(astronomy.Body, name)
            vec = astronomy.GeoVector(body, time, True)
            ecl = astronomy.Ecliptic(vec)
            planet_positions.append(PlanetPosition(PLANET_LABELS_ES[name], ecl.elon, longitude_to_zodiac_sign(ecl.elon)))

        return AstronomySnapshot(
            date=date,
            moon_phase_angle=phase_angle,
            moon_phase_name=_moon_phase_name(phase_angle),
            moon_illumination_fraction=illum.phase_fraction,
            sun_position=sun_position,
            planet_positions=planet_positions,
            nearest_season_event=self._nearest_season_event(astronomy, time, date),
            upcoming_solar_eclipse=self._eclipse_event(astronomy.SearchGlobalSolarEclipse(time), "eclipse solar", date),
            upcoming_lunar_eclipse=self._eclipse_event(astronomy.SearchLunarEclipse(time), "eclipse lunar", date),
            solar_activity_note="No disponible en esta fase — requeriría una fuente en vivo (ej. NOAA SWPC), no integrada todavía.",
        )

    def _nearest_season_event(self, astronomy, time, date: datetime) -> SeasonEvent | None:
        seasons = astronomy.Seasons(date.year)
        next_year_mar_equinox = astronomy.Seasons(date.year + 1).mar_equinox
        candidates = [
            ("equinoccio de marzo", seasons.mar_equinox),
            ("solsticio de junio", seasons.jun_solstice),
            ("equinoccio de septiembre", seasons.sep_equinox),
            ("solsticio de diciembre", seasons.dec_solstice),
            ("equinoccio de marzo", next_year_mar_equinox),
        ]
        reference = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
        best, best_diff = None, None
        for name, t in candidates:
            event_dt = t.Utc().replace(tzinfo=timezone.utc)
            diff_days = (event_dt - reference).days
            if best_diff is None or abs(diff_days) < abs(best_diff):
                best, best_diff = SeasonEvent(name, event_dt, diff_days), diff_days
        return best

    def _eclipse_event(self, result, kind: str, date: datetime) -> EclipseEvent | None:
        if result is None:
            return None
        reference = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
        event_dt = result.peak.Utc().replace(tzinfo=timezone.utc)
        days_away = (event_dt - reference).days
        kind_label = f"{kind} ({result.kind.name.lower()})" if hasattr(result, "kind") else kind
        return EclipseEvent(kind_label, event_dt, days_away)
