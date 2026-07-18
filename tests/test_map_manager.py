"""Tests de core.map_manager."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.map_manager import MapManager, deg2num, num2deg


def _create_test_mbtiles(path: Path) -> None:
    """Crea un archivo .mbtiles mínimo con un solo tile, para tests."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, "
        "tile_row INTEGER, tile_data BLOB)"
    )
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    conn.executemany(
        "INSERT INTO metadata (name, value) VALUES (?, ?)",
        [("name", "Test Map"), ("minzoom", "0"), ("maxzoom", "18")],
    )
    # Tile en zoom=5, xyz=(3,4) -> tms_y = (2**5 - 1) - 4 = 27
    conn.execute(
        "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) "
        "VALUES (?, ?, ?, ?)",
        (5, 3, 27, b"contenido-de-tile-falso"),
    )
    conn.commit()
    conn.close()


def test_deg2num_and_num2deg_roundtrip() -> None:
    lat, lon, zoom = -34.6037, -58.3816, 15
    x, y = deg2num(lat, lon, zoom)
    back_lat, back_lon = num2deg(x, y, zoom)
    # num2deg da la esquina del tile, no el punto exacto: tolerancia amplia
    assert abs(back_lat - lat) < 0.1
    assert abs(back_lon - lon) < 0.1


def test_deg2num_known_value() -> None:
    # Greenwich (0,0) en zoom 0 siempre cae en el único tile (0,0)
    x, y = deg2num(0.0, 0.0, 0)
    assert x == 0
    assert y == 0


def test_map_manager_unavailable_when_file_missing(tmp_path: Path) -> None:
    manager = MapManager(tmp_path / "no_existe.mbtiles")
    assert manager.is_available is False
    assert manager.get_tile(5, 3, 4) is None
    assert manager.get_metadata() == {}


def test_map_manager_reads_real_tile(tmp_path: Path) -> None:
    mbtiles_path = tmp_path / "test.mbtiles"
    _create_test_mbtiles(mbtiles_path)

    manager = MapManager(mbtiles_path)
    assert manager.is_available is True

    tile = manager.get_tile(5, 3, 4)  # xyz (3,4) -> tms_row 27
    assert tile == b"contenido-de-tile-falso"

    manager.close()


def test_map_manager_missing_tile_returns_none(tmp_path: Path) -> None:
    mbtiles_path = tmp_path / "test.mbtiles"
    _create_test_mbtiles(mbtiles_path)

    manager = MapManager(mbtiles_path)
    assert manager.get_tile(5, 99, 99) is None
    manager.close()


def test_map_manager_metadata(tmp_path: Path) -> None:
    mbtiles_path = tmp_path / "test.mbtiles"
    _create_test_mbtiles(mbtiles_path)

    manager = MapManager(mbtiles_path)
    metadata = manager.get_metadata()
    assert metadata["name"] == "Test Map"
    assert metadata["minzoom"] == "0"
    manager.close()


def test_map_manager_tms_yflip_is_correct(tmp_path: Path) -> None:
    """Verifica explícitamente la conversión XYZ -> TMS."""
    mbtiles_path = tmp_path / "test.mbtiles"
    _create_test_mbtiles(mbtiles_path)
    manager = MapManager(mbtiles_path)

    # El tile insertado es tms_row=27 en zoom 5; xyz correspondiente es y=4
    assert manager.get_tile(5, 3, 4) is not None
    # xyz y=27 (mal, sin convertir) NO debería encontrar nada
    assert manager.get_tile(5, 3, 27) is None
    manager.close()
