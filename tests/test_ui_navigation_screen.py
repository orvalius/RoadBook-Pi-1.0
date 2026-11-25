"""Tests básicos de la pantalla de Navegación y del widget de mapa."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from core.gps_manager import GpsPosition  # noqa: E402
from core.map_manager import MapManager  # noqa: E402
from core.roadbook_engine import RoadbookEngine, build_entries  # noqa: E402
from database.models import Waypoint  # noqa: E402
from ui.screens.map_widget import MapWidget  # noqa: E402
from ui.screens.navigation import NavigationScreen  # noqa: E402


def _engine() -> RoadbookEngine:
    wps = [
        Waypoint(id=1, nombre="Largada", latitud=0.0, longitud=0.0, radio=50),
        Waypoint(id=2, nombre="Cruce", latitud=0.01, longitud=0.0, radio=50),
    ]
    return RoadbookEngine(build_entries(wps))


def test_no_fix_message(qtbot) -> None:
    screen = NavigationScreen()
    qtbot.addWidget(screen)
    screen.update_position(GpsPosition(latitude=0, longitude=0, has_fix=False))
    assert screen.status_label.text() == "Sin fix GPS"


def test_fix_updates_readout_and_strip(qtbot) -> None:
    screen = NavigationScreen(roadbook_engine=_engine())
    qtbot.addWidget(screen)
    assert len(screen.roadbook_strip._rows) == 2

    screen.update_position(
        GpsPosition(latitude=0.0, longitude=0.0, speed=42, heading=90, has_fix=True)
    )

    assert screen.status_label.text() == "0.000000, 0.000000"
    assert "42 km/h" in screen.detail_label.text()
    assert "90°" in screen.detail_label.text()


def test_lost_fix_shows_elapsed_time(qtbot) -> None:
    screen = NavigationScreen()
    qtbot.addWidget(screen)
    screen.update_position(GpsPosition(latitude=0, longitude=0, has_fix=True))
    screen.update_position(GpsPosition(latitude=0, longitude=0, has_fix=False))
    assert screen.status_label.text().startswith("Sin fix GPS (última posición hace")


def test_map_widget_placeholder_without_map(qtbot) -> None:
    widget = MapWidget(MapManager(None))
    qtbot.addWidget(widget)
    assert widget.text() == "Sin mapa offline cargado"
    widget.reload_source()
    assert widget.text() == "Sin mapa offline cargado"
