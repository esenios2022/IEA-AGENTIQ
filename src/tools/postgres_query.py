"""Read-only, aggregation-only SQL access to the platform's own Postgres database.

Maps to the `supabase_query` tool id in agents_config.json. Never returns full
tables to the model's context — only aggregated results (COUNT/SUM/AVG) with a
LIMIT, per the platform's cost-discipline rule. In production, point this at a
read-only DB role if the hosting provider supports one (defense in depth on
top of the guards below).
"""

import re

from crewai.tools import BaseTool
from sqlalchemy import text

from src.database import SessionLocal

ALLOWED_TABLES = {"agents", "clients", "client_agents", "usage_log", "leads", "kb_articles"}
FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "grant",
    "revoke",
    "create",
    "into",
    "exec",
    "execute",
    "call",
    "copy",
    "vacuum",
    "attach",
    "detach",
    "pragma",
}
DEFAULT_LIMIT = 500


def _validate_and_prepare(query: str) -> tuple[bool, str]:
    """Returns (ok, query_or_error_message)."""
    stripped = query.strip().rstrip(";").strip()
    if not stripped:
        return False, "Consulta vacía."

    if ";" in stripped:
        return False, "Solo se permite una sentencia por consulta (no uses ';' dentro de la query)."

    lowered = stripped.lower()
    if not lowered.startswith("select"):
        return False, "Solo se permiten consultas SELECT de solo lectura."

    tokens = set(re.findall(r"[a-zA-Z_]+", lowered))
    forbidden_hit = tokens & FORBIDDEN_KEYWORDS
    if forbidden_hit:
        return False, f"Consulta rechazada: contiene palabras no permitidas ({', '.join(sorted(forbidden_hit))})."

    referenced_tables = set(re.findall(r"(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered))
    unknown_tables = referenced_tables - ALLOWED_TABLES
    if unknown_tables:
        return False, f"Tabla no permitida: {', '.join(sorted(unknown_tables))}."

    if "limit" not in lowered:
        stripped = f"{stripped} LIMIT {DEFAULT_LIMIT}"

    return True, stripped


class PostgresQueryTool(BaseTool):
    name: str = "postgres_query"
    description: str = (
        "Ejecuta una consulta SQL de solo lectura (SELECT) sobre la base de datos de la plataforma "
        f"(tablas permitidas: {', '.join(sorted(ALLOWED_TABLES))}). Usá SIEMPRE agregaciones "
        "(COUNT/SUM/AVG/GROUP BY) y nunca traigas una tabla entera: el resultado se recorta a "
        f"{DEFAULT_LIMIT} filas si no especificás LIMIT."
    )

    def _run(self, query: str) -> str:
        ok, result = _validate_and_prepare(query)
        if not ok:
            return f"Error: {result}"

        db = SessionLocal()
        try:
            rows = db.execute(text(result)).mappings().all()
        except Exception as exc:
            return f"Error ejecutando la consulta: {exc}"
        finally:
            db.close()

        if not rows:
            return "La consulta no devolvió resultados."
        return "\n".join(str(dict(row)) for row in rows)
