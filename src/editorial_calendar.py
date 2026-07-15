"""
FASE 3.1/3.2A — Calendario Editorial Inteligente (90 días / 13 semanas).

Puente entre el Departamento Cosmos (FASE 3.0, src/strategic_intelligence.py)
y Marketing: en vez de un informe de un solo día, mantiene un calendario
deslizante de 13 semanas con tema, prioridad, objetivo de negocio, ideas de
contenido por plataforma y un marketing_brief listo para Marketing (FASE
3.2B, todavía no consumido).

El Coordinador Cosmos SÍ se llama en lotes de COORDINADOR_BATCH_WEEKS
semanas (no una sola llamada para todas) — hallazgo real, no anticipado en
el diseño original: una sola llamada larga se corta a mitad de una semana
por el límite de max_tokens del tier asignado (confirmado en la
verificación real de FASE 3.1). Cada lote recibe el análisis completo de
los especialistas como contexto, pero solo genera el formato semanal para
las semanas de ese lote.

FASE 3.2A agrega el calendario **deslizante**: `generate_editorial_calendar`
sigue siendo el cold start (13 semanas nuevas, sin nada previo);
`roll_editorial_calendar` (usado por el scheduler recurrente,
src/scheduler.py) descarta las semanas ya vencidas del calendario vigente,
renumera las que quedan y genera SOLO las semanas nuevas necesarias para
volver a completar 13 — llamadas mucho más chicas que regenerar todo, y
continuidad real de la planificación semana a semana. Cada calendario
nuevo incrementa `calendar_version` y archiva (nunca borra) el anterior.

src/strategic_intelligence.py (informe de un solo día) sigue existiendo sin
cambios — este es un módulo paralelo que reutiliza los mismos providers
(src/cosmos/providers/) y el mismo run_agent_service.
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
COORDINADOR_BATCH_WEEKS = 2  # ver hallazgo real en el docstring del modulo (16 campos por semana, bajado de 5)

CALCULABLE_SOURCES = {"astronomia", "astrologia", "maya", "dreamspell"}

WEEK_FIELD_LABELS = [
    "TEMA CENTRAL",
    "EVENTOS DESTACADOS",
    "ASPECTOS DE INTERÉS",
    "EMOCIONES PREDOMINANTES",
    "PRIORIDAD",
    "OBJETIVO PRINCIPAL",
    "AUDIENCIA",
    "HASHTAGS",
    "PALABRAS CLAVE",
    "TERAPIAS RELACIONADAS",
    "LLAMADO A LA ACCIÓN",
    "IDEAS INSTAGRAM",
    "IDEAS FACEBOOK",
    "IDEAS LINKEDIN",
    "IDEAS YOUTUBE",
    "IDEAS EMAIL",
]

LIST_FIELD_KEYS = {"hashtags", "palabras_clave", "terapias_relacionadas"}

PLATFORM_FIELDS = [
    ("Instagram", "ideas_instagram"),
    ("Facebook", "ideas_facebook"),
    ("LinkedIn", "ideas_linkedin"),
    ("YouTube", "ideas_youtube"),
    ("Email", "ideas_email"),
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
    "PRIORIDAD: ALTA, MEDIA o BAJA — según qué tan relevante es el contexto de esta semana\n"
    "OBJETIVO PRINCIPAL: elegí uno — captar pacientes, generar confianza, educar, posicionar marca, "
    "conseguir registros, vender una mentoría, webinar, evento, comunidad\n"
    "AUDIENCIA: a quién le habla el contenido de esta semana, en una línea\n"
    "HASHTAGS: 3 a 5, separados por coma\n"
    "PALABRAS CLAVE: 3 a 5, separadas por coma\n"
    "TERAPIAS RELACIONADAS: de las que ofrece el cliente, separadas por coma\n"
    "LLAMADO A LA ACCIÓN: ...\n"
    "IDEAS INSTAGRAM: ...\n"
    "IDEAS FACEBOOK: ...\n"
    "IDEAS LINKEDIN: ...\n"
    "IDEAS YOUTUBE: ...\n"
    "IDEAS EMAIL: ...\n\n"
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
        + "\nCategorías generales del enfoque (no varían por fecha):\n"
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
        f"{anchor_dates[-1].isoformat()} ({len(anchor_dates)} semanas).\n\n"
        f"Dame tu análisis para este período completo (no hace falta desglosarlo semana por semana).\n\n"
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
        f"Cliente: {client.name}. Calendario editorial — semanas de este pedido: {fechas}.\n\n"
        f"Análisis recibidos de los especialistas habilitados:\n\n{coord_input}\n\n"
        + COORDINADOR_WEEK_TEMPLATE.format(week_list=week_list)
        + f"\n\n{FRAMING_INSTRUCTION}"
    )


def _split_list_field(raw: str | None) -> list[str]:
    """Convierte 'tag1, tag2, tag3' en una lista real. Nunca inventa
    valores — si no hay nada, lista vacía."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_marketing_brief(week: dict) -> dict:
    """Resumen determinístico en Python para FASE 3.2B (todavía no
    consumido por nada) — no se le pide esto al LLM para evitar tokens
    extra y posibles contradicciones con los campos ya generados de la
    misma semana."""
    canales = [platform for platform, field in PLATFORM_FIELDS if week.get(field)]
    return {
        "tema": week.get("tema_central"),
        "audiencia": week.get("audiencia"),
        "objetivo": week.get("objetivo_principal"),
        "cta": week.get("llamado_a_la_accion"),
        "canales": canales,
        "urgencia": week.get("prioridad"),
    }


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
            key = (
                label.lower()
                .replace(" ", "_")
                .replace("á", "a")
                .replace("é", "e")
                .replace("í", "i")
                .replace("ó", "o")
                .replace("ú", "u")
            )
            field_re = re.compile(rf"{re.escape(label)}:?\s*(.+?)(?=\n(?:{label_alternation}):|\Z)", re.IGNORECASE | re.DOTALL)
            field_match = field_re.search(chunk)
            raw_value = field_match.group(1).strip() if field_match else None
            week[key] = _split_list_field(raw_value) if key in LIST_FIELD_KEYS else raw_value
        week["marketing_brief"] = _build_marketing_brief(week)
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


