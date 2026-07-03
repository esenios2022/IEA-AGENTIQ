"""Persistent per-patient conversation memory for agents with `case_memory: true`.

A `PatientCase` is a named thread (e.g. "Ana Pérez") a therapist opens once
and keeps sending messages into over days or weeks. Every message — both
the therapist's input and the agent's reply — is saved to `CaseMessage` and
replayed back to the model as prior conversation turns on the next message,
so context (programs already found, commands already applied) isn't lost
between sessions the way it would be with the platform's default
single-shot `run()`.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import CaseMessage, PatientCase

HISTORY_LIMIT = 60


def create_case(db: Session, *, agent_id, client_id, patient_label: str) -> PatientCase:
    case = PatientCase(agent_id=agent_id, client_id=client_id, patient_label=patient_label)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def list_cases(db: Session, *, agent_id=None, client_id=None) -> list[PatientCase]:
    query = select(PatientCase).order_by(PatientCase.updated_at.desc())
    if agent_id is not None:
        query = query.where(PatientCase.agent_id == agent_id)
    if client_id is not None:
        query = query.where(PatientCase.client_id == client_id)
    return list(db.scalars(query).all())


def get_case(db: Session, case_id) -> PatientCase | None:
    return db.get(PatientCase, case_id)


def get_case_history(db: Session, case_id, limit: int = HISTORY_LIMIT) -> list[dict]:
    rows = db.scalars(
        select(CaseMessage).where(CaseMessage.case_id == case_id).order_by(CaseMessage.created_at).limit(limit)
    ).all()
    return [{"role": row.role, "content": row.content} for row in rows]


def append_message(db: Session, case_id, role: str, content: str, cost_usd: float | None = None) -> CaseMessage:
    msg = CaseMessage(case_id=case_id, role=role, content=content, cost_usd=cost_usd)
    db.add(msg)
    case = db.get(PatientCase, case_id)
    if case is not None:
        case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return msg
