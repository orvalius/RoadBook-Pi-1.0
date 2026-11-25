"""Tests de core.action_dispatcher."""

from __future__ import annotations

from core.action_dispatcher import ActionDispatcher, ActionType


def test_execute_calls_registered_handler() -> None:
    dispatcher = ActionDispatcher()
    received = []
    dispatcher.register_handler(
        ActionType.SHOW_IMAGE, lambda payload: received.append(payload)
    )

    dispatcher.execute(ActionType.SHOW_IMAGE, {"path": "x.jpg"})

    assert received == [{"path": "x.jpg"}]


def test_execute_without_handler_does_not_raise() -> None:
    dispatcher = ActionDispatcher()
    # No hay handler registrado para PLAY_AUDIO: no debe lanzar excepción
    dispatcher.execute(ActionType.PLAY_AUDIO, {"path": "x.wav"})


def test_execute_with_none_payload_passes_empty_dict() -> None:
    dispatcher = ActionDispatcher()
    received = []
    dispatcher.register_handler(
        ActionType.LOG_EVENT, lambda payload: received.append(payload)
    )

    dispatcher.execute(ActionType.LOG_EVENT, None)

    assert received == [{}]


def test_handler_exception_does_not_propagate() -> None:
    dispatcher = ActionDispatcher()

    def failing_handler(payload: dict) -> None:
        raise RuntimeError("boom")

    dispatcher.register_handler(ActionType.RUN_PLUGIN, failing_handler)

    # No debe lanzar, solo loguear el error
    dispatcher.execute(ActionType.RUN_PLUGIN, {})


def test_register_handler_replaces_previous() -> None:
    dispatcher = ActionDispatcher()
    calls = []
    dispatcher.register_handler(ActionType.HIDE_IMAGE, lambda p: calls.append("first"))
    dispatcher.register_handler(ActionType.HIDE_IMAGE, lambda p: calls.append("second"))

    dispatcher.execute(ActionType.HIDE_IMAGE, {})

    assert calls == ["second"]


def test_action_type_values_match_expected_strings() -> None:
    # Estos valores deben coincidir con lo que se guarda en la columna
    # actions.tipo; un cambio accidental acá rompería waypoints existentes.
    assert ActionType.SHOW_IMAGE.value == "show_image"
    assert ActionType.PLAY_AUDIO.value == "play_audio"
    assert ActionType.WAIT.value == "wait"
    assert ActionType.HIDE_IMAGE.value == "hide_image"
    assert ActionType.LOG_EVENT.value == "log_event"
    assert ActionType.RUN_PLUGIN.value == "run_plugin"
