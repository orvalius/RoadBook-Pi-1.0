"""Tests de la pantalla "Mapas y ruta" (ui.screens.maps_route)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from core.config_manager import ConfigManager  # noqa: E402
from core.resource_manager import ResourceManager  # noqa: E402
from tests.conftest import GPX_ROUTE_ONLY, GPX_TRACK, make_mbtiles  # noqa: E402
from ui.screens.maps_route import (  # noqa: E402
    NO_MAP_LABEL,
    MapsRouteScreen,
    _ImportWorker,
    format_size,
)


class Harness:
    """Pantalla + dependencias reales en tmp_path, con picker y callbacks falsos."""

    def __init__(self, qtbot, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.resources = ResourceManager(tmp_path / "resources")
        self.config = ConfigManager(tmp_path / "config.json")
        self.picked: str = ""
        self.map_changes: list[tuple[str | None, object]] = []
        self.route_changes: list[str | None] = []
        self.screen: MapsRouteScreen | None = None
        self.qtbot = qtbot

    def build(self) -> MapsRouteScreen:
        self.screen = MapsRouteScreen(
            self.config,
            self.resources,
            on_map_change=lambda p, info: self.map_changes.append((p, info)),
            on_route_change=self.route_changes.append,
            file_picker=lambda *_: self.picked,
        )
        self.qtbot.addWidget(self.screen)
        return self.screen

    def external(self, name: str) -> Path:
        folder = self.tmp / "pendrive"
        folder.mkdir(exist_ok=True)
        return folder / name


@pytest.fixture
def h(qtbot, tmp_path: Path) -> Harness:
    return Harness(qtbot, tmp_path)


def _items(combo) -> list[str]:
    return [combo.itemText(i) for i in range(combo.count())]


def test_lists_library_files_and_marks_current(h: Harness) -> None:
    make_mbtiles(h.tmp / "resources" / "maps" / "cordoba.mbtiles")
    make_mbtiles(h.tmp / "resources" / "maps" / "sierras.mbtiles")
    (h.tmp / "resources" / "maps" / "notas.txt").write_text("x")
    h.config.set("maps.mbtiles_path", "resources/maps/sierras.mbtiles")

    screen = h.build()

    assert _items(screen.map_combo) == [
        NO_MAP_LABEL,
        "cordoba.mbtiles",
        "sierras.mbtiles",
    ]
    assert screen.map_combo.currentText() == "sierras.mbtiles"
    assert "zoom 10–12" in screen.map_info_label.text()


def test_shows_missing_configured_file(h: Harness) -> None:
    # Default de fábrica: default.mbtiles, que no viene incluido.
    screen = h.build()
    assert screen.map_combo.currentText().endswith("— no encontrado")
    assert "⚠" in screen.map_info_label.text()


def test_import_gpx_copies_and_applies(h: Harness) -> None:
    source = h.external("especial.gpx")
    source.write_text(GPX_TRACK, encoding="utf-8")
    h.picked = str(source)
    screen = h.build()

    screen.route_import_button.click()

    assert h.route_changes == ["resources/routes/especial.gpx"]
    assert (h.tmp / "resources" / "routes" / "especial.gpx").exists()
    assert screen.route_combo.currentText() == "especial.gpx"
    assert "Ruta activa" in screen.status_label.text()


def test_import_route_only_gpx_is_accepted(h: Harness) -> None:
    source = h.external("ruta.gpx")
    source.write_text(GPX_ROUTE_ONLY, encoding="utf-8")
    h.picked = str(source)
    h.build().route_import_button.click()
    assert h.route_changes == ["resources/routes/ruta.gpx"]


def test_invalid_gpx_is_not_copied(h: Harness) -> None:
    source = h.external("roto.gpx")
    source.write_text("<gpx>", encoding="utf-8")
    h.picked = str(source)
    screen = h.build()

    screen.route_import_button.click()

    assert h.route_changes == []
    assert h.resources.list_resources("routes") == []
    assert "No se importó" in screen.status_label.text()


def test_cancelled_picker_does_nothing(h: Harness) -> None:
    screen = h.build()
    screen.route_import_button.click()
    screen.map_import_button.click()
    assert h.route_changes == [] and h.map_changes == []
    assert screen.status_label.text() == ""


def test_clear_route(h: Harness) -> None:
    h.config.set("roadbook.gpx_path", "resources/routes/x.gpx")
    screen = h.build()
    screen.route_combo.setCurrentIndex(0)
    screen.route_apply_button.click()
    assert h.route_changes == [None]


def test_import_mbtiles_runs_in_background_and_applies(h: Harness) -> None:
    source = make_mbtiles(h.external("cordoba.mbtiles"))
    h.picked = str(source)
    screen = h.build()

    screen.map_import_button.click()
    h.qtbot.waitUntil(lambda: bool(h.map_changes), timeout=5000)

    path, info = h.map_changes[0]
    assert path == "resources/maps/cordoba.mbtiles"
    assert info.max_zoom == 12
    assert not screen.is_importing
    assert screen.map_import_button.isEnabled()
    assert screen.map_combo.currentText() == "cordoba.mbtiles"


def test_vector_mbtiles_rejected_before_copy(h: Harness) -> None:
    h.picked = str(make_mbtiles(h.external("v.mbtiles"), tile_format="pbf"))
    screen = h.build()
    screen.map_import_button.click()
    assert h.map_changes == []
    assert h.resources.list_resources("maps") == []
    assert "vectoriales" in screen.status_label.text()


def test_non_mbtiles_rejected_before_copy(h: Harness) -> None:
    fake = h.external("foto.mbtiles")
    fake.write_bytes(b"no soy sqlite" * 100)
    h.picked = str(fake)
    screen = h.build()
    screen.map_import_button.click()
    assert h.map_changes == []
    assert h.resources.list_resources("maps") == []


def test_apply_and_clear_map(h: Harness) -> None:
    make_mbtiles(h.tmp / "resources" / "maps" / "a.mbtiles")
    screen = h.build()

    screen.map_combo.setCurrentIndex(screen.map_combo.findText("a.mbtiles"))
    screen.map_apply_button.click()
    screen.map_combo.setCurrentIndex(0)
    screen.map_apply_button.click()

    assert [p for p, _ in h.map_changes] == ["resources/maps/a.mbtiles", None]


def test_cancelled_import_worker_leaves_no_file(qtbot, tmp_path: Path) -> None:
    resources = ResourceManager(tmp_path / "resources")
    source = make_mbtiles(tmp_path / "m.mbtiles")
    worker = _ImportWorker(resources, str(source), "maps")
    failures: list[str] = []
    worker.failed.connect(failures.append)

    worker.cancel()
    worker.start()
    qtbot.waitUntil(lambda: failures == [""], timeout=3000)

    assert resources.list_resources("maps") == []


@pytest.mark.parametrize(
    ("size", "text"),
    [(512, "512 B"), (2048, "2 KB"), (5 * 1024**2, "5.0 MB"), (3 * 1024**3, "3.0 GB")],
)
def test_format_size(size: int, text: str) -> None:
    assert format_size(size) == text


def test_generate_map_from_route(qtbot, tmp_path: Path) -> None:
    from core.map_generator import RouteMap

    h = Harness(qtbot, tmp_path)
    route = RouteMap(
        line=[(-31.42, -64.18), (-31.43, -64.19)], notes=[(-31.42, -64.18, "Largada")]
    )
    screen = MapsRouteScreen(
        h.config,
        h.resources,
        on_map_change=lambda p, info: h.map_changes.append((p, info)),
        on_route_change=h.route_changes.append,
        route_provider=lambda: route,
    )
    qtbot.addWidget(screen)
    assert screen.map_generate_button.isVisibleTo(screen)

    screen.map_generate_button.click()
    qtbot.waitUntil(lambda: bool(h.map_changes), timeout=30000)

    path, info = h.map_changes[-1]
    assert path == "resources/maps/ruta_generada.mbtiles"
    assert info.tile_format == "jpg"
    assert screen.map_combo.currentText() == "ruta_generada.mbtiles"


def test_generate_button_hidden_without_provider(h: Harness) -> None:
    assert not h.build().map_generate_button.isVisibleTo(h.screen)


def test_generate_without_waypoints(qtbot, tmp_path: Path) -> None:
    h = Harness(qtbot, tmp_path)
    screen = MapsRouteScreen(
        h.config,
        h.resources,
        lambda *a: None,
        lambda *a: None,
        route_provider=lambda: None,
    )
    qtbot.addWidget(screen)
    screen.map_generate_button.click()
    assert "No hay waypoints" in screen.status_label.text()
