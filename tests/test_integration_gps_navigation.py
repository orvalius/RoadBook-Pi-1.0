"""Test de integración: GpsManager (simulador) -> NavigationEngine.

Verifica el pipeline completo sin necesidad de Qt ni hardware real.
"""

from __future__ import annotations

import time

from core.gps_manager import GpsManager, GpsPosition
from core.navigation_engine import NavigationEngine
from database.models import Waypoint


def test_gps_simulator_triggers_navigation_event() -> None:
    waypoint = Waypoint(
        id=1, nombre="Meta", latitud=-34.6037, longitud=-58.3816, radio=100.0
    )

    engine = NavigationEngine()
    reached: list[Waypoint] = []
    engine.on_waypoint_reached = reached.append
    engine.load_waypoints([waypoint])

    # Track del simulador: primera posición coincide exactamente con el waypoint
    track = [GpsPosition(latitude=-34.6037, longitude=-58.3816, has_fix=True)]
    gps = GpsManager(
        backend="simulator", simulator_track=track, simulator_interval=0.05
    )
    gps.register_callback(engine.update_position)

    gps.start()
    time.sleep(0.15)
    gps.stop()

    assert len(reached) == 1
    assert reached[0].nombre == "Meta"
