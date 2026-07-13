"""FASE 2.4 — src.social_publishing. Unit tests use a MagicMock Session
(same convention as tests/test_lead_qualification.py) and patch
run_agent_service / CONNECTORS at the module boundary — no real DB, no
real Composio, no real agent execution."""

from unittest.mock import MagicMock, patch

import pytest

from src import social_publishing


def _asset(**overrides):
    defaults = dict(id="asset-1", status="aprobado", title="Foto", file_type="imagen", category="Marca", subcategory=None)
    defaults.update(overrides)
    return MagicMock(**defaults)


def test_prepare_publication_rejects_missing_asset():
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(ValueError, match="no encontrado"):
        social_publishing.prepare_publication(db, client_id="c1", library_asset_id="missing", platform="instagram", caption="hola")


def test_prepare_publication_rejects_asset_not_approved():
    db = MagicMock()
    db.get.return_value = _asset(status="borrador")

    with pytest.raises(ValueError, match="aprobado"):
        social_publishing.prepare_publication(db, client_id="c1", library_asset_id="asset-1", platform="instagram", caption="hola")


def test_prepare_publication_rejects_unknown_platform():
    db = MagicMock()
    db.get.return_value = _asset()

    with pytest.raises(ValueError, match="no soportada"):
        social_publishing.prepare_publication(db, client_id="c1", library_asset_id="asset-1", platform="tiktok", caption="hola")


def test_prepare_publication_creates_in_borrador():
    db = MagicMock()
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.validate_content.return_value = []

    with patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        social_publishing.prepare_publication(db, client_id="c1", library_asset_id="asset-1", platform="instagram", caption="hola")

    fake_connector.validate_content.assert_called_once()
    assert db.add.called
    added = db.add.call_args[0][0]
    assert added.status == "borrador"
    assert added.platform == "instagram"


def test_request_legal_review_rejects_wrong_initial_status():
    db = MagicMock()
    db.get.return_value = MagicMock(status="aprobado")

    with pytest.raises(social_publishing.InvalidPublicationTransitionError):
        social_publishing.request_legal_review(db, "pub-1")


def test_request_legal_review_raises_when_elias_missing():
    db = MagicMock()
    db.get.return_value = MagicMock(status="borrador")
    db.scalar.return_value = None

    with pytest.raises(RuntimeError, match="Elías"):
        social_publishing.request_legal_review(db, "pub-1")


def test_request_legal_review_no_firmar_rejects():
    db = MagicMock()
    publication = MagicMock(status="borrador", client_id="c1", library_asset_id="asset-1")
    db.get.side_effect = lambda model, id_: publication if id_ == "pub-1" else _asset()
    db.scalar.return_value = MagicMock(agent_code="agent_004")

    with patch("src.social_publishing.run_agent_service", return_value=MagicMock(result="NO FIRMAR: contenido con promesa médica no verificable")):
        social_publishing.request_legal_review(db, "pub-1")

    assert publication.legal_review_verdict == "NO_FIRMAR"
    assert publication.status == "rechazado"


def test_request_legal_review_firmar_moves_to_pendiente_aprobacion():
    db = MagicMock()
    publication = MagicMock(status="borrador", client_id="c1", library_asset_id="asset-1")
    db.get.side_effect = lambda model, id_: publication if id_ == "pub-1" else _asset()
    db.scalar.return_value = MagicMock(agent_code="agent_004")

    with patch("src.social_publishing.run_agent_service", return_value=MagicMock(result="FIRMAR: sin observaciones")):
        social_publishing.request_legal_review(db, "pub-1")

    assert publication.legal_review_verdict == "FIRMAR"
    assert publication.status == "pendiente_aprobacion"


def test_approve_publication_rejects_wrong_status():
    db = MagicMock()
    db.get.return_value = MagicMock(status="borrador")

    with pytest.raises(social_publishing.InvalidPublicationTransitionError):
        social_publishing.approve_publication(db, "pub-1", "Fabian")


def test_approve_publication_moves_to_en_cola():
    db = MagicMock()
    publication = MagicMock(status="pendiente_aprobacion")
    db.get.return_value = publication

    social_publishing.approve_publication(db, "pub-1", "Fabian")

    assert publication.approved_by == "Fabian"
    assert publication.status == "en_cola"


def test_reject_publication_rejects_from_en_cola():
    db = MagicMock()
    db.get.return_value = MagicMock(status="en_cola")

    with pytest.raises(social_publishing.InvalidPublicationTransitionError):
        social_publishing.reject_publication(db, "pub-1")


def test_reject_publication_from_borrador():
    db = MagicMock()
    publication = MagicMock(status="borrador", legal_review_text=None)
    db.get.return_value = publication

    social_publishing.reject_publication(db, "pub-1", reason="marca no coincide")

    assert publication.status == "rechazado"
    assert "marca no coincide" in publication.legal_review_text
