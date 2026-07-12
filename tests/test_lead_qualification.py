"""
FASE 2.2 — src.lead_qualification. Unit tests mock `ai_lab_client` at
the module boundary (same convention as tests/test_ai_lab_client.py
uses for `requests`), with a lightweight `Lead` instance (constructed
directly, never persisted) and a `MagicMock` `Session` — this repo's
own established pattern for isolating expensive/external dependencies
(see tests/test_agent_platform.py's Anthropic mocking).

test_real_lead_qualification.py (separate file) proves the real,
non-mocked round trip against a live AI LAB Service.
"""

from unittest.mock import MagicMock, patch

from src.ai_lab_client import AiLabNotConfiguredError, AiLabRequestError
from src.lead_qualification import qualify_and_contact_lead
from src.models import Lead


def _lead(**overrides) -> Lead:
    defaults = dict(
        id=1, nombre="Maria", email="maria@example.com", telefono="5511999999999",
        tenant="ealumina", idioma="es", plan_interes="ansiedad", tipo_terapia=None,
        disponibilidad=None, notas=None, pais="Brasil", ciudad="Sao Paulo",
        clasificacion_ia=None, estado="prospecto", fuente="landing_web",
    )
    defaults.update(overrides)
    return Lead(**defaults)


def test_returns_none_when_no_telefono():
    lead = _lead(telefono=None)
    db = MagicMock()
    result = qualify_and_contact_lead(lead, db)
    assert result is None
    db.add.assert_not_called()


def test_full_flow_success_classifies_and_contacts():
    lead = _lead()
    db = MagicMock()
    with patch("src.lead_qualification.ai_lab_client") as mock_client:
        mock_client.generate_message.side_effect = ["tipo_terapia: ansiedad | urgencia: media", "Hola Maria! Gracias por tu consulta."]
        mock_client.whatsapp_send.return_value = {"status": "sent"}

        interaction = qualify_and_contact_lead(lead, db)

    assert mock_client.generate_message.call_count == 2  # clasificacion + bienvenida
    mock_client.whatsapp_send.assert_called_once()
    assert lead.clasificacion_ia == "tipo_terapia: ansiedad | urgencia: media"
    assert lead.estado == "contactado"
    assert interaction.status == "sent"
    assert interaction.message == "Hola Maria! Gracias por tu consulta."
    assert db.add.called
    assert db.commit.called


def test_skips_classification_when_already_classified():
    lead = _lead(clasificacion_ia="tipo_terapia: duelo | urgencia: baja")
    db = MagicMock()
    with patch("src.lead_qualification.ai_lab_client") as mock_client:
        mock_client.generate_message.return_value = "Hola Maria!"
        mock_client.whatsapp_send.return_value = {"status": "sent"}

        qualify_and_contact_lead(lead, db)

    assert mock_client.generate_message.call_count == 1  # solo bienvenida, no reclasifica


def test_request_failure_logs_failed_interaction_and_leaves_estado_unchanged():
    lead = _lead()
    db = MagicMock()
    with patch("src.lead_qualification.ai_lab_client") as mock_client:
        mock_client.generate_message.side_effect = AiLabRequestError("timed out")

        interaction = qualify_and_contact_lead(lead, db)

    assert interaction.status == "failed"
    assert "timed out" in interaction.error
    assert lead.estado == "prospecto"


def test_not_configured_is_treated_as_a_real_failure_not_an_exception():
    lead = _lead()
    db = MagicMock()
    with patch("src.lead_qualification.ai_lab_client") as mock_client:
        mock_client.generate_message.side_effect = AiLabNotConfiguredError("AI_LAB_BASE_URL is not configured.")

        interaction = qualify_and_contact_lead(lead, db)

    assert interaction.status == "failed"
