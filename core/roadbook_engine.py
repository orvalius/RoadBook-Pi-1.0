"""Roadbook Engine de RoadBook Pi.

Reemplaza el antiguo "visor de imágenes" del Sprint 6 por un motor de
renderizado continuo, similar a los sistemas de rally raid: en vez de
reaccionar solo a un waypoint puntual, mantiene una **secuencia
ordenada** de waypoints (la "ruta" activa, ver ``core/route.py``) y
resuelve en cada actualización de posición cuál es la nota actual,
cuáles ya se pasaron, y cuánto falta para la próxima.

Diferencia clave con ``NavigationEngine``: ``NavigationEngine`` vigila
TODOS los waypoints activos de forma independiente para disparar sus
secuencias de acciones (Event Engine, sin cambios). ``RoadbookEngine``
en cambio avanza secuencialmente sobre un subconjunto ORDENADO de esos
mismos waypoints, solo para decidir qué mostrar en la tira. No dispara
ninguna acción — eso lo sigue haciendo exclusivamente el Event Engine.

Distancia: por decisión de diseño, el "odómetro virtual" usa distancia
en línea recta (haversine) al próximo punto, no proyección sobre una
ruta real. Es la opción simple: no necesita que la geometría de la
ruta sea precisa para funcionar.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.gps_manager import GpsPosition
from core.logger import get_logger
from core.navigation_engine import NavigationEngine
from core.turns import Turn, compute_turns
from database.models import Waypoint

logger = get_logger(__name__)


@dataclass
class RoadbookEntry:
    """Un ítem de la tira de roadbook, vinculado a un Waypoint existente.

    Attributes:
        waypoint: Waypoint asociado (reusa toda su lógica de radio,
            imagen, audio, secuencia de acciones, etc.).
        orden: Posición de esta entrada en la secuencia (0-based).
        distancia_parcial_m: Distancia en línea recta desde la entrada
            anterior (0 si es la primera).
        distancia_total_m: Distancia acumulada desde el inicio de la ruta.
        giro: Para qué lado dobla la ruta en esta nota y cuántos grados
            (ver ``core.turns``). None en la largada, la llegada, o si
            no hay geometría suficiente para calcularlo.
    """

    waypoint: Waypoint
    orden: int
    distancia_parcial_m: float
    distancia_total_m: float
    giro: Turn | None = None


@dataclass
class RoadbookState:
    """Snapshot del estado de la tira, listo para que la UI lo renderice.

    Attributes:
        entries: Todas las entradas de la ruta activa.
        current_index: Índice de la entrada "actual" dentro de ``entries``.
        distance_to_next_m: Distancia en línea recta a la entrada
            actual. None si no hay posición GPS válida todavía.
        progress_fraction: Progreso estimado (0.0-1.0) dentro del tramo
            actual, basado en cuánto se acortó la distancia recta
            respecto al tramo completo.
        distance_traveled_m: Distancia total recorrida estimada desde
            el inicio de la ruta.
    """

    entries: list[RoadbookEntry]
    current_index: int
    distance_to_next_m: float | None
    progress_fraction: float
    distance_traveled_m: float


def build_entries(
    ordered_waypoints: list[Waypoint],
    track: list[tuple[float, float]] | None = None,
) -> list[RoadbookEntry]:
    """Construye la lista de ``RoadbookEntry`` a partir de waypoints ya ordenados.

    Args:
        ordered_waypoints: Waypoints ya en el orden final de la ruta
            (ver ``core.route.resolve_route_order``).
        track: Puntos del track GPX activo, si hay. Mejora el cálculo de
            los giros (ver ``core.turns``); no cambia las distancias.

    Returns:
        Entradas con distancia parcial/total calculadas (línea recta
        entre waypoints consecutivos).
    """
    turns = compute_turns(
        [(wp.latitud, wp.longitud) for wp in ordered_waypoints], track
    )
    entries: list[RoadbookEntry] = []
    total = 0.0
    previous: Waypoint | None = None

    for i, wp in enumerate(ordered_waypoints):
        parcial = (
            0.0
            if previous is None
            else NavigationEngine.haversine_distance(
                previous.latitud, previous.longitud, wp.latitud, wp.longitud
            )
        )
        total += parcial
        entries.append(
            RoadbookEntry(
                waypoint=wp,
                orden=i,
                distancia_parcial_m=parcial,
                distancia_total_m=total,
                giro=turns[i],
            )
        )
        previous = wp

    return entries


class RoadbookEngine:
    """Resuelve, ante cada posición GPS, el estado de la tira de roadbook.

    Attributes:
        entries: Entradas de la ruta activa, en orden.
    """

    def __init__(self, entries: list[RoadbookEntry]) -> None:
        self.entries = entries
        self._current_index = 0
        logger.info("RoadbookEngine inicializado con %d entradas", len(entries))

    def update_position(self, position: GpsPosition) -> RoadbookState:
        """Avanza el puntero de progreso si corresponde y devuelve el estado.

        Corre en el hilo que la invoque; no toca Qt ni dispara acciones.

        Args:
            position: Posición GPS actual.

        Returns:
            Snapshot del estado actual de la tira.
        """
        if not self.entries:
            return RoadbookState(
                entries=[],
                current_index=0,
                distance_to_next_m=None,
                progress_fraction=0.0,
                distance_traveled_m=0.0,
            )

        if not position.has_fix:
            return self._snapshot(None)

        # Avanza mientras estemos dentro del radio de la entrada actual
        # (la consideramos "alcanzada" y pasamos a vigilar la siguiente).
        while self._current_index < len(self.entries) - 1:
            current_wp = self.entries[self._current_index].waypoint
            distance = NavigationEngine.haversine_distance(
                position.latitude,
                position.longitude,
                current_wp.latitud,
                current_wp.longitud,
            )
            if distance <= current_wp.radio:
                self._current_index += 1
            else:
                break

        return self._snapshot(position)

    def _snapshot(self, position: GpsPosition | None) -> RoadbookState:
        current_entry = self.entries[self._current_index]
        distance_to_next: float | None = None
        progress = 0.0

        if position is not None:
            distance_to_next = NavigationEngine.haversine_distance(
                position.latitude,
                position.longitude,
                current_entry.waypoint.latitud,
                current_entry.waypoint.longitud,
            )
            segment_total = current_entry.distancia_parcial_m
            progress = (
                max(0.0, min(1.0, 1 - (distance_to_next / segment_total)))
                if segment_total > 0
                else 1.0
            )

        already_traveled = (
            self.entries[self._current_index - 1].distancia_total_m
            if self._current_index > 0
            else 0.0
        )
        within_segment = (
            (current_entry.distancia_parcial_m - distance_to_next)
            if distance_to_next is not None and current_entry.distancia_parcial_m > 0
            else 0.0
        )

        return RoadbookState(
            entries=self.entries,
            current_index=self._current_index,
            distance_to_next_m=distance_to_next,
            progress_fraction=progress,
            distance_traveled_m=max(0.0, already_traveled + within_segment),
        )

    def reset(self) -> None:
        """Reinicia el puntero de progreso al comienzo de la ruta."""
        self._current_index = 0
        logger.info("RoadbookEngine reiniciado al comienzo de la ruta")