def _run_specialists(
    db: Session,
    client: Client,
    client_id: uuid.UUID | str,
    enabled_sources: list[str],
    dates: list[date],
    tier_override: str | None = None,
    gemini_key: str | None = None,
    platform_cost: bool = True,
) -> tuple[list[tuple[str, str]], set[str]]:
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
            weekly_facts_text = _WEEKLY_DATA_BUILDERS[key](dates)
            prompt = _build_weekly_specialist_prompt(weekly_facts_text, client, dates)
        else:
            prompt = _build_general_specialist_prompt(client, dates)

        outcome = run_agent_service(
            db, agent, prompt, user_id=str(client_id), client_id=client.id,
            tier_override=tier_override, gemini_key=gemini_key, platform_cost=platform_cost,
        )
        sections.append((SPECIALIST_LABELS[key], outcome.result))
        sections_ran.add(key)
    return sections, sections_ran


def _run_ancestral(
    db: Session,
    client: Client,
    client_id: uuid.UUID | str,
    ancestral_modules: list[str],
    dates: list[date],
    sections: list[tuple[str, str]],
    tier_override: str | None = None,
    gemini_key: str | None = None,
    platform_cost: bool = True,
) -> bool:
    if not ancestral_modules:
        return False
    agent = db.scalar(select(Agent).where(Agent.agent_code == SPECIALIST_AGENT_CODES["ancestral"]))
    if agent is None:
        return False
    active = get_active_modules(ancestral_modules)
    real_data_text = (
        "\n".join(f"- {m.label}: {m.summary}" for m in active) or "Módulos configurados pero sin contenido real todavía."
    )
    prompt = _build_general_specialist_prompt(client, dates) + f"\n\nDatos de tus módulos activos:\n{real_data_text}"
    outcome = run_agent_service(
        db, agent, prompt, user_id=str(client_id), client_id=client.id,
        tier_override=tier_override, gemini_key=gemini_key, platform_cost=platform_cost,
    )
    sections.append((SPECIALIST_LABELS["ancestral"], outcome.result))
    return True


