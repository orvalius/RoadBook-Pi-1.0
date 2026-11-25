"""Pantalla "Mapas y ruta".

Permite elegir, importar y quitar desde la app:

- el mapa offline (``.mbtiles``) que se dibuja de fondo en Navegación;
- el track GPX que ordena la tira del Roadbook Rendering Engine.

Antes había que editar ``maps.mbtiles_path`` / ``roadbook.gpx_path`` a
mano en ``config.json`` (pendiente anotado en los releases 1.0.0 y
1.1.0).

Reglas que respeta:
- Todo archivo importado se copia a la biblioteca (``resources/maps``,
  ``resources/routes``) vía ``ResourceManager``: en la config siempre
  queda una ruta relativa, nunca absoluta.
- Los archivos se validan **antes** de copiarlos: un mbtiles de varios
  GB tarda minutos en copiarse a la SD de una Pi, no tiene sentido
  descubrir al final que era otro tipo de archivo.
- Esta pantalla no aplica nada por su cuenta: avisa a ``MainWindow``
  por callbacks, que es quien reconfigura MapManager / RoadbookEngine.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.logger import get_logger
from core.map_generator import RouteMap, generate_mbtiles
from core.map_manager import InvalidMbtilesError, MbtilesInfo, inspect_mbtiles
from core.resource_manager import ResourceManager
from core.route import GpxInfo, InvalidGpxError, inspect_gpx

logger = get_logger(__name__)

NO_MAP_LABEL = "(sin mapa)"
NO_ROUTE_LABEL = "(sin GPX: ordenar por waypoints)"

# Firma de un selector de archivos: (padre, título, filtro) -> ruta o "".
# Inyectable para poder testear la pantalla sin abrir diálogos reales.
FilePicker = Callable[[QWidget, str, str], str]
MapChangeCallback = Callable[[str | None, MbtilesInfo | None], None]
RouteChangeCallback = Callable[[str | None], None]
RouteProvider = Callable[[], RouteMap | None]
GENERATED_MAP = "ruta_generada.mbtiles"


def _default_file_picker(parent: QWidget, title: str, file_filter: str) -> str:
    path, _ = QFileDialog.getOpenFileName(parent, title, str(Path.home()), file_filter)
    return path


def format_size(size_bytes: int) -> str:
    """Tamaño legible: '850 KB', '1.4 GB'."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - inalcanzable


def describe_mbtiles(info: MbtilesInfo) -> str:
    """Texto de resumen de un mbtiles para mostrar en pantalla."""
    if info.min_zoom is None:
        zoom = "sin tiles"
    elif info.min_zoom == info.max_zoom:
        zoom = f"zoom {info.min_zoom}"
    else:
        zoom = f"zoom {info.min_zoom}–{info.max_zoom}"
    size = format_size(info.size_bytes)
    text = f"{info.name} · {info.tile_format.upper()} · {zoom} · {size}"
    if info.is_vector:
        text += "\n⚠ Tiles vectoriales: no se pueden dibujar (se necesita raster)."
    return text


def describe_gpx(info: GpxInfo) -> str:
    """Texto de resumen de un GPX para mostrar en pantalla."""
    return f"{info.point_count} puntos · {info.length_m / 1000:.1f} km"


class _CopyCancelled(Exception):
    pass


class _ImportWorker(QObject):
    """Copia un recurso en un hilo aparte, reportando progreso por señales.

    La copia corre fuera del hilo de Qt para que la UI no se congele
    con archivos grandes; las señales llegan encoladas al hilo principal.
    """

    progress = pyqtSignal(int)  # porcentaje 0-100
    finished = pyqtSignal(str)  # ruta relativa del recurso importado
    failed = pyqtSignal(str)  # mensaje de error ("" si se canceló)

    def __init__(
        self, resource_manager: ResourceManager, source: str, category: str
    ) -> None:
        super().__init__()
        self._resource_manager = resource_manager
        self._source = source
        self._category = category
        self._cancel = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._run, daemon=True, name="ResourceImport"
        )
        self.thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def _on_progress(self, copied: int, total: int) -> None:
        if self._cancel.is_set():
            raise _CopyCancelled
        self.progress.emit(int(copied * 100 / total) if total else 100)

    def _work(self) -> str:
        return self._resource_manager.import_resource(
            self._source, self._category, progress=self._on_progress
        )

    def _run(self) -> None:
        try:
            relative = self._work()
        except _CopyCancelled:
            logger.info("Tarea cancelada: %s", self._source)
            self.failed.emit("")
        except Exception as exc:  # noqa: BLE001 - se informa en la UI
            logger.exception("Error en tarea de fondo: %s", self._source)
            self.failed.emit(str(exc))
        else:
            self.finished.emit(relative)


