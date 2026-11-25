"""Cierre ordenado de la aplicación ante señales del sistema operativo.

Problema que resuelve: bajo systemd, ``systemctl stop`` y el apagado de
la Raspberry Pi envían ``SIGTERM``. Antes de este módulo la app lo
ignoraba por dos motivos combinados:

1. ``pygame.mixer.init()`` inicializa SDL, que instala sus propios
   handlers de ``SIGINT``/``SIGTERM`` (los convierte en un evento
   ``SDL_QUIT`` que nadie consume). El proceso nunca terminaba.
2. Aunque Python tenga un handler propio, mientras corre el loop de Qt
   (``app.exec()``, código C++) el intérprete no recupera el control y
   el handler no se ejecuta hasta que llega algún evento de Qt.

La solución estándar: instalar handlers de Python (que reemplazan a los
de SDL, por eso hay que instalarlos *después* de inicializar el audio)
y usar ``signal.set_wakeup_fd`` sobre un par de sockets vigilado por un
``QSocketNotifier``. Cuando llega una señal, el byte escrito en el
socket despierta el loop de Qt, el handler de Python corre, y se pide
``QApplication.quit()``. Así ``app.exec()`` retorna y ``main.py``
ejecuta su limpieza normal (GPS, mapas, base de datos).

No hay polling: cero costo de CPU mientras no llegue ninguna señal.
"""

from __future__ import annotations

import signal
import socket
from collections.abc import Callable, Iterable
from types import FrameType

from PyQt6.QtCore import QObject, QSocketNotifier

from core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SIGNALS: tuple[signal.Signals, ...] = tuple(
    s for s in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None)) if s
)


class GracefulShutdown(QObject):
    """Conecta señales del SO con un callback de cierre dentro del loop Qt.

    Attributes:
        received_signal: Número de la última señal recibida, o ``None``.
    """

    def __init__(
        self,
        on_shutdown: Callable[[], None],
        signals: Iterable[signal.Signals] = DEFAULT_SIGNALS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_shutdown = on_shutdown
        self._signals = tuple(signals)
        self._previous_handlers: dict[signal.Signals, object] = {}
        self._previous_wakeup_fd: int = -1
        self.received_signal: int | None = None

        self._read_sock, self._write_sock = socket.socketpair()
        self._read_sock.setblocking(False)
        self._write_sock.setblocking(False)

        self._notifier = QSocketNotifier(
            self._read_sock.fileno(), QSocketNotifier.Type.Read, self
        )
        self._notifier.activated.connect(self._drain_wakeup_socket)

    def install(self) -> None:
        """Instala los handlers. Llamar después de inicializar pygame/SDL."""
        self._previous_wakeup_fd = signal.set_wakeup_fd(
            self._write_sock.fileno(), warn_on_full_buffer=False
        )
        for sig in self._signals:
            self._previous_handlers[sig] = signal.signal(sig, self._handle_signal)
        logger.info(
            "Cierre ordenado habilitado para: %s",
            ", ".join(s.name for s in self._signals),
        )

    def uninstall(self) -> None:
        """Restaura los handlers previos y libera los sockets."""
        for sig, handler in self._previous_handlers.items():
            try:
                signal.signal(sig, handler)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                signal.signal(sig, signal.SIG_DFL)
        self._previous_handlers.clear()
        signal.set_wakeup_fd(self._previous_wakeup_fd)
        self._notifier.setEnabled(False)
        self._read_sock.close()
        self._write_sock.close()

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        if self.received_signal is not None:
            # Segunda señal mientras ya se está cerrando: no repetir.
            logger.warning("Señal %s recibida durante el cierre, ignorada", signum)
            return
        self.received_signal = signum
        name = signal.Signals(signum).name
        logger.info("Señal %s recibida: cerrando RoadBook Pi de forma ordenada", name)
        self._on_shutdown()

    def _drain_wakeup_socket(self) -> None:
        # Solo sirve para despertar al loop de Qt; el contenido se descarta.
        try:
            while self._read_sock.recv(64):
                pass
        except (BlockingIOError, OSError):
            pass
