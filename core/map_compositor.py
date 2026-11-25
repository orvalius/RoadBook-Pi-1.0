"""Compositor de mapas de RoadBook Pi.

Arma una imagen raster centrada en una coordenada geográfica,
combinando los tiles de MBTiles necesarios para cubrir el área
visible. Usa Pillow (ya parte del stack), no Qt: la conversión final a
QPixmap vive en ``ui/screens/map_widget.py``.

También incluye ``should_redraw``, lógica pura de throttling: en
hardware limitado (Raspberry Pi 2) recomponer tiles en cada actualización
GPS (varias veces por segundo) sería un desperdicio de CPU si el
vehículo apenas se movió unos metros.
"""

from __future__ import annotations

import io
from typing import Protocol

from PIL import Image

from core.lru_cache import LRUCache
from core.map_manager import deg2num_fractional
from core.navigation_engine import NavigationEngine

PLACEHOLDER_COLOR = (222, 222, 222)
DEFAULT_TILE_CACHE_SIZE = 96


class TileSource(Protocol):
    """Protocolo mínimo que necesita el compositor (ver MapManager)."""

    def get_tile(self, zoom: int, x: int, y: int) -> bytes | None: ...


def compose_map_image(
    tile_source: TileSource | None,
    center_lat: float,
    center_lon: float,
    zoom: int,
    width_px: int,
    height_px: int,
    tile_size: int = 256,
) -> Image.Image:
    """Compone una imagen raster del mapa centrada en una coordenada.

    Args:
        tile_source: Objeto con ``get_tile(zoom, x, y)`` (ej: MapManager).
            Si es None, se devuelve una imagen de placeholder gris.
        center_lat: Latitud del centro del mapa.
        center_lon: Longitud del centro del mapa.
        zoom: Nivel de zoom.
        width_px: Ancho de la imagen resultante en píxeles.
        height_px: Alto de la imagen resultante en píxeles.
        tile_size: Tamaño de cada tile en píxeles (256 es el estándar).

    Returns:
        Imagen PIL de tamaño exacto (width_px, height_px).
    """
    canvas = Image.new(
        "RGB", (max(width_px, 1), max(height_px, 1)), color=PLACEHOLDER_COLOR
    )

    if tile_source is None or width_px <= 0 or height_px <= 0:
        return canvas

    center_x, center_y = deg2num_fractional(center_lat, center_lon, zoom)
    center_px_x = center_x * tile_size
    center_px_y = center_y * tile_size
    offset_x = center_px_x - width_px / 2
    offset_y = center_px_y - height_px / 2

    n_tiles = 2**zoom
    first_tile_x = int(offset_x // tile_size)
    first_tile_y = int(offset_y // tile_size)
    last_tile_x = int((offset_x + width_px) // tile_size)
    last_tile_y = int((offset_y + height_px) // tile_size)

    for tile_x in range(first_tile_x, last_tile_x + 1):
        for tile_y in range(first_tile_y, last_tile_y + 1):
            if not (0 <= tile_x < n_tiles and 0 <= tile_y < n_tiles):
                continue

            if hasattr(tile_source, "get_tile_image"):
                tile_image = tile_source.get_tile_image(zoom, tile_x, tile_y, tile_size)
            else:
                tile_image = _load_tile_image(
                    tile_source, zoom, tile_x, tile_y, tile_size
                )

            paste_x = int(tile_x * tile_size - offset_x)
            paste_y = int(tile_y * tile_size - offset_y)
            canvas.paste(tile_image, (paste_x, paste_y))

    return canvas


def _load_tile_image(
    tile_source: TileSource, zoom: int, tile_x: int, tile_y: int, tile_size: int
) -> Image.Image:
    """Carga un tile como imagen PIL, o un placeholder si no está disponible."""
    tile_bytes = tile_source.get_tile(zoom, tile_x, tile_y)
    if tile_bytes is None:
        return Image.new("RGB", (tile_size, tile_size), color=PLACEHOLDER_COLOR)

    try:
        return Image.open(io.BytesIO(tile_bytes)).convert("RGB")
    except OSError:
        return Image.new("RGB", (tile_size, tile_size), color=PLACEHOLDER_COLOR)


def should_redraw(
    last_lat: float | None,
    last_lon: float | None,
    new_lat: float,
    new_lon: float,
    threshold_meters: float = 20.0,
) -> bool:
    """Decide si vale la pena recomponer el mapa ante una nueva posición.

    Args:
        last_lat: Latitud del último renderizado (None si nunca se
            renderizó).
        last_lon: Longitud del último renderizado.
        new_lat: Latitud de la posición actual.
        new_lon: Longitud de la posición actual.
        threshold_meters: Distancia mínima recorrida para justificar
            un nuevo renderizado.

    Returns:
        True si hay que recomponer el mapa.
    """
    if last_lat is None or last_lon is None:
        return True

    distance = NavigationEngine.haversine_distance(last_lat, last_lon, new_lat, new_lon)
    return distance >= threshold_meters


class CachedTileSource:
    """Envuelve un ``TileSource`` cacheando las imágenes ya decodificadas.

    Optimización de Sprint 10: decodificar un PNG/JPG es la parte más
    cara de recomponer el mapa. Cuando el vehículo se mueve poco, la
    mayoría de los tiles visibles son los mismos que en el frame
    anterior — cachearlos evita re-decodificarlos en cada redraw, algo
    especialmente valioso en una Raspberry Pi 2.

    Attributes:
        tile_source: Fuente real de tiles (ej: MapManager).
    """

    def __init__(
        self, tile_source: TileSource, max_cached_tiles: int = DEFAULT_TILE_CACHE_SIZE
    ) -> None:
        self.tile_source = tile_source
        self._cache: LRUCache[tuple[int, int, int], Image.Image] = LRUCache(
            max_cached_tiles
        )

    def get_tile_image(self, zoom: int, x: int, y: int, tile_size: int) -> Image.Image:
        """Obtiene un tile ya decodificado como imagen PIL, usando el cache.

        Args:
            zoom: Nivel de zoom.
            x: Coordenada X del tile.
            y: Coordenada Y del tile.
            tile_size: Tamaño esperado del tile en píxeles (para el
                placeholder si no hay datos).

        Returns:
            Imagen PIL decodificada (desde cache o recién decodificada).
        """
        key = (zoom, x, y)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        image = _load_tile_image(self.tile_source, zoom, x, y, tile_size)
        self._cache.put(key, image)
        return image

    def cache_size(self) -> int:
        """Cantidad de tiles actualmente en cache (para tests/diagnóstico)."""
        return len(self._cache)
