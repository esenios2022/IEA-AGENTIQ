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


# --- FASE 2.5: execute_publish() y las 5 reglas de seguridad obligatorias ---

def _queued_publication(**overrides):
    defaults = dict(
        status="en_cola", approved_by="Fabian", legal_review_verdict="FIRMAR",
        is_test=False, library_asset_id="asset-1", client_id="client-1", platform="instagram",
        caption="caption real",
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def test_execute_publish_rejects_wrong_status():
    db = MagicMock()
    publication = _queued_publication(status="borrador")

    with patch("src.social_publishing.get_publication", return_value=publication):
        with pytest.raises(social_publishing.PublishExecutionError, match="en_cola"):
            social_publishing.execute_publish(db, "pub-1")

    assert publication.publish_error


def test_execute_publish_rejects_missing_approved_by():
    db = MagicMock()
    publication = _queued_publication(approved_by=None)

    with patch("src.social_publishing.get_publication", return_value=publication):
        with pytest.raises(social_publishing.PublishExecutionError, match="aprobador"):
            social_publishing.execute_publish(db, "pub-1")


def test_execute_publish_rejects_unfavorable_verdict():
    db = MagicMock()
    publication = _queued_publication(legal_review_verdict="INDETERMINADO")

    with patch("src.social_publishing.get_publication", return_value=publication):
        with pytest.raises(social_publishing.PublishExecutionError, match="Elías"):
            social_publishing.execute_publish(db, "pub-1")


def test_execute_publish_allows_firmar_con_cambios():
    db = MagicMock()
    publication = _queued_publication(legal_review_verdict="FIRMAR_CON_CAMBIOS")
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = True
    fake_connector.publish.return_value = {"id": "post-1"}

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        result = social_publishing.execute_publish(db, "pub-1")

    assert result.status == "publicado"


def test_execute_publish_rejects_when_platform_not_connected():
    db = MagicMock()
    publication = _queued_publication()
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = False

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        with pytest.raises(social_publishing.PublishExecutionError, match="conectada"):
            social_publishing.execute_publish(db, "pub-1")

    fake_connector.publish.assert_not_called()


def test_execute_publish_rejects_when_asset_missing():
    db = MagicMock()
    publication = _queued_publication()
    db.get.return_value = None

    with patch("src.social_publishing.get_publication", return_value=publication):
        with pytest.raises(social_publishing.PublishExecutionError, match="recurso"):
            social_publishing.execute_publish(db, "pub-1")


def test_execute_publish_success_marks_publicado_and_stores_response():
    db = MagicMock()
    publication = _queued_publication()
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = True
    fake_connector.publish.return_value = {"id": "post-real-1"}

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        result = social_publishing.execute_publish(db, "pub-1")

    assert result.status == "publicado"
    assert result.platform_post_id == "post-real-1"
    assert result.publish_response == {"id": "post-real-1"}
    assert result.published_at is not None


def test_execute_publish_on_connector_failure_stays_en_cola_and_records_error():
    from src.connectors.providers.base import SocialProviderError

    db = MagicMock()
    publication = _queued_publication()
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = True
    fake_connector.publish.side_effect = SocialProviderError("Instagram rechazó la imagen")

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        with pytest.raises(social_publishing.PublishExecutionError, match="rechazó"):
            social_publishing.execute_publish(db, "pub-1")

    assert publication.status == "en_cola"  # nunca se pierde ni se saca de la cola
    assert "rechazó" in publication.publish_error


# --- 2026-08-13: execute_publish() debe hablar con Composio usando
# Client.config["composio_user_id"] (identidad real), no el UUID crudo del cliente
# (ver src/connectors/base.py::resolve_composio_user_id para el bug real corregido) ---

def _fake_get_with_client(asset, client):
    from src.models import Client, LibraryAsset

    def _get(model, id_):
        if model is Client:
            return client
        if model is LibraryAsset:
            return asset
        return None

    return _get


def test_execute_publish_uses_composio_user_id_override_not_raw_uuid():
    db = MagicMock()
    publication = _queued_publication(client_id="11111111-1111-1111-1111-111111111111")
    client = MagicMock(id="11111111-1111-1111-1111-111111111111", config={"composio_user_id": "ealumina"})
    db.get.side_effect = _fake_get_with_client(_asset(), client)
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = True
    fake_connector.publish.return_value = {"id": "post-1"}

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        social_publishing.execute_publish(db, "pub-1")

    fake_connector.is_connected.assert_called_once_with("ealumina")
    assert fake_connector.publish.call_args[0][0] == "ealumina"


def test_execute_publish_falls_back_to_uuid_when_client_has_no_composio_override():
    db = MagicMock()
    publication = _queued_publication(client_id="11111111-1111-1111-1111-111111111111")
    client = MagicMock(id="11111111-1111-1111-1111-111111111111", config=None)
    db.get.side_effect = _fake_get_with_client(_asset(), client)
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = True
    fake_connector.publish.return_value = {"id": "post-1"}

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        social_publishing.execute_publish(db, "pub-1")

    fake_connector.is_connected.assert_called_once_with("11111111-1111-1111-1111-111111111111")
    assert fake_connector.publish.call_args[0][0] == "11111111-1111-1111-1111-111111111111"


def test_execute_publish_rejects_when_client_missing():
    db = MagicMock()
    publication = _queued_publication()
    db.get.side_effect = _fake_get_with_client(_asset(), None)
    fake_connector = MagicMock()

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        with pytest.raises(social_publishing.PublishExecutionError, match="cliente"):
            social_publishing.execute_publish(db, "pub-1")

    fake_connector.publish.assert_not_called()


def test_execute_publish_is_test_skips_legal_review_check():
    db = MagicMock()
    publication = _queued_publication(is_test=True, legal_review_verdict=None)
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.is_connected.return_value = True
    fake_connector.publish.return_value = {"id": "post-test-1"}

    with patch("src.social_publishing.get_publication", return_value=publication), \
         patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        result = social_publishing.execute_publish(db, "pub-1")

    assert result.status == "publicado"


def test_prepare_test_publication_appends_marker_and_sets_en_cola():
    db = MagicMock()
    db.get.return_value = _asset()
    fake_connector = MagicMock()
    fake_connector.validate_content.return_value = []

    with patch.dict(social_publishing.CONNECTORS, {"instagram": fake_connector}, clear=True):
        publication = social_publishing.prepare_test_publication(
            db, client_id="client-1", library_asset_id="asset-1", platform="instagram",
            caption="probando el pipeline", approved_by="Fabian",
        )

    assert publication.is_test is True
    assert publication.status == "en_cola"
    assert publication.approved_by == "Fabian"
    assert social_publishing.TEST_MARKER in publication.caption
