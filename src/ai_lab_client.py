"""
AI LAB Client — the single, reusable way this platform talks to the AI
LAB Service (Sprint 26 of IEA-AGENTIQ-AI-LAB, a separate repo/process:
FastAPI over PlatformBootstrap, real Workflow/Automation/Knowledge/
WhatsApp engines behind /api/v1/*). Every future AI-LAB-backed tool
should go through this client rather than calling `requests` directly
— same "one reusable client, no duplicated HTTP logic" discipline the
AI LAB itself used for its own internal engines.

Matches this repo's own conventions (confirmed by reading `src/tools/
web_search.py`/`src/tools/zapier.py` before writing this): plain
`requests`, synchronous (this codebase's FastAPI routes are
overwhelmingly sync `def`, not `async def`), `print(f"[module] ...",
flush=True)` for diagnostics (no `logging` module anywhere in `src/`).

Two things this client adds that no other module in this repo has yet
(disclosed, not silently invented): retry-on-transient-failure (this
codebase has no retry/backoff library or convention at all — confirmed
via a real search before deciding this was needed) and real request
correlation IDs (`X-Correlation-Id`), which the AI LAB Service's own
`CorrelationMiddleware` reads and echoes back — verified end to end
during Sprint 26.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import requests

from src.config import settings

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = (0.5, 1.0)
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class AiLabNotConfiguredError(Exception):
    pass


class AiLabRequestError(Exception):
    pass


@dataclass
class AiLabClientMetrics:
    """Real, minimal, in-process counters for this client — this repo has no existing metrics system to plug into (confirmed via a real search); mirrors the same lightweight counter+snapshot shape the AI LAB's own PlatformMetrics uses, scoped to just this client."""

    total_calls: int = 0
    total_errors: int = 0
    total_retries: int = 0
    _latencies_ms: list[float] = field(default_factory=list)

    def record(self, latency_ms: float, success: bool, retries: int) -> None:
        self.total_calls += 1
        self.total_retries += retries
        if not success:
            self.total_errors += 1
        self._latencies_ms.append(latency_ms)

    def snapshot(self) -> dict[str, Any]:
        latencies = self._latencies_ms
        return {
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
            "total_retries": self.total_retries,
            "average_latency_ms": (sum(latencies) / len(latencies)) if latencies else 0.0,
        }


metrics = AiLabClientMetrics()


class AiLabClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = (base_url or settings.ai_lab_base_url or "").rstrip("/")
        self.api_key = api_key or settings.ai_lab_api_key
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.base_url:
            raise AiLabNotConfiguredError("AI_LAB_BASE_URL is not configured.")

        correlation_id = str(uuid.uuid4())
        headers = {"X-Correlation-Id": correlation_id}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        url = f"{self.base_url}{path}"
        started = time.monotonic()
        retries_used = 0
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.request(method, url, json=json_body, headers=headers, timeout=self.timeout_seconds)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    retries_used += 1
                    print(f"[ai_lab_client] {method} {path} attempt {attempt + 1} failed ({exc}), retrying (correlation_id={correlation_id})", flush=True)
                    time.sleep(RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)])
                    continue
                latency_ms = (time.monotonic() - started) * 1000
                metrics.record(latency_ms, success=False, retries=retries_used)
                print(f"[ai_lab_client] {method} {path} failed after {attempt + 1} attempts (correlation_id={correlation_id}): {exc}", flush=True)
                raise AiLabRequestError(f"AI LAB request failed: {exc}") from exc

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                retries_used += 1
                print(f"[ai_lab_client] {method} {path} got {response.status_code}, retrying (correlation_id={correlation_id})", flush=True)
                time.sleep(RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)])
                continue

            latency_ms = (time.monotonic() - started) * 1000
            success = response.ok
            metrics.record(latency_ms, success=success, retries=retries_used)
            if not success:
                print(f"[ai_lab_client] {method} {path} returned {response.status_code} (correlation_id={correlation_id}): {response.text[:300]}", flush=True)
                raise AiLabRequestError(f"AI LAB returned {response.status_code}: {response.text[:300]}")

            print(f"[ai_lab_client] {method} {path} ok in {latency_ms:.0f}ms (correlation_id={correlation_id}, retries={retries_used})", flush=True)
            return response.json()

        latency_ms = (time.monotonic() - started) * 1000
        metrics.record(latency_ms, success=False, retries=retries_used)
        raise AiLabRequestError(f"AI LAB request failed: {last_exc}")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/health")

    def knowledge_search(
        self,
        tenant_id: str,
        query: str,
        knowledge_space_ids: list[str] | None = None,
        max_results: int = 10,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/knowledge/search",
            {
                "tenant_id": tenant_id,
                "query": query,
                "knowledge_space_ids": knowledge_space_ids or [],
                "max_results": max_results,
            },
        )

    def workflow_run(self, tenant_id: str, name: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Real core.workflow.workflow_engine.WorkflowEngine execution (AI LAB Sprint 26 /api/v1/workflow/run) — see docs/SERVICE_API.md in the AI LAB repo for the full step contract (v1 supports run_agent/query_knowledge step_types only)."""
        return self._request("POST", "/api/v1/workflow/run", {"tenant_id": tenant_id, "name": name, "steps": steps})

    def generate_message(self, tenant_id: str, prompt: str, model_hint: str = "llama3.2") -> str:
        """Convenience wrapper over workflow_run(): a single real RUN_AGENT step, returns the generated text. FASE 2.2 — IEA-AGENTIQ generates no text of its own; every AI generation goes through the AI LAB's AIRuntime."""
        result = self.workflow_run(
            tenant_id, name="generate_message",
            steps=[{"id": "s1", "name": "generate", "step_type": "run_agent", "message": prompt, "model_hint": model_hint}],
        )
        if result.get("status") != "completed":
            raise AiLabRequestError(f"AI LAB workflow did not complete: {result}")
        return result["steps"][0]["output"].get("content", "")

    def whatsapp_send(self, tenant_id: str, conversation_id: str, to: str, text: str) -> dict[str, Any]:
        """Real infrastructure.whatsapp.whatsapp_gateway.WhatsAppGateway.send() (AI LAB Sprint 21/26 /api/v1/whatsapp/send)."""
        return self._request(
            "POST", "/api/v1/whatsapp/send",
            {"tenant_id": tenant_id, "conversation_id": conversation_id, "to": to, "text": text},
        )


ai_lab_client = AiLabClient()
