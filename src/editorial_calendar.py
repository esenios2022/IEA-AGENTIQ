"""
FASE 3.1 — Calendario Editorial Inteligente (90 días / 13 semanas).

Puente entre el Departamento Cosmos (FASE 3.0, src/strategic_intelligence.py)
y Marketing: en vez de un informe de un solo día, calcula datos reales para
N fechas ancla (cada 7 días) y pide a cada especialista UNA interpretación
cubriendo todas las semanas de una sola vez — no N llamadas por especialista
— para mantener el costo razonable (ver plan aprobado: ~9-11 llamadas reales
para 13 semanas, en vez de ~117 si se repitiera el patrón diario).

El Coordinador Cosmos SÍ se llama en lotes de COORDINADOR_BATCH_WEEKS
semanas (no una sola llamada para las 13) — hallazgo real, no anticipado
en el diseño original: una sola llamada de 13 semanas se corta a mitad de
la semana 7 por el límite de max_tokens del tier asignado (confirmado en
la verificación real de esta fase). Cada lote recibe el análisis completo
de los especialistas como contexto, pero solo genera el formato semanal
para las semanas de ese lote.

src/strategic_intelligence.py (informe de un solo día) sigue existiendo sin
cambios — este es un módulo nuevo y paralelo que reutiliza los mismos
providers (src/cosmos/providers/) y el mismo run_agent_service.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src import library
from src.agent_service import run as run_agent_service
from src.config import settings
from src.cosmos.providers.ancestral import get_active_modules
from src.cosmos.registry import DEFAULT_PROVIDERS
from src.models import Agent, Client, LibraryAsset
from src.strategic_intelligence import (
    COORDINADOR_AGENT_CODE,
    DEFAULT_SOURCES,
    FRAMING_INSTRUCTION,
    SPECIALIST_AGENT_CODES,
    SPECIALIST_LABELS,
)

WEEKS = 13
COORDINADOR_BATCH_WEEKS = 5  # ver hallazgo real en el docstring del modulo

CALCULABLE_SOURCES = {"astronomia", "astrologia", "maya", "dreamspell"}

WEEK_FIELD_LABELS = [
    "TEMA CENTRAL",
    "EVENTOS DESTACADOS",
    "ASPECTOS DE INTERÉS",
    "EMOCIONES PREDOMINANTES",
    "IDEAS DE CONTENIDO",
]

WEEK_HEADING_RE = re.compile(r"^##?\s*SEMANA\s+(\d+)\s*\(?(\d{4}-\d{2}-\d{2})?\)?", re.IGNORECASE | re.MULTILINE)

COORDINADOR_WEEK_TEMPLATE = (
    "AVISO IMPORTANTE — ESTE PEDIDO ES DISTINTO A TU FORMATO HABITUAL DE 7 PREGUNTAS: "
    "para esta respuesta específica NO uses el formato de 7 preguntas de tu prompt base. "
    "Es un pedido diferente: un Calendario Editorial semana por semana, para eso te contrataron acá. "
    "No respondas las 7 preguntas, no repitas ese formato, no lo menciones.\n\n"
    "Para CADA UNA de estas semanas específicas — {week_list} — y SOLO para esas semanas (no generes ninguna "
    "otra), respondé usando EXACTAMENTE este formato, sin desviarte, una vez por semana, sin texto antes ni "
    "después de la lista de semanas:\n\n"
    "## SEMANA <n> (<fecha de inicio de esa semana>)\n"
    "TEMA CENTRAL: ...\n"
    "EVENTOS DESTACADOS: ...\n"
    "ASPECTOS DE INTERÉS: ...\n"
    "EMOCIONES PREDOMINANTES: ...\n"
    "IDEAS DE CONTENIDO:\n"
    "- Reel: ...\n"
    "- Carrusel: ...\n"
    "- Video: ...\n"
    "- Email: ...\n"
    "- Artículo: ...\n\n"
    "Sé muy breve en cada campo (1 línea corta). Empezá tu respuesta directamente con la primera semana "
    "pedida, sin introducción ni texto de cierre."
)


def _week_anchor_dates(today: date, weeks: int) -> list[date]:
    return [today + timedelta(weeks=i) for i in range(weeks)]


def _astronomy_weekly_facts(provider, anchor_dates: list[date]) -> str:
    lines = []
    for i, d in enumerate(anchor_dates, start=1):
        snap = provider.get_snapshot(datetime(d.year, d.month, d.day))
        events = []
        for event in (snap.nearest_season_event, snap.upcoming_solar_eclipse, snap.upcoming_lunar_eclipse):
            if event is not None and abs(event.days_away) <= 7:
                events.append(event.name if hasattr(event, "name") else event.kind)
        events_text = f" Eventos de esta semana: {', '.join(events)}." if events else ""
        lines.append(f"Semana {i} ({d.isoformat()}): Sol en {snap.sun_position.zodiac_sign}, luna {snap.moon_phase_name}.{events_text}")
    return "\n".join(lines)


def _astrology_weekly_facts(provider, anchor_dates: list[date]) -> str:
    lines = []
    for i, d in enumerate(anchor_dates, start=1):
        snap = provider.get_snapshot(datetime(d.year, d.month, d.day))
        planets = ", ".join(f"{p.body} en {p.zodiac_sign}" for p in snap.planet_positions)
        lines.append(f"Semana {i} ({d.isoformat()}): Sol en {snap.sun_position.zodiac_sign}. {planets}.")
    return "\n".join(lines)


def _maya_weekly_facts(provider, anchor_dates: list[date]) -> str:
    lines = []
    for i, d in enumerate(anchor_dates, start=1):
        snap = provider.get_snapshot(d)
        lines.append(f"Semana {i} ({d.isoformat()}): Tzolkin {snap.tzolkin}, Haab {snap.haab}.")
    return "\n".join(lines)


def _dreamspell_weekly_facts(provider, anchor_dates: list[date]) -> str:
    lines = []
    for i, d in enumerate(anchor_dates, start=1):
        snap = provider.get_snapshot(d)
        dot = " (Día Fuera del Tiempo esta semana)" if snap.is_day_out_of_time else ""
        lines.append(
            f"Semana {i} ({d.isoformat()}): {snap.kin}, Onda Encantada n°{snap.wavespell.number} "
            f"(sello semilla: {snap.wavespell.seed_seal}){dot}."
        )
    return "\n".join(lines)


def _yoruba_weekly_facts(provider, anchor_dates: list[date]) -> str:
    lines = []
    for i, d in enumerate(anchor_dates, start=1):
        snap = provider.get_snapshot(d)
        lines.append(
            f"Semana {i} ({d.isoformat()}): día del ciclo tradicional de 4 días: {snap.four_day_position.day_name} "
            f"(posición ilustrativa, sin fuente de anclaje cultural verificada). "
            f"Tema general de Ifá: {snap.general_theme.name} — {snap.general_theme.description}"
        )
    return "\n".join(lines)


def _biodecoding_weekly_facts(provider, anchor_dates: list[date]) -> str:
    categories = provider.get_categories()
    lines = [f"- {c.body_system}: {c.symbolic_theme}" for c in categories]
    return (
        provider.get_disclaimer()
        + "\nCategorías generales del enfoque (aplican por igual a las 13 semanas, no varían por fecha):\n"
        + "\n".join(lines)
    )


_WEEKLY_DATA_BUILDERS = {
    "astronomia": lambda dates: _astronomy_weekly_facts(DEFAULT_PROVIDERS["astronomia"], dates),
    "astrologia": lambda dates: _astrology_weekly_facts(DEFAULT_PROVIDERS["astrologia"], dates),
    "maya": lambda dates: _maya_weekly_facts(DEFAULT_PROVIDERS["maya"], dates),
    "dreamspell": lambda dates: _dreamspell_weekly_facts(DEFAULT_PROVIDERS["dreamspell"], dates),
    "yoruba": lambda dates: _yoruba_weekly_facts(DEFAULT_PROVIDERS["yoruba"], dates),
    "biodecodificacion": lambda dates: _biodecoding_weekly_facts(DEFAULT_PROVIDERS["biodecodificacion"], dates),
    # "tendencias" y "ancestral" no tienen datos precomputados por semana —
    # ver _build_general_specialist_prompt.
}


def _build_weekly_specialist_prompt(weekly_facts_text: str, client: Client, anchor_dates: list[date]) -> str:
    return (
        f"Cliente: {client.name}. Rango de análisis: {anchor_dates[0].isoformat()} a "
        f"{anchor_dates[-1].isoformat()} ({len(anchor_dates)} semanas).\n\n"
        f"Estos son los datos/hechos reales de tu especialidad para cada una de las {len(anchor_dates)} semanas:\n\n"
        f"{weekly_facts_text}\n\n"
        f"Para CADA semana (Semana 1 a Semana {len(anchor_dates)}), dame una interpretación breve (2-4 líneas) "
        f"en tu especialidad. Señalá también, si las hay, semanas donde tu especialidad indica algo "
        f"particularmente relevante (ej. un eclipse, un Día Fuera del Tiempo, un cierre de ciclo).\n\n"
        f"{FRAMING_INSTRUCTION}"
    )


def _build_general_specialist_prompt(client: Client, anchor_dates: list[date]) -> str:
    return (
        f"Cliente: {client.name}. Rango de análisis: {anchor_dates[0].isoformat()} a "
        f"{anchor_dates[-1].isoformat()} ({len(anchor_dates)} semanas, calendario editorial trimestral).\n\n"
        f"Dame tu análisis para este trimestre completo (no hace falta desglosarlo semana por semana).\n\n"
        f"{FRAMING_INSTRUCTION}"
    )


def _batches(anchor_dates: list[date], batch_size: int) -> list[list[tuple[int, date]]]:
    indexed = list(enumerate(anchor_dates, start=1))
    return [indexed[i : i + batch_size] for i in range(0, len(indexed), batch_size)]


def _build_coordinador_prompt(
    sections: list[tuple[str, str]], client: Client, anchor_dates: list[date], batch: list[tuple[int, date]]
) -> str:
    coord_input = "\n\n".join(f"## {label}\n{text}" for label, text in sections)
    fechas = ", ".join(f"Semana {i + 1}={d.isoformat()}" for i, d in enumerate(anchor_dates))
    week_list = ", ".join(f"Semana {i} ({d.isoformat()})" for i, d in batch)
    return (
        f"Cliente: {client.name}. Calendario editorial de {len(anchor_dates)} semanas en total, "
        f"fechas de inicio de cada semana: {fechas}.\n\n"
        f"Análisis recibidos de los especialistas habilitados para todo el trimestre:\n\n{coord_input}\n\n"
        + COORDINADOR_WEEK_TEMPLATE.format(week_list=week_list)
        + f"\n\n{FRAMING_INSTRUCTION}"
    )


def _parse_coordinador_weeks(raw_text: str, anchor_dates: list[date]) -> list[dict]:
    """Parsea el texto del Coordinador según COORDINADOR_WEEK_TEMPLATE. Tolerante:
    si un campo o una semana no matchea el formato pedido, se guarda lo que haya
    (nunca se inventa ni se completa un campo faltante) — el humano lo revisa en
    la verificación real antes de dar la fase por cerrada."""
    matches = list(WEEK_HEADING_RE.finditer(raw_text))
    label_alternation = "|".join(re.escape(label) for label in WEEK_FIELD_LABELS)
    weeks = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
        chunk = raw_text[start:end]
        week_number = int(m.group(1))
        start_date = m.group(2) or (anchor_dates[week_number - 1].isoformat() if 1 <= week_number <= len(anchor_dates) else None)

        week = {"week_number": week_number, "start_date": start_date, "raw_text": chunk.strip()}
        for label in WEEK_FIELD_LABELS:
            key = label.lower().replace(" ", "_").replace("í", "i").replace("é", "e")
            field_re = re.compile(rf"{re.escape(label)}:?\s*(.+?)(?=\n(?:{label_alternation}):|\Z)", re.IGNORECASE | re.DOTALL)
            field_match = field_re.search(chunk)
            week[key] = field_match.group(1).strip() if field_match else None
        weeks.append(week)
    return weeks


def _confidence_table(
    enabled_sources: list[str], sections_ran: set[str], ancestral_modules: list[str], ancestral_ran: bool
) -> dict:
    """Tabla de confianza calculada por reglas fijas en Python — nunca por el
    LLM (ver plan: un % o etiqueta de confianza inventada por el modelo sería
    autoridad fabricada, igual que asignar un odù a una fecha)."""
    fuentes = {}
    for key in enabled_sources:
        label = SPECIALIST_LABELS.get(key)
        if label is None:
            continue
        if key not in sections_ran:
            fuentes[label] = "No disponible"
        elif key in CALCULABLE_SOURCES:
            fuentes[label] = "Calculado"
        elif key == "yoruba":
            fuentes[label] = "Calendario ilustrativo + corpus documental"
        elif key == "biodecodificacion":
            fuentes[label] = "Interpretación documental"
        elif key == "tendencias":
            fuentes[label] = (
                "Búsqueda en vivo (SERPER_API_KEY configurada)"
                if settings.serper_api_key
                else "Búsqueda en vivo (no disponible: falta SERPER_API_KEY)"
            )
        else:
            fuentes[label] = "Generado"

    fuentes[SPECIALIST_LABELS["ancestral"]] = (
        "Documental (módulo activo)" if (ancestral_modules and ancestral_ran) else "No disponible"
    )

    calculable_enabled = CALCULABLE_SOURCES & set(enabled_sources)
    calculable_ok = calculable_enabled.issubset(sections_ran)
    tendencias_ok = "tendencias" not in enabled_sources or bool(settings.serper_api_key)
    nivel_global = "Alto" if calculable_ok and tendencias_ok else "Medio"

    return {"fuentes": fuentes, "nivel_global": nivel_global}


def generate_editorial_calendar(db: Session, client_id: uuid.UUID | str, weeks: int = WEEKS) -> LibraryAsset:
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError("Cliente no encontrado.")

    enabled_sources = (client.config or {}).get("intelligence_sources") or DEFAULT_SOURCES
    today = date.today()
    anchor_dates = _week_anchor_dates(today, weeks)
    sections: list[tuple[str, str]] = []
    sections_ran: set[str] = set()

    for key in enabled_sources:
        agent_code = SPECIALIST_AGENT_CODES.get(key)
        if agent_code is None:
            continue
        agent = db.scalar(select(Agent).where(Agent.agent_code == agent_code))
        if agent is None:
            continue

        if key in _WEEKLY_DATA_BUILDERS:
            weekly_facts_text = _WEEKLY_DATA_BUILDERS[key](anchor_dates)
            prompt = _build_weekly_specialist_prompt(weekly_facts_text, client, anchor_dates)
        else:
            prompt = _build_general_specialist_prompt(client, anchor_dates)

        outcome = run_agent_service(db, agent, prompt, user_id=str(client_id), client_id=client.id)
        sections.append((SPECIALIST_LABELS[key], outcome.result))
        sections_ran.add(key)

    ancestral_modules = (client.config or {}).get("ancestral_modules") or []
    ancestral_ran = False
    if ancestral_modules:
        agent = db.scalar(select(Agent).where(Agent.agent_code == SPECIALIST_AGENT_CODES["ancestral"]))
        if agent is not None:
            active = get_active_modules(ancestral_modules)
            real_data_text = (
                "\n".join(f"- {m.label}: {m.summary}" for m in active)
                or "Módulos configurados pero sin contenido real todavía."
            )
            prompt = _build_general_specialist_prompt(client, anchor_dates) + f"\n\nDatos de tus módulos activos:\n{real_data_text}"
            outcome = run_agent_service(db, agent, prompt, user_id=str(client_id), client_id=client.id)
            sections.append((SPECIALIST_LABELS["ancestral"], outcome.result))
            ancestral_ran = True

    if not sections:
        raise ValueError("El cliente no tiene ninguna fuente de inteligencia habilitada (Client.config['intelligence_sources']).")

    coordinador = db.scalar(select(Agent).where(Agent.agent_code == COORDINADOR_AGENT_CODE))
    if coordinador is None:
        raise RuntimeError(f"No se encontró el Coordinador Cosmos ({COORDINADOR_AGENT_CODE}).")

    parsed_weeks: list[dict] = []
    raw_texts: list[str] = []
    for batch in _batches(anchor_dates, COORDINADOR_BATCH_WEEKS):
        coord_prompt = _build_coordinador_prompt(sections, client, anchor_dates, batch)
        coord_outcome = run_agent_service(db, coordinador, coord_prompt, user_id=str(client_id), client_id=client.id)
        raw_texts.append(coord_outcome.result)
        parsed_weeks.extend(_parse_coordinador_weeks(coord_outcome.result, anchor_dates))

    confidence = _confidence_table(enabled_sources, sections_ran, ancestral_modules, ancestral_ran)

    structured_content = {
        "weeks": parsed_weeks,
        "confidence": confidence,
        "weeks_requested": weeks,
        "weeks_parsed": len(parsed_weeks),
    }

    return library.create_asset(
        db,
        client_id=client.id,
        category="Documentación",
        subcategory="Calendario Editorial",
        title=f"Calendario editorial Cosmos — {today.isoformat()} a {anchor_dates[-1].isoformat()}",
        description="Generado por el Departamento de Inteligencia Estratégica y Contextual — calendario de 90 días para Marketing",
        file_type="calendario_editorial",
        mime_type=None,
        file_extension=None,
        file_size_bytes=None,
        storage_key="",
        text_content="\n\n".join(raw_texts),
        structured_content=structured_content,
        tags=["inteligencia-estrategica", "cosmos", "calendario-editorial"] + list(enabled_sources),
        created_by_agent_id=coordinador.id,
        status="aprobado",
    )
