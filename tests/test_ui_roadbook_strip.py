"""Tests de la tira del Roadbook Rendering Engine (ui.screens.roadbook_strip_widget)."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtCore import QPoint  # noqa: E402

from core.roadbook_engine import build_entries  # noqa: E402
from database.models import Waypoint  # noqa: E402
from ui.screens.roadbook_strip_widget import RoadbookStripWidget  # noqa: E402


def _strip(qtbot) -> RoadbookStripWidget:
    strip = RoadbookStripWidget()
    qtbot.addWidget(strip)
    strip.resize(320, 480)
    strip.set_entries(
        build_entries(
            [
                Waypoint(id=i, nombre=f"WP{i}", latitud=i * 0.01, longitud=0.0)
                for i in range(1, 4)
            ]
        )
    )
    strip.show()
    qtbot.waitExposed(strip)
    return strip


def test_rows_have_dark_background(qtbot) -> None:
    # Regresión v1.1: "background: transparent" del QScrollArea se heredaba
    # a las filas y quedaba texto claro sobre el fondo claro de la ventana.
    strip = _strip(qtbot)
    image = strip.grab().toImage()
    ratio = image.width() / strip.width()
    viewport = strip.scroll_area.viewport()
    for fy in (0.1, 0.5, 0.95):
        point = viewport.mapTo(strip, QPoint(5, int(viewport.height() * fy)))
        color = image.pixelColor(int(point.x() * ratio), int(point.y() * ratio))
        assert color.lightness() < 60, (fy, color.name())


def test_one_row_per_entry(qtbot) -> None:
    assert len(_strip(qtbot)._rows) == 3
