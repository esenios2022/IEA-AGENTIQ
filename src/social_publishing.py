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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent_service import run as run_agent_service
from src.connectors.base import PublishPreview, PublishValidationError
from src.connectors.providers.base import SocialProviderError
from src.connectors.registry import CONNECTORS
from src.models import Agent, LibraryAsset, SocialPublication

ELIAS_AGENT_CODE = "agent_004"
FAVORABLE_VERDICTS = {"FIRMAR", "FIRMAR_CON_CAMBIOS"}
TEST_MARKER = "\n\n[PRUEBA TÉCNICA - IEA AGENTIQ]"


class InvalidPublicationTransitionError(Exception):
    pass


class PublishExecutionError(Exception):
    """Alguna de las 5 reglas de seguridad obligatorias falló, o
    connector.publish() falló contra la API real. En todos los casos el
    motivo queda guardado en SocialPublication.publish_error y la
    publicación permanece en 'en_cola' (nunca se pierde ni se saca de la
    cola) — se puede reintentar apretando Publicar de nuevo."""

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


def execute_publish(db: Session, publication_id: uuid.UUID | str) -> SocialPublication | None:
    """FASE 2.5 — único punto de entrada real hacia connector.publish().
    Antes de ejecutar, verifica las 5 reglas de seguridad obligatorias
    (autorizado explícitamente por el usuario, 2026-07-13): (1) estado
    en_cola, (2) aprobación humana registrada, (3) dictamen favorable de
    Elías — FIRMAR o FIRMAR_CON_CAMBIOS, salvo is_test que la saltea a
    propósito, (4) cuenta de la plataforma conectada y validada, (5) el
    recurso existe. Cualquier falla (de estas reglas o de connector.
    publish() contra la API real) se registra en publish_error y la
    publicación queda en 'en_cola' para poder reintentar — nunca se
    pierde ni se saca de la cola."""
    publication = get_publication(db, publication_id)
    if publication is None:
        return None

    def _fail(reason: str) -> None:
        publication.publish_error = reason
        db.commit()
        raise PublishExecutionError(reason)

    if publication.status != "en_cola":
        _fail(f"No se puede publicar desde el estado '{publication.status}' (debe estar en 'en_cola').")
    if not publication.approved_by:
        _fail("Falta un usuario aprobador registrado para esta publicación.")
    if not publication.is_test and publication.legal_review_verdict not in FAVORABLE_VERDICTS:
        _fail(f"No hay un dictamen favorable de Elías registrado (veredicto actual: '{publication.legal_review_verdict}').")

    asset = db.get(LibraryAsset, publication.library_asset_id)
    if asset is None or not asset.storage_key:
        _fail("El recurso de la Biblioteca ya no existe o no tiene un archivo asociado.")

    connector = _get_connector(publication.platform)
    if not connector.is_connected(str(publication.client_id)):
        _fail(f"La cuenta de {publication.platform} no está conectada o no está activa.")

    try:
        result = connector.publish(str(publication.client_id), asset, publication.caption)
    except (PublishValidationError, SocialProviderError) as exc:
        _fail(str(exc))
        return None  # inalcanzable, _fail siempre lanza — deja claro el flujo al lector

    publication.status = "publicado"
    publication.platform_post_id = result.get("id")
    publication.publish_response = result
    publication.publish_error = None
    publication.published_at = datetime.utcnow()
    db.commit()
    db.refresh(publication)
    return publication


def prepare_test_publication(
    db: Session,
    *,
    client_id: uuid.UUID | str,
    library_asset_id: uuid.UUID | str,
    platform: str,
    caption: str,
    approved_by: str,
) -> SocialPublication:
    """'Publicar en modo prueba' (sugerencia del usuario, 2026-07-13) — salta
    a propósito la revisión legal, porque no es contenido de campaña real
    sino una validación técnica del pipeline. Marca is_test=True y agrega
    el marcador al caption para que nunca se confunda con una publicación
    real en los registros. Quien dispara el test queda como aprobador
    (satisface la regla de "aprobación humana registrada" de todos modos)."""
    publication = prepare_publication(
        db,
        client_id=client_id,
        library_asset_id=library_asset_id,
        platform=platform,
        caption=f"{caption}{TEST_MARKER}",
    )
    publication.is_test = True
    publication.approved_by = approved_by
    publication.status = "en_cola"
    db.commit()
    db.refresh(publication)
    return publication
