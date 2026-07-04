"""Deterministic, no-LLM checklist tool for Miguel (QA/security auditor agent).

Runs plain Python checks (env vars, DB counters) instead of asking the model
to reason about them — zero token cost for routine audits, per the platform's
cost-discipline rule.
"""

from datetime import datetime, timedelta

from crewai.tools import BaseTool
from sqlalchemy import func, select

from src.config import settings
from src.database import SessionLocal
from src.models import Agent, UsageLog

_INSECURE_DEFAULTS = {"admin_password": "change-me", "secret_key": "dev-secret-change-me"}


def _check_seguridad_basica() -> list[str]:
    findings = []
    for field, insecure_default in _INSECURE_DEFAULTS.items():
        if getattr(settings, field, None) == insecure_default:
            findings.append(f"CRÍTICO: {field} sigue con el valor por defecto inseguro.")
    if not settings.anthropic_api_key:
        findings.append("ALTO: ANTHROPIC_API_KEY no está configurada.")
    if not findings:
        findings.append("OK: no se detectaron credenciales por defecto ni claves faltantes.")
    return findings


def _check_salud_agentes() -> list[str]:
    db = SessionLocal()
    try:
        paused = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == "paused")) or 0
        active = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == "active")) or 0
        since = datetime.utcnow() - timedelta(hours=24)
        failed_24h = (
            db.scalar(
                select(func.count()).select_from(UsageLog).where(UsageLog.success.is_(False), UsageLog.created_at >= since)
            )
            or 0
        )
        return [
            f"Agentes activos: {active}",
            f"Agentes pausados por presupuesto: {paused}",
            f"Ejecuciones fallidas (últimas 24h): {failed_24h}",
        ]
    finally:
        db.close()


CHECKLISTS = {
    "seguridad_basica": _check_seguridad_basica,
    "salud_agentes": _check_salud_agentes,
}


class ChecklistTool(BaseTool):
    name: str = "testing_tools"
    description: str = (
        "Corre un checklist determinístico sin usar el modelo (costo cero). "
        f"Checklists disponibles: {', '.join(CHECKLISTS)}."
    )

    def _run(self, checklist: str) -> str:
        key = checklist.strip().lower()
        fn = CHECKLISTS.get(key)
        if fn is None:
            return f"Checklist desconocido «{checklist}». Disponibles: {', '.join(CHECKLISTS)}."
        return "\n".join(fn())
