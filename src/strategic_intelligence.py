"""
FASE 3.0 — Departamento de Inteligencia Estratégica y Contextual ("Cosmos").
Orquestación Python simple reutilizando `run_agent_service` (único patrón
real de este repo para "código dispara un agente y captura su resultado",
ver `scheduler.py` y `social_publishing.py::request_legal_review`) — no
`Process.hierarchical` de CrewAI, nunca usado ni probado en este repo
(confirmado antes de diseñar esta fase).

Los datos "duros" (astronómicos, calendáricos) los calcula Python de
forma determinista ANTES de llamar a cada agente especialista — el LLM
nunca inventa un hecho, solo lo interpreta con el marco fijo de
"múltiples posibilidades, sin predicciones, sin verdad absoluta" que cada
agente ya trae en su propio prompt (ver src/data/agents_config.json).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src import library
from src.agent_service import run as run_agent_service
from src.cosmos.providers.ancestral import get_active_modules
from src.cosmos.registry import DEFAULT_PROVIDERS
from src.models import Agent, Client, LibraryAsset

COORDINADOR_AGENT_CODE = "agent_046"

DEFAULT_SOURCES = ["astronomia", "astrologia", "maya", "dreamspell", "yoruba", "biodecodificacion", "tendencias"]

SPECIALIST_AGENT_CODES = {
    "astronomia": "agent_038",
    "astrologia": "agent_039",
    "maya": "agent_040",
    "dreamspell": "agent_041",
    "yoruba": "agent_042",
    "ancestral": "agent_043",
    "biodecodificacion": "agent_044",
    "tendencias": "agent_045",
}

SPECIALIST_LABELS = {
    "astronomia": "Inteligencia Astronómica",
    "astrologia": "Inteligencia Astrológica",
    "maya": "Inteligencia del Calendario Maya",
    "dreamspell": "Inteligencia del Calendario de 13 Lunas (Dreamspell)",
    "yoruba": "Inteligencia Yoruba (Ifá)",
    "ancestral": "Inteligencia de Tradiciones Ancestrales",
    "biodecodificacion": "Inteligencia de Biodescodificación",
    "tendencias": "Inteligencia de Tendencias Sociales",
}

FRAMING_INSTRUCTION = (
    "Trabajá siempre con el concepto de múltiples posibilidades — identificando tendencias, "
    "coincidencias y escenarios probables. Nunca hagas predicciones ni presentes ninguna "
    "tradición como verdad absoluta."
)


def _build_specialist_prompt(real_data_text: str, client: Client, today: date) -> str:
    return (
        f"Fecha de análisis: {today.isoformat()}. Cliente: {client.name}.\n\n"
        f"Estos son los datos/hechos reales de tu especialidad para hoy:\n\n{real_data_text}\n\n"
        f"{FRAMING_INSTRUCTION}"
    )


def _astronomy_facts(provider, today: date) -> str:
    snap = provider.get_snapshot(datetime(today.year, today.month, today.day))
    lines = [
        f"Fase lunar: {snap.moon_phase_name} ({snap.moon_phase_angle:.1f}°, {snap.moon_illumination_fraction * 100:.1f}% iluminada).",
        f"Sol en {snap.sun_position.zodiac_sign} ({snap.sun_position.ecliptic_longitude:.1f}°).",
    ]
    if snap.nearest_season_event:
        e = snap.nearest_season_event
        lines.append(f"Evento estacional más cercano: {e.name}, {e.date.date().isoformat()} ({e.days_away:+d} días).")
    if snap.upcoming_solar_eclipse:
        e = snap.upcoming_solar_eclipse
        lines.append(f"Próximo {e.kind}: {e.date.date().isoformat()} ({e.days_away:+d} días).")
    if snap.upcoming_lunar_eclipse:
        e = snap.upcoming_lunar_eclipse
        lines.append(f"Próximo {e.kind}: {e.date.date().isoformat()} ({e.days_away:+d} días).")
    lines.append(f"Actividad solar: {snap.solar_activity_note}")
    lines.append("Posiciones planetarias: " + ", ".join(f"{p.body} en {p.zodiac_sign}" for p in snap.planet_positions))
    return "\n".join(lines)


def _astrology_facts(provider, today: date) -> str:
    """Reutiliza los mismos datos reales que calcula Astronomía — nunca calcula nada propio."""
    snap = provider.get_snapshot(datetime(today.year, today.month, today.day))
    lines = [f"Sol en {snap.sun_position.zodiac_sign}."]
    lines.append("Planetas: " + ", ".join(f"{p.body} en {p.zodiac_sign}" for p in snap.planet_positions))
    return "\n".join(lines)


def _maya_facts(provider, today: date) -> str:
    snap = provider.get_snapshot(today)
    return f"Tzolkin: {snap.tzolkin}. Haab: {snap.haab}."


def _dreamspell_facts(provider, today: date) -> str:
    snap = provider.get_snapshot(today)
    lines = [str(snap.kin), f"Onda Encantada n°{snap.wavespell.number} (sello semilla: {snap.wavespell.seed_seal})."]
    if snap.is_day_out_of_time:
        lines.append("Hoy es Día Fuera del Tiempo (25 de julio) en el sistema Dreamspell.")
    return "\n".join(lines)


def _yoruba_facts(provider, today: date) -> str:
    snap = provider.get_snapshot(today)
    return (
        f"Día del ciclo tradicional de 4 días: {snap.four_day_position.day_name} "
        f"(posición ilustrativa, sin fuente de anclaje cultural verificada). "
        f"Tema general de Ifá: {snap.general_theme.name} — {snap.general_theme.description}"
    )


def _biodecoding_facts(provider) -> str:
    categories = provider.get_categories()
    lines = [f"- {c.body_system}: {c.symbolic_theme}" for c in categories]
    return provider.get_disclaimer() + "\nCategorías generales del enfoque:\n" + "\n".join(lines)


_REAL_DATA_BUILDERS = {
    "astronomia": lambda today: _astronomy_facts(DEFAULT_PROVIDERS["astronomia"], today),
    "astrologia": lambda today: _astrology_facts(DEFAULT_PROVIDERS["astrologia"], today),
    "maya": lambda today: _maya_facts(DEFAULT_PROVIDERS["maya"], today),
    "dreamspell": lambda today: _dreamspell_facts(DEFAULT_PROVIDERS["dreamspell"], today),
    "yoruba": lambda today: _yoruba_facts(DEFAULT_PROVIDERS["yoruba"], today),
    "biodecodificacion": lambda today: _biodecoding_facts(DEFAULT_PROVIDERS["biodecodificacion"]),
    # "tendencias" no tiene hechos precomputados — el agente busca en vivo (tools=["web_search"]).
}


def generate_strategic_report(db: Session, client_id: uuid.UUID | str) -> LibraryAsset:
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError("Cliente no encontrado.")

    enabled_sources = (client.config or {}).get("intelligence_sources") or DEFAULT_SOURCES
    today = date.today()
    sections: list[tuple[str, str]] = []

    for key in enabled_sources:
        agent_code = SPECIALIST_AGENT_CODES.get(key)
        if agent_code is None:
            continue
        agent = db.scalar(select(Agent).where(Agent.agent_code == agent_code))
        if agent is None:
            continue

        real_data_text = _REAL_DATA_BUILDERS.get(key, lambda _today: "")(today)
        prompt = _build_specialist_prompt(real_data_text, client, today)
        outcome = run_agent_service(db, agent, prompt, user_id=str(client_id), client_id=client.id)
        sections.append((SPECIALIST_LABELS[key], outcome.result))

    ancestral_modules = (client.config or {}).get("ancestral_modules") or []
    if ancestral_modules:
        agent = db.scalar(select(Agent).where(Agent.agent_code == SPECIALIST_AGENT_CODES["ancestral"]))
        if agent is not None:
            active = get_active_modules(ancestral_modules)
            real_data_text = (
                "\n".join(f"- {m.label}: {m.summary}" for m in active)
                or "Módulos configurados pero sin contenido real todavía."
            )
            prompt = _build_specialist_prompt(real_data_text, client, today)
            outcome = run_agent_service(db, agent, prompt, user_id=str(client_id), client_id=client.id)
            sections.append((SPECIALIST_LABELS["ancestral"], outcome.result))

    if not sections:
        raise ValueError("El cliente no tiene ninguna fuente de inteligencia habilitada (Client.config['intelligence_sources']).")

    coordinador = db.scalar(select(Agent).where(Agent.agent_code == COORDINADOR_AGENT_CODE))
    if coordinador is None:
        raise RuntimeError(f"No se encontró el Coordinador Cosmos ({COORDINADOR_AGENT_CODE}).")

    coord_input = "\n\n".join(f"## {label}\n{text}" for label, text in sections)
    coord_prompt = f"Fecha: {today.isoformat()}. Cliente: {client.name}.\n\nAnálisis recibidos de los especialistas habilitados:\n\n{coord_input}"
    coord_outcome = run_agent_service(db, coordinador, coord_prompt, user_id=str(client_id), client_id=client.id)

    return library.create_asset(
        db,
        client_id=client.id,
        category="Documentación",
        subcategory="Inteligencia Estratégica",
        title=f"Informe estratégico Cosmos — {today.isoformat()}",
        description="Generado por el Departamento de Inteligencia Estratégica y Contextual",
        file_type="informe",
        mime_type=None,
        file_extension=None,
        file_size_bytes=None,
        storage_key="",
        text_content=coord_outcome.result,
        tags=["inteligencia-estrategica", "cosmos"] + list(enabled_sources),
        created_by_agent_id=coordinador.id,
        status="aprobado",
    )
