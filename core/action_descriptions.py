"""Descripciones legibles de acciones de un waypoint.

Traduce una acción (tipo + payload, tal como se guarda en la tabla
``actions``) a un texto legible para mostrar en la UI de autoría de
secuencias. Lógica pura, sin Qt, para poder testearla sin levantar
ninguna ventana.
"""

from __future__ import annotations

from pathlib import Path

from core.action_dispatcher import ActionType

ACTION_TYPE_LABELS: dict[str, str] = {
    ActionType.SHOW_IMAGE.value: "Mostrar imagen",
    ActionType.PLAY_AUDIO.value: "Reproducir audio",
    ActionType.WAIT.value: "Esperar",
    ActionType.HIDE_IMAGE.value: "Ocultar imagen",
    ActionType.LOG_EVENT.value: "Registrar log",
    ActionType.RUN_PLUGIN.value: "Ejecutar plugin",
}


def describe_action(tipo: str, payload: dict) -> str:
    """Devuelve una descripción legible de una acción, para mostrar en UI.

    Args:
        tipo: Valor de ``ActionType`` (ej: "show_image").
        payload: Payload de la acción.

    Returns:
        Texto descriptivo, ej: "Mostrar imagen: curva.jpg".
    """
    label = ACTION_TYPE_LABELS.get(tipo, tipo)

    if tipo == ActionType.SHOW_IMAGE.value:
        filename = Path(payload.get("path", "")).name or "(sin archivo)"
        return f"{label}: {filename}"

    if tipo == ActionType.PLAY_AUDIO.value:
        filename = Path(payload.get("path", "")).name or "(sin archivo)"
        return f"{label}: {filename}"

    if tipo == ActionType.WAIT.value:
        seconds = payload.get("seconds", 0)
        return f"{label} {seconds}s"

    if tipo == ActionType.LOG_EVENT.value:
        message = payload.get("message", "")
        return f'{label}: "{message}"' if message else label

    if tipo == ActionType.RUN_PLUGIN.value:
        plugin_name = payload.get("plugin_name", "(sin nombre)")
        return f"{label}: {plugin_name}"

    # HIDE_IMAGE y cualquier tipo desconocido: sin parámetros que mostrar
    return label
