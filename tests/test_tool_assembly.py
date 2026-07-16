"""2026-07-16 — src.tool_assembly.assemble_tools()'s composio_user_id
override. Real bug found and fixed: user_id doubles as both the
Biblioteca/knowledge-base tenant scope AND the Composio account identity,
but a client's real connected Composio account (confirmed for real:
EALumina's Instagram) can live under a different user_id than the
client's UUID — composio_user_id lets a caller override just the second
role without touching library/knowledge scoping."""

from unittest.mock import patch

from src.tool_assembly import assemble_tools


def _definition_with_composio_tool():
    return {"tools": [{"name": "instagram", "type": "composio"}]}


def test_composio_user_id_override_used_when_provided():
    with patch("src.tool_assembly.get_toolkit_tools", return_value=[]) as mock_get:
        assemble_tools(_definition_with_composio_tool(), user_id="client-uuid-123", composio_user_id="ealumina")

    mock_get.assert_called_once_with("ealumina", ["instagram"])


def test_composio_user_id_falls_back_to_user_id_when_not_provided():
    with patch("src.tool_assembly.get_toolkit_tools", return_value=[]) as mock_get:
        assemble_tools(_definition_with_composio_tool(), user_id="client-uuid-123")

    mock_get.assert_called_once_with("client-uuid-123", ["instagram"])


def test_composio_override_does_not_change_library_scoping():
    """The override must only affect _composio_tools(), never library_search's
    client_id — confirmed by checking the real LibrarySearchTool instance gets
    the original user_id, not the composio override."""
    definition = {"tools": [{"name": "library_search"}]}

    tools = assemble_tools(definition, user_id="client-uuid-123", composio_user_id="ealumina")

    assert len(tools) == 1
    assert tools[0].client_id == "client-uuid-123"
