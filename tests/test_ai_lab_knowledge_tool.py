"""FASE 2.1 — AiLabKnowledgeSearchTool, and its wiring into tool_assembly.py's per-agent scoping (mirrors the existing knowledge_base/KnowledgeBaseTool test coverage pattern)."""

from unittest.mock import patch

from src.ai_lab_client import AiLabNotConfiguredError, AiLabRequestError
from src.tool_assembly import _matching_tools
from src.tools.ai_lab_knowledge import AiLabKnowledgeSearchTool


def test_returns_message_when_no_tenant_id():
    tool = AiLabKnowledgeSearchTool(tenant_id=None)
    assert "no hay tenant_id" in tool._run("hola").lower()


def test_returns_text_from_real_client_call():
    tool = AiLabKnowledgeSearchTool(tenant_id="acme")
    with patch("src.tools.ai_lab_knowledge.ai_lab_client.knowledge_search", return_value={"text": "contenido relevante", "sources": []}) as mock_search:
        result = tool._run("politica de vacaciones")

    assert result == "contenido relevante"
    mock_search.assert_called_once_with(tenant_id="acme", query="politica de vacaciones")


def test_returns_message_when_not_configured():
    tool = AiLabKnowledgeSearchTool(tenant_id="acme")
    with patch("src.tools.ai_lab_knowledge.ai_lab_client.knowledge_search", side_effect=AiLabNotConfiguredError("x")):
        result = tool._run("hola")
    assert "AI_LAB_BASE_URL" in result


def test_returns_message_on_request_error():
    tool = AiLabKnowledgeSearchTool(tenant_id="acme")
    with patch("src.tools.ai_lab_knowledge.ai_lab_client.knowledge_search", side_effect=AiLabRequestError("timed out")):
        result = tool._run("hola")
    assert "timed out" in result


def test_tool_assembly_scopes_tenant_id_from_user_id():
    definition = {"tools": [{"name": "ai_lab_knowledge"}]}
    tools = _matching_tools(definition, agent_id="agent-1", user_id="client-42")
    assert len(tools) == 1
    assert isinstance(tools[0], AiLabKnowledgeSearchTool)
    assert tools[0].tenant_id == "client-42"