MAX_COORDINADOR_ATTEMPTS = 2

RETRY_PREFIX = (
    "REINTENTO — tu respuesta anterior no siguió el formato semanal pedido (probablemente volviste "
    "a tu formato habitual de 7 preguntas). Es crítico que esta vez uses EXACTAMENTE el formato de "
    "abajo, nada más, ninguna otra estructura.\n\n"
)


def _run_coordinador_batches(
    db: Session,
    coordinador: Agent,
    sections: list[tuple[str, str]],
    client: Client,
    dates: list[date],
    client_id: uuid.UUID | str,
    tier_override: str | None = None,
    gemini_key: str | None = None,
    platform_cost: bool = True,
) -> list[dict]:
    """Hallazgo real de producción: el Coordinador a veces ignora
    COORDINADOR_WEEK_TEMPLATE y vuelve a su formato de 7 preguntas fijado en
    su propio system prompt — no es un evento único ya resuelto en FASE
    3.1/3.2A, es probabilístico y puede repetirse en cualquier corrida real.
    Sin este reintento+validación, una corrida fallida guardaba un
    calendario con 0 semanas marcado igual como "aprobado", sin ningún
    error — silenciosamente inservible para Marketing. Ahora: si un lote no
    devuelve al menos tantas semanas como se pidieron, se reintenta con un
    prefijo más forzado; si tras MAX_COORDINADOR_ATTEMPTS sigue fallando,
    se levanta RuntimeError en vez de guardar un calendario incompleto."""
    weeks: list[dict] = []
    for batch in _batches(dates, COORDINADOR_BATCH_WEEKS):
        batch_weeks: list[dict] = []
        for attempt in range(1, MAX_COORDINADOR_ATTEMPTS + 1):
            coord_prompt = _build_coordinador_prompt(sections, client, dates, batch)
            if attempt > 1:
                coord_prompt = RETRY_PREFIX + coord_prompt
            coord_outcome = run_agent_service(
                db, coordinador, coord_prompt, user_id=str(client_id), client_id=client.id,
                tier_override=tier_override, gemini_key=gemini_key, platform_cost=platform_cost,
            )
            batch_weeks = _parse_coordinador_weeks(coord_outcome.result, dates)
            if len(batch_weeks) >= len(batch):
                break
        if len(batch_weeks) < len(batch):
            week_numbers = [n for n, _ in batch]
            raise RuntimeError(
                f"El Coordinador Cosmos no devolvió el formato semanal esperado para las semanas "
                f"{week_numbers} después de {MAX_COORDINADOR_ATTEMPTS} intentos — no se guardó ningún "
                f"calendario incompleto."
            )
        weeks.extend(batch_weeks)
    return weeks


def _get_current_calendar(db: Session, client_id: uuid.UUID | str) -> LibraryAsset | None:
    return db.scalar(
        select(LibraryAsset)
        .where(
            LibraryAsset.client_id == client_id,
            LibraryAsset.file_type == "calendario_editorial",
            LibraryAsset.status == "aprobado",
        )
        .order_by(LibraryAsset.created_at.desc())
    )


def _archive_calendar(db: Session, current: LibraryAsset | None) -> int | None:
    """Marca el calendario vigente como archivado (nunca se borra — sigue
    disponible para consultar versiones anteriores) y devuelve su
    calendar_version para que el nuevo incremente desde ahí. No hace commit
    acá a propósito: queda pendiente en la sesión y se confirma junto con
    el nuevo LibraryAsset en library.create_asset() — o ambos cambios
    quedan (archivado viejo + creado nuevo) o ninguno, nunca a medias."""
    if current is None:
        return None
    previous_version = (current.structured_content or {}).get("calendar_version")
    current.status = "archivado"
    return previous_version


