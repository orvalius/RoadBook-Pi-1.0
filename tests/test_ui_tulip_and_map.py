"""Tests de la tulipa, la tarjeta de próxima curva y el vehículo en el mapa."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from PyQt6.QtGui import QColor  # noqa: E402

from core.gps_manager import GpsPosition  # noqa: E402
from core.map_manager import MapManager  # noqa: E402
from core.roadbook_engine import RoadbookEngine, build_entries  # noqa: E402
from core.turns import Turn  # noqa: E402
from database.models import Waypoint  # noqa: E402
from tests.conftest import make_mbtiles  # noqa: E402
from ui.screens.map_widget import MapWidget  # noqa: E402
from ui.screens.navigation import NavigationScreen  # noqa: E402
from ui.screens.roadbook_strip_widget import (  # noqa: E402
    RoadbookStripWidget,
    _format_distance,
    turn_caption,
)
from ui.screens.tulip_widget import HOT, TulipWidget  # noqa: E402


def _accent_side(qtbot, angle: float) -> str:
    tulip = TulipWidget(80)
    qtbot.addWidget(tulip)
    tulip.set_turn(Turn(angulo=angle, rumbo_salida=0))
    tulip.set_tone("current")
    image = tulip.grab().toImage()
    ratio = image.width() / 80
    left = right = 0
    mid = image.width() / 2
    band = 9 * ratio  # el eje y la punta de la flecha recta quedan dentro
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            is_hot = (
                abs(c.red() - HOT.red()) < 30
                and abs(c.green() - HOT.green()) < 40
                and c.blue() < 80
            )
            if is_hot and x < mid - band:
                left += 1
            elif is_hot and x > mid + band:
                right += 1
    if right > max(left * 2, 10):
        return "derecha"
    if left > max(right * 2, 10):
        return "izquierda"
    return "centro"


@pytest.mark.parametrize(
    ("angle", "side"),
    [(90, "derecha"), (-90, "izquierda"), (155, "derecha"), (0, "centro")],
)
def test_tulip_arrow_points_to_the_turn_side(qtbot, angle, side) -> None:
    assert _accent_side(qtbot, angle) == side


@pytest.mark.parametrize(
    ("meters", "text"),
    [(345, "350 m"), (999, "1000 m"), (1240, "1,2 km"), (12_400, "12,4 km")],
)
def test_distance_format(meters, text) -> None:
    assert _format_distance(meters) == text


def _entries():
    wps = [
        Waypoint(id=1, nombre="Largada", latitud=0.0, longitud=0.0, icono="largada"),
        Waypoint(id=2, nombre="Cruce", latitud=0.01, longitud=0.0),
        Waypoint(id=3, nombre="Puente", latitud=0.01, longitud=0.01),
        Waypoint(id=4, nombre="Fin", latitud=0.02, longitud=0.01, icono="llegada"),
    ]
    return build_entries(wps)


def test_turn_captions() -> None:
    entries = _entries()
    assert turn_caption(entries[0]).endswith("Largada")
    assert turn_caption(entries[1]) == "Derecha 90° · media"
    assert turn_caption(entries[2]) == "Izquierda 90° · media"
    assert turn_caption(entries[3]).endswith("Llegada")


def test_next_turn_card_follows_the_route(qtbot) -> None:
    strip = RoadbookStripWidget()
    qtbot.addWidget(strip)
    engine = RoadbookEngine(_entries())
    strip.set_entries(engine.entries)
    strip.update_state(engine.update_position(GpsPosition(0, 0, has_fix=True)))
    card = strip.next_card
    assert card.turn_label.text() == "Derecha 90°"
    assert "media" in card.distance_label.text() and "km" in card.distance_label.text()
    assert card.name_label.text() == "Cruce"


def test_strip_survives_empty_then_entries_then_empty(qtbot) -> None:
    # Antes, vaciar la ruta destruía el cartel de "sin ruta" y fallaba al reusarlo.
    strip = RoadbookStripWidget()
    qtbot.addWidget(strip)
    strip.set_entries([])
    strip.set_entries(_entries())
    strip.set_entries([])
    strip.set_entries([])
    assert strip.empty_label.text() == "Sin ruta de roadbook activa"
    assert strip.next_card.isHidden()


def _map(qtbot, mbtiles: Path | None) -> MapWidget:
    widget = MapWidget(MapManager(mbtiles) if mbtiles else None, zoom=12)
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def _color_at(widget: MapWidget, lat: float, lon: float) -> QColor:
    x, y = widget.viewport.to_pixel(lat, lon)
    image = widget.pixmap().toImage()
    ratio = image.width() / widget.viewport.width
    return image.pixelColor(int(x * ratio), int(y * ratio))


def test_vehicle_is_drawn_where_the_gps_says(qtbot, tmp_path) -> None:
    widget = _map(qtbot, make_mbtiles(tmp_path / "m.mbtiles", zooms=(12,)))
    widget.update_vehicle(-31.42, -64.18, heading=0)
    color = _color_at(widget, -31.42, -64.18)
    assert color.blue() > 200 and color.red() < 100  # flecha azul del vehículo


def test_route_and_next_note_are_drawn_without_map(qtbot) -> None:
    widget = _map(qtbot, None)
    assert widget.text() == "Sin mapa offline cargado"  # sin posición todavía
    widget.set_route([(-31.40, -64.20), (-31.44, -64.20)], current_index=1)
    widget.update_vehicle(-31.42, -64.25, heading=None)
    assert not widget.pixmap().isNull()
    line = _color_at(widget, -31.42, -64.20)
    assert line.red() > 200 and line.blue() < 80  # ruta naranja
    x, y = widget.viewport.to_pixel(-31.44, -64.20)
    image = widget.pixmap().toImage()
    ratio = image.width() / widget.viewport.width
    ring = image.pixelColor(int((x + 6) * ratio), int(y * ratio))  # al lado del número
    assert ring.red() > 200 and ring.green() > 100 and ring.blue() < 80


def test_base_is_recomposed_only_near_the_edge(qtbot, tmp_path) -> None:
    widget = _map(qtbot, make_mbtiles(tmp_path / "m.mbtiles", zooms=(12,)))
    widget.update_vehicle(-31.42, -64.18, heading=None)
    first = widget.viewport
    widget.update_vehicle(-31.421, -64.181, heading=None)  # ~150 m
    assert widget.viewport is first
    far = first.to_latlon(first.width - 5, first.height / 2)
    widget.update_vehicle(*far, heading=90)
    assert widget.viewport is not first


def test_navigation_screen_moves_vehicle_and_highlights_next(qtbot) -> None:
    engine = RoadbookEngine(_entries())
    screen = NavigationScreen(roadbook_engine=engine)
    qtbot.addWidget(screen)
    screen.resize(800, 480)
    screen.show()
    qtbot.waitExposed(screen)
    screen.update_position(GpsPosition(0.0, 0.0, speed=50, heading=0, has_fix=True))
    screen.update_position(GpsPosition(0.005, 0.0, speed=50, heading=0, has_fix=True))
    assert screen.map_widget._current_index == 1  # pasó la largada: va al cruce
    assert screen.map_widget._last_lat == pytest.approx(0.005)