class _GenerateWorker(_ImportWorker):
    """Genera el mapa de la ruta en segundo plano (mismo protocolo de señales)."""

    def __init__(
        self, resource_manager: ResourceManager, route: RouteMap, relative: str
    ) -> None:
        super().__init__(resource_manager, relative, "maps")
        self._route = route

    def _work(self) -> str:
        generate_mbtiles(
            self._resource_manager.resolve_relative_path(self._source),
            self._route,
            progress=self._on_progress,
        )
        return self._source


class MapsRouteScreen(QWidget):
    """Pantalla de gestión del mapa offline y del track GPX de la ruta.

    Attributes:
        status_label: Último mensaje de resultado (para el usuario y tests).
    """

    def __init__(
        self,
        config: ConfigManager,
        resource_manager: ResourceManager,
        on_map_change: MapChangeCallback,
        on_route_change: RouteChangeCallback,
        file_picker: FilePicker | None = None,
        route_provider: RouteProvider | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.resource_manager = resource_manager
        self._on_map_change = on_map_change
        self._on_route_change = on_route_change
        self._pick_file = file_picker or _default_file_picker
        self._route_provider = route_provider
        self._import_worker: _ImportWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        map_box = QGroupBox("Mapa offline (.mbtiles)")
        map_layout = QVBoxLayout(map_box)
        self.map_combo = QComboBox()
        self.map_combo.currentIndexChanged.connect(self._show_selected_map_info)
        self.map_info_label = QLabel()
        self.map_info_label.setWordWrap(True)
        self.map_import_button = QPushButton("Importar…")
        self.map_import_button.clicked.connect(self._import_map)
        self.map_apply_button = QPushButton("Usar este mapa")
        self.map_apply_button.clicked.connect(self._apply_selected_map)
        map_layout.addWidget(self.map_combo)
        map_layout.addWidget(self.map_info_label)
        self.map_generate_button = QPushButton("Generar desde la ruta")
        self.map_generate_button.setToolTip(
            "Arma un mapa ilustrativo de la zona de la ruta (no es cartografía real)"
        )
        self.map_generate_button.clicked.connect(self._generate_map)
        self.map_generate_button.setVisible(self._route_provider is not None)
        map_layout.addLayout(
            _button_row(
                self.map_import_button,
                self.map_generate_button,
                self.map_apply_button,
            )
        )

        route_box = QGroupBox("Track de la ruta (.gpx)")
        route_layout = QVBoxLayout(route_box)
        self.route_combo = QComboBox()
        self.route_combo.currentIndexChanged.connect(self._show_selected_route_info)
        self.route_info_label = QLabel()
        self.route_info_label.setWordWrap(True)
        self.route_import_button = QPushButton("Importar…")
        self.route_import_button.clicked.connect(self._import_route)
        self.route_apply_button = QPushButton("Usar esta ruta")
        self.route_apply_button.clicked.connect(self._apply_selected_route)
        route_layout.addWidget(self.route_combo)
        route_layout.addWidget(self.route_info_label)
        route_layout.addLayout(
            _button_row(self.route_import_button, self.route_apply_button)
        )

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)

        layout.addWidget(map_box)
        layout.addWidget(route_box)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def refresh(self) -> None:
        """Recarga las listas desde la biblioteca y marca lo que está en uso."""
        _fill_combo(
            self.map_combo,
            NO_MAP_LABEL,
            self._library_files("maps", ".mbtiles"),
            self.config.get("maps.mbtiles_path", None),
            self._resolve,
        )
        _fill_combo(
            self.route_combo,
            NO_ROUTE_LABEL,
            self._library_files("routes", ".gpx"),
            self.config.get("roadbook.gpx_path", None),
            self._resolve,
        )
        self._show_selected_map_info()
        self._show_selected_route_info()

    def _library_files(self, category: str, suffix: str) -> list[str]:
        return [
            self.resource_manager.to_relative_path(category, name)
            for name in self.resource_manager.list_resources(category)
            if name.lower().endswith(suffix)
        ]

    def _resolve(self, path: str) -> Path:
        # Rutas de la biblioteca: relativas a la raíz del proyecto, no al
        # directorio desde donde se lanzó la app. Las absolutas quedan igual.
        return self.resource_manager.resolve_relative_path(path)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ----------------------------------------------------------- Mapa

    def _show_selected_map_info(self) -> None:
        path = self.map_combo.currentData()
        if path is None:
            self.map_info_label.setText("La pantalla de Navegación no mostrará mapa.")
            return
        try:
            self.map_info_label.setText(
                describe_mbtiles(inspect_mbtiles(self._resolve(path)))
            )
        except InvalidMbtilesError as exc:
            self.map_info_label.setText(f"⚠ {exc}")

    def _apply_selected_map(self) -> None:
        path = self.map_combo.currentData()
        self._apply_map(path)

    def _apply_map(self, path: str | None) -> None:
        if path is None:
            self._on_map_change(None, None)
            self._set_status("Mapa offline quitado.")
            return
        try:
            info = inspect_mbtiles(self._resolve(path))
        except InvalidMbtilesError as exc:
            self._set_status(f"No se pudo usar el mapa: {exc}")
            return
        if info.is_vector:
            self._set_status(
                "Ese mapa tiene tiles vectoriales; RoadBook Pi solo dibuja "
                "mapas raster (PNG/JPG)."
            )
            return
        self._on_map_change(path, info)
        self._set_status(f"Mapa activo: {info.name}")

    def _import_map(self) -> None:
        source = self._pick_file(
            self, "Elegir mapa offline", "Mapas MBTiles (*.mbtiles);;Todos (*)"
        )
        if not source:
            return
        try:
            info = inspect_mbtiles(source)
        except InvalidMbtilesError as exc:
            self._set_status(f"No se importó: {exc}")
            return
        if info.is_vector:
            self._set_status(
                "No se importó: tiene tiles vectoriales y RoadBook Pi solo "
                "dibuja mapas raster (PNG/JPG)."
            )
            return
        self._start_import(source, "maps", info.size_bytes)

    def _generate_map(self) -> None:
        route = self._route_provider() if self._route_provider else None
        if route is None or not (route.line or route.notes):
            self._set_status("No hay waypoints activos para generar el mapa.")
            return
        relative = self.resource_manager.to_relative_path("maps", GENERATED_MAP)
        if self.config.get("maps.mbtiles_path", None) == relative:
            # Soltar el archivo activo antes de reemplazarlo (en Windows,
            # un archivo abierto no se puede pisar).
            self._on_map_change(None, None)
        worker = _GenerateWorker(self.resource_manager, route, relative)
        self._start_job(
            worker,
            "Generando el mapa de la ruta…",
            "Generando mapa",
            "Generando mapa…",
        )

    # ----------------------------------------------------------- Ruta

    def _show_selected_route_info(self) -> None:
        path = self.route_combo.currentData()
        if path is None:
            self.route_info_label.setText(
                "La tira del roadbook sigue el orden de ruta de los waypoints."
            )
            return
        try:
            self.route_info_label.setText(
                describe_gpx(inspect_gpx(self._resolve(path)))
            )
        except InvalidGpxError as exc:
            self.route_info_label.setText(f"⚠ {exc}")

    def _apply_selected_route(self) -> None:
        self._apply_route(self.route_combo.currentData())

    def _apply_route(self, path: str | None) -> None:
        if path is None:
            self._on_route_change(None)
            self._set_status("Ruta GPX quitada: la tira usa el orden de waypoints.")
            return
        try:
            info = inspect_gpx(self._resolve(path))
        except InvalidGpxError as exc:
            self._set_status(f"No se pudo usar la ruta: {exc}")
            return
        self._on_route_change(path)
        self._set_status(f"Ruta activa: {Path(path).name} ({describe_gpx(info)})")

    def _import_route(self) -> None:
        source = self._pick_file(
            self, "Elegir track GPX", "Tracks GPX (*.gpx);;Todos (*)"
        )
        if not source:
            return
        try:
            info = inspect_gpx(source)
        except InvalidGpxError as exc:
            self._set_status(f"No se importó: {exc}")
            return
        # Los GPX pesan poco: copia directa, sin hilo ni diálogo.
        try:
            relative = self.resource_manager.import_resource(source, "routes")
        except OSError as exc:
            self._set_status(f"No se importó: {exc}")
            return
        logger.info("GPX importado: %s (%s)", relative, describe_gpx(info))
        self.refresh()
        _select_data(self.route_combo, relative)
        self._apply_route(relative)

    # ------------------------------------------------- Copia en segundo plano

    def _start_import(self, source: str, category: str, size_bytes: int) -> None:
        worker = _ImportWorker(self.resource_manager, source, category)
        self._start_job(
            worker,
            f"Copiando {Path(source).name} ({format_size(size_bytes)})…",
            "Importando mapa",
            "Importando mapa…",
        )

    def _start_job(
        self, worker: _ImportWorker, label: str, title: str, status: str
    ) -> None:
        worker.finished.connect(self._on_map_import_finished)
        worker.failed.connect(self._on_import_failed)
        self._import_worker = worker
        self._set_import_buttons_enabled(False)

        dialog = QProgressDialog(label, "Cancelar", 0, 100, self)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(500)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(worker.cancel)
        worker.progress.connect(dialog.setValue)
        self._progress_dialog = dialog

        self._set_status(status)
        worker.start()

    def _end_import(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        self._import_worker = None
        self._set_import_buttons_enabled(True)

    def _on_map_import_finished(self, relative: str) -> None:
        self._end_import()
        self.refresh()
        _select_data(self.map_combo, relative)
        self._apply_map(relative)

    def _on_import_failed(self, message: str) -> None:
        self._end_import()
        if message:
            self._set_status(f"Error: {message}")
            QMessageBox.warning(self, "No se pudo completar", message)
        else:
            self._set_status("Cancelado.")

    def _set_import_buttons_enabled(self, enabled: bool) -> None:
        for button in (
            self.map_import_button,
            self.map_generate_button,
            self.map_apply_button,
            self.route_import_button,
            self.route_apply_button,
        ):
            button.setEnabled(enabled)

    @property
    def is_importing(self) -> bool:
        """True mientras hay una copia en curso (para tests/diagnóstico)."""
        return self._import_worker is not None


def _button_row(*buttons: QPushButton) -> QHBoxLayout:
    row = QHBoxLayout()
    for button in buttons:
        button.setMinimumHeight(40)  # tocable en la pantalla táctil de la Pi
        row.addWidget(button)
    return row


def _fill_combo(
    combo: QComboBox,
    none_label: str,
    paths: list[str],
    current: str | None,
    resolve: Callable[[str], Path],
) -> None:
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(none_label, userData=None)
    for path in paths:
        combo.addItem(Path(path).name, userData=path)
    if current and current not in paths:
        # Configurado a mano fuera de la biblioteca (o archivo borrado):
        # se muestra igual para que el usuario vea qué hay en la config.
        suffix = "" if resolve(current).exists() else " — no encontrado"
        combo.addItem(f"{current}{suffix}", userData=current)
    _select_data(combo, current)
    combo.blockSignals(False)


def _select_data(combo: QComboBox, data: str | None) -> None:
    index = combo.findData(data) if data is not None else 0
    combo.setCurrentIndex(index if index >= 0 else 0)
