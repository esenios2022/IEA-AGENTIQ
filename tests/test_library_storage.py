"""FASE 2.3 — src.library_storage. Unit tests mock `boto3.client` (this
repo's own convention for external SDKs — see tests/test_ai_lab_client.py
mocking `requests`), so no real bucket/credentials are needed to run
these."""

from unittest.mock import MagicMock, patch

import pytest

from src import library_storage


def _reset_client():
    library_storage._client = None


def test_build_storage_key_scopes_by_client_and_sanitizes_filename():
    key = library_storage.build_storage_key("client-1", "Redes Sociales", "Instagram/Publicaciones", "foto raro!.png")
    assert key.startswith("client-1/Redes Sociales/Instagram/Publicaciones/")
    assert key.endswith(".png") or "foto_raro" in key


def test_build_storage_key_uses_global_scope_when_no_client():
    key = library_storage.build_storage_key(None, "Marca", None, "logo.png")
    assert key.startswith("global/Marca/")


def test_get_s3_client_raises_when_not_configured():
    _reset_client()
    with patch.object(library_storage.settings, "library_s3_bucket", None):
        with pytest.raises(library_storage.LibraryStorageNotConfiguredError):
            library_storage._get_s3_client()


def test_upload_asset_calls_put_object():
    _reset_client()
    fake_client = MagicMock()
    with patch.object(library_storage, "_get_s3_client", return_value=fake_client), \
         patch.object(library_storage.settings, "library_s3_bucket", "test-bucket"):
        library_storage.upload_asset(b"hello", "global/Marca/key.txt", content_type="text/plain")

    fake_client.put_object.assert_called_once()
    _, kwargs = fake_client.put_object.call_args
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == "global/Marca/key.txt"
    assert kwargs["Body"] == b"hello"


def test_delete_asset_calls_delete_object():
    _reset_client()
    fake_client = MagicMock()
    with patch.object(library_storage, "_get_s3_client", return_value=fake_client):
        library_storage.delete_asset("global/Marca/key.txt")

    fake_client.delete_object.assert_called_once()


def test_get_asset_url_returns_external_urls_as_is():
    """FASE 2.4A — LibrarySaveTool stores an agent's source_url (HeyGen/Canva/
    Runway link) directly as storage_key; it must never be treated as an S3
    key (found via real functional testing — it was being silently mangled
    into a broken presigned-URL path before this fix)."""
    with patch.object(library_storage.settings, "library_s3_public_base_url", "https://cdn.example.com"):
        url = library_storage.get_asset_url("https://heygen.example.com/videos/abc123.mp4")
    assert url == "https://heygen.example.com/videos/abc123.mp4"


def test_get_asset_url_uses_public_base_url_when_configured():
    with patch.object(library_storage.settings, "library_s3_public_base_url", "https://cdn.example.com"):
        url = library_storage.get_asset_url("global/Marca/key.txt")
    assert url == "https://cdn.example.com/global/Marca/key.txt"


def test_get_asset_url_falls_back_to_presigned_url():
    _reset_client()
    fake_client = MagicMock()
    fake_client.generate_presigned_url.return_value = "https://s3.example.com/signed"
    with patch.object(library_storage, "_get_s3_client", return_value=fake_client), \
         patch.object(library_storage.settings, "library_s3_public_base_url", None):
        url = library_storage.get_asset_url("global/Marca/key.txt")

    assert url == "https://s3.example.com/signed"
    fake_client.generate_presigned_url.assert_called_once()
