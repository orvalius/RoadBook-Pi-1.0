"""Tests del pre-filtro de optimización de NavigationEngine (Sprint 10)."""

from __future__ import annotations

from core.gps_manager import GpsPosition
from core.navigation_engine import NavigationEngine
from database.models import Waypoint


def test_definitely_outside_true_when_far_in_latitude() -> None:
    position = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
    wp = Waypoint(id=1, nombre="Lejos", latitud=5.0, longitud=0.0, radio=100.0)
    assert NavigationEngine._definitely_outside(position, wp) is True


def test_definitely_outside_false_when_close_in_latitude() -> None:
    position = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
    wp = Waypoint(id=1, nombre="Cerca", latitud=0.0001, longitud=0.0, radio=100.0)
    assert NavigationEngine._definitely_outside(position, wp) is False


def test_quick_reject_never_produces_false_negative() -> None:
    """El pre-filtro nunca debe descartar un waypoint que en verdad está
    dentro del radio (nunca falso positivo en "definitivamente afuera")."""
    position = GpsPosition(latitude=-34.6037, longitude=-58.3816, has_fix=True)
    wp = Waypoint(id=1, nombre="Test", latitud=-34.6037, longitud=-58.3816, radio=50.0)

    # Mismo punto exacto: jamás puede considerarse "definitivamente afuera"
    assert NavigationEngine._definitely_outside(position, wp) is False


def test_haversine_not_called_for_far_waypoints() -> None:
    """Verifica que el pre-filtro efectivamente evita la llamada al
    haversine (la parte cara) para waypoints obviamente lejanos."""
    engine = NavigationEngine()
    far_wp = Waypoint(id=1, nombre="Lejos", latitud=10.0, longitud=10.0, radio=100.0)
    engine.load_waypoints([far_wp])

    calls = []
    original = NavigationEngine.haversine_distance

    def counting_haversine(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    NavigationEngine.haversine_distance = staticmethod(counting_haversine)
    try:
        position = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
        engine.update_position(position)
    finally:
        NavigationEngine.haversine_distance = staticmethod(original)

    assert calls == [], "no debía llamarse al haversine para un waypoint tan lejano"


def test_haversine_called_for_nearby_waypoints_and_still_fires() -> None:
    """Un waypoint cercano SÍ debe pasar el pre-filtro y disparar
    normalmente (la optimización no debe romper la funcionalidad)."""
    engine = NavigationEngine()
    fired = []
    engine.on_waypoint_reached = fired.append

    near_wp = Waypoint(id=1, nombre="Cerca", latitud=0.0, longitud=0.0, radio=100.0)
    engine.load_waypoints([near_wp])

    position = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
    engine.update_position(position)

    assert len(fired) == 1


def test_state_resets_to_outside_even_when_quick_rejected() -> None:
    """Si el vehículo estaba INSIDE y luego se aleja mucho (quick-reject
    lo descarta), el estado igual debe resetear a OUTSIDE para permitir
    una futura re-entrada."""
    engine = NavigationEngine()
    fired = []
    engine.on_waypoint_reached = fired.append

    wp = Waypoint(id=1, nombre="Test", latitud=0.0, longitud=0.0, radio=100.0, re_triggerable=True)
    engine.load_waypoints([wp])

    inside = GpsPosition(latitude=0.0, longitude=0.0, has_fix=True)
    far_away = GpsPosition(latitude=20.0, longitude=20.0, has_fix=True)  # quick-rejected

    engine.update_position(inside)
    assert len(fired) == 1

    engine.update_position(far_away)  # debe resetear el estado a OUTSIDE
    engine.update_position(inside)  # re-entrada: debe volver a disparar

    assert len(fired) == 2
