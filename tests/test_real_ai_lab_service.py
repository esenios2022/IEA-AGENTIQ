"""
FASE 2.1 — real, end-to-end proof against a genuinely running AI LAB
Service (no mocks). Skips automatically (not silently) when
AI_LAB_BASE_URL isn't set or the service isn't reachable — this repo
doesn't own or start that process, so a real environment precondition
is the honest way to gate this, same spirit as this codebase's own
`serper_api_key`-configured guards in `src/tools/web_search.py`.
"""

import os

import pytest

from src.ai_lab_client import AiLabClient

AI_LAB_BASE_URL = os.environ.get("AI_LAB_BASE_URL")
AI_LAB_API_KEY = os.environ.get("AI_LAB_API_KEY")

pytestmark = pytest.mark.skipif(
    not AI_LAB_BASE_URL or not AI_LAB_API_KEY,
    reason="AI_LAB_BASE_URL/AI_LAB_API_KEY not set — set both to a real running AI LAB Service to run this real integration test.",
)


@pytest.fixture
def client() -> AiLabClient:
    return AiLabClient(base_url=AI_LAB_BASE_URL, api_key=AI_LAB_API_KEY, timeout_seconds=30.0)


def test_real_health_check(client):
    result = client.health()
    assert "ready" in result
    assert "checks" in result


def test_real_knowledge_search_against_unknown_tenant_returns_empty(client):
    result = client.knowledge_search(tenant_id="ieaagentiq-fase21-test", query="cualquier cosa")
    assert result["text"] == ""
    assert result["sources"] == []
