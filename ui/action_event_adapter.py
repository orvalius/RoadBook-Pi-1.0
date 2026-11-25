"""Adapter Qt para ActionDispatcher.

Mismo patrón que ``QtGpsAdapter`` y ``WaypointEventAdapter``: registra
un handler por cada ``ActionType`` en el ``ActionDispatcher`` (que
puede invocarse desde el hilo del GPS o desde un hilo de
``threading.Timer``) y lo traduce a una señal Qt, que Qt encola
automáticamente en el hilo principal porque este adapter vive ahí.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.action_dispatcher import ActionDispatcher, ActionType
from core.logger import get_logger

logger = get_logger(__name__)


class QtActionAdapter(QObject):
    """Traduce cada acción despachada a una señal Qt.

    Attributes:
        action_triggered: Señal emitida con (ActionType, payload dict).
    """

    action_triggered = pyqtSignal(object, object)

    def __init__(
        self, action_dispatcher: ActionDispatcher, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        for action_type in ActionType:
            if action_type is ActionType.WAIT:
                continue  # WAIT nunca llega al dispatcher, la resuelve el Event Engine
            action_dispatcher.register_handler(
                action_type, self._make_handler(action_type)
            )

    def _make_handler(self, action_type: ActionType):
        def handler(payload: dict) -> None:
            # Puede correr en el hilo del GPS o en un hilo de threading.Timer.
            self.action_triggered.emit(action_type, payload)

        return handler
