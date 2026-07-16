"""
Library Storage — S3-compatible object storage for the Biblioteca
Inteligente de Marketing (FASE 2.3). Uses `boto3`'s generic S3 client so
this works unmodified against Cloudflare R2, AWS S3, Backblaze B2, or
Supabase Storage's S3-compatible endpoint — the provider is chosen purely
by which endpoint/credentials are set in `Settings`, never hardcoded here.

Matches this repo's own conventions (same as src/ai_lab_client.py):
`print(f"[library_storage] ...", flush=True)` for diagnostics, no
`logging` module. The S3 client is built lazily on first use, not at
import time, so importing this module never requires credentials.
"""

from __future__ import annotations

import mimetypes
import re
import uuid
from typing import Any

from src.config import settings

DEFAULT_PRESIGNED_EXPIRES_SECONDS = 3600
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class LibraryStorageNotConfiguredError(Exception):
    pass


class LibraryStorageError(Exception):
    pass


_client: Any = None


def _get_s3_client() -> Any:
    global _client
    if _client is not None:
        return _client

    if not settings.library_s3_bucket or not settings.library_s3_access_key_id or not settings.library_s3_secret_access_key:
        raise LibraryStorageNotConfiguredError(
            "library_s3_bucket / library_s3_access_key_id / library_s3_secret_access_key are not configured."
        )

    import boto3

    _client = boto3.client(
        "s3",
        endpoint_url=settings.library_s3_endpoint_url,
        aws_access_key_id=settings.library_s3_access_key_id,
        aws_secret_access_key=settings.library_s3_secret_access_key,
        region_name=settings.library_s3_region,
    )
    return _client


def _safe_filename(filename: str) -> str:
    return _SAFE_FILENAME_RE.sub("_", filename.strip()) or "archivo"


def build_storage_key(client_id: str | None, category: str, subcategory: str | None, filename: str) -> str:
    """Tenant isolation at the storage layer too (defense in depth beyond the DB's client_id scoping)."""
    scope = client_id or "global"
    parts = [scope, category, subcategory or "", f"{uuid.uuid4()}_{_safe_filename(filename)}"]
    return "/".join(p for p in parts if p)


def upload_asset(content: bytes, key: str, content_type: str | None = None) -> None:
    client = _get_s3_client()
    extra_args = {"ContentType": content_type} if content_type else {}
    try:
        client.put_object(Bucket=settings.library_s3_bucket, Key=key, Body=content, **extra_args)
    except Exception as exc:
        print(f"[library_storage] upload failed for key={key}: {exc}", flush=True)
        raise LibraryStorageError(f"Upload failed: {exc}") from exc
    print(f"[library_storage] uploaded key={key} ({len(content)} bytes)", flush=True)


def download_asset(key: str) -> bytes:
    client = _get_s3_client()
    try:
        obj = client.get_object(Bucket=settings.library_s3_bucket, Key=key)
        return obj["Body"].read()
    except Exception as exc:
        print(f"[library_storage] download failed for key={key}: {exc}", flush=True)
        raise LibraryStorageError(f"Download failed: {exc}") from exc


def delete_asset(key: str) -> None:
    client = _get_s3_client()
    try:
        client.delete_object(Bucket=settings.library_s3_bucket, Key=key)
    except Exception as exc:
        print(f"[library_storage] delete failed for key={key}: {exc}", flush=True)
        raise LibraryStorageError(f"Delete failed: {exc}") from exc
    print(f"[library_storage] deleted key={key}", flush=True)


def get_asset_url(key: str, expires_in: int = DEFAULT_PRESIGNED_EXPIRES_SECONDS) -> str:
    # FASE 2.4A: LibrarySaveTool guarda `source_url` (ej. un link de HeyGen/
    # Canva/Runway) directamente como storage_key cuando el agente no subio
    # bytes propios — esa URL ya es la ubicacion real del archivo, no una
    # key de nuestro bucket S3. Devolverla tal cual, sin tratarla como key.
    if key.startswith("http://") or key.startswith("https://"):
        return key

    if settings.library_s3_public_base_url:
        return f"{settings.library_s3_public_base_url.rstrip('/')}/{key}"

    client = _get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.library_s3_bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception as exc:
        print(f"[library_storage] presign failed for key={key}: {exc}", flush=True)
        raise LibraryStorageError(f"Could not generate URL: {exc}") from exc


def guess_content_type(filename: str) -> str | None:
    return mimetypes.guess_type(filename)[0]
