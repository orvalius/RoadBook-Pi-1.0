"""Adapter Qt para GpsManager.

Único módulo autorizado a conectar el ``GpsManager`` (que corre en su
propio hilo, agnóstico de Qt) con el mundo de señales/slots de Qt. El
core (``core/gps_manager.py``) nunca importa PyQt; esta clase vive en
``ui/`` a propósito.

La emisión de una señal Qt desde un hilo distinto al principal es
segura: Qt encola la entrega en el hilo del receptor automáticamente
(conexión "auto", que se resuelve a "queued" cuando emisor y receptor
están en hilos distintos).
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.gps_manager import GpsManager, GpsPosition
from core.logger import get_logger

logger = get_logger(__name__)


class QtGpsAdapter(QObject):
    """Traduce las posiciones del GpsManager a una señal Qt.

    Attributes:
        position_received: Señal emitida con cada nueva ``GpsPosition``.
    """

    position_received = pyqtSignal(object)  # payload: GpsPosition

    def __init__(self, gps_manager: GpsManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.gps_manager = gps_manager
        self.gps_manager.register_callback(self._on_position)

    def _on_position(self, position: GpsPosition) -> None:
        # Este método corre en el hilo del GpsManager, no en el hilo Qt.
        self.position_received.emit(position)

    def start(self) -> None:
        """Inicia el GpsManager subyacente."""
        self.gps_manager.start()
        logger.info("QtGpsAdapter: GPS iniciado")

    def stop(self) -> None:
        """Detiene el GpsManager subyacente."""
        self.gps_manager.stop()
        logger.info("QtGpsAdapter: GPS detenido")
