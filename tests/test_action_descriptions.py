"""Tests de core.action_descriptions."""

from __future__ import annotations

from core.action_descriptions import describe_action
from core.action_dispatcher import ActionType


def test_describe_show_image() -> None:
    text = describe_action(ActionType.SHOW_IMAGE.value, {"path": "resources/images/curva.jpg"})
    assert text == "Mostrar imagen: curva.jpg"


def test_describe_show_image_without_path() -> None:
    text = describe_action(ActionType.SHOW_IMAGE.value, {})
    assert "sin archivo" in text.lower()


def test_describe_play_audio() -> None:
    text = describe_action(ActionType.PLAY_AUDIO.value, {"path": "resources/audio/beep.wav"})
    assert text == "Reproducir audio: beep.wav"


def test_describe_wait() -> None:
    text = describe_action(ActionType.WAIT.value, {"seconds": 3.5})
    assert text == "Esperar 3.5s"


def test_describe_hide_image_has_no_parameters() -> None:
    text = describe_action(ActionType.HIDE_IMAGE.value, {})
    assert text == "Ocultar imagen"


def test_describe_log_event_with_message() -> None:
    text = describe_action(ActionType.LOG_EVENT.value, {"message": "hola mundo"})
    assert text == 'Registrar log: "hola mundo"'


def test_describe_log_event_without_message() -> None:
    text = describe_action(ActionType.LOG_EVENT.value, {})
    assert text == "Registrar log"


def test_describe_run_plugin() -> None:
    text = describe_action(ActionType.RUN_PLUGIN.value, {"plugin_name": "clima"})
    assert text == "Ejecutar plugin: clima"


def test_describe_unknown_type_falls_back_to_raw_value() -> None:
    text = describe_action("tipo_inventado", {})
    assert text == "tipo_inventado"
