"""Tests de ResourceManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.resource_manager import ResourceManager


def _make_manager(tmp_path: Path) -> ResourceManager:
    return ResourceManager(tmp_path / "resources")


def _make_source_file(tmp_path: Path, name: str = "foto.jpg") -> Path:
    source = tmp_path / name
    source.write_bytes(b"contenido de prueba")
    return source


def test_creates_category_folders(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    for category in ("images", "audio", "icons", "maps"):
        assert (manager.resources_root / category).is_dir()


def test_import_resource_copies_file(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    source = _make_source_file(tmp_path)

    relative = manager.import_resource(source, "images")

    assert relative == "resources/images/foto.jpg"
    assert (manager.resources_root / "images" / "foto.jpg").exists()


def test_import_resource_invalid_category_raises(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    source = _make_source_file(tmp_path)
    with pytest.raises(ValueError):
        manager.import_resource(source, "videos")


def test_import_resource_missing_source_raises(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    with pytest.raises(FileNotFoundError):
        manager.import_resource(tmp_path / "no_existe.jpg", "images")


def test_import_resource_avoids_overwriting_existing(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    source1 = _make_source_file(tmp_path, "foto.jpg")
    manager.import_resource(source1, "images")

    # Un segundo archivo con el mismo nombre, distinto contenido
    other_dir = tmp_path / "otro"
    other_dir.mkdir()
    source2 = other_dir / "foto.jpg"
    source2.write_bytes(b"contenido distinto")

    relative2 = manager.import_resource(source2, "images")

    assert relative2 == "resources/images/foto_1.jpg"
    # El original no se pisó
    original = (manager.resources_root / "images" / "foto.jpg").read_bytes()
    assert original == b"contenido de prueba"


def test_list_resources_returns_sorted_filenames(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.import_resource(_make_source_file(tmp_path, "zebra.jpg"), "images")
    manager.import_resource(_make_source_file(tmp_path, "alfa.jpg"), "images")

    assert manager.list_resources("images") == ["alfa.jpg", "zebra.jpg"]


def test_list_resources_empty_category(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    assert manager.list_resources("audio") == []


def test_get_absolute_path(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.import_resource(_make_source_file(tmp_path), "images")
    path = manager.get_absolute_path("images", "foto.jpg")
    assert path.exists()


def test_to_relative_path(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    relative = manager.to_relative_path("audio", "sonido.wav")
    assert relative == "resources/audio/sonido.wav"


def test_resolve_relative_path(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.import_resource(_make_source_file(tmp_path), "images")
    resolved = manager.resolve_relative_path("resources/images/foto.jpg")
    assert resolved.exists()


def test_delete_resource_removes_file(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.import_resource(_make_source_file(tmp_path), "images")
    manager.delete_resource("images", "foto.jpg")
    assert manager.list_resources("images") == []


def test_delete_missing_resource_raises(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    with pytest.raises(FileNotFoundError):
        manager.delete_resource("images", "no_existe.jpg")