def generate_editorial_calendar(
    db: Session,
    client_id: uuid.UUID | str,
    weeks: int = WEEKS,
    tier_override: str | None = None,
    gemini_key: str | None = None,
    platform_cost: bool = True,
) -> LibraryAsset:
    """Cold start: genera un calendario nuevo de `weeks` semanas completas.
    Usado cuando el cliente no tiene ningún calendario vigente todavía, o
    cuando roll_editorial_calendar detecta que el vigente ya no tiene
    ninguna semana útil. `tier_override` (ej. "economy") fuerza el tier de
    TODAS las llamadas — pensado para validar con saldo real limitado, ver
    src/agent_service.py::run(). `gemini_key` enruta las 9 llamadas de
    Cosmos a Gemini en vez de Claude — Cosmos no usa herramientas, así que
    el executor de Gemini (sin tool-calling) alcanza sin cambios.
    `platform_cost=True` (default) asume que `gemini_key` es la cuenta
    propia de IEA-AGENTIQ (confirmado 2026-07-14) -> el costo real entra
    al cost-tracking de la plataforma; pasar False solo si algún día
    Cosmos corre con una key BYOK de un cliente específico."""
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError("Cliente no encontrado.")

    enabled_sources = (client.config or {}).get("intelligence_sources") or DEFAULT_SOURCES
    today = date.today()
    anchor_dates = _week_anchor_dates(today, weeks)

    sections, sections_ran = _run_specialists(
        db, client, client_id, enabled_sources, anchor_dates, tier_override, gemini_key, platform_cost
    )

    ancestral_modules = (client.config or {}).get("ancestral_modules") or []
    ancestral_ran = _run_ancestral(
        db, client, client_id, ancestral_modules, anchor_dates, sections, tier_override, gemini_key, platform_cost
    )

    if not sections:
        raise ValueError("El cliente no tiene ninguna fuente de inteligencia habilitada (Client.config['intelligence_sources']).")

    coordinador = db.scalar(select(Agent).where(Agent.agent_code == COORDINADOR_AGENT_CODE))
    if coordinador is None:
        raise RuntimeError(f"No se encontró el Coordinador Cosmos ({COORDINADOR_AGENT_CODE}).")

    parsed_weeks = _run_coordinador_batches(
        db, coordinador, sections, client, anchor_dates, client_id, tier_override, gemini_key, platform_cost
    )
    confidence = _confidence_table(enabled_sources, sections_ran, ancestral_modules, ancestral_ran)

    previous_version = _archive_calendar(db, _get_current_calendar(db, client_id))
    calendar_version = (previous_version or 0) + 1

    structured_content = {
        "weeks": parsed_weeks,
        "confidence": confidence,
        "weeks_requested": weeks,
        "weeks_parsed": len(parsed_weeks),
        "calendar_version": calendar_version,
    }

    return library.create_asset(
        db,
        client_id=client.id,
        category="Documentación",
        subcategory="Calendario Editorial",
        title=f"Calendario editorial Cosmos — {today.isoformat()} a {anchor_dates[-1].isoformat()} (v{calendar_version})",
        description="Generado por el Departamento de Inteligencia Estratégica y Contextual — calendario de 90 días para Marketing",
        file_type="calendario_editorial",
        mime_type=None,
        file_extension=None,
        file_size_bytes=None,
        storage_key="",
        text_content="\n\n".join(w.get("raw_text") or "" for w in parsed_weeks),
        structured_content=structured_content,
        tags=["inteligencia-estrategica", "cosmos", "calendario-editorial", f"v{calendar_version}"] + list(enabled_sources),
        created_by_agent_id=coordinador.id,
        status="aprobado",
    )


