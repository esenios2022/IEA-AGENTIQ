"""2026-07-19 — src.provider_routing.select_provider(). Función pura (sin
DB real, sin red): MagicMock alcanza para Agent/Client, mismo convenio que
tests/test_gemini_executor.py y tests/test_editorial_calendar.py."""

import pytest
from unittest.mock import MagicMock, patch

from src.provider_routing import select_provider


def _agent(tools=None, name="Cosmos"):
    # ojo: MagicMock(name=...) NO fija el atributo .name (es un kwarg
    # reservado para el repr interno del mock) -- hay que asignarlo aparte.
    agent = MagicMock()
    agent.name = name
    agent.definition = {"tools": tools or []}
    return agent


def _client(gemini_key=None):
    config = {"api_keys": {"gemini": gemini_key}} if gemini_key else {}
    return MagicMock(config=config)


def test_agent_with_tools_always_claude_even_with_byok_key_available():
    decision = select_provider(_agent(tools=["composio_googlesheets"]), _client(gemini_key="AIza-fake"))
    assert decision.provider == "claude"
    assert decision.gemini_key is None
    assert "herramientas" in decision.reason


def test_agent_with_tools_and_explicit_gemini_key_raises():
    with pytest.raises(ValueError, match="herramientas"):
        select_provider(_agent(tools=["composio_googlesheets"]), None, requested_gemini_key="AIza-fake")


def test_toolless_agent_prefers_byok_gemini_when_client_has_key():
    decision = select_provider(_agent(tools=[]), _client(gemini_key="AIza-fake"))
    assert decision.provider == "gemini"
    assert decision.gemini_key == "AIza-fake"
    assert decision.platform_cost is False


def test_toolless_agent_falls_back_to_ollama_without_client_key_when_reachable():
    with patch("src.provider_routing.is_ollama_reachable", return_value=True):
        decision = select_provider(_agent(tools=[]), _client(gemini_key=None))
    assert decision.provider == "ollama"
    assert decision.gemini_key is None
    assert decision.platform_cost is False


def test_toolless_agent_falls_back_to_claude_without_client_key_or_ollama():
    with patch("src.provider_routing.is_ollama_reachable", return_value=False):
        decision = select_provider(_agent(tools=[]), _client(gemini_key=None))
    assert decision.provider == "claude"
    assert decision.gemini_key is None


def test_toolless_agent_falls_back_to_claude_with_no_client_at_all_and_no_ollama():
    with patch("src.provider_routing.is_ollama_reachable", return_value=False):
        decision = select_provider(_agent(tools=[]), None)
    assert decision.provider == "claude"


def test_toolless_agent_prefers_byok_gemini_over_ollama_even_when_both_available():
    with patch("src.provider_routing.is_ollama_reachable", return_value=True) as mock_reachable:
        decision = select_provider(_agent(tools=[]), _client(gemini_key="AIza-fake"))
    assert decision.provider == "gemini"
    # ni siquiera debería consultar Ollama si ya hay key BYOK -- Gemini gana primero
    mock_reachable.assert_not_called()


def test_explicit_requested_key_wins_over_client_config_for_toolless_agent():
    decision = select_provider(_agent(tools=[]), _client(gemini_key="from-client-config"), requested_gemini_key="explicit-key")
    assert decision.provider == "gemini"
    assert decision.gemini_key == "explicit-key"
