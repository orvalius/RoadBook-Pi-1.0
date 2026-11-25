"""Tests de MapViewport y del centro adelantado (core.map_compositor)."""

from __future__ import annotations

import pytest

from core.map_compositor import MapViewport, look_ahead_center

VIEW = MapViewport(-31.5, -64.3, 15, 640, 480)


def test_center_maps_to_middle_of_image() -> None:
    assert VIEW.to_pixel(-31.5, -64.3) == pytest.approx((320, 240))


def test_pixel_roundtrip() -> None:
    lat, lon = VIEW.to_latlon(*VIEW.to_pixel(-31.49, -64.31))
    assert (lat, lon) == pytest.approx((-31.49, -64.31), abs=1e-9)


def test_north_is_up_and_east_is_right() -> None:
    x_east, _ = VIEW.to_pixel(-31.5, -64.29)
    _, y_north = VIEW.to_pixel(-31.49, -64.3)
    assert x_east > 320 and y_north < 240


def test_contains_inner_excludes_margin() -> None:
    assert VIEW.contains_inner(-31.5, -64.3)
    near_edge = VIEW.to_latlon(630, 240)
    assert not VIEW.contains_inner(*near_edge, margin=0.2)


@pytest.mark.parametrize(
    ("heading", "axis", "sign"), [(0, 0, 1), (90, 1, 1), (180, 0, -1)]
)
def test_look_ahead_moves_center_forward(heading, axis, sign) -> None:
    center = look_ahead_center(-31.5, -64.3, heading, 15, 640, 480)
    delta = center[axis] - (-31.5, -64.3)[axis]
    assert delta * sign > 0


def test_look_ahead_without_heading_centers_on_vehicle() -> None:
    assert look_ahead_center(-31.5, -64.3, None, 15, 640, 480) == (-31.5, -64.3)
