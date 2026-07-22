"""Tests de core.route (Roadbook Rendering Engine)."""

from __future__ import annotations

from pathlib import Path

from core.route import (
    order_waypoints_by_track,
    order_waypoints_fallback,
    parse_gpx,
    resolve_route_order,
)
from database.models import Waypoint

GPX_SAMPLE = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="-31.60" lon="-64.30"></trkpt>
    <trkpt lat="-31.50" lon="-64.35"></trkpt>
    <trkpt lat="-31.40" lon="-64.40"></trkpt>
  </trkseg></trk>
</gpx>"""


def test_parse_gpx_reads_track_points(tmp_path: Path) -> None:
    gpx_path = tmp_path / "track.gpx"
    gpx_path.write_text(GPX_SAMPLE, encoding="utf-8")

    track = parse_gpx(gpx_path)

    assert track == [(-31.60, -64.30), (-31.50, -64.35), (-31.40, -64.40)]


def test_parse_gpx_missing_file_returns_empty(tmp_path: Path) -> None:
    assert parse_gpx(tmp_path / "no_existe.gpx") == []


def test_parse_gpx_invalid_xml_returns_empty(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.gpx"
    bad_path.write_text("esto no es xml <<<", encoding="utf-8")
    assert parse_gpx(bad_path) == []


def test_order_waypoints_by_track() -> None:
    track = [(-31.60, -64.30), (-31.50, -64.35), (-31.40, -64.40)]
    wp_a = Waypoint(id=1, nombre="A", latitud=-31.41, longitud=-64.39)  # cerca del índice 2
    wp_b = Waypoint(id=2, nombre="B", latitud=-31.59, longitud=-64.31)  # cerca del índice 0
    wp_c = Waypoint(id=3, nombre="C", latitud=-31.49, longitud=-64.34)  # cerca del índice 1

    ordered = order_waypoints_by_track([wp_a, wp_b, wp_c], track)

    assert [w.nombre for w in ordered] == ["B", "C", "A"]


def test_order_waypoints_by_track_empty_track_returns_input_unchanged() -> None:
    wp_a = Waypoint(id=1, nombre="A", latitud=0, longitud=0)
    wp_b = Waypoint(id=2, nombre="B", latitud=1, longitud=1)
    assert order_waypoints_by_track([wp_a, wp_b], []) == [wp_a, wp_b]


def test_order_waypoints_fallback_uses_orden_ruta_then_id() -> None:
    wp1 = Waypoint(id=5, nombre="Primero", latitud=0, longitud=0, orden_ruta=2)
    wp2 = Waypoint(id=3, nombre="Segundo", latitud=0, longitud=0, orden_ruta=1)
    wp3 = Waypoint(id=1, nombre="SinOrden", latitud=0, longitud=0)  # orden_ruta None -> al final

    ordered = order_waypoints_fallback([wp1, wp2, wp3])

    assert [w.nombre for w in ordered] == ["Segundo", "Primero", "SinOrden"]


def test_resolve_route_order_without_gpx_uses_fallback() -> None:
    wp1 = Waypoint(id=5, nombre="Primero", latitud=0, longitud=0, orden_ruta=2)
    wp2 = Waypoint(id=3, nombre="Segundo", latitud=0, longitud=0, orden_ruta=1)

    resolved = resolve_route_order([wp1, wp2], None)

    assert [w.nombre for w in resolved] == ["Segundo", "Primero"]


def test_resolve_route_order_falls_back_when_gpx_invalid() -> None:
    wp1 = Waypoint(id=5, nombre="Primero", latitud=0, longitud=0, orden_ruta=2)
    wp2 = Waypoint(id=3, nombre="Segundo", latitud=0, longitud=0, orden_ruta=1)

    resolved = resolve_route_order([wp1, wp2], "/no/existe.gpx")

    assert [w.nombre for w in resolved] == ["Segundo", "Primero"]


def test_resolve_route_order_uses_gpx_when_valid(tmp_path: Path) -> None:
    gpx_path = tmp_path / "track.gpx"
    gpx_path.write_text(GPX_SAMPLE, encoding="utf-8")

    wp_a = Waypoint(id=1, nombre="A", latitud=-31.41, longitud=-64.39)
    wp_b = Waypoint(id=2, nombre="B", latitud=-31.59, longitud=-64.31)

    resolved = resolve_route_order([wp_a, wp_b], gpx_path)

    assert [w.nombre for w in resolved] == ["B", "A"]
