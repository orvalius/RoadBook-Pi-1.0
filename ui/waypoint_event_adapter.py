"""Adapter Qt para el evento de waypoint alcanzado.

Igual que ``QtGpsAdapter``, este es el único puente autorizado entre
el callback de ``NavigationEngine.on_waypoint_reached`` (que corre en
el hilo del GPS Manager) y el hilo principal de Qt. El core nunca
importa PyQt directamente.

NOTA: Este adapter es un puente temporal y directo hasta el Sprint 8
(Event Engine), donde el Event Engine real se insertará entre el
NavigationEngine y el despacho de acciones, permitiendo secuencias de
múltiples acciones (mostrar imagen -> esperar -> ocultar -> audio,
etc.) en vez de la reacción directa que implementa este adapter.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger
from core.navigation_engine import NavigationEngine
from database.models import Waypoint

logger = get_logger(__name__)


class WaypointEventAdapter(QObject):
    """Traduce el evento de waypoint alcanzado a una señal Qt.

    Attributes:
        waypoint_reached: Señal emitida con el ``Waypoint`` alcanzado.
    """

    waypoint_reached = pyqtSignal(object)  # payload: Waypoint

    def __init__(
        self, navigation_engine: NavigationEngine, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        navigation_engine.on_waypoint_reached = self._on_reached

    def _on_reached(self, waypoint: Waypoint) -> None:
        # Corre en el hilo del GPS Manager, no en el hilo Qt.
        self.waypoint_reached.emit(waypoint)