def roll_editorial_calendar(
    db: Session,
    client_id: uuid.UUID | str,
    weeks: int = WEEKS,
    tier_override: str | None = None,
    gemini_key: str | None = None,
    platform_cost: bool = True,
) -> LibraryAsset:
    """Calendario deslizante (FASE 3.2A): descarta las semanas ya vencidas
    del calendario vigente, renumera las que quedan y genera solo las
    semanas nuevas necesarias para volver a completar `weeks` — llamadas
    mucho más chicas que un cold start completo. Usado por el scheduler
    recurrente (src/scheduler.py)."""
    current = _get_current_calendar(db, client_id)
    if current is None or not (current.structured_content or {}).get("weeks"):
        return generate_editorial_calendar(
            db, client_id, weeks=weeks, tier_override=tier_override, gemini_key=gemini_key, platform_cost=platform_cost
        )

    existing_weeks = current.structured_content["weeks"]
    today = date.today()
    first_start_raw = existing_weeks[0].get("start_date") if existing_weeks else None
    weeks_to_advance = (
        max(1, (today - date.fromisoformat(first_start_raw)).days // 7) if first_start_raw else len(existing_weeks)
    )

    if weeks_to_advance >= len(existing_weeks):
        # El calendario vigente ya no tiene ninguna semana util - equivale a un cold start.
        return generate_editorial_calendar(
            db, client_id, weeks=weeks, tier_override=tier_override, gemini_key=gemini_key, platform_cost=platform_cost
        )

    client = db.get(Client, client_id)
    if client is None:
        raise ValueError("Cliente no encontrado.")

    carried = existing_weeks[weeks_to_advance:]
    for i, week in enumerate(carried, start=1):
        week["week_number"] = i

    last_carried_date = (
        date.fromisoformat(carried[-1]["start_date"]) if carried and carried[-1].get("start_date") else today
    )
    new_dates = [last_carried_date + timedelta(weeks=i) for i in range(1, weeks_to_advance + 1)]

    enabled_sources = (client.config or {}).get("intelligence_sources") or DEFAULT_SOURCES
    sections, sections_ran = _run_specialists(
        db, client, client_id, enabled_sources, new_dates, tier_override, gemini_key, platform_cost
    )

    ancestral_modules = (client.config or {}).get("ancestral_modules") or []
    ancestral_ran = _run_ancestral(
        db, client, client_id, ancestral_modules, new_dates, sections, tier_override, gemini_key, platform_cost
    )

    if not sections:
        raise ValueError("El cliente no tiene ninguna fuente de inteligencia habilitada (Client.config['intelligence_sources']).")

    coordinador = db.scalar(select(Agent).where(Agent.agent_code == COORDINADOR_AGENT_CODE))
    if coordinador is None:
        raise RuntimeError(f"No se encontró el Coordinador Cosmos ({COORDINADOR_AGENT_CODE}).")

    new_weeks = _run_coordinador_batches(
        db, coordinador, sections, client, new_dates, client_id, tier_override, gemini_key, platform_cost
    )
    offset = len(carried)
    for week in new_weeks:
        week["week_number"] = offset + week["week_number"]

    all_weeks = carried + new_weeks
    confidence = _confidence_table(enabled_sources, sections_ran, ancestral_modules, ancestral_ran)

    previous_version = _archive_calendar(db, current)
    calendar_version = (previous_version or 0) + 1

    structured_content = {
        "weeks": all_weeks,
        "confidence": confidence,
        "weeks_requested": len(all_weeks),
        "weeks_parsed": len(all_weeks),
        "calendar_version": calendar_version,
    }

    last_week_date = (
        date.fromisoformat(all_weeks[-1]["start_date"]) if all_weeks and all_weeks[-1].get("start_date") else today
    )

    return library.create_asset(
        db,
        client_id=client.id,
        category="Documentación",
        subcategory="Calendario Editorial",
        title=f"Calendario editorial Cosmos — {today.isoformat()} a {last_week_date.isoformat()} (v{calendar_version})",
        description="Generado por el Departamento de Inteligencia Estratégica y Contextual — calendario deslizante de 90 días para Marketing",
        file_type="calendario_editorial",
        mime_type=None,
        file_extension=None,
        file_size_bytes=None,
        storage_key="",
        text_content="\n\n".join(w.get("raw_text") or "" for w in all_weeks),
        structured_content=structured_content,
        tags=["inteligencia-estrategica", "cosmos", "calendario-editorial", f"v{calendar_version}"] + list(enabled_sources),
        created_by_agent_id=coordinador.id,
        status="aprobado",
    )
