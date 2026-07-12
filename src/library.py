"""
Biblioteca Inteligente de Marketing — logica de negocio (FASE 2.3).

Sin busqueda vectorial: `search_assets` filtra por columnas exactas y hace
ILIKE sobre title/description/text_content, siguiendo la misma filosofia de
"evitar dependencias exoticas de Postgres" que src/tools/knowledge_base.py
(brute-force cosine en vez de pgvector). A esta escala (biblioteca de
contenido de marketing, no un corpus de RAG masivo) alcanza.

`client_id=None` en las funciones de lectura siempre significa "solo
Recursos Globales"; pasar un client_id incluye ademas los recursos propios
de ese cliente — mismo patron NULL-es-global que KbArticle.client_id.
"""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src import library_storage
from src.library_taxonomy import folder_tree_for_client
from src.models import Client, LibraryAsset

DEFAULT_SEARCH_LIMIT = 20


def _client_scope(client_id: uuid.UUID | str | None):
    scope = LibraryAsset.client_id.is_(None)
    if client_id is not None:
        scope = or_(scope, LibraryAsset.client_id == client_id)
    return scope


def search_assets(
    db: Session,
    *,
    client_id: uuid.UUID | str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    file_type: str | None = None,
    language: str | None = None,
    tags: list[str] | None = None,
    status: str | None = "aprobado",
    query: str | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> list[LibraryAsset]:
    conditions = [_client_scope(client_id)]
    if category:
        conditions.append(LibraryAsset.category == category)
    if subcategory:
        conditions.append(LibraryAsset.subcategory == subcategory)
    if file_type:
        conditions.append(LibraryAsset.file_type == file_type)
    if language:
        conditions.append(LibraryAsset.language == language)
    if status:
        conditions.append(LibraryAsset.status == status)
    if tags:
        conditions.append(LibraryAsset.tags.overlap(tags))
    if query:
        like = f"%{query}%"
        conditions.append(
            or_(
                LibraryAsset.title.ilike(like),
                LibraryAsset.description.ilike(like),
                LibraryAsset.text_content.ilike(like),
            )
        )

    stmt = select(LibraryAsset).where(*conditions).order_by(LibraryAsset.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def get_asset(db: Session, asset_id: uuid.UUID | str) -> LibraryAsset | None:
    return db.get(LibraryAsset, asset_id)


def create_asset(
    db: Session,
    *,
    client_id: uuid.UUID | str | None,
    category: str,
    subcategory: str | None,
    title: str,
    description: str | None,
    file_type: str,
    mime_type: str | None,
    file_extension: str | None,
    file_size_bytes: int | None,
    storage_key: str,
    text_content: str | None,
    language: str = "es",
    tags: list[str] | None = None,
    author: str | None = None,
    created_by_agent_id: uuid.UUID | str | None = None,
    status: str = "borrador",
) -> LibraryAsset:
    asset = LibraryAsset(
        client_id=client_id or None,
        category=category,
        subcategory=subcategory or None,
        title=title,
        description=description,
        file_type=file_type,
        mime_type=mime_type,
        file_extension=file_extension,
        file_size_bytes=file_size_bytes,
        storage_key=storage_key,
        text_content=text_content,
        language=language,
        tags=tags or None,
        author=author,
        created_by_agent_id=created_by_agent_id or None,
        status=status,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_asset_metadata(db: Session, asset_id: uuid.UUID | str, **fields) -> LibraryAsset | None:
    asset = get_asset(db, asset_id)
    if asset is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(asset, key):
            setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


def move_asset(db: Session, asset_id: uuid.UUID | str, category: str, subcategory: str | None) -> LibraryAsset | None:
    return update_asset_metadata(db, asset_id, category=category, subcategory=subcategory or None)


def set_asset_status(db: Session, asset_id: uuid.UUID | str, status: str) -> LibraryAsset | None:
    asset = get_asset(db, asset_id)
    if asset is None:
        return None
    asset.status = status
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, asset_id: uuid.UUID | str) -> bool:
    asset = get_asset(db, asset_id)
    if asset is None:
        return False
    if asset.storage_key:
        try:
            library_storage.delete_asset(asset.storage_key)
        except library_storage.LibraryStorageError as exc:
            print(f"[library] warning: could not delete storage object for asset {asset_id}: {exc}", flush=True)
    db.delete(asset)
    db.commit()
    return True


def get_folder_tree(db: Session, client_id: uuid.UUID | str | None = None) -> dict:
    extra_categories: list[str] = []
    if client_id:
        client = db.get(Client, client_id)
        if client and client.config:
            extra_categories = client.config.get("library_extra_categories") or []
    return folder_tree_for_client(extra_categories)
