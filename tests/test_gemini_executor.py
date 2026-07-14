"""Modo Producción (2026-07-15) — src.gemini_executor. Reescrito con el
SDK google-genai (el google.generativeai viejo está deprecado y,
confirmado real, ya devuelve 404 para keys nuevas). Se patchea
google.genai.Client en el límite real del módulo (el import es local a
run_gemini, no hay un genai importado a nivel de módulo para patchear)."""

from unittest.mock import MagicMock, patch

from src.gemini_executor import GEMINI_MODEL, _clean_assistant_msg, run_gemini


def _agent():
    return MagicMock(definition={"instructions": {"system_prompt": "Sos un asistente de prueba."}})


def test_clean_assistant_msg_strips_metadata_prefix():
    text = "[tier: economy]\n\nHola, esto es la respuesta real."
    assert _clean_assistant_msg(text) == "Hola, esto es la respuesta real."


def test_clean_assistant_msg_leaves_plain_text_untouched():
    assert _clean_assistant_msg("Sin prefijo, texto normal.") == "Sin prefijo, texto normal."


def test_run_gemini_returns_real_token_usage():
    fake_usage = MagicMock(prompt_token_count=20, candidates_token_count=12, thoughts_token_count=168)
    fake_response = MagicMock(text="Respuesta real de Gemini.", usage_metadata=fake_usage)
    fake_chat = MagicMock()
    fake_chat.send_message.return_value = fake_response
    fake_client = MagicMock()
    fake_client.chats.create.return_value = fake_chat

    with patch("google.genai.Client", return_value=fake_client):
        result = run_gemini(_agent(), "hola", "fake-api-key")

    assert result.text == "Respuesta real de Gemini."
    assert result.model == GEMINI_MODEL
    assert result.input_tokens == 20
    assert result.output_tokens == 12 + 168  # candidates + thinking tokens cuentan como salida real
    assert result.tool_calls == 0


def test_run_gemini_handles_missing_usage_metadata_without_crashing():
    fake_response = MagicMock(text="Respuesta sin metadata.", usage_metadata=None)
    fake_chat = MagicMock()
    fake_chat.send_message.return_value = fake_response
    fake_client = MagicMock()
    fake_client.chats.create.return_value = fake_chat

    with patch("google.genai.Client", return_value=fake_client):
        result = run_gemini(_agent(), "hola", "fake-api-key")

    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_run_gemini_builds_history_and_cleans_assistant_prefixes():
    fake_response = MagicMock(text="ok", usage_metadata=None)
    fake_chat = MagicMock()
    fake_chat.send_message.return_value = fake_response
    fake_client = MagicMock()
    fake_client.chats.create.return_value = fake_chat

    history = [
        {"role": "user", "content": "primera pregunta"},
        {"role": "assistant", "content": "[tier: economy]\n\nprimera respuesta"},
    ]

    with patch("google.genai.Client", return_value=fake_client):
        run_gemini(_agent(), "segunda pregunta", "fake-api-key", history=history)

    call_kwargs = fake_client.chats.create.call_args.kwargs
    built_history = call_kwargs["history"]
    assert len(built_history) == 2
    assert built_history[0].role == "user"
    assert built_history[1].role == "model"
    assert built_history[1].parts[0].text == "primera respuesta"  # prefijo de metadata removido
