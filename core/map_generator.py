"""Generador de mapas offline (.mbtiles) a partir de la ruta.

Para cuando no hay un mapa real de la zona (MOBAC, mb-util, etc.):
arma un .mbtiles raster que cubre la ruta con un margen, con un fondo
de terreno generado, una cuadrícula de coordenadas, el camino de la
ruta (o del track GPX) y el nombre de cada nota.

Importante: **no es cartografía real**. El relieve y la vegetación son
textura generada para que el mapa se lea como mapa; lo único con
posición real son la ruta, las notas y la cuadrícula. Así queda dicho
en los metadatos del archivo (``description``).

El terreno se calcula en coordenadas del mundo (no por tile), así se
ve continuo entre tiles y coherente entre niveles de zoom.
"""

from __future__ import annotations

import io
import math
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.logger import get_logger
from core.map_manager import deg2num, deg2num_fractional, num2deg

logger = get_logger(__name__)

TILE = 256
EARTH_KM = 40075.016686
DESCRIPTION = (
    "Mapa generado automáticamente por RoadBook Pi a partir de la ruta. "
    "No es cartografía real: el relieve es ilustrativo; la ruta, las notas "
    "y la cuadrícula sí tienen posición real."
)

# Paleta tipo carta topográfica, suave para que la ruta naranja resalte.
LOW = np.array([240, 234, 214], dtype=np.float32)
HIGH = np.array([200, 184, 146], dtype=np.float32)
GREEN = np.array([172, 204, 144], dtype=np.float32)
CONTOUR = np.array([160, 140, 105], dtype=np.float32)
ROAD_CASING = (120, 92, 60)
ROAD_FILL = (250, 236, 196)
GRID = (150, 150, 150, 70)
LABEL = (45, 40, 35)

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class RouteMap:
    """Qué dibujar: la línea de la ruta y las notas con su nombre."""

    line: Sequence[tuple[float, float]]
    notes: Sequence[tuple[float, float, str]]


# ---------------------------------------------------------------- Terreno


def _hash(ix: np.ndarray, iy: np.ndarray, seed: int) -> np.ndarray:
    """Hash entero -> [0, 1) por punto de la grilla (determinístico)."""
    h = (ix.astype(np.uint32) * np.uint32(374761393)) ^ (
        iy.astype(np.uint32) * np.uint32(668265263)
    )
    h ^= np.uint32(seed * 2654435761 & 0xFFFFFFFF)
    h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
    h ^= h >> np.uint32(16)
    return (h & np.uint32(0xFFFFFF)).astype(np.float64) / float(0x1000000)


