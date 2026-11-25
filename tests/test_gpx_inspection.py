"""Tests de parseo de rutas GPX (rtept) e inspección de GPX."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.route import InvalidGpxError, inspect_gpx, parse_gpx, track_length_m
from tests.conftest import GPX_ROUTE_ONLY, GPX_TRACK


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_gpx_falls_back_to_route_points(tmp_path: Path) -> None:
    points = parse_gpx(_write(tmp_path / "r.gpx", GPX_ROUTE_ONLY))
    assert points == [(-31.40, -64.40), (-31.60, -64.30)]


def test_parse_gpx_prefers_track_over_route(tmp_path: Path) -> None:
    both = GPX_TRACK.replace("</gpx>", '<rte><rtept lat="0" lon="0"/></rte></gpx>')
    points = parse_gpx(_write(tmp_path / "b.gpx", both))
    assert len(points) == 3
    assert (0.0, 0.0) not in points


def test_track_length() -> None:
    # 0.1° de latitud ~ 11.1 km
    assert track_length_m([(0.0, 0.0), (0.1, 0.0)]) == pytest.approx(11_120, rel=0.01)
    assert track_length_m([(0.0, 0.0)]) == 0
    assert track_length_m([]) == 0


def test_inspect_gpx(tmp_path: Path) -> None:
    info = inspect_gpx(_write(tmp_path / "t.gpx", GPX_TRACK))
    assert info.point_count == 3
    assert 20_000 < info.length_m < 25_000


def test_inspect_gpx_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(InvalidGpxError, match="No existe"):
        inspect_gpx(tmp_path / "nada.gpx")


def test_inspect_gpx_rejects_invalid_xml(tmp_path: Path) -> None:
    with pytest.raises(InvalidGpxError):
        inspect_gpx(_write(tmp_path / "x.gpx", "esto <no es xml"))


def test_inspect_gpx_rejects_without_points(tmp_path: Path) -> None:
    empty = (
        '<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="1" lon="1"/></gpx>'
    )
    with pytest.raises(InvalidGpxError, match="no tiene puntos"):
        inspect_gpx(_write(tmp_path / "w.gpx", empty))
