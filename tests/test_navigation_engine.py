"""Tests de NavigationEngine."""

from __future__ import annotations

from core.navigation_engine import NavigationEngine


def test_haversine_distance_same_point_is_zero() -> None:
    distance = NavigationEngine.haversine_distance(
        -34.6037, -58.3816, -34.6037, -58.3816
    )
    assert distance == 0.0


def test_haversine_distance_known_points() -> None:
    # Buenos Aires -> Córdoba, aprox. 650 km
    distance = NavigationEngine.haversine_distance(
        -34.6037, -58.3816, -31.4201, -64.1888
    )
    assert 600_000 < distance < 700_000
