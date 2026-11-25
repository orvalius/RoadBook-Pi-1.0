"""Test de concurrencia de NavigationEngine.

Simula el escenario real: el hilo del GPS llama a update_position()
en loop mientras el hilo de la UI llama a load_waypoints() al mismo
tiempo (el usuario edita un waypoint mientras el vehículo se mueve).
No debe lanzar excepciones ni corromper el estado interno.
"""

from __future__ import annotations

import threading

from core.gps_manager import GpsPosition
from core.navigation_engine import NavigationEngine
from database.models import Waypoint


def test_concurrent_load_and_update_does_not_crash() -> None:
    engine = NavigationEngine()
    position = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
    errors: list[Exception] = []
    stop = threading.Event()

    def gps_loop() -> None:
        while not stop.is_set():
            try:
                engine.update_position(position)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    def ui_loop() -> None:
        for i in range(200):
            wp = Waypoint(
                id=i % 5, nombre=f"WP{i}", latitud=0.0, longitud=0.0, radio=100.0
            )
            try:
                engine.load_waypoints([wp])
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    gps_thread = threading.Thread(target=gps_loop)
    ui_thread = threading.Thread(target=ui_loop)

    gps_thread.start()
    ui_thread.start()
    ui_thread.join(timeout=5)
    stop.set()
    gps_thread.join(timeout=2)

    assert errors == [], f"Errores durante acceso concurrente: {errors}"
