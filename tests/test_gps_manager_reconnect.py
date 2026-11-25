"""Tests de reconexión automática de GpsManager (Sprint 11)."""

from __future__ import annotations

import socket
import time

from core.gps_manager import GpsManager


def _unused_port() -> int:
    """Encuentra un puerto TCP local que casi seguro no tiene nada escuchando."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_gpsd_connection_failure_does_not_kill_thread() -> None:
    """Si gpsd no está disponible, el hilo debe seguir vivo reintentando,
    no morir silenciosamente tras el primer fallo."""
    port = _unused_port()
    manager = GpsManager(
        backend="gpsd",
        gpsd_host="127.0.0.1",
        gpsd_port=port,
        reconnect_interval_seconds=0.05,
    )

    manager.start()
    time.sleep(0.3)  # tiempo suficiente para varios intentos fallidos + reintentos

    assert manager.is_running is True, "el hilo no debía morir tras la conexión fallida"

    manager.stop()
    assert manager.is_running is False


def test_gpsd_stop_during_backoff_wait_is_responsive() -> None:
    """stop() debe interrumpir rápido aunque el hilo esté esperando el
    intervalo de reintento, no esperar el backoff completo."""
    port = _unused_port()
    manager = GpsManager(
        backend="gpsd",
        gpsd_host="127.0.0.1",
        gpsd_port=port,
        reconnect_interval_seconds=10.0,  # backoff largo a propósito
    )

    manager.start()
    time.sleep(0.2)  # dejar que falle la primera conexión y entre en backoff

    start = time.monotonic()
    manager.stop()
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, f"stop() tardó {elapsed:.1f}s, debía ser casi inmediato"
