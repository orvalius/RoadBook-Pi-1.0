"""Utilidades de formateo de tiempo para la UI.

Lógica pura, sin Qt, para poder testearla sin levantar ninguna
ventana.
"""

from __future__ import annotations


def format_duration_seconds(seconds: float) -> str:
    """Formatea una duración en segundos como texto legible en español.

    Args:
        seconds: Duración en segundos (no negativa).

    Returns:
        Texto como "5s", "1m 30s", "2h 5m".
    """
    seconds = max(0, int(seconds))

    if seconds < 60:
        return f"{seconds}s"

    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        if remaining_seconds == 0:
            return f"{minutes}m"
        return f"{minutes}m {remaining_seconds}s"

    hours, remaining_minutes = divmod(minutes, 60)
    if remaining_minutes == 0:
        return f"{hours}h"
    return f"{hours}h {remaining_minutes}m"
