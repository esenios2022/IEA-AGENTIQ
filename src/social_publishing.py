"""
Publicación Multicanal — logica de negocio generica (FASE 2.4). Nada
especifico de Instagram vive aca; todo lo especifico de una plataforma
esta detras de src/connectors/registry.py::CONNECTORS.

Flujo secuencial (mismo espiritu que src/library.py::STATUS_FLOW):
borrador -> revision_legal -> pendiente_aprobacion -> aprobado -> en_cola -> [publicado]
con "rechazado" como salida desde cualquier paso previo a en_cola.

request_legal_review() reutiliza el UNICO patron existente en este repo
para "codigo dispara un agente y captura su resultado de forma
sincronica" (src/scheduler.py:_run_due_schedules, misma llamada a
run_agent_service) — no se inventa un mecanismo nuevo de invocacion de
agentes.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent_service import run as run_agent_service
from src.connectors.base import PublishPreview
from src.connectors.registry import CONNECTORS
from src.models import Agent, LibraryAsset, SocialPublication

ELIAS_AGENT_CODE = "agent_004"


class InvalidPublicationTransitionError(Exception):
    pass


def _get_connector(platform: str):
    connector = CONNECTORS.get(platform)
    if connector is None:
        raise ValueError(f"Plataforma no soportada: '{platform}'. Disponibles: {list(CONNECTORS)}.")
    return connector


def prepare_publication(
    db: Session,
    *,
    client_id: uuid.UUID | str,
    library_asset_id: uuid.UUID | str,
    platform: str,
    caption: str,
    created_by_agent_id: uuid.UUID | str | None = None,
) -> SocialPublication:
    asset = db.get(LibraryAsset, library_asset_id)
    if asset is None:
        raise ValueError("Recurso no encontrado en la Biblioteca.")
    if asset.status != "aprobado":
        raise ValueError(
            f"El recurso debe estar 'aprobado' en la Biblioteca antes de preparar una publicación "
            f"(estado actual: '{asset.status}')."
        )

    connector = _get_connector(platform)
    connector.validate_content(asset, caption)  # lanza PublishValidationError si hay un error duro

    publication = SocialPublication(
        client_id=client_id,
        library_asset_id=library_asset_id,
        platform=platform,
        caption=caption,
        created_by_agent_id=created_by_agent_id or None,
        status="borrador",
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return publication


def get_publication(db: Session, publication_id: uuid.UUID | str) -> SocialPublication | None:
    return db.get(SocialPublication, publication_id)


def get_preview(db: Session, publication_id: uuid.UUID | str) -> PublishPreview | None:
    publication = get_publication(db, publication_id)
    if publication is None:
        return None
    asset = db.get(LibraryAsset, publication.library_asset_id)
    connector = _get_connector(publication.platform)
    return connector.build_preview(asset, publication.caption)


def _parse_verdict(text: str) -> str:
    """Parseo best-effort del dictamen de Elías — su propio prompt ya usa
    exactamente estos 3 niveles para contratos; se le pide el mismo formato
    para revisar contenido de marketing. Si no matchea ninguno, se trata
    como indeterminado y el flujo sigue igual requiriendo aprobación humana
    explícita (nunca se auto-aprueba por un parseo ambiguo)."""
    upper = (text or "").upper()
    if "NO FIRMAR" in upper:
        return "NO_FIRMAR"
    if "FIRMAR CON CAMBIOS" in upper:
        return "FIRMAR_CON_CAMBIOS"
    if "FIRMAR" in upper:
        return "FIRMAR"
    return "INDETERMINADO"


def _build_legal_review_prompt(publication: SocialPublication, asset: LibraryAsset) -> str:
    return (
        f"Revisá esta publicación antes de que se envíe a aprobación humana. "
        f"Plataforma: {publication.platform}. Recurso: '{asset.title}' (tipo {asset.file_type}, "
        f"categoría {asset.category}/{asset.subcategory or ''}). "
        f"Caption/texto a publicar:\n\n{publication.caption}\n\n"
        f"Emití tu dictamen en el mismo formato de siempre: FIRMAR / FIRMAR CON CAMBIOS / NO FIRMAR, "
        f"citando el riesgo exacto si corresponde (disclaimers de salud, promesas no verificables, "
        f"cumplimiento normativo del mercado del cliente)."
    )


def request_legal_review(db: Session, publication_id: uuid.UUID | str) -> SocialPublication | None:
    publication = get_publication(db, publication_id)
    if publication is None:
        return None
    if publication.status != "borrador":
        raise InvalidPublicationTransitionError(
            f"Solo se puede enviar a revisión legal desde 'borrador' (estado actual: '{publication.status}')."
        )

    elias = db.scalar(select(Agent).where(Agent.agent_code == ELIAS_AGENT_CODE))
    if elias is None:
        raise RuntimeError(f"No se encontró el agente Elías ({ELIAS_AGENT_CODE}) para la revisión legal.")

    asset = db.get(LibraryAsset, publication.library_asset_id)
    prompt = _build_legal_review_prompt(publication, asset)
    outcome = run_agent_service(db, elias, prompt, user_id=str(publication.client_id), client_id=publication.client_id)

    publication.status = "revision_legal"
    publication.legal_review_text = outcome.result
    verdict = _parse_verdict(outcome.result)
    publication.legal_review_verdict = verdict
    db.commit()

    publication.status = "rechazado" if verdict == "NO_FIRMAR" else "pendiente_aprobacion"
    db.commit()
    db.refresh(publication)
    return publication


def approve_publication(db: Session, publication_id: uuid.UUID | str, approved_by: str) -> SocialPublication | None:
    publication = get_publication(db, publication_id)
    if publication is None:
        return None
    if publication.status != "pendiente_aprobacion":
        raise InvalidPublicationTransitionError(
            f"Solo se puede aprobar desde 'pendiente_aprobacion' (estado actual: '{publication.status}')."
        )
    publication.status = "aprobado"
    publication.approved_by = approved_by
    db.commit()

    # Encolar es consecuencia automática de aprobar, no una decisión aparte.
    publication.status = "en_cola"
    db.commit()
    db.refresh(publication)
    return publication


def reject_publication(db: Session, publication_id: uuid.UUID | str, reason: str | None = None) -> SocialPublication | None:
    publication = get_publication(db, publication_id)
    if publication is None:
        return None
    if publication.status in ("en_cola", "publicado", "rechazado"):
        raise InvalidPublicationTransitionError(f"No se puede rechazar desde el estado '{publication.status}'.")
    publication.status = "rechazado"
    if reason:
        note = f"\n\n[Rechazado manualmente: {reason}]"
        publication.legal_review_text = (publication.legal_review_text or "") + note
    db.commit()
    db.refresh(publication)
    return publication
