"""Tests básicos de la pantalla de Navegación y del widget de mapa."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtGui import QColor, QImage  # noqa: E402

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


def _shown_screen(qtbot) -> NavigationScreen:
    screen = NavigationScreen(roadbook_engine=_engine())
    qtbot.addWidget(screen)
    screen.resize(800, 480)
    screen.show()
    qtbot.waitExposed(screen)
    return screen


def _pixel(screen: NavigationScreen, widget, fx: float, fy: float) -> QColor:
    """Color real dibujado en un punto relativo de ``widget``."""
    image = screen.grab().toImage()
    local = QPoint(int(widget.width() * fx), int(widget.height() * fy))
    point = widget.mapTo(screen, local)
    ratio = image.width() / screen.width()
    return image.pixelColor(int(point.x() * ratio), int(point.y() * ratio))


def test_waypoint_image_covers_map_and_strip(qtbot, tmp_path) -> None:
    # Regresión v1.1: la imagen del evento quedaba debajo del mapa y la tira.
    red = QImage(400, 300, QImage.Format.Format_RGB32)
    red.fill(QColor(255, 0, 0))
    path = tmp_path / "rojo.png"
    red.save(str(path))
    screen = _shown_screen(qtbot)

    screen.show_image(path, auto_hide=False)

    for widget in (screen.map_widget, screen.roadbook_strip):
        color = _pixel(screen, widget, 0.5, 0.15)
        assert (color.red(), color.green(), color.blue()) == (255, 0, 0), widget


def test_gps_readout_is_drawn_above_map(qtbot) -> None:
    screen = _shown_screen(qtbot)
    map_gray = _pixel(screen, screen.map_widget, 0.1, 0.1)  # zona sin readout

    screen.update_position(GpsPosition(latitude=-31.5, longitude=-64.3, has_fix=True))
    qtbot.wait(20)

    # El fondo semitransparente negro del readout oscurece el mapa debajo.
    under_label = _pixel(screen, screen.status_label, 0.02, 0.5)
    assert under_label.lightness() < map_gray.lightness() - 40


def test_readout_does_not_block_touches_on_strip(qtbot) -> None:
    screen = _shown_screen(qtbot)
    strip_point = screen.roadbook_strip.mapTo(
        screen, screen.roadbook_strip.rect().center()
    )
    target = screen.childAt(strip_point)
    assert target is not None
    assert screen.roadbook_strip.isAncestorOf(target) or target is screen.roadbook_strip
