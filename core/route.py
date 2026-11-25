"""Route de RoadBook Pi.

Resuelve de dónde sale el **orden** de los waypoints que forman la
ruta del Roadbook Rendering Engine (Sprint 6 rediseñado):

- Si hay un track GPX configurado (``roadbook.gpx_path``), se usa para
  ordenar los waypoints según su posición a lo largo de ese track
  (más fiel a un reconocimiento real).
- Si no hay GPX, se ordenan por ``orden_ruta`` (si el usuario lo definió
  manualmente) y, en su defecto, por id de creación.

Importante: esto solo define el **orden** de la secuencia. La
distancia entre entradas consecutivas (el "odómetro virtual") se
calcula como línea recta (haversine) entre puntos consecutivos, no
como proyección sobre la geometría del track — decisión tomada para
mantener esta pieza simple y no depender de una ruta real para
funcionar.

Lógica pura, sin dependencias de Qt ni de la base de datos (recibe
waypoints ya cargados).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger
from core.navigation_engine import NavigationEngine
from database.models import Waypoint

logger = get_logger(__name__)


def parse_gpx(path: str | Path) -> list[tuple[float, float]]:
    """Parsea los puntos de un archivo GPX.

    Usa los puntos de track (``trkpt``). Si el archivo no tiene track
    pero sí una ruta (``rtept`` — formato habitual de los GPX que
    exportan los organizadores de rally y muchas apps de planificación),
    usa la ruta. Ignora el namespace del GPX (busca por nombre de tag
    local), así que funciona con GPX 1.0 y 1.1 sin configuración extra.

    Args:
        path: Ruta al archivo .gpx.

    Returns:
        Lista de (latitud, longitud) en orden. Vacía si el archivo no
        existe, no es XML válido, o no tiene puntos de track ni de ruta.
    """
    path = Path(path)
    if not path.exists():
        logger.warning("Route: no se encontró el archivo GPX en %s", path)
        return []

    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        logger.error("Route: error parseando GPX %s: %s", path, exc)
        return []

    by_tag: dict[str, list[tuple[float, float]]] = {"trkpt": [], "rtept": []}
    for elem in tree.getroot().iter():
        local_tag = elem.tag.rsplit("}", 1)[-1]
        if local_tag not in by_tag:
            continue
        lat_raw, lon_raw = elem.get("lat"), elem.get("lon")
        if lat_raw is None or lon_raw is None:
            continue
        try:
            by_tag[local_tag].append((float(lat_raw), float(lon_raw)))
        except ValueError:
            continue

    points = by_tag["trkpt"] or by_tag["rtept"]
    kind = "track" if by_tag["trkpt"] else "ruta"
    logger.info("Route: %d puntos de %s leídos desde %s", len(points), kind, path)
    return points


class InvalidGpxError(ValueError):
    """El archivo no existe, no es GPX válido, o no tiene puntos."""


@dataclass(frozen=True)
class GpxInfo:
    """Resumen de un archivo GPX, para mostrar antes de usarlo.

    Attributes:
        path: Ruta del archivo inspeccionado.
        point_count: Cantidad de puntos de track (o de ruta).
        length_m: Largo del recorrido en metros (suma haversine).
    """

    path: Path
    point_count: int
    length_m: float


def track_length_m(track: list[tuple[float, float]]) -> float:
    """Largo de un track en metros (suma de tramos en línea recta)."""
    return sum(
        NavigationEngine.haversine_distance(a[0], a[1], b[0], b[1])
        for a, b in zip(track, track[1:], strict=False)
    )


def inspect_gpx(path: str | Path) -> GpxInfo:
    """Valida un GPX y devuelve su resumen.

    Raises:
        InvalidGpxError: Si no hay puntos utilizables.
    """
    path = Path(path)
    if not path.is_file():
        raise InvalidGpxError(f"No existe el archivo: {path}")
    track = parse_gpx(path)
    if not track:
        raise InvalidGpxError(
            f"{path.name} no tiene puntos de track ni de ruta (¿es un GPX válido?)"
        )
    return GpxInfo(path=path, point_count=len(track), length_m=track_length_m(track))


def _nearest_track_index(
    track: list[tuple[float, float]], point: tuple[float, float]
) -> int:
    """Índice del punto del track más cercano a ``point`` (distancia haversine)."""
    best_index = 0
    best_distance = float("inf")
    for i, (lat, lon) in enumerate(track):
        distance = NavigationEngine.haversine_distance(point[0], point[1], lat, lon)
        if distance < best_distance:
            best_distance = distance
            best_index = i
    return best_index


def order_waypoints_by_track(
    waypoints: list[Waypoint], track: list[tuple[float, float]]
) -> list[Waypoint]:
    """Ordena waypoints según su posición a lo largo de un track GPX.

    Args:
        waypoints: Waypoints a ordenar.
        track: Puntos (lat, lon) del track de referencia, en orden.

    Returns:
        Waypoints ordenados por el índice del punto del track más
        cercano a cada uno. Si ``track`` está vacío, devuelve la lista
        de entrada sin modificar.
    """
    if not track:
        return list(waypoints)

    indexed = [
        (wp, _nearest_track_index(track, (wp.latitud, wp.longitud))) for wp in waypoints
    ]
    indexed.sort(key=lambda pair: pair[1])
    return [wp for wp, _ in indexed]


def order_waypoints_fallback(waypoints: list[Waypoint]) -> list[Waypoint]:
    """Orden por defecto cuando no hay track GPX disponible.

    Ordena por ``orden_ruta`` (los que lo tengan definido, de menor a
    mayor), y como desempate / para los que no lo tengan, por id de
    creación ascendente.

    Args:
        waypoints: Waypoints a ordenar.

    Returns:
        Waypoints ordenados.
    """

    def sort_key(wp: Waypoint) -> tuple[float, int]:
        orden = wp.orden_ruta if wp.orden_ruta is not None else float("inf")
        return (orden, wp.id if wp.id is not None else 0)

    return sorted(waypoints, key=sort_key)


def resolve_route_order(
    waypoints: list[Waypoint], gpx_path: str | Path | None
) -> list[Waypoint]:
    """Resuelve el orden final de la ruta: GPX si está disponible, si no fallback.

    Args:
        waypoints: Waypoints activos a incluir en la ruta.
        gpx_path: Ruta a un archivo GPX, o None/vacío para usar el
            fallback directamente.

    Returns:
        Waypoints ordenados, listos para pasar a
        ``core.roadbook_engine.build_entries``.
    """
    if gpx_path:
        track = parse_gpx(gpx_path)
        if track:
            return order_waypoints_by_track(waypoints, track)
        logger.warning(
            "Route: gpx_path configurado (%s) pero sin puntos válidos, "
            "usando orden fallback",
            gpx_path,
        )

    return order_waypoints_fallback(waypoints)
