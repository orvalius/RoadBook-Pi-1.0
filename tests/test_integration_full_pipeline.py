"""Test de integración end-to-end (Sprint 11: Beta).

Simula una "sesión de manejo" completa usando únicamente el Core (sin
Qt, que no está disponible en este entorno de tests): base de datos
real, GPS simulado con un track de dos paradas, un waypoint con
secuencia custom y otro con comportamiento legacy (imagen/audio), y
verifica que el pipeline completo dispare las acciones correctas de
punta a punta.

    GPS (simulador) -> NavigationEngine -> EventEngine -> ActionDispatcher
"""

from __future__ import annotations

import time
from pathlib import Path

from core.action_dispatcher import ActionDispatcher, ActionType
from core.event_engine import EventEngine
from core.gps_manager import GpsManager, GpsPosition
from core.navigation_engine import NavigationEngine
from database.action_repository import ActionRepository
from database.db_manager import DatabaseManager
from database.models import Action, Waypoint
from database.waypoint_repository import WaypointRepository


class RecordingDispatcher(ActionDispatcher):
    """Dispatcher que registra cada acción ejecutada, con timestamp."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[float, ActionType, dict]] = []

    def execute(self, action_type: ActionType, payload: dict | None = None) -> None:
        self.calls.append((time.monotonic(), action_type, payload or {}))


def _wait_until(condition, timeout: float = 3.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


def test_full_drive_session(tmp_path: Path) -> None:
    # --- Setup: base de datos real con dos waypoints ---
    db = DatabaseManager(tmp_path / "session.db")
    db.initialize_schema()
    waypoint_repo = WaypointRepository(db)
    action_repo = ActionRepository(db)

    # Waypoint 1: comportamiento legacy (imagen + audio, sin fila en actions)
    waypoint_repo.create(
        Waypoint(
            nombre="Curva peligrosa",
            latitud=-34.6037,
            longitud=-58.3816,
            radio=100.0,
            imagen="resources/images/curva.jpg",
            audio="resources/audio/alerta.wav",
        )
    )

    # Waypoint 2: secuencia custom (solo un log distintivo)
    custom_wp = waypoint_repo.create(
        Waypoint(
            nombre="Punto de interés", latitud=-34.7000, longitud=-58.5000, radio=80.0
        )
    )
    action_repo.create(
        Action(
            waypoint_id=custom_wp.id,
            orden=0,
            tipo="log_event",
            payload={"message": "Bienvenido al mirador"},
        )
    )

    # --- Setup: motor de navegación + motor de eventos reales ---
    navigation_engine = NavigationEngine()
    navigation_engine.load_waypoints(waypoint_repo.list_all(only_active=True))

    dispatcher = RecordingDispatcher()
    event_engine = EventEngine(
        dispatcher, action_repository=action_repo, default_image_display_seconds=0.05
    )
    navigation_engine.on_waypoint_reached = event_engine.handle_waypoint

    # --- Setup: GPS simulado con un track que pasa por ambos waypoints ---
    track = [
        GpsPosition(latitude=-30.0, longitude=-50.0, has_fix=True),  # lejos de todo
        GpsPosition(
            latitude=-34.6037, longitude=-58.3816, has_fix=True
        ),  # waypoint legacy
        GpsPosition(latitude=-30.0, longitude=-50.0, has_fix=True),  # se aleja
        GpsPosition(
            latitude=-34.7000, longitude=-58.5000, has_fix=True
        ),  # waypoint custom
    ]
    gps = GpsManager(
        backend="simulator", simulator_track=track, simulator_interval=0.05
    )
    gps.register_callback(navigation_engine.update_position)

    # --- Ejecutar la "sesión de manejo" ---
    gps.start()
    assert _wait_until(lambda: len(dispatcher.calls) >= 4, timeout=3.0)
    time.sleep(0.3)  # dejar completar cualquier WAIT pendiente de la secuencia legacy
    gps.stop()
    db.close()

    # --- Verificaciones ---
    types_in_order = [call[1] for call in dispatcher.calls]

    # El waypoint legacy debe haber disparado su secuencia default completa
    assert ActionType.SHOW_IMAGE in types_in_order
    assert ActionType.PLAY_AUDIO in types_in_order
    assert ActionType.HIDE_IMAGE in types_in_order

    # El waypoint custom debe haber disparado su log distintivo
    custom_logs = [
        call[2].get("message")
        for call in dispatcher.calls
        if call[1] is ActionType.LOG_EVENT
    ]
    assert "Bienvenido al mirador" in custom_logs

    # La imagen mostrada debe ser la del waypoint legacy, no una inventada
    show_image_calls = [
        call[2] for call in dispatcher.calls if call[1] is ActionType.SHOW_IMAGE
    ]
    assert show_image_calls[0]["path"] == "resources/images/curva.jpg"
