"""Navigation Engine de RoadBook Pi.

Recibe posiciones del GPS Manager, calcula distancias hacia los
waypoints activos y determina cuándo el vehículo entra en el radio de
un waypoint. Nunca la UI debe calcular esto directamente.

Implementa histéresis por waypoint: el evento se dispara únicamente
en la transición ``fuera -> dentro``, nunca mientras el vehículo
permanece dentro del radio. El flag ``re_triggerable`` de cada
waypoint controla si puede volver a dispararse tras una nueva
re-entrada (comportamiento normal) o si ya disparado una vez, queda
consumido por el resto de la sesión (útil para anuncios de "una sola
vez", como una largada).

Condiciones opcionales por waypoint:

- ``velocidad``: si está seteada, el evento solo dispara si la
  velocidad actual del vehículo es >= a ese valor (km/h). Útil para
  alertas que solo tienen sentido circulando ("frenar" a alta
  velocidad, por ejemplo).
- ``angulo``: si está seteado, el evento solo dispara si el rumbo
  actual del vehículo está dentro de la tolerancia angular respecto a
  ese valor. Útil para waypoints direccionales (solo avisar si se
  aproxima desde cierto sentido).

Ambas condiciones son ``None`` por defecto (sin restricción).

Thread-safety: ``update_position`` corre en el hilo del GPS Manager,
mientras que ``load_waypoints`` puede ser llamado desde el hilo
principal (Qt) cuando el usuario edita waypoints. Un ``threading.Lock``
protege el acceso concurrente al estado interno.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from enum import Enum, auto

from core.gps_manager import GpsPosition
from core.logger import get_logger
from database.models import Waypoint

logger = get_logger(__name__)

WaypointCallback = Callable[[Waypoint], None]

DEFAULT_HEADING_TOLERANCE_DEGREES = 45.0


class ProximityState(Enum):
    """Estado de proximidad de un waypoint respecto al vehículo."""

    OUTSIDE = auto()
    INSIDE = auto()


class NavigationEngine:
    """Motor de navegación: traduce posiciones GPS en eventos de proximidad.

    Attributes:
        on_waypoint_reached: Callback invocado con el ``Waypoint``
            alcanzado, solo en la transición fuera->dentro y con las
            condiciones opcionales (velocidad/ángulo) satisfechas.
        heading_tolerance_degrees: Tolerancia angular (+/-) para la
            condición de rumbo de los waypoints.
    """

    def __init__(self, heading_tolerance_degrees: float = DEFAULT_HEADING_TOLERANCE_DEGREES) -> None:
        self.on_waypoint_reached: WaypointCallback | None = None
        self.heading_tolerance_degrees = heading_tolerance_degrees

        self._waypoints: list[Waypoint] = []
        self._state: dict[int, ProximityState] = {}
        self._already_fired: set[int] = set()
        self._lock = threading.Lock()

        logger.info(
            "NavigationEngine inicializado (tolerancia de rumbo: %.1f°)",
            heading_tolerance_degrees,
        )

    def load_waypoints(self, waypoints: list[Waypoint]) -> None:
        """Carga (o recarga) el conjunto de waypoints activos a vigilar.

        Debe llamarse cada vez que cambian los waypoints en base de
        datos (alta, baja, edición, activar/desactivar). Thread-safe:
        puede llamarse desde el hilo de la UI mientras el hilo del GPS
        está procesando posiciones.

        Args:
            waypoints: Lista de waypoints a monitorear (usualmente solo
                los activos).
        """
        with self._lock:
            self._waypoints = [wp for wp in waypoints if wp.activo]
            valid_ids = {wp.id for wp in self._waypoints if wp.id is not None}
            self._state = {
                wp_id: state for wp_id, state in self._state.items()
                if wp_id in valid_ids
            }
            for wp in self._waypoints:
                if wp.id is not None and wp.id not in self._state:
                    self._state[wp.id] = ProximityState.OUTSIDE

        logger.debug(
            "NavigationEngine: %d waypoints activos cargados", len(self._waypoints)
        )

    def update_position(self, position: GpsPosition) -> None:
        """Procesa una nueva posición GPS y detecta transiciones de radio.

        Corre típicamente en el hilo del GPS Manager.

        Args:
            position: Posición GPS actual del vehículo.
        """
        if not position.has_fix:
            return

        with self._lock:
            waypoints_snapshot = list(self._waypoints)

        for wp in waypoints_snapshot:
            if wp.id is None:
                continue

            if self._definitely_outside(position, wp):
                # Sabemos con certeza que is_inside=False sin calcular el
                # haversine (caro). Si estaba INSIDE, igual hay que
                # resetear el estado para permitir una futura re-entrada.
                with self._lock:
                    if self._state.get(wp.id) is ProximityState.INSIDE:
                        self._state[wp.id] = ProximityState.OUTSIDE
                continue

            distance = self.haversine_distance(
                position.latitude, position.longitude, wp.latitud, wp.longitud
            )
            is_inside = distance <= wp.radio

            with self._lock:
                previous_state = self._state.get(wp.id, ProximityState.OUTSIDE)
                if is_inside and previous_state is ProximityState.OUTSIDE:
                    self._state[wp.id] = ProximityState.INSIDE
                    should_handle_entry = True
                elif not is_inside and previous_state is ProximityState.INSIDE:
                    self._state[wp.id] = ProximityState.OUTSIDE
                    should_handle_entry = False
                else:
                    should_handle_entry = False

            if should_handle_entry:
                self._handle_entry(wp, position)

    @staticmethod
    def _definitely_outside(position: GpsPosition, waypoint: Waypoint) -> bool:
        """Pre-filtro barato: descarta waypoints obviamente lejanos sin
        pagar el costo de las funciones trigonométricas del haversine.

        Optimización de Sprint 10: en una ruta con muchos waypoints, la
        gran mayoría están lejos del vehículo en un instante dado. Un
        grado de latitud son ~111.320m sin importar la posición (a
        diferencia de la longitud, que varía con `cos(latitud)`), así
        que comparar solo la diferencia de latitud en metros da un
        límite inferior seguro de la distancia real: si ese límite ya
        supera el radio, el waypoint está garantizado fuera de rango y
        el haversine completo puede saltearse con seguridad.

        Args:
            position: Posición actual del vehículo.
            waypoint: Waypoint a evaluar.

        Returns:
            True si el waypoint está garantizado fuera de su radio
            (nunca da falsos positivos: si devuelve True, el waypoint
            realmente está afuera).
        """
        METERS_PER_DEGREE_LATITUDE = 111_320
        lat_diff_m = abs(position.latitude - waypoint.latitud) * METERS_PER_DEGREE_LATITUDE
        return lat_diff_m > waypoint.radio

    def _conditions_met(self, waypoint: Waypoint, position: GpsPosition) -> bool:
        """Evalúa las condiciones opcionales de velocidad y rumbo.

        Args:
            waypoint: Waypoint a evaluar.
            position: Posición/estado actual del vehículo.

        Returns:
            True si no hay condiciones o si todas se cumplen.
        """
        if waypoint.velocidad is not None and position.speed < waypoint.velocidad:
            logger.debug(
                "Waypoint %s: velocidad insuficiente (%.1f < %.1f)",
                waypoint.id, position.speed, waypoint.velocidad,
            )
            return False

        if waypoint.angulo is not None:
            if position.heading is None:
                logger.debug(
                    "Waypoint %s: requiere rumbo pero no hay heading disponible",
                    waypoint.id,
                )
                return False
            diff = self.angular_difference(position.heading, waypoint.angulo)
            if diff > self.heading_tolerance_degrees:
                logger.debug(
                    "Waypoint %s: rumbo fuera de tolerancia (%.1f° > %.1f°)",
                    waypoint.id, diff, self.heading_tolerance_degrees,
                )
                return False

        return True

    def _handle_entry(self, waypoint: Waypoint, position: GpsPosition) -> None:
        """Dispara el callback de entrada, respetando condiciones y re_triggerable."""
        assert waypoint.id is not None

        if not self._conditions_met(waypoint, position):
            return

        if not waypoint.re_triggerable and waypoint.id in self._already_fired:
            logger.debug(
                "Waypoint %s no re-disparable, ya se ejecutó en esta sesión",
                waypoint.id,
            )
            return

        self._already_fired.add(waypoint.id)
        logger.info(
            "Waypoint alcanzado: id=%s nombre=%s", waypoint.id, waypoint.nombre
        )

        if self.on_waypoint_reached is not None:
            self.on_waypoint_reached(waypoint)

    def get_nearest_waypoint(
        self, position: GpsPosition
    ) -> tuple[Waypoint, float] | None:
        """Devuelve el waypoint activo más cercano y la distancia a él.

        Útil para mostrar información en pantalla (ej: "faltan 350m
        para X"), sin disparar ningún evento.

        Args:
            position: Posición actual del vehículo.

        Returns:
            Tupla (waypoint, distancia_metros), o None si no hay
            waypoints cargados.
        """
        with self._lock:
            waypoints_snapshot = list(self._waypoints)

        if not waypoints_snapshot:
            return None

        nearest: tuple[Waypoint, float] | None = None
        for wp in waypoints_snapshot:
            distance = self.haversine_distance(
                position.latitude, position.longitude, wp.latitud, wp.longitud
            )
            if nearest is None or distance < nearest[1]:
                nearest = (wp, distance)
        return nearest

    @staticmethod
    def angular_difference(a: float, b: float) -> float:
        """Calcula la diferencia angular mínima entre dos rumbos (0-360°).

        Args:
            a: Primer ángulo en grados.
            b: Segundo ángulo en grados.

        Returns:
            Diferencia angular absoluta mínima, entre 0 y 180 grados.
        """
        diff = abs(a - b) % 360
        return diff if diff <= 180 else 360 - diff

    @staticmethod
    def haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calcula la distancia en metros entre dos coordenadas GPS.

        Args:
            lat1: Latitud del punto 1.
            lon1: Longitud del punto 1.
            lat2: Latitud del punto 2.
            lon2: Longitud del punto 2.

        Returns:
            Distancia en metros.
        """
        from math import atan2, cos, radians, sin, sqrt

        r = 6_371_000
        phi1, phi2 = radians(lat1), radians(lat2)
        d_phi = radians(lat2 - lat1)
        d_lambda = radians(lon2 - lon1)

        a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return r * c
