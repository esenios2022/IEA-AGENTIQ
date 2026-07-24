"""Runs recurring agent orders (e.g. "every week") in the background."""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from src.agent_service import run as run_agent_service
from src.database import SessionLocal
from src.editorial_calendar import roll_editorial_calendar
from src.instagram_comment_automation import poll_recent_comments
from src.models import Agent, Client, ClientAgent

CHECK_INTERVAL_SECONDS = 300
# Mas seguido que CHECK_INTERVAL_SECONDS a proposito -- la ventana util para
# responder un comentario (antes de que la persona se vaya de Instagram) es
# de minutos, no de 5 en 5 minutos como el resto de los jobs recurrentes.
INSTAGRAM_COMMENT_POLL_SECONDS = 90


def _poll_instagram_comments() -> None:
    try:
        poll_recent_comments()
    except Exception as exc:
        print(f"[scheduler] poll_recent_comments fallo: {exc}", flush=True)

FREQUENCY_DELTAS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


def _run_due_schedules() -> None:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = db.scalars(
            select(ClientAgent).where(
                ClientAgent.schedule_frequency.isnot(None),
                ClientAgent.next_run_at.isnot(None),
                ClientAgent.next_run_at <= now,
            )
        ).all()

        for link in due:
            agent = db.get(Agent, link.agent_id)
            if agent is None:
                continue
            try:
                outcome = run_agent_service(
                    db, agent, link.schedule_input, user_id=str(link.client_id), client_id=link.client_id
                )
                link.last_result = outcome.result
            except Exception as exc:
                link.last_result = f"Error: {exc}"

            link.last_run_at = now
            delta = FREQUENCY_DELTAS.get(link.schedule_frequency, timedelta(days=7))
            link.next_run_at = now + delta
            db.commit()
    finally:
        db.close()


def _run_due_editorial_calendars() -> None:
    """FASE 3.2A — regenera (deslizando) el Calendario Editorial de cada
    cliente con cosmos_calendar_enabled=True cuyo turno ya llegó. Opt-in
    por cliente, apagado por default (ver Client.cosmos_calendar_enabled)."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = db.scalars(
            select(Client).where(
                Client.cosmos_calendar_enabled.is_(True),
                Client.cosmos_calendar_next_run_at.isnot(None),
                Client.cosmos_calendar_next_run_at <= now,
            )
        ).all()

        for client in due:
            try:
                roll_editorial_calendar(db, client.id, auto_provider=True)
                client.cosmos_calendar_last_error = None
            except Exception as exc:
                client.cosmos_calendar_last_error = f"Error: {exc}"

            client.cosmos_calendar_last_run_at = now
            delta = FREQUENCY_DELTAS.get(client.cosmos_calendar_frequency, timedelta(days=7))
            client.cosmos_calendar_next_run_at = now + delta
            db.commit()
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_due_schedules, "interval", seconds=CHECK_INTERVAL_SECONDS)
    scheduler.add_job(_run_due_editorial_calendars, "interval", seconds=CHECK_INTERVAL_SECONDS)
    scheduler.add_job(_poll_instagram_comments, "interval", seconds=INSTAGRAM_COMMENT_POLL_SECONDS)
    scheduler.start()
    return scheduler
