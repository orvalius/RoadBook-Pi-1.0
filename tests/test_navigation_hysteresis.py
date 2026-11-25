"""Tests de histéresis en NavigationEngine."""

from __future__ import annotations

from core.gps_manager import GpsPosition
from core.navigation_engine import NavigationEngine
from database.models import Waypoint

# Waypoint fijo en (0, 0), radio 100m
WP = Waypoint(id=1, nombre="Test", latitud=0.0, longitud=0.0, radio=100.0)

INSIDE_POSITION = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
OUTSIDE_POSITION = GpsPosition(latitude=1.0, longitude=1.0, has_fix=True)  # ~157km


def test_fires_once_on_entry() -> None:
    engine = NavigationEngine()
    fired: list[Waypoint] = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([WP])

    engine.update_position(INSIDE_POSITION)
    engine.update_position(INSIDE_POSITION)  # sigue dentro, no debe volver a disparar
    engine.update_position(INSIDE_POSITION)

    assert len(fired) == 1


def test_refires_on_reentry_when_re_triggerable() -> None:
    engine = NavigationEngine()
    fired: list[Waypoint] = []
    engine.on_waypoint_reached = fired.append
    wp = Waypoint(
        id=1, nombre="Test", latitud=0.0, longitud=0.0, radio=100.0, re_triggerable=True
    )
    engine.load_waypoints([wp])

    engine.update_position(INSIDE_POSITION)
    engine.update_position(OUTSIDE_POSITION)
    engine.update_position(INSIDE_POSITION)

    assert len(fired) == 2


def test_does_not_refire_when_not_re_triggerable() -> None:
    engine = NavigationEngine()
    fired: list[Waypoint] = []
    engine.on_waypoint_reached = fired.append
    wp = Waypoint(
        id=1,
        nombre="Test",
        latitud=0.0,
        longitud=0.0,
        radio=100.0,
        re_triggerable=False,
    )
    engine.load_waypoints([wp])

    engine.update_position(INSIDE_POSITION)
    engine.update_position(OUTSIDE_POSITION)
    engine.update_position(INSIDE_POSITION)

    assert len(fired) == 1


def test_ignores_position_without_fix() -> None:
    engine = NavigationEngine()
    fired: list[Waypoint] = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([WP])

    no_fix = GpsPosition(latitude=0.0, longitude=0.0, has_fix=False)
    engine.update_position(no_fix)

    assert len(fired) == 0


def test_inactive_waypoint_is_not_monitored() -> None:
    engine = NavigationEngine()
    fired: list[Waypoint] = []
    engine.on_waypoint_reached = fired.append
    inactive_wp = Waypoint(
        id=1, nombre="Inactivo", latitud=0.0, longitud=0.0, radio=100.0, activo=False
    )
    engine.load_waypoints([inactive_wp])

    engine.update_position(INSIDE_POSITION)

    assert len(fired) == 0
