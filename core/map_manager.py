"""Map Manager de RoadBook Pi.

Lee tiles raster desde un archivo MBTiles (SQLite estándar: tabla
``tiles`` con zoom_level/tile_column/tile_row/tile_data). Decisión de
arquitectura para Sprint 7: se eligió MBTiles raster en vez de tiles
vectoriales u OSM crudo renderizado en runtime, porque el hardware
mínimo objetivo (Raspberry Pi 2) no tiene margen de CPU/GPU para
renderizar geometrías vectoriales en tiempo real. Leer un blob PNG de
una tabla SQLite es prácticamente gratis en comparación.

Incluye las funciones de conversión de coordenadas estándar del
"slippy map" (OSM/Google/Web Mercator), puras y testeables sin SQLite.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    """Convierte lat/lon a coordenadas de tile enteras (esquema XYZ).

    Args:
        lat_deg: Latitud en grados decimales.
        lon_deg: Longitud en grados decimales.
        zoom: Nivel de zoom.

    Returns:
        Tupla (tile_x, tile_y).
    """
    x, y = deg2num_fractional(lat_deg, lon_deg, zoom)
    return int(x), int(y)


def deg2num_fractional(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    """Igual que ``deg2num`` pero sin truncar (posición exacta dentro del tile).

    Args:
        lat_deg: Latitud en grados decimales.
        lon_deg: Longitud en grados decimales.
        zoom: Nivel de zoom.

    Returns:
        Tupla (tile_x, tile_y) fraccional.
    """
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    x = (lon_deg + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def num2deg(xtile: float, ytile: float, zoom: int) -> tuple[float, float]:
    """Convierte coordenadas de tile a lat/lon (esquina superior izquierda).

    Args:
        xtile: Coordenada X del tile.
        ytile: Coordenada Y del tile.
        zoom: Nivel de zoom.

    Returns:
        Tupla (latitud, longitud) en grados decimales.
    """
    n = 2.0**zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


class MapManager:
    """Lee tiles raster desde un archivo MBTiles.

    Attributes:
        mbtiles_path: Ruta al archivo .mbtiles.
    """

    def __init__(self, mbtiles_path: str | Path) -> None:
        self.mbtiles_path = Path(mbtiles_path)
        self._connection: sqlite3.Connection | None = None

        if self.mbtiles_path.exists():
            try:
                self._connection = sqlite3.connect(
                    str(self.mbtiles_path), check_same_thread=False
                )
                logger.info("MapManager: mbtiles cargado desde %s", self.mbtiles_path)
            except sqlite3.Error as exc:
                logger.error("MapManager: error abriendo mbtiles: %s", exc)
                self._connection = None
        else:
            logger.warning(
                "MapManager: no se encontró el archivo mbtiles en %s "
                "(el mapa offline no estará disponible)",
                self.mbtiles_path,
            )

    @property
    def is_available(self) -> bool:
        """Indica si hay un archivo mbtiles válido cargado."""
        return self._connection is not None

    def get_metadata(self) -> dict[str, str]:
        """Devuelve los metadatos del mbtiles (name, bounds, min/maxzoom, etc.).

        Returns:
            Diccionario clave-valor de la tabla ``metadata``. Vacío si
            no hay mbtiles cargado.
        """
        if self._connection is None:
            return {}
        try:
            rows = self._connection.execute("SELECT name, value FROM metadata").fetchall()
            return dict(rows)
        except sqlite3.Error as exc:
            logger.error("MapManager: error leyendo metadata: %s", exc)
            return {}

    def get_tile(self, zoom: int, x: int, y: int) -> bytes | None:
        """Obtiene los bytes de un tile (esquema XYZ, se convierte a TMS internamente).

        MBTiles almacena tiles con el esquema TMS (fila 0 = abajo),
        mientras que la mayoría de las librerías de mapas usan XYZ
        (fila 0 = arriba). Esta conversión es interna: quien llama a
        ``get_tile`` siempre piensa en XYZ.

        Args:
            zoom: Nivel de zoom.
            x: Coordenada X del tile (esquema XYZ).
            y: Coordenada Y del tile (esquema XYZ).

        Returns:
            Bytes del tile (usualmente PNG o JPG), o None si no existe
            o no hay mbtiles cargado.
        """
        if self._connection is None:
            return None

        tms_y = (2**zoom - 1) - y
        try:
            row = self._connection.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? "
                "AND tile_row = ?",
                (zoom, x, tms_y),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.error("MapManager: error leyendo tile (%s,%s,%s): %s", zoom, x, y, exc)
            return None

        return row[0] if row else None

    def close(self) -> None:
        """Cierra la conexión al archivo mbtiles, si está abierta."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
