"""Tests de condiciones opcionales y utilidades de NavigationEngine."""

from __future__ import annotations

from core.gps_manager import GpsPosition
from core.navigation_engine import NavigationEngine
from database.models import Waypoint

INSIDE = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
OUTSIDE = GpsPosition(latitude=1.0, longitude=1.0, has_fix=True)


def test_angular_difference_simple() -> None:
    assert NavigationEngine.angular_difference(10, 20) == 10


def test_angular_difference_wraparound() -> None:
    assert NavigationEngine.angular_difference(350, 10) == 20


def test_angular_difference_opposite() -> None:
    assert NavigationEngine.angular_difference(0, 180) == 180


def test_velocidad_condition_blocks_when_too_slow() -> None:
    wp = Waypoint(
        id=1, nombre="Rapido", latitud=0.0, longitud=0.0, radio=100.0, velocidad=60.0
    )
    engine = NavigationEngine()
    fired = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([wp])

    slow_position = GpsPosition(latitude=0.0, longitude=0.0, speed=20.0, has_fix=True)
    engine.update_position(slow_position)

    assert fired == []


def test_velocidad_condition_allows_when_fast_enough() -> None:
    wp = Waypoint(
        id=1, nombre="Rapido", latitud=0.0, longitud=0.0, radio=100.0, velocidad=60.0
    )
    engine = NavigationEngine()
    fired = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([wp])

    fast_position = GpsPosition(latitude=0.0, longitude=0.0, speed=80.0, has_fix=True)
    engine.update_position(fast_position)

    assert len(fired) == 1


def test_angulo_condition_blocks_when_wrong_heading() -> None:
    wp = Waypoint(
        id=1, nombre="Direccional", latitud=0.0, longitud=0.0, radio=100.0, angulo=0.0
    )
    engine = NavigationEngine(heading_tolerance_degrees=30.0)
    fired = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([wp])

    wrong_heading = GpsPosition(
        latitude=0.0, longitude=0.0, heading=180.0, has_fix=True
    )
    engine.update_position(wrong_heading)

    assert fired == []


def test_angulo_condition_allows_within_tolerance() -> None:
    wp = Waypoint(
        id=1, nombre="Direccional", latitud=0.0, longitud=0.0, radio=100.0, angulo=0.0
    )
    engine = NavigationEngine(heading_tolerance_degrees=30.0)
    fired = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([wp])

    close_heading = GpsPosition(latitude=0.0, longitude=0.0, heading=20.0, has_fix=True)
    engine.update_position(close_heading)

    assert len(fired) == 1


def test_angulo_condition_blocks_when_no_heading_available() -> None:
    wp = Waypoint(
        id=1, nombre="Direccional", latitud=0.0, longitud=0.0, radio=100.0, angulo=0.0
    )
    engine = NavigationEngine()
    fired = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([wp])

    no_heading = GpsPosition(latitude=0.0, longitude=0.0, heading=None, has_fix=True)
    engine.update_position(no_heading)

    assert fired == []


def test_no_conditions_always_fires() -> None:
    wp = Waypoint(id=1, nombre="Libre", latitud=0.0, longitud=0.0, radio=100.0)
    engine = NavigationEngine()
    fired = []
    engine.on_waypoint_reached = fired.append
    engine.load_waypoints([wp])

    engine.update_position(INSIDE)

    assert len(fired) == 1


def test_get_nearest_waypoint_returns_closest() -> None:
    near = Waypoint(id=1, nombre="Cerca", latitud=0.0, longitud=0.0, radio=50.0)
    far = Waypoint(id=2, nombre="Lejos", latitud=5.0, longitud=5.0, radio=50.0)
    engine = NavigationEngine()
    engine.load_waypoints([near, far])

    result = engine.get_nearest_waypoint(INSIDE)

    assert result is not None
    waypoint, distance = result
    assert waypoint.nombre == "Cerca"


def test_get_nearest_waypoint_empty_returns_none() -> None:
    engine = NavigationEngine()
    result = engine.get_nearest_waypoint(INSIDE)
    assert result is None
