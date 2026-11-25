"""Tests de core.turns: lado y ángulo de cada giro de la ruta."""

from __future__ import annotations

import pytest

from core.roadbook_engine import build_entries
from core.turns import (
    Turn,
    bearing_deg,
    compute_turns,
    signed_turn_deg,
)
from database.models import Waypoint

# ~1,1 km por cada 0.01° cerca del ecuador: geometría fácil de razonar.
N, E, S, W = (0.01, 0.0), (0.0, 0.01), (-0.01, 0.0), (0.0, -0.01)


def _p(*steps: tuple[float, float]) -> list[tuple[float, float]]:
    """Camino que arranca en (0,0) y suma cada paso."""
    lat = lon = 0.0
    points = [(lat, lon)]
    for dlat, dlon in steps:
        lat, lon = lat + dlat, lon + dlon
        points.append((lat, lon))
    return points


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ((0, 0), (1, 0), 0),
        ((0, 0), (0, 1), 90),
        ((0, 0), (-1, 0), 180),
        ((0, 0), (0, -1), 270),
    ],
)
def test_bearing_cardinal(a, b, expected) -> None:
    assert bearing_deg(a, b) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    ("b_in", "b_out", "expected"),
    [
        (0, 90, 90),
        (0, 270, -90),
        (350, 10, 20),
        (10, 350, -20),
        (0, 180, 180),
        (90, 90, 0),
    ],
)
def test_signed_turn_wraps_around_north(b_in, b_out, expected) -> None:
    assert signed_turn_deg(b_in, b_out) == pytest.approx(expected)


def test_right_and_left_turns() -> None:
    # Norte, luego este (derecha 90°), luego norte de nuevo (izquierda 90°).
    turns = compute_turns(_p(N, E, N))
    assert turns[0] is None and turns[-1] is None
    assert (turns[1].lado, turns[1].grados) == ("derecha", 90)
    assert (turns[2].lado, turns[2].grados) == ("izquierda", 90)
    assert turns[1].texto == "Derecha 90°"
    assert turns[1].rumbo_salida == pytest.approx(90, abs=0.1)


def test_straight_and_hairpin() -> None:
    turns = compute_turns(_p(N, N, S))
    assert turns[1].lado == "recto" and turns[1].texto == "Recto"
    assert turns[1].severidad == ""
    assert turns[2].grados == 180 and turns[2].severidad == "horquilla"


@pytest.mark.parametrize(
    ("angulo", "grados", "severidad"),
    [
        (30, 30, "suave"),
        (46, 45, "suave"),
        (60, 60, "media"),
        (110, 110, "cerrada"),
        (-150, 150, "horquilla"),
    ],
)
def test_severity_uses_displayed_degrees(angulo, grados, severidad) -> None:
    turn = Turn(angulo=angulo, rumbo_salida=0)
    assert turn.grados == grados
    assert turn.severidad == severidad


def test_overlapping_waypoints_use_next_distinct_point() -> None:
    # Dos notas en el mismo lugar (largada de dos pruebas): el giro se mide
    # contra el siguiente punto realmente distinto, no da cualquier cosa.
    points = _p(N, (0, 0), E)
    turns = compute_turns(points)
    assert turns[1].lado == "derecha" and turns[1].grados == 90
    assert turns[2].lado == "derecha" and turns[2].grados == 90


def test_track_gives_the_real_curve_not_the_straight_line() -> None:
    # Las notas están en línea recta (sur -> norte), pero el camino real
    # hace una S con una curva a la derecha justo en la nota del medio.
    waypoints = [(0.0, 0.0), (0.02, 0.0), (0.04, 0.0)]
    track = [
        (0.0, 0.0),
        (0.01, 0.0),
        (0.02, 0.0),
        (0.02, 0.01),
        (0.03, 0.01),
        (0.04, 0.0),
    ]
    assert compute_turns(waypoints)[1].lado == "recto"
    with_track = compute_turns(waypoints, track)[1]
    assert (with_track.lado, with_track.grados) == ("derecha", 90)


def test_build_entries_attaches_turns() -> None:
    wps = [
        Waypoint(id=i + 1, nombre=f"WP{i}", latitud=lat, longitud=lon)
        for i, (lat, lon) in enumerate(_p(N, E, N))
    ]
    entries = build_entries(wps)
    assert entries[0].giro is None
    assert entries[1].giro.texto == "Derecha 90°"
    assert entries[2].giro.texto == "Izquierda 90°"
    assert entries[3].giro is None
