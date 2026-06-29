"""Generic Zapier webhook tool: lets any agent trigger any Zap the user has configured."""

import requests
from crewai.tools import BaseTool

WEBHOOK_TIMEOUT_SECONDS = 15


class ZapierWebhookTool(BaseTool):
    name: str = "zapier_webhook"
    description: str = "Ejecuta una automatización de Zapier enviándole datos."
    webhook_url: str = ""

    def _run(self, payload: str) -> str:
        try:
            response = requests.post(
                self.webhook_url, json={"data": payload}, timeout=WEBHOOK_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return f"Automatización de Zapier ejecutada correctamente (status {response.status_code})."
        except requests.RequestException as exc:
            return f"Error ejecutando el webhook de Zapier: {exc}"


def build_zapier_tools(tool_specs: list[dict]) -> list[BaseTool]:
    """One ZapierWebhookTool per configured webhook in the agent's definition."""
    tools = []
    for spec in tool_specs:
        if spec.get("type") != "zapier_webhook":
            continue
        config = spec.get("config") or {}
        url = config.get("url")
        if not url:
            continue
        tools.append(
            ZapierWebhookTool(
                name=spec.get("name", "zapier_webhook"),
                description=spec.get("description", "Ejecuta una automatización de Zapier."),
                webhook_url=url,
            )
        )
    return tools
