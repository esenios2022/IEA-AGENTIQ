"""2026-07-19 — src.ollama_executor. Mismo convenio que
tests/test_gemini_executor.py: se patchea requests en el límite real del
módulo (import a nivel de módulo acá, a diferencia de google.genai que se
importa local a la función)."""

from unittest.mock import MagicMock, patch

import requests

from src.ollama_executor import OLLAMA_MODEL, OllamaUnavailableError, is_ollama_reachable, run_ollama


def _agent():
    return MagicMock(definition={"instructions": {"system_prompt": "Sos un asistente de prueba."}})


def test_run_ollama_returns_real_token_usage():
    fake_response = MagicMock(ok=True)
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "message": {"role": "assistant", "content": "Respuesta real de Ollama."},
        "prompt_eval_count": 38,
        "eval_count": 3,
    }

    with patch("src.ollama_executor.requests.post", return_value=fake_response) as mock_post:
        result = run_ollama(_agent(), "hola")

    assert result.text == "Respuesta real de Ollama."
    assert result.model == OLLAMA_MODEL
    assert result.input_tokens == 38
    assert result.output_tokens == 3
    assert result.tool_calls == 0
    assert mock_post.call_args.kwargs["json"]["model"] == OLLAMA_MODEL
    assert mock_post.call_args.kwargs["json"]["messages"][-1] == {"role": "user", "content": "hola"}


def test_run_ollama_raises_ollama_unavailable_on_connection_error():
    with patch("src.ollama_executor.requests.post", side_effect=requests.ConnectionError("refused")):
        try:
            run_ollama(_agent(), "hola")
            assert False, "esperaba OllamaUnavailableError"
        except OllamaUnavailableError:
            pass


def test_run_ollama_includes_history_and_system_prompt():
    fake_response = MagicMock(ok=True)
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"message": {"content": "ok"}, "prompt_eval_count": 1, "eval_count": 1}

    history = [{"role": "user", "content": "primer mensaje"}, {"role": "assistant", "content": "primera respuesta"}]
    with patch("src.ollama_executor.requests.post", return_value=fake_response) as mock_post:
        run_ollama(_agent(), "segundo mensaje", history=history)

    sent_messages = mock_post.call_args.kwargs["json"]["messages"]
    assert sent_messages[0]["role"] == "system"
    assert {"role": "user", "content": "primer mensaje"} in sent_messages
    assert {"role": "assistant", "content": "primera respuesta"} in sent_messages
    assert sent_messages[-1] == {"role": "user", "content": "segundo mensaje"}


def test_is_ollama_reachable_true_when_service_responds():
    fake_response = MagicMock(ok=True)
    with patch("src.ollama_executor.requests.get", return_value=fake_response):
        assert is_ollama_reachable() is True


def test_is_ollama_reachable_false_on_connection_error():
    with patch("src.ollama_executor.requests.get", side_effect=requests.ConnectionError("refused")):
        assert is_ollama_reachable() is False


def test_is_ollama_reachable_false_on_timeout():
    with patch("src.ollama_executor.requests.get", side_effect=requests.Timeout("timed out")):
        assert is_ollama_reachable() is False
