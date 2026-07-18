"""Action Dispatcher de RoadBook Pi.

Ejecuta las acciones concretas que decide el Event Engine: mostrar
imagen, reproducir audio, ocultar imagen, registrar log, ejecutar
plugin (``WAIT`` nunca llega hasta acá: el Event Engine la resuelve
internamente como una demora entre pasos, ver ``core/event_engine.py``).

El Core no sabe qué significa "mostrar una imagen" en términos de Qt;
solo invoca el handler que fue registrado para cada ``ActionType``. La
UI registra esos handlers a través de un adapter (ver
``ui/action_event_adapter.py``), manteniendo la separación Core/UI.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from core.logger import get_logger

logger = get_logger(__name__)

ActionHandler = Callable[[dict], None]


class ActionType(str, Enum):
    """Tipos de acción que el sistema de eventos puede disparar.

    Hereda de ``str`` para que el valor coincida exactamente con lo
    que se guarda en la columna ``actions.tipo`` de la base de datos
    (ej: ``ActionType.SHOW_IMAGE.value == "show_image"``).
    """

    SHOW_IMAGE = "show_image"
    PLAY_AUDIO = "play_audio"
    WAIT = "wait"
    HIDE_IMAGE = "hide_image"
    LOG_EVENT = "log_event"
    RUN_PLUGIN = "run_plugin"


class ActionDispatcher:
    """Ejecuta acciones individuales solicitadas por el Event Engine.

    Attributes:
        Ninguno público; los handlers se registran vía
        ``register_handler``.
    """

    def __init__(self) -> None:
        self._handlers: dict[ActionType, ActionHandler] = {}
        logger.info("ActionDispatcher inicializado")

    def register_handler(self, action_type: ActionType, handler: ActionHandler) -> None:
        """Registra el handler que ejecuta un tipo de acción.

        Si ya había un handler registrado para ese tipo, lo reemplaza.

        Args:
            action_type: Tipo de acción a manejar.
            handler: Función que recibe el ``payload`` de la acción.
        """
        self._handlers[action_type] = handler
        logger.debug("Handler registrado para %s", action_type.value)

    def execute(self, action_type: ActionType, payload: dict | None = None) -> None:
        """Ejecuta una acción según su tipo.

        Args:
            action_type: Tipo de acción a ejecutar.
            payload: Datos necesarios para la acción (ej: ruta de imagen).
        """
        handler = self._handlers.get(action_type)
        if handler is None:
            logger.warning(
                "No hay handler registrado para %s, acción ignorada", action_type.value
            )
            return

        try:
            handler(payload or {})
        except Exception:
            logger.exception("Error ejecutando acción %s", action_type.value)
