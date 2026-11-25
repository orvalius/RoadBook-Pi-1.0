"""Configuración común de pytest.

Los tests de UI (``test_ui_*.py``) corren sin pantalla gracias a la
plataforma ``offscreen`` de Qt, y sin placa de audio con el driver
``dummy`` de SDL. Se fija acá, antes de que cualquier test importe Qt
o pygame. Para correrlos hace falta ``pytest-qt`` (ver requirements).
"""

from __future__ import annotations

import io
import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def make_png_bytes(color: tuple[int, int, int] = (40, 120, 200)) -> bytes:
    """PNG de 256x256 de un color, para tiles de prueba."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (256, 256), color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_mbtiles(
    path: Path,
    *,
    name: str | None = "Mapa de prueba",
    tile_format: str | None = "png",
    zooms: tuple[int, ...] = (10, 11, 12),
    with_metadata_zoom: bool = True,
    bounds: str | None = "-64.6,-31.7,-64.1,-31.2",
) -> Path:
    """Crea un .mbtiles real (raster) con un tile por zoom alrededor de Córdoba."""
    from core.map_manager import deg2num

    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, "
        "tile_row INTEGER, tile_data BLOB)"
    )
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    meta: list[tuple[str, str]] = []
    if name is not None:
        meta.append(("name", name))
    if tile_format is not None:
        meta.append(("format", tile_format))
    if bounds is not None:
        meta.append(("bounds", bounds))
    if with_metadata_zoom and zooms:
        meta += [("minzoom", str(min(zooms))), ("maxzoom", str(max(zooms)))]
    conn.executemany("INSERT INTO metadata VALUES (?, ?)", meta)
    png = make_png_bytes()
    for zoom in zooms:
        x, y = deg2num(-31.42, -64.18, zoom)
        conn.execute(
            "INSERT INTO tiles VALUES (?, ?, ?, ?)", (zoom, x, (2**zoom - 1) - y, png)
        )
    conn.commit()
    conn.close()
    return path


GPX_TRACK = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="-31.60" lon="-64.30"/>
    <trkpt lat="-31.50" lon="-64.35"/>
    <trkpt lat="-31.40" lon="-64.40"/>
  </trkseg></trk>
</gpx>"""

GPX_ROUTE_ONLY = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <rte>
    <rtept lat="-31.40" lon="-64.40"/>
    <rtept lat="-31.60" lon="-64.30"/>
  </rte>
</gpx>"""
