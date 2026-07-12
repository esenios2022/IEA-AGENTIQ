"""
FASE 2.1 — AI LAB Client. Unit tests mock `requests.request` (this
repo's own established convention for external SDKs/APIs — see
`tests/test_agent_platform.py`'s `Anthropic` mocking); a separate,
real integration test (`test_real_ai_lab_service.py`) hits an actual
running AI LAB Service instead, skipped automatically when one isn't
reachable rather than always mocked.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.ai_lab_client import AiLabClient, AiLabNotConfiguredError, AiLabRequestError


def _client() -> AiLabClient:
    return AiLabClient(base_url="http://ai-lab.test", api_key="test-key", timeout_seconds=5.0)


def _ok_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = payload
    return response


def test_raises_when_base_url_not_configured():
    client = AiLabClient(base_url=None, api_key="test-key")
    with pytest.raises(AiLabNotConfiguredError):
        client.health()


def test_health_sends_api_key_and_correlation_headers():
    client = _client()
    with patch("src.ai_lab_client.requests.request", return_value=_ok_response({"ready": True})) as mock_request:
        result = client.health()

    assert result == {"ready": True}
    _, kwargs = mock_request.call_args
    assert kwargs["headers"]["X-API-Key"] == "test-key"
    assert "X-Correlation-Id" in kwargs["headers"]


def test_knowledge_search_posts_expected_body():
    client = _client()
    with patch("src.ai_lab_client.requests.request", return_value=_ok_response({"text": "hola", "sources": []})) as mock_request:
        result = client.knowledge_search(tenant_id="acme", query="vacaciones", max_results=3)

    assert result["text"] == "hola"
    args, kwargs = mock_request.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/api/v1/knowledge/search")
    assert kwargs["json"] == {"tenant_id": "acme", "query": "vacaciones", "knowledge_space_ids": [], "max_results": 3}


def test_retries_on_connection_error_then_succeeds():
    client = _client()
    with patch("src.ai_lab_client.requests.request") as mock_request, patch("src.ai_lab_client.time.sleep"):
        mock_request.side_effect = [requests.ConnectionError("boom"), _ok_response({"ready": True})]
        result = client.health()

    assert result == {"ready": True}
    assert mock_request.call_count == 2


def test_retries_on_5xx_then_gives_up():
    client = _client()
    failing_response = MagicMock(ok=False, status_code=503, text="Service Unavailable")
    with patch("src.ai_lab_client.requests.request", return_value=failing_response) as mock_request, patch("src.ai_lab_client.time.sleep"):
        with pytest.raises(AiLabRequestError):
            client.health()

    assert mock_request.call_count == 3  # 1 initial + MAX_RETRIES(2)


def test_does_not_retry_on_4xx():
    client = _client()
    failing_response = MagicMock(ok=False, status_code=401, text="Invalid API key")
    with patch("src.ai_lab_client.requests.request", return_value=failing_response) as mock_request:
        with pytest.raises(AiLabRequestError):
            client.health()

    assert mock_request.call_count == 1


def test_metrics_record_real_calls():
    from src.ai_lab_client import metrics

    before = metrics.snapshot()["total_calls"]
    client = _client()
    with patch("src.ai_lab_client.requests.request", return_value=_ok_response({"ready": True})):
        client.health()

    after = metrics.snapshot()["total_calls"]
    assert after == before + 1
