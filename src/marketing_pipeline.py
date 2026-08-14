"""
ETAPA 4.1 — Integración Cosmos → Marketing.

Puente entre el Calendario Editorial (src/editorial_calendar.py) y los 6
agentes de Marketing (Daniel, Clara, Ariel, Valentina, Marco, Elena):
cada uno busca la semana vigente del calendario con su propia
`library_search` (ver current_week en src/tools/library_search.py) y
guarda su pieza con `library_save` — el mismo patrón agente-llama-la-tool
ya establecido desde FASE 2.4A, no uno nuevo. El orquestador solo
encadena los 6 pasos en orden (cada uno recibe el trabajo de los
anteriores como contexto, mismo patrón que
strategic_intelligence.py/editorial_calendar.py) y reutiliza
run_agent_service — nunca CrewAI hierarchical, nunca usado ni probado en
este repo (misma decisión de diseño de FASE 3.0).

Verificación, no fe ciega: un LLM no siempre invoca la herramienta que se
le pide (confirmado en este mismo proyecto — el Coordinador Cosmos
ignoró su formato pedido en corridas reales, dos veces). Por eso, después
de cada paso, se consulta la Biblioteca por un LibraryAsset nuevo creado
por ese agente para este cliente — si no aparece ninguno, se registra
como advertencia explícita en el resultado en vez de asumir éxito.

Todo lo que produce este pipeline queda en status="borrador" (forzado
por LibrarySaveTool) — no publica nada, no toca redes sociales nuevas,
no se dispara solo todavía (eso es ETAPA 4.2, scheduler.py sin cambios).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent_service import run as run_agent_service
from src.library import find_recent_asset, search_assets
from src.models import Agent, Client

PIPELINE = [
    ("agent_017", "Daniel", "Investigá contexto de mercado, tendencias y competencia relevante para la semana actual del Calendario Editorial de este cliente."),
    ("agent_010", "Clara", "Definí la estrategia de campaña de la semana actual del Calendario Editorial: objetivo, audiencia, mensaje central y qué canal prioriza qué."),
    ("agent_006", "Ariel", "Redactá UNA sola pieza de copy para Instagram (no el lote completo de 12) de la semana actual del Calendario Editorial, usando las ideas y hashtags ya sugeridos."),
    ("agent_015", "Valentina", "Definí el brief de diseño visual (composición, paleta, referencia) de esa única pieza para la semana actual del Calendario Editorial."),
    ("agent_033", "Marco", "Escribí un guion corto (no el shot-list completo) del video de la semana actual del Calendario Editorial."),
    ("agent_034", "Elena", "Redactá UN solo email (no una secuencia) de la semana actual del Calendario Editorial, usando el llamado a la acción ya definido."),
]

# Hallazgo real de producción (ver ETAPA 4.1): pedirle a estos agentes su
# tarea "completa" tal como la describe su propio prompt base (ej. el lote
# de 12 piezas de Ariel) agota max_tokens del tier ANTES de que lleguen a
# invocar library_save — el resultado se corta a mitad de la redacción y
# nunca queda guardado, sin ningún error visible. Por eso PIPELINE pide
# una sola pieza chica por agente (suficiente para validar que todo el
# circuito Cosmos → Marketing → Biblioteca funciona de punta a punta);
# producir el lote completo real es una decisión de costo (tier/
# max_tokens más altos) para cuando este mecanismo ya esté probado.
BASE_INSTRUCTION = (
    "PASOS OBLIGATORIOS, EN ESTE ORDEN, SIN SALTARTE NINGUNO:\n"
    "1. Llamá a library_search con exactamente la palabra \"calendario editorial\" (así, textual) para "
    "encontrar el Calendario Editorial vigente de este cliente — vas a recibir current_week con el plan "
    "completo de la semana. Basá tu trabajo en eso, nunca lo inventes.\n"
    "2. Escribí tu pieza en 3-6 líneas. NO expliques tu proceso, NO armes una tabla de brief, NO listes "
    "los pasos que vas a seguir — andá directo al contenido final.\n"
    "3. Llamá a library_save con esa pieza INMEDIATAMENTE después de escribirla, en el mismo turno. Este "
    "paso es obligatorio — un borrador guardado e imperfecto vale más que uno perfecto que nunca se guarda.\n"
    "No agregues explicaciones antes ni después de estos 3 pasos."
)


def _build_prompt(
    client: Client,
    instruction: str,
    previous_steps: list[dict],
    forced_week: dict | None = None,
    extra_context: str | None = None,
) -> str:
    if forced_week:
        # Semana especifica pedida a mano -- reemplaza el paso 1 de
        # BASE_INSTRUCTION (buscar "calendario editorial" con library_search)
        # porque esa tool siempre devuelve la semana de HOY, nunca una
        # semana futura puntual (ver _find_week_by_start_date arriba).
        base_instruction = (
            "PASOS OBLIGATORIOS, EN ESTE ORDEN, SIN SALTARTE NINGUNO:\n"
            "1. NO llames a library_search para el calendario editorial esta vez -- ya te doy acá abajo, "
            "textual, los datos reales de la semana que tenés que usar. Basá tu trabajo en eso, nunca "
            "inventes otra cosa.\n"
            "2. Escribí tu pieza en 3-6 líneas. NO expliques tu proceso, NO armes una tabla de brief, NO "
            "listes los pasos que vas a seguir — andá directo al contenido final.\n"
            "3. Llamá a library_save con esa pieza INMEDIATAMENTE después de escribirla, en el mismo "
            "turno. Este paso es obligatorio — un borrador guardado e imperfecto vale más que uno "
            "perfecto que nunca se guarda.\n"
            "No agregues explicaciones antes ni después de estos 3 pasos.\n\n"
            f"DATOS REALES DE LA SEMANA A USAR (start_date={forced_week.get('start_date')}):\n"
            f"{json.dumps(forced_week, ensure_ascii=False, indent=2)}"
        )
    else:
        base_instruction = BASE_INSTRUCTION

    prompt = f"Cliente: {client.name}.\n\n{instruction}\n\n{base_instruction}"
    if extra_context:
        prompt += f"\n\nCONTEXTO ADICIONAL REAL PARA ESTA SEMANA (usalo si encaja con el tema, no lo fuerces):\n{extra_context}"
    if previous_steps:
        material = "\n\n".join(f"## {step['agent']}\n{step['result']}" for step in previous_steps)
        prompt += f"\n\nMaterial ya producido esta semana por el resto del equipo:\n\n{material}"
    return prompt


def _saved_asset_since(db: Session, agent_id, client_id, since: datetime) -> uuid.UUID | None:
    asset = find_recent_asset(db, created_by_agent_id=agent_id, client_id=client_id, since=since)
    return asset.id if asset is not None else None


def _find_week_by_start_date(db: Session, client_id: uuid.UUID | str, target_week_start: str) -> dict | None:
    """2026-08-14 -- LibrarySearchTool._current_week() (src/tools/
    library_search.py) SIEMPRE resuelve la semana por fecha de hoy — no hay
    forma de que un agente pida "la semana que viene" a través de esa tool.
    Para un pedido puntual de generar contenido de una semana FUTURA
    especifica (ej. "generá el contenido de la semana que viene"), se busca
    acá directamente en el calendario editorial guardado, por start_date
    exacto, y esa semana se INYECTA en el prompt de cada agente en vez de
    pedirles que la busquen ellos — evita tocar LibrarySearchTool (tool
    generica, compartida por mucho mas que este pipeline)."""
    asset = next(
        iter(search_assets(db, client_id=client_id, file_type="calendario_editorial", status=None, limit=1)),
        None,
    )
    if asset is None:
        return None
    for week in (asset.structured_content or {}).get("weeks", []):
        if week.get("start_date") == target_week_start:
            return week
    return None


def generate_weekly_marketing_content(
    db: Session,
    client_id: uuid.UUID | str,
    tier_override: str | None = None,
    target_week_start: str | None = None,
    extra_context: str | None = None,
) -> dict:
    """`tier_override` (ej. "economy") fuerza el tier de las 6 llamadas —
    pensado para validar con saldo real limitado, ver
    src/agent_service.py::run().

    `target_week_start` (ISO "YYYY-MM-DD") -- opcional, por defecto None
    (cada agente resuelve "la semana vigente" el mismo de siempre, por
    fecha de hoy). Si se pasa, tiene que matchear EXACTO el start_date de
    una semana ya guardada en el Calendario Editorial de este cliente —
    si no se encuentra, se lanza ValueError en vez de generar con datos
    inventados o de la semana equivocada.

    `extra_context` -- texto libre opcional, se agrega tal cual al prompt
    de los 6 pasos (ej. transitos astrologicos reales verificados para esa
    semana puntual, pedido explicito del usuario 2026-08-14) — nunca
    generado ni inventado por este modulo, siempre provisto por quien
    llama."""
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError("Cliente no encontrado.")

    forced_week: dict | None = None
    if target_week_start:
        forced_week = _find_week_by_start_date(db, client_id, target_week_start)
        if forced_week is None:
            raise ValueError(
                f"No se encontró ninguna semana con start_date='{target_week_start}' en el Calendario "
                "Editorial de este cliente."
            )

    steps: list[dict] = []
    warnings: list[str] = []

    # 2026-07-16 -- ver comentario en tool_assembly.py::assemble_tools(): la
    # cuenta real de Composio de este cliente puede estar conectada bajo un
    # user_id propio (confirmado real para Instagram/EALumina: "ealumina",
    # no el UUID) — si Client.config lo tiene, se usa para que los agentes
    # con tools de Composio (ej. Ariel + composio_instagram) encuentren la
    # cuenta ya conectada de verdad.
    composio_user_id = (client.config or {}).get("composio_user_id")

    for agent_code, name, instruction in PIPELINE:
        agent = db.scalar(select(Agent).where(Agent.agent_code == agent_code))
        if agent is None:
            raise RuntimeError(f"No se encontró el agente {name} ({agent_code}).")

        prompt = _build_prompt(client, instruction, steps, forced_week=forced_week, extra_context=extra_context)
        # Margen de 5s hacia atrás — evita perder por milisegundos un asset
        # guardado justo al arrancar la llamada.
        started_at = datetime.utcnow() - timedelta(seconds=5)
        outcome = run_agent_service(
            db, agent, prompt, user_id=str(client_id), client_id=client.id,
            tier_override=tier_override, composio_user_id=composio_user_id,
        )

        saved_asset_id = _saved_asset_since(db, agent.id, client.id, started_at)
        if saved_asset_id is None:
            warnings.append(f"{name} no guardó ningún recurso nuevo en la Biblioteca (revisar manualmente).")

        steps.append({
            "agent": name,
            "result": outcome.result,
            "saved_asset_id": str(saved_asset_id) if saved_asset_id else None,
            "cost_usd": outcome.cost_usd,
        })

    return {"steps": steps, "warnings": warnings}
