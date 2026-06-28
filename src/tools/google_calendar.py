"""Real Google Calendar access for CrewAI agents, via a service account."""

import json
import os
from datetime import datetime, timedelta

from crewai.tools import BaseTool
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TIMEZONE = "America/Montevideo"


def _calendar_service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("calendar", "v3", credentials=credentials)


def _calendar_id() -> str:
    return os.environ["GOOGLE_CALENDAR_ID"]


class CreateCalendarEventTool(BaseTool):
    name: str = "google_calendar_writer"
    description: str = (
        "Crea un evento real en Google Calendar. El input debe ser un único string con este "
        "formato exacto, separado por '|': 'titulo|YYYY-MM-DDTHH:MM|duracion_minutos|notas'. "
        "Ejemplo: 'Primera sesión - Juan Pérez|2026-07-14T10:00|50|Paciente nuevo, motivo: ansiedad'. "
        "Devuelve el link del evento creado."
    )

    def _run(self, event_spec: str) -> str:
        try:
            title, start_str, duration_str, notes = event_spec.split("|", 3)
        except ValueError:
            return "Error: formato inválido. Usá 'titulo|YYYY-MM-DDTHH:MM|duracion_minutos|notas'."

        try:
            start = datetime.fromisoformat(start_str.strip())
            end = start + timedelta(minutes=int(duration_str.strip()))
        except ValueError as exc:
            return f"Error de formato de fecha/duración: {exc}"

        service = _calendar_service()
        event = {
            "summary": title.strip(),
            "description": notes.strip(),
            "start": {"dateTime": start.isoformat(), "timeZone": DEFAULT_TIMEZONE},
            "end": {"dateTime": end.isoformat(), "timeZone": DEFAULT_TIMEZONE},
        }
        created = service.events().insert(calendarId=_calendar_id(), body=event).execute()
        return f"Evento creado con éxito: {created.get('htmlLink')}"


class ListUpcomingEventsTool(BaseTool):
    name: str = "google_calendar_reader"
    description: str = (
        "Devuelve los turnos ya agendados en Google Calendar para los próximos N días. "
        "El input es la cantidad de días como texto, por ejemplo '14'."
    )

    def _run(self, days: str = "14") -> str:
        try:
            horizon = int(str(days).strip())
        except ValueError:
            horizon = 14

        service = _calendar_service()
        now = datetime.utcnow()
        events_result = (
            service.events()
            .list(
                calendarId=_calendar_id(),
                timeMin=now.isoformat() + "Z",
                timeMax=(now + timedelta(days=horizon)).isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return "No hay turnos agendados en ese rango."

        lines = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            lines.append(f"- {start}: {event.get('summary', 'Sin título')}")
        return "\n".join(lines)


TOOL_REGISTRY: dict[str, BaseTool] = {
    "google_calendar_writer": CreateCalendarEventTool(),
    "google_calendar_reader": ListUpcomingEventsTool(),
    "google_calendar": CreateCalendarEventTool(),
    "calendar": CreateCalendarEventTool(),
}
