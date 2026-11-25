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
from dataclasses import dataclass
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


def deg2num_fractional(
    lat_deg: float, lon_deg: float, zoom: int
) -> tuple[float, float]:
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


class InvalidMbtilesError(ValueError):
    """El archivo no existe o no es un MBTiles utilizable."""


@dataclass(frozen=True)
class MbtilesInfo:
    """Resumen de un archivo MBTiles, para mostrar antes de usarlo.

    Attributes:
        path: Ruta del archivo inspeccionado.
        name: Nombre declarado en ``metadata`` (o el nombre de archivo).
        tile_format: Formato de los tiles (``png``, ``jpg``, ``pbf``...).
        min_zoom: Zoom mínimo disponible, o None si no hay tiles.
        max_zoom: Zoom máximo disponible, o None si no hay tiles.
        bounds: (oeste, sur, este, norte) en grados, si está declarado.
        size_bytes: Tamaño del archivo en disco.
    """

    path: Path
    name: str
    tile_format: str
    min_zoom: int | None
    max_zoom: int | None
    bounds: tuple[float, float, float, float] | None
    size_bytes: int

    @property
    def is_vector(self) -> bool:
        """True si los tiles son vectoriales (no soportados por el renderer)."""
        return self.tile_format.lower() in ("pbf", "mvt")

    def clamp_zoom(self, zoom: int) -> int:
        """Ajusta un zoom al rango disponible en este archivo."""
        if self.min_zoom is None or self.max_zoom is None:
            return zoom
        return max(self.min_zoom, min(self.max_zoom, zoom))


def _open_readonly(path: Path) -> sqlite3.Connection:
    # Solo lectura: no hay motivo para escribir un mbtiles, y en la
    # tarjeta SD de la Pi evita crear archivos -journal al lado.
    return sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False
    )


def _parse_bounds(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    try:
        west, south, east, north = (float(v) for v in raw.split(","))
    except ValueError:
        return None
    return west, south, east, north


def inspect_mbtiles(path: str | Path) -> MbtilesInfo:
    """Valida un archivo MBTiles y devuelve su resumen.

    Pensado para la pantalla de Mapas: permite rechazar un archivo
    equivocado (ej: un .db cualquiera) antes de activarlo, y mostrar
    el rango de zoom para que el usuario sepa qué esperar.

    Args:
        path: Ruta al archivo.

    Returns:
        ``MbtilesInfo`` con los datos del archivo.

    Raises:
        InvalidMbtilesError: Si el archivo no existe, no es SQLite, o
            no tiene la tabla/vista ``tiles``.
    """
    path = Path(path)
    if not path.is_file():
        raise InvalidMbtilesError(f"No existe el archivo: {path}")

    try:
        conn = _open_readonly(path)
    except sqlite3.Error as exc:
        raise InvalidMbtilesError(f"No se pudo abrir {path.name}: {exc}") from exc

    try:
        try:
            objects = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                )
            }
        except sqlite3.DatabaseError as exc:
            raise InvalidMbtilesError(
                f"{path.name} no es una base SQLite válida ({exc})"
            ) from exc
        if "tiles" not in objects:
            raise InvalidMbtilesError(
                f"{path.name} no es un MBTiles (no tiene la tabla 'tiles')"
            )

        metadata: dict[str, str] = {}
        if "metadata" in objects:
            try:
                metadata = dict(conn.execute("SELECT name, value FROM metadata"))
            except sqlite3.Error:
                metadata = {}

        min_zoom, max_zoom = _zoom_range(conn, metadata)
        return MbtilesInfo(
            path=path,
            name=metadata.get("name") or path.stem,
            tile_format=metadata.get("format", "png"),
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            bounds=_parse_bounds(metadata.get("bounds")),
            size_bytes=path.stat().st_size,
        )
    finally:
        conn.close()


def _zoom_range(
    conn: sqlite3.Connection, metadata: dict[str, str]
) -> tuple[int | None, int | None]:
    try:
        return int(metadata["minzoom"]), int(metadata["maxzoom"])
    except (KeyError, ValueError):
        pass
    # Sin metadata confiable: preguntarle a los tiles (usa el índice
    # estándar de MBTiles, es rápido incluso en archivos grandes).
    try:
        row = conn.execute(
            "SELECT MIN(zoom_level), MAX(zoom_level) FROM tiles"
        ).fetchone()
    except sqlite3.Error:
        return None, None
    return (row[0], row[1]) if row else (None, None)


class MapManager:
    """Lee tiles raster desde un archivo MBTiles.

    El archivo se puede cambiar en caliente con ``open()`` (pantalla
    "Mapas y ruta"), sin reiniciar la aplicación.

    Attributes:
        mbtiles_path: Ruta al archivo .mbtiles actual, o None.
    """

    def __init__(self, mbtiles_path: str | Path | None) -> None:
        self.mbtiles_path: Path | None = None
        self._connection: sqlite3.Connection | None = None
        if mbtiles_path:
            self.open(mbtiles_path)
        else:
            logger.info("MapManager: sin mapa offline configurado")

    def open(self, mbtiles_path: str | Path | None) -> bool:
        """Cambia el archivo MBTiles activo (o lo quita, con None).

        Si el archivo nuevo no se puede abrir, queda sin mapa (no se
        mantiene el anterior a medias): la pantalla de mapas valida
        con ``inspect_mbtiles`` antes de llamar a esto.

        Args:
            mbtiles_path: Ruta al nuevo archivo, o None para quitar el mapa.

        Returns:
            True si quedó un mapa disponible.
        """
        self.close()
        self.mbtiles_path = Path(mbtiles_path) if mbtiles_path else None
        if self.mbtiles_path is None:
            logger.info("MapManager: mapa offline quitado")
            return False

        if not self.mbtiles_path.exists():
            logger.warning(
                "MapManager: no se encontró el archivo mbtiles en %s "
                "(el mapa offline no estará disponible)",
                self.mbtiles_path,
            )
            return False
        try:
            self._connection = _open_readonly(self.mbtiles_path)
            logger.info("MapManager: mbtiles cargado desde %s", self.mbtiles_path)
        except sqlite3.Error as exc:
            logger.error("MapManager: error abriendo mbtiles: %s", exc)
            self._connection = None
        return self._connection is not None

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
            rows = self._connection.execute(
                "SELECT name, value FROM metadata"
            ).fetchall()
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
            logger.error(
                "MapManager: error leyendo tile (%s,%s,%s): %s", zoom, x, y, exc
            )
            return None

        return row[0] if row else None

    def close(self) -> None:
        """Cierra la conexión al archivo mbtiles, si está abierta."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
