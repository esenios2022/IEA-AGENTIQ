"""FASE 2.3 — src.library. Unit tests use a `MagicMock` `Session` (same
convention as tests/test_lead_qualification.py) since this repo's test
suite otherwise relies on a real configured Postgres (see test_main.py),
which isn't available in every environment these tests run in."""

from unittest.mock import MagicMock, patch

from src import library
from src.library_taxonomy import GENERIC_LIBRARY_FOLDERS


def test_search_assets_queries_and_returns_results():
    db = MagicMock()
    fake_asset = MagicMock()
    db.scalars.return_value.all.return_value = [fake_asset]

    results = library.search_assets(db, client_id="client-1", category="Marca", query="logo")

    assert results == [fake_asset]
    db.scalars.assert_called_once()


def test_create_asset_adds_commits_and_refreshes():
    db = MagicMock()

    library.create_asset(
        db,
        client_id=None,
        category="Marca",
        subcategory="Logos",
        title="Logo principal",
        description=None,
        file_type="imagen",
        mime_type="image/png",
        file_extension="png",
        file_size_bytes=1024,
        storage_key="global/Marca/Logos/x.png",
        text_content=None,
    )

    assert db.add.called
    assert db.commit.called
    assert db.refresh.called
    added_asset = db.add.call_args[0][0]
    assert added_asset.title == "Logo principal"
    assert added_asset.status == "borrador"


def test_update_asset_metadata_returns_none_when_not_found():
    db = MagicMock()
    db.get.return_value = None

    result = library.update_asset_metadata(db, "missing-id", title="Nuevo título")

    assert result is None
    db.commit.assert_not_called()


def test_update_asset_metadata_updates_only_provided_fields():
    db = MagicMock()
    fake_asset = MagicMock(title="Viejo", category="Marca")
    db.get.return_value = fake_asset

    result = library.update_asset_metadata(db, "asset-1", title="Nuevo título", category=None)

    assert result is fake_asset
    assert fake_asset.title == "Nuevo título"
    assert fake_asset.category == "Marca"  # None values are not applied
    db.commit.assert_called_once()


def test_set_asset_status_updates_status():
    db = MagicMock()
    fake_asset = MagicMock(status="borrador")
    db.get.return_value = fake_asset

    result = library.set_asset_status(db, "asset-1", "aprobado")

    assert result is fake_asset
    assert fake_asset.status == "aprobado"


def test_delete_asset_removes_from_storage_and_db():
    db = MagicMock()
    fake_asset = MagicMock(storage_key="global/Marca/x.png")
    db.get.return_value = fake_asset

    with patch("src.library.library_storage.delete_asset") as mock_delete:
        deleted = library.delete_asset(db, "asset-1")

    assert deleted is True
    mock_delete.assert_called_once_with("global/Marca/x.png")
    db.delete.assert_called_once_with(fake_asset)
    db.commit.assert_called_once()


def test_delete_asset_returns_false_when_not_found():
    db = MagicMock()
    db.get.return_value = None

    assert library.delete_asset(db, "missing-id") is False


def test_get_folder_tree_without_client_returns_generic_tree():
    db = MagicMock()

    tree = library.get_folder_tree(db, client_id=None)

    assert tree == GENERIC_LIBRARY_FOLDERS
    db.get.assert_not_called()


def test_get_folder_tree_merges_client_extra_categories():
    db = MagicMock()
    fake_client = MagicMock(config={"library_extra_categories": ["Recursos terapéuticos"]})
    db.get.return_value = fake_client

    tree = library.get_folder_tree(db, client_id="ealumina-id")

    assert "Recursos terapéuticos" in tree
    assert "Marca" in tree
