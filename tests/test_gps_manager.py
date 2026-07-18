"""Tests de GpsManager (backend simulador, sin hardware real)."""

from __future__ import annotations

import time

from core.gps_manager import GpsManager, GpsPosition


def test_simulator_delivers_positions_via_callback() -> None:
    received: list[GpsPosition] = []
    manager = GpsManager(backend="simulator", simulator_interval=0.05)
    manager.register_callback(received.append)

    manager.start()
    time.sleep(0.2)
    manager.stop()

    assert len(received) >= 2
    assert all(p.has_fix for p in received)


def test_get_position_returns_last_known() -> None:
    manager = GpsManager(backend="simulator", simulator_interval=0.05)
    manager.start()
    time.sleep(0.1)
    manager.stop()

    position = manager.get_position()
    assert position is not None
    assert isinstance(position, GpsPosition)


def test_stop_actually_stops_thread() -> None:
    manager = GpsManager(backend="simulator", simulator_interval=0.05)
    manager.start()
    assert manager.is_running is True
    manager.stop()
    assert manager.is_running is False


def test_custom_simulator_track_is_used() -> None:
    track = [GpsPosition(latitude=1.0, longitude=2.0, has_fix=True)]
    received: list[GpsPosition] = []
    manager = GpsManager(
        backend="simulator", simulator_track=track, simulator_interval=0.05
    )
    manager.register_callback(received.append)

    manager.start()
    time.sleep(0.15)
    manager.stop()

    assert all(p.latitude == 1.0 and p.longitude == 2.0 for p in received)
