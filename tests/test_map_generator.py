"""Tests del generador de mapas offline (core.map_generator)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import core.map_generator as gen
from core.map_generator import (
    RouteMap,
    bounds_with_margin,
    generate_mbtiles,
    place_labels,
    render_tile,
    tiles_for,
)
from core.map_manager import MapManager, deg2num, inspect_mbtiles

ROUTE = RouteMap(
    line=[(-31.578, -64.367), (-31.50, -64.36), (-31.40, -64.45)],
    notes=[
        (-31.578, -64.367, "Parque de Servicios - Autódromo Cabalén"),
        (-31.5781, -64.3671, "Largada Shakedown"),
        (-31.40, -64.45, "RZ Combustible"),
    ],
)


def test_bounds_include_margin() -> None:
    west, south, east, north = bounds_with_margin(ROUTE.line, 2.0)
    assert south < -31.578 < -31.40 < north
    assert west < -64.45 < -64.36 < east
    assert (north - (-31.40)) == pytest.approx(2.0 / 111.32)


def test_tiles_cover_route_at_each_zoom() -> None:
    tiles = tiles_for(bounds_with_margin(ROUTE.line, 1.0), range(12, 14))
    for z in (12, 13):
        for lat, lon in ROUTE.line:
            assert (z, *deg2num(lat, lon, z)) in tiles


def test_tile_has_texture_and_correct_size() -> None:
    z = 14
    tile = render_tile(ROUTE, z, *deg2num(-31.5, -64.36, z))
    assert tile.size == (256, 256)
    pixels = np.asarray(tile, dtype=np.float32)
    assert pixels.std() > 3  # no es un color liso


def test_terrain_is_continuous_across_tile_edges() -> None:
    z = 15
    x, y = deg2num(-31.45, -64.6, z)  # lejos de la ruta: solo terreno
    left = np.asarray(gen._terrain_tile(z, x, y), dtype=np.float32)
    right = np.asarray(gen._terrain_tile(z, x + 1, y), dtype=np.float32)
    seam = np.abs(left[:, -1] - right[:, 0]).mean()
    inside = np.abs(left[:, -2] - left[:, -1]).mean()
    assert seam < inside * 3 + 2


def test_labels_do_not_overlap() -> None:
    placed = place_labels(ROUTE.notes, 15)
    names = [p[2] for p in placed]
    # Las dos primeras notas están a ~15 m: solo entra una de las dos.
    assert "RZ Combustible" in names
    assert len(names) == 2


def test_generate_valid_mbtiles(tmp_path: Path) -> None:
    calls: list[tuple[int, int]] = []
    out = generate_mbtiles(
        tmp_path / "ruta.mbtiles",
        ROUTE,
        min_zoom=11,
        max_zoom=12,
        margin_km=1,
        progress=lambda d, t: calls.append((d, t)),
    )
    info = inspect_mbtiles(out)
    assert (info.min_zoom, info.max_zoom) == (11, 12)
    assert info.tile_format == "jpg" and not info.is_vector
    assert calls[-1][0] == calls[-1][1]
    manager = MapManager(out)
    assert "No es cartografía real" in manager.get_metadata()["description"]
    x, y = deg2num(-31.5, -64.36, 12)
    assert manager.get_tile(12, x, y) is not None
    manager.close()
    assert not (tmp_path / "ruta.mbtiles.part").exists()


def test_cancelled_generation_leaves_nothing(tmp_path: Path) -> None:
    def cancel(done: int, _total: int) -> None:
        if done >= 2:
            raise RuntimeError("cancelado")

    with pytest.raises(RuntimeError):
        generate_mbtiles(tmp_path / "x.mbtiles", ROUTE, 11, 12, progress=cancel)
    assert list(tmp_path.iterdir()) == []


def test_empty_route_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        generate_mbtiles(tmp_path / "x.mbtiles", RouteMap(line=[], notes=[]))
