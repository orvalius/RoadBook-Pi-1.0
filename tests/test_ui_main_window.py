"""Tests de integración de MainWindow con la pantalla "Mapas y ruta".

Usa dependencias reales (SQLite, ResourceManager, MapManager) en un
directorio temporal: verifica que elegir un mapa o un GPX desde la UI
reconfigura de verdad el MapManager y la tira del roadbook, y que el
cambio queda persistido en la config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from core.audio_manager import AudioManager  # noqa: E402
from core.config_manager import ConfigManager  # noqa: E402
from core.map_manager import MapManager, inspect_mbtiles  # noqa: E402
from core.navigation_engine import NavigationEngine  # noqa: E402
from core.plugin_manager import PluginManager  # noqa: E402
from core.resource_manager import ResourceManager  # noqa: E402
from core.roadbook_engine import RoadbookEngine, build_entries  # noqa: E402
from core.route import order_waypoints_fallback  # noqa: E402
from database.action_repository import ActionRepository  # noqa: E402
from database.db_manager import DatabaseManager  # noqa: E402
from database.models import Waypoint  # noqa: E402
from database.waypoint_repository import WaypointRepository  # noqa: E402
from tests.conftest import GPX_TRACK, make_mbtiles  # noqa: E402
from ui.main_window import SCREEN_NAMES, MainWindow  # noqa: E402


@pytest.fixture
def env(qtbot, tmp_path: Path):
    db = DatabaseManager(tmp_path / "test.db")
    db.initialize_schema()
    waypoints = WaypointRepository(db)
    # Cargados en orden inverso al del track GPX de prueba (que va de sur a norte).
    for nombre, lat, lon in [
        ("Norte", -31.40, -64.40),
        ("Centro", -31.50, -64.35),
        ("Sur", -31.60, -64.30),
    ]:
        waypoints.create(Waypoint(nombre=nombre, latitud=lat, longitud=lon))

    resources = ResourceManager(tmp_path / "resources")
    config = ConfigManager(tmp_path / "config.json")
    config.set("maps.mbtiles_path", None)
    config.set("maps.default_zoom", 15)
    map_manager = MapManager(None)
    navigation = NavigationEngine()
    active = waypoints.list_all(only_active=True)
    navigation.load_waypoints(active)

    window = MainWindow(
        config,
        waypoints,
        navigation,
        resources,
        AudioManager(enabled=False),
        ActionRepository(db),
        PluginManager(),
        map_manager=map_manager,
        roadbook_engine=RoadbookEngine(build_entries(order_waypoints_fallback(active))),
    )
    qtbot.addWidget(window)
    yield window, config, map_manager, tmp_path
    map_manager.close()
    db.close()


def _roadbook_names(window: MainWindow) -> list[str]:
    return [e.waypoint.nombre for e in window.roadbook_engine.entries]


def test_maps_route_screen_is_in_menu(env) -> None:
    window, *_ = env
    assert "Mapas y ruta" in SCREEN_NAMES
    index = SCREEN_NAMES.index("Mapas y ruta")
    assert window.stack.widget(index) is window.maps_route_screen


def test_apply_map_opens_file_persists_and_clamps_zoom(env) -> None:
    window, config, map_manager, tmp = env
    make_mbtiles(tmp / "resources" / "maps" / "cba.mbtiles", zooms=(10, 11, 12))
    info = inspect_mbtiles(tmp / "resources" / "maps" / "cba.mbtiles")

    window._apply_map("resources/maps/cba.mbtiles", info)

    assert map_manager.is_available
    assert window.navigation_screen.map_widget.zoom == 12  # 15 fuera de rango
    saved = ConfigManager(config.config_path)
    assert saved.get("maps.mbtiles_path") == "resources/maps/cba.mbtiles"
    assert saved.get("maps.default_zoom") == 12


def test_map_draws_after_switch(env) -> None:
    window, _, _, tmp = env
    make_mbtiles(tmp / "resources" / "maps" / "cba.mbtiles", zooms=(12,))
    widget = window.navigation_screen.map_widget
    window._apply_map(
        "resources/maps/cba.mbtiles",
        inspect_mbtiles(tmp / "resources" / "maps" / "cba.mbtiles"),
    )
    widget.resize(400, 300)
    widget.update_center(-31.42, -64.18, force=True)

    pixmap = widget.pixmap()
    assert pixmap is not None and not pixmap.isNull()


def test_clear_map(env) -> None:
    window, config, map_manager, tmp = env
    path = make_mbtiles(tmp / "resources" / "maps" / "cba.mbtiles")
    window._apply_map("resources/maps/cba.mbtiles", inspect_mbtiles(path))

    window._apply_map(None, None)

    assert not map_manager.is_available
    assert window.navigation_screen.map_widget.text() == "Sin mapa offline cargado"
    assert ConfigManager(config.config_path).get("maps.mbtiles_path") is None


def test_apply_route_reorders_roadbook_by_gpx(env) -> None:
    window, config, _, tmp = env
    assert _roadbook_names(window) == ["Norte", "Centro", "Sur"]  # orden de alta
    gpx = tmp / "resources" / "routes" / "especial.gpx"
    gpx.write_text(GPX_TRACK, encoding="utf-8")

    window._apply_route("resources/routes/especial.gpx")

    assert _roadbook_names(window) == ["Sur", "Centro", "Norte"]  # orden del track
    strip = window.navigation_screen.roadbook_strip
    assert len(strip._rows) == 3
    assert ConfigManager(config.config_path).get("roadbook.gpx_path") == (
        "resources/routes/especial.gpx"
    )

    window._apply_route(None)
    assert _roadbook_names(window) == ["Norte", "Centro", "Sur"]