def _value_noise(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = x - x0, y - y0
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    ix, iy = x0.astype(np.int64), y0.astype(np.int64)
    n00, n10 = _hash(ix, iy, seed), _hash(ix + 1, iy, seed)
    n01, n11 = _hash(ix, iy + 1, seed), _hash(ix + 1, iy + 1, seed)
    top = n00 + (n10 - n00) * sx
    bottom = n01 + (n11 - n01) * sx
    return top + (bottom - top) * sy


def _fbm(x: np.ndarray, y: np.ndarray, seed: int, octaves: int = 5) -> np.ndarray:
    total = np.zeros_like(x, dtype=np.float64)
    amplitude, frequency, norm = 1.0, 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * _value_noise(x * frequency, y * frequency, seed + octave)
        norm += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return total / norm


def _terrain_tile(z: int, tx: int, ty: int) -> Image.Image:
    """Fondo de terreno de un tile, continuo con sus vecinos."""
    scale = TILE * 2**z
    # 1 px de borde para que el sombreado no deje costuras entre tiles.
    px = (np.arange(-1, TILE + 1, dtype=np.float64) + 0.5 + tx * TILE) / scale
    py = (np.arange(-1, TILE + 1, dtype=np.float64) + 0.5 + ty * TILE) / scale
    gx, gy = np.meshgrid(px, py)
    # Rasgos de unos 4 km: escala fija en el mundo, no en el tile.
    features = EARTH_KM / 4.0
    # float64: en zoom alto un píxel mide ~0,001 unidades de ruido, por
    # debajo de la precisión de float32 (dejaba rayas horizontales).
    wx, wy = gx * features, gy * features

    # 8 octavas: rasgos de 4 km hasta ~30 m, así hay textura también en zoom 15-16.
    height = _fbm(wx, wy, seed=7, octaves=8)
    moisture = _fbm(wx * 1.7 + 31.0, wy * 1.7 - 17.0, seed=101, octaves=6)

    dy, dx = np.gradient(height)
    # Pendiente en unidades del ruido (no por píxel): el sombreado queda
    # igual en todos los zooms y no se satura en manchas de dos tonos.
    pixel_world = features / scale
    shade = np.clip(1.0 + (dx - dy) / pixel_world * 0.07, 0.84, 1.12)[1:-1, 1:-1]
    h = height[1:-1, 1:-1]
    m = moisture[1:-1, 1:-1]

    t = np.clip((h - 0.32) / 0.36, 0, 1)[..., None]
    color = LOW * (1 - t) + HIGH * t
    green = np.clip((m - 0.48) / 0.14, 0, 1)[..., None] * 0.85
    color = color * (1 - green) + GREEN * green
    color *= shade[..., None]

    if z >= 13:
        # Curvas de nivel de ~1 px en cualquier zoom: distancia en píxeles a
        # la curva más cercana = diferencia de altura / pendiente por píxel.
        # Más curvas cuanto más zoom, como en una carta de mayor escala.
        step = 1 / {13: 14, 14: 24}.get(z, 36)
        slope = np.hypot(dx, dy)[1:-1, 1:-1]
        offset = np.abs(h / step - np.round(h / step)) * step
        distance_px = offset / np.maximum(slope, 1e-9)
        line = (np.clip(1.0 - distance_px / 0.9, 0, 1) * 0.4)[..., None]
        color = color * (1 - line) + CONTOUR * line

    return Image.fromarray(np.clip(color, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- Dibujo


def _to_tile_px(
    lat: float, lon: float, z: int, tx: int, ty: int
) -> tuple[float, float]:
    x, y = deg2num_fractional(lat, lon, z)
    return (x - tx) * TILE, (y - ty) * TILE


def _grid_step(z: int) -> float:
    return 0.05 if z <= 12 else (0.02 if z <= 14 else 0.01)


def _draw_grid(img: Image.Image, z: int, tx: int, ty: int) -> None:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    step = _grid_step(z)
    north, west = num2deg(tx, ty, z)
    south, east = num2deg(tx + 1, ty + 1, z)
    lon = math.floor(west / step) * step
    while lon <= east:
        x, _ = _to_tile_px(north, lon, z, tx, ty)
        draw.line([(x, 0), (x, TILE)], fill=GRID, width=1)
        lon += step
    lat = math.floor(south / step) * step
    while lat <= north:
        _, y = _to_tile_px(lat, west, z, tx, ty)
        draw.line([(0, y), (TILE, y)], fill=GRID, width=1)
        lat += step
    img.paste(overlay, (0, 0), overlay)


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    # DejaVu viene con Raspberry Pi OS y tiene tildes; la fuente por
    # defecto de Pillow no siempre ("Cabalén" salía con un cuadradito).
    for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def place_labels(
    notes: Sequence[tuple[float, float, str]], z: int
) -> list[tuple[float, float, str, float, float]]:
    """Elige qué nombres rotular en un zoom sin que se pisen.

    Se decide una sola vez para todo el mapa (en píxeles globales), así
    un nombre que cruza el borde entre dos tiles aparece en ambos.

    Returns:
        (lat, lon, nombre, x_global, y_global) de los nombres aceptados.
    """
    font = _font(_label_size(z))
    taken: list[tuple[float, float, float, float]] = []
    placed = []
    for lat, lon, name in notes:
        gx, gy = deg2num_fractional(lat, lon, z)
        x, y = gx * TILE, gy * TILE
        left, top, right, bottom = font.getbbox(name)
        box = (x + 7, y - 7 + top - 2, x + 7 + right + 2, y - 7 + bottom + 2)
        if any(
            box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3]
            for b in taken
        ):
            continue
        taken.append(box)
        placed.append((lat, lon, name, x, y))
    return placed


def _label_size(z: int) -> int:
    return 11 if z < 15 else 13


def _draw_route(
    img: Image.Image,
    route: RouteMap,
    z: int,
    tx: int,
    ty: int,
    labels: Sequence[tuple[float, float, str, float, float]] | None = None,
) -> None:
    draw = ImageDraw.Draw(img)
    if len(route.line) >= 2:
        points = [_to_tile_px(lat, lon, z, tx, ty) for lat, lon in route.line]
        casing, fill = max(3, z - 8), max(1, z - 11)
        draw.line(points, fill=ROAD_CASING, width=casing, joint="curve")
        draw.line(points, fill=ROAD_FILL, width=fill, joint="curve")
    if z < 13:
        return
    font = _font(_label_size(z))
    for lat, lon, _ in route.notes:
        x, y = _to_tile_px(lat, lon, z, tx, ty)
        if -6 < x < TILE + 6 and -6 < y < TILE + 6:
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=ROAD_CASING)
    for lat, lon, name, *_ in (
        labels if labels is not None else place_labels(route.notes, z)
    ):
        x, y = _to_tile_px(lat, lon, z, tx, ty)
        if -300 < x < TILE + 20 and -30 < y < TILE + 30:
            draw.text(
                (x + 7, y - 7),
                name,
                font=font,
                fill=LABEL,
                stroke_width=2,
                stroke_fill=(246, 242, 230),
            )


def render_tile(
    route: RouteMap,
    z: int,
    tx: int,
    ty: int,
    labels: Sequence[tuple[float, float, str, float, float]] | None = None,
) -> Image.Image:
    """Dibuja un tile completo (esquema XYZ).

    ``labels`` son los nombres ya ubicados para ese zoom (ver
    ``place_labels``); si es None se calculan acá.
    """
    img = _terrain_tile(z, tx, ty)
    _draw_grid(img, z, tx, ty)
    _draw_route(img, route, z, tx, ty, labels)
    return img


# ---------------------------------------------------------------- MBTiles


def bounds_with_margin(
    points: Sequence[tuple[float, float]], margin_km: float
) -> tuple[float, float, float, float]:
    """(oeste, sur, este, norte) que cubre los puntos más un margen."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    dlat = margin_km / 111.32
    mid = math.radians((min(lats) + max(lats)) / 2)
    dlon = margin_km / (111.32 * max(math.cos(mid), 0.1))
    return min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat


def tiles_for(
    bounds: tuple[float, float, float, float], zooms: range
) -> list[tuple[int, int, int]]:
    """Todos los tiles (z, x, y) XYZ que cubren el rectángulo."""
    west, south, east, north = bounds
    tiles = []
    for z in zooms:
        x0, y0 = deg2num(north, west, z)
        x1, y1 = deg2num(south, east, z)
        tiles += [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    return tiles


def generate_mbtiles(
    output: str | Path,
    route: RouteMap,
    min_zoom: int = 11,
    max_zoom: int = 15,
    margin_km: float = 3.0,
    name: str = "Mapa de la ruta (generado)",
    quality: int = 88,
    progress: ProgressCallback | None = None,
) -> Path:
    """Genera el .mbtiles completo.

    Args:
        output: Archivo a crear (se reemplaza si existe).
        route: Línea de la ruta y notas a rotular.
        min_zoom: Zoom mínimo a generar.
        max_zoom: Zoom máximo a generar.
        margin_km: Margen alrededor de la ruta.
        name: Nombre para los metadatos.
        quality: Calidad JPEG de los tiles.
        progress: Opcional, llamado con (tiles hechos, total).

    Returns:
        Ruta del archivo generado.

    Raises:
        ValueError: Si la ruta no tiene puntos.
    """
    points = list(route.line) or [(lat, lon) for lat, lon, _ in route.notes]
    if not points:
        raise ValueError("La ruta no tiene puntos para generar el mapa")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".part")
    partial.unlink(missing_ok=True)

    bounds = bounds_with_margin(points, margin_km)
    tiles = tiles_for(bounds, range(min_zoom, max_zoom + 1))
    logger.info(
        "Generando %d tiles (z%d-%d) en %s", len(tiles), min_zoom, max_zoom, output
    )

    conn = sqlite3.connect(partial)
    try:
        conn.executescript(
            "CREATE TABLE metadata (name TEXT, value TEXT);"
            "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, "
            "tile_row INTEGER, tile_data BLOB);"
        )
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        conn.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [
                ("name", name),
                ("format", "jpg"),
                ("type", "baselayer"),
                ("version", "1"),
                ("description", DESCRIPTION),
                ("minzoom", str(min_zoom)),
                ("maxzoom", str(max_zoom)),
                ("bounds", ",".join(f"{v:.6f}" for v in bounds)),
                ("center", f"{center_lon:.6f},{center_lat:.6f},{max_zoom - 1}"),
            ],
        )
        labels = {
            z: place_labels(route.notes, z) for z in range(min_zoom, max_zoom + 1)
        }
        for done, (z, x, y) in enumerate(tiles, start=1):
            buffer = io.BytesIO()
            render_tile(route, z, x, y, labels[z]).save(buffer, "JPEG", quality=quality)
            conn.execute(
                "INSERT INTO tiles VALUES (?, ?, ?, ?)",
                (z, x, (2**z - 1) - y, buffer.getvalue()),
            )
            if progress is not None:
                progress(done, len(tiles))
        conn.execute(
            "CREATE UNIQUE INDEX tile_index "
            "ON tiles (zoom_level, tile_column, tile_row)"
        )
        conn.commit()
    except BaseException:
        conn.close()
        partial.unlink(missing_ok=True)
        raise
    conn.close()
    partial.replace(output)
    return output
