"""Tests de core.graphic_utils."""

from __future__ import annotations

import pytest

from core.graphic_utils import compute_scaled_size


def test_wide_image_limited_by_width() -> None:
    # Imagen 16:9 en un contenedor cuadrado -> el ancho es el límite
    width, height = compute_scaled_size(1600, 900, 800, 800)
    assert width == 800
    assert round(height) == 450


def test_tall_image_limited_by_height() -> None:
    # Imagen 9:16 en un contenedor cuadrado -> el alto es el límite
    width, height = compute_scaled_size(900, 1600, 800, 800)
    assert height == 800
    assert round(width) == 450


def test_preserves_aspect_ratio() -> None:
    width, height = compute_scaled_size(1920, 1080, 640, 480)
    original_ratio = 1920 / 1080
    scaled_ratio = width / height
    assert abs(original_ratio - scaled_ratio) < 0.01


def test_never_exceeds_max_dimensions() -> None:
    width, height = compute_scaled_size(3000, 2000, 500, 500)
    assert width <= 500
    assert height <= 500


def test_same_aspect_ratio_fills_exactly() -> None:
    width, height = compute_scaled_size(800, 600, 400, 300)
    assert round(width) == 400
    assert round(height) == 300


def test_invalid_original_dimensions_raise() -> None:
    with pytest.raises(ValueError):
        compute_scaled_size(0, 600, 400, 300)
    with pytest.raises(ValueError):
        compute_scaled_size(800, -1, 400, 300)


def test_zero_target_area_returns_zero() -> None:
    assert compute_scaled_size(800, 600, 0, 300) == (0.0, 0.0)
