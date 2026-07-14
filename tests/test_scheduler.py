"""FASE 3.2A — src.scheduler._run_due_editorial_calendars. Patchea
SessionLocal y roll_editorial_calendar en el límite del módulo, mismo
convenio que el resto de los tests de orquestación de este repo (Session
MagicMock, sin DB real)."""

from unittest.mock import MagicMock, patch

from src import scheduler


def test_run_due_editorial_calendars_rolls_due_clients():
    db = MagicMock()
    due_client = MagicMock(cosmos_calendar_frequency="weekly")
    db.scalars.return_value.all.return_value = [due_client]

    with patch("src.scheduler.SessionLocal", return_value=db), \
         patch("src.scheduler.roll_editorial_calendar") as roll_mock:
        scheduler._run_due_editorial_calendars()

    roll_mock.assert_called_once_with(db, due_client.id)
    assert due_client.cosmos_calendar_last_error is None
    assert due_client.cosmos_calendar_last_run_at is not None
    assert due_client.cosmos_calendar_next_run_at is not None
    db.commit.assert_called()


def test_run_due_editorial_calendars_records_error_and_keeps_going():
    db = MagicMock()
    due_client = MagicMock(cosmos_calendar_frequency="weekly")
    db.scalars.return_value.all.return_value = [due_client]

    with patch("src.scheduler.SessionLocal", return_value=db), \
         patch("src.scheduler.roll_editorial_calendar", side_effect=RuntimeError("boom")):
        scheduler._run_due_editorial_calendars()

    assert "boom" in due_client.cosmos_calendar_last_error
    assert due_client.cosmos_calendar_last_run_at is not None
    # el scheduler solo registra el error y reprograma - nunca borra ni
    # toca el calendario vigente anterior (eso lo garantiza
    # roll_editorial_calendar/generate_editorial_calendar, no este loop).


def test_run_due_editorial_calendars_daily_frequency_advances_by_1_day():
    db = MagicMock()
    due_client = MagicMock(cosmos_calendar_frequency="daily")
    db.scalars.return_value.all.return_value = [due_client]

    with patch("src.scheduler.SessionLocal", return_value=db), \
         patch("src.scheduler.roll_editorial_calendar"):
        scheduler._run_due_editorial_calendars()

    delta = due_client.cosmos_calendar_next_run_at - due_client.cosmos_calendar_last_run_at
    assert delta.days == 1


def test_run_due_editorial_calendars_no_due_clients_does_nothing():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    with patch("src.scheduler.SessionLocal", return_value=db), \
         patch("src.scheduler.roll_editorial_calendar") as roll_mock:
        scheduler._run_due_editorial_calendars()

    roll_mock.assert_not_called()
