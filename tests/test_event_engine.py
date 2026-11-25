"""Tests de core.event_engine."""

from __future__ import annotations

import time

from core.action_dispatcher import ActionDispatcher, ActionType
from core.event_engine import EventEngine
from database.models import Action, Waypoint


class RecordingDispatcher(ActionDispatcher):
    """Dispatcher que registra cada acción ejecutada, con timestamp."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[float, ActionType, dict]] = []

    def execute(self, action_type: ActionType, payload: dict | None = None) -> None:
        self.calls.append((time.monotonic(), action_type, payload or {}))


class FakeActionRepository:
    """Repositorio falso: devuelve una secuencia fija para un waypoint dado."""

    def __init__(self, sequences: dict[int, list[Action]] | None = None) -> None:
        self.sequences = sequences or {}

    def list_for_waypoint(self, waypoint_id: int) -> list[Action]:
        return self.sequences.get(waypoint_id, [])


def _wait_until(condition, timeout: float = 2.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


def test_default_sequence_with_image_and_audio() -> None:
    dispatcher = RecordingDispatcher()
    engine = EventEngine(dispatcher, default_image_display_seconds=0.05)
    wp = Waypoint(
        id=1,
        nombre="Curva",
        latitud=0,
        longitud=0,
        imagen="resources/images/x.jpg",
        audio="resources/audio/x.wav",
    )

    engine.handle_waypoint(wp)

    assert _wait_until(lambda: len(dispatcher.calls) >= 4)
    types = [call[1] for call in dispatcher.calls]
    assert types == [
        ActionType.SHOW_IMAGE,
        ActionType.PLAY_AUDIO,
        ActionType.HIDE_IMAGE,
        ActionType.LOG_EVENT,
    ]


def test_default_sequence_without_image_has_no_wait_or_hide() -> None:
    dispatcher = RecordingDispatcher()
    engine = EventEngine(dispatcher)
    wp = Waypoint(
        id=2, nombre="Solo audio", latitud=0, longitud=0, audio="resources/audio/x.wav"
    )

    engine.handle_waypoint(wp)

    assert _wait_until(lambda: len(dispatcher.calls) >= 2)
    types = [call[1] for call in dispatcher.calls]
    assert types == [ActionType.PLAY_AUDIO, ActionType.LOG_EVENT]


def test_wait_step_is_non_blocking() -> None:
    """handle_waypoint debe retornar inmediatamente aunque la secuencia
    tenga un WAIT largo (la espera corre en threading.Timer, no bloquea)."""
    dispatcher = RecordingDispatcher()
    engine = EventEngine(dispatcher, default_image_display_seconds=1.0)
    wp = Waypoint(id=3, nombre="Con imagen", latitud=0, longitud=0, imagen="x.jpg")

    start = time.monotonic()
    engine.handle_waypoint(wp)
    elapsed = time.monotonic() - start

    assert elapsed < 0.2, "handle_waypoint no debe bloquear durante el WAIT"


def test_wait_actually_delays_hide_image() -> None:
    dispatcher = RecordingDispatcher()
    engine = EventEngine(dispatcher, default_image_display_seconds=0.2)
    wp = Waypoint(id=4, nombre="Con imagen", latitud=0, longitud=0, imagen="x.jpg")

    engine.handle_waypoint(wp)
    assert _wait_until(lambda: len(dispatcher.calls) >= 2)

    show_time = dispatcher.calls[0][0]
    hide_time = next(c[0] for c in dispatcher.calls if c[1] is ActionType.HIDE_IMAGE)
    assert hide_time - show_time >= 0.15  # tolerancia bajo la carga del test runner


def test_custom_sequence_overrides_default() -> None:
    dispatcher = RecordingDispatcher()
    custom_actions = [
        Action(waypoint_id=5, orden=0, tipo="log_event", payload={"message": "custom"}),
    ]
    repo = FakeActionRepository({5: custom_actions})
    engine = EventEngine(dispatcher, action_repository=repo)
    wp = Waypoint(
        id=5, nombre="Con secuencia custom", latitud=0, longitud=0, imagen="x.jpg"
    )

    engine.handle_waypoint(wp)

    assert _wait_until(lambda: len(dispatcher.calls) >= 1)
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0][1] == ActionType.LOG_EVENT
    assert dispatcher.calls[0][2] == {"message": "custom"}


def test_concurrent_waypoints_do_not_interfere() -> None:
    dispatcher = RecordingDispatcher()
    engine = EventEngine(dispatcher, default_image_display_seconds=0.05)

    wp_a = Waypoint(id=10, nombre="A", latitud=0, longitud=0, imagen="a.jpg")
    wp_b = Waypoint(id=11, nombre="B", latitud=0, longitud=0, imagen="b.jpg")

    engine.handle_waypoint(wp_a)
    engine.handle_waypoint(wp_b)

    assert _wait_until(lambda: len(dispatcher.calls) >= 6)

    paths_shown = {
        call[2].get("path")
        for call in dispatcher.calls
        if call[1] is ActionType.SHOW_IMAGE
    }
    assert paths_shown == {"a.jpg", "b.jpg"}


def test_waypoint_without_any_action_source_still_logs() -> None:
    dispatcher = RecordingDispatcher()
    engine = EventEngine(dispatcher)
    wp = Waypoint(id=6, nombre="Vacío", latitud=0, longitud=0)

    engine.handle_waypoint(wp)

    assert _wait_until(lambda: len(dispatcher.calls) >= 1)
    assert dispatcher.calls[0][1] == ActionType.LOG_EVENT
