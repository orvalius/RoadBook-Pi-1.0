"""Tests de inspección/validación de MBTiles y cambio de mapa en caliente."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.map_manager import InvalidMbtilesError, MapManager, inspect_mbtiles
from tests.conftest import make_mbtiles


def test_inspect_valid_mbtiles(tmp_path: Path) -> None:
    info = inspect_mbtiles(make_mbtiles(tmp_path / "cba.mbtiles"))

    assert info.name == "Mapa de prueba"
    assert info.tile_format == "png"
    assert (info.min_zoom, info.max_zoom) == (10, 12)
    assert info.bounds == (-64.6, -31.7, -64.1, -31.2)
    assert info.size_bytes > 0
    assert not info.is_vector


def test_inspect_reads_zoom_from_tiles_when_metadata_lacks_it(tmp_path: Path) -> None:
    path = make_mbtiles(tmp_path / "m.mbtiles", zooms=(7, 9), with_metadata_zoom=False)
    info = inspect_mbtiles(path)
    assert (info.min_zoom, info.max_zoom) == (7, 9)


def test_inspect_defaults_name_and_format(tmp_path: Path) -> None:
    path = make_mbtiles(tmp_path / "sin_meta.mbtiles", name=None, tile_format=None)
    info = inspect_mbtiles(path)
    assert info.name == "sin_meta"
    assert info.tile_format == "png"


def test_inspect_flags_vector_tiles(tmp_path: Path) -> None:
    info = inspect_mbtiles(make_mbtiles(tmp_path / "v.mbtiles", tile_format="pbf"))
    assert info.is_vector


def test_inspect_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidMbtilesError, match="No existe"):
        inspect_mbtiles(tmp_path / "nada.mbtiles")


def test_inspect_rejects_non_sqlite(tmp_path: Path) -> None:
    path = tmp_path / "foto.mbtiles"
    path.write_bytes(b"\x89PNG esto no es sqlite" * 50)
    with pytest.raises(InvalidMbtilesError):
        inspect_mbtiles(path)


def test_inspect_rejects_sqlite_without_tiles(tmp_path: Path) -> None:
    path = tmp_path / "otra.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE waypoints (id INTEGER)")
    conn.close()
    with pytest.raises(InvalidMbtilesError, match="tiles"):
        inspect_mbtiles(path)


def test_clamp_zoom(tmp_path: Path) -> None:
    info = inspect_mbtiles(make_mbtiles(tmp_path / "m.mbtiles", zooms=(10, 14)))
    assert info.clamp_zoom(15) == 14
    assert info.clamp_zoom(3) == 10
    assert info.clamp_zoom(12) == 12


def test_map_manager_accepts_none() -> None:
    manager = MapManager(None)
    assert not manager.is_available
    assert manager.mbtiles_path is None


def test_map_manager_open_swaps_files(tmp_path: Path) -> None:
    first = make_mbtiles(tmp_path / "a.mbtiles", name="A")
    second = make_mbtiles(tmp_path / "b.mbtiles", name="B")
    manager = MapManager(first)
    assert manager.get_metadata()["name"] == "A"

    assert manager.open(second) is True
    assert manager.get_metadata()["name"] == "B"
    assert manager.mbtiles_path == second

    assert manager.open(None) is False
    assert not manager.is_available
    manager.close()


def test_map_manager_open_missing_file_leaves_no_map(tmp_path: Path) -> None:
    manager = MapManager(make_mbtiles(tmp_path / "a.mbtiles"))
    assert manager.open(tmp_path / "no_existe.mbtiles") is False
    assert not manager.is_available


def test_map_manager_opens_read_only(tmp_path: Path) -> None:
    path = make_mbtiles(tmp_path / "a.mbtiles")
    manager = MapManager(path)
    assert manager._connection is not None
    with pytest.raises(sqlite3.OperationalError):
        manager._connection.execute("DELETE FROM tiles")
    manager.close()
