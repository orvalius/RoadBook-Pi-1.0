"""Pantalla de gestión de Waypoints.

CRUD completo sobre la tabla waypoints, vía ``WaypointRepository``.
Esta pantalla nunca escribe SQL directamente: todo pasa por el
repositorio, que a su vez pasa por ``DatabaseManager``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.resource_manager import ResourceManager
from database.action_repository import ActionRepository
from database.models import Waypoint
from database.waypoint_repository import WaypointNotFoundError, WaypointRepository
from ui.screens.action_sequence_dialog import ActionSequenceDialog

logger = get_logger(__name__)

COLUMNS = ["ID", "Nombre", "Categoría", "Lat", "Lon", "Radio (m)", "Activo"]


class WaypointFormDialog(QDialog):
    """Diálogo de alta/edición de un waypoint."""

    def __init__(
        self,
        resource_manager: ResourceManager,
        waypoint: Waypoint | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar waypoint" if waypoint else "Nuevo waypoint")
        self.resource_manager = resource_manager
        self._waypoint = waypoint
        self._build_ui()
        if waypoint is not None:
            self._load_from_waypoint(waypoint)

    def _build_ui(self) -> None:
        form = QFormLayout()

        self.nombre_input = QLineEdit()

        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90.0, 90.0)
        self.lat_input.setDecimals(6)

        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180.0, 180.0)
        self.lon_input.setDecimals(6)

        self.radio_input = QDoubleSpinBox()
        self.radio_input.setRange(1.0, 10_000.0)
        self.radio_input.setValue(50.0)
        self.radio_input.setSuffix(" m")

        self.categoria_input = QLineEdit()
        self.descripcion_input = QTextEdit()
        self.descripcion_input.setFixedHeight(60)

        self.imagen_selector = QComboBox()
        self.imagen_selector.addItem("(ninguna)", userData=None)
        for filename in self.resource_manager.list_resources("images"):
            self.imagen_selector.addItem(filename, userData=filename)

        self.audio_selector = QComboBox()
        self.audio_selector.addItem("(ninguno)", userData=None)
        for filename in self.resource_manager.list_resources("audio"):
            self.audio_selector.addItem(filename, userData=filename)

        self.prioridad_input = QSpinBox()
        self.prioridad_input.setRange(0, 100)

        self.activo_checkbox = QCheckBox("Waypoint activo")
        self.activo_checkbox.setChecked(True)

        self.re_triggerable_checkbox = QCheckBox("Puede volver a dispararse (re-entrada)")
        self.re_triggerable_checkbox.setChecked(True)

        form.addRow("Nombre:", self.nombre_input)
        form.addRow("Latitud:", self.lat_input)
        form.addRow("Longitud:", self.lon_input)
        form.addRow("Radio:", self.radio_input)
        form.addRow("Categoría:", self.categoria_input)
        form.addRow("Imagen:", self.imagen_selector)
        form.addRow("Audio:", self.audio_selector)
        form.addRow("Prioridad:", self.prioridad_input)
        form.addRow("Descripción:", self.descripcion_input)
        form.addRow(self.activo_checkbox)
        form.addRow(self.re_triggerable_checkbox)

        hint = QLabel(
            "¿No aparece el recurso que buscás? Importalo primero desde "
            "la pantalla de Biblioteca."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid); font-size: 11px;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def _load_from_waypoint(self, waypoint: Waypoint) -> None:
        self.nombre_input.setText(waypoint.nombre)
        self.lat_input.setValue(waypoint.latitud)
        self.lon_input.setValue(waypoint.longitud)
        self.radio_input.setValue(waypoint.radio)
        self.categoria_input.setText(waypoint.categoria or "")
        self.prioridad_input.setValue(waypoint.prioridad)
        self.descripcion_input.setPlainText(waypoint.descripcion or "")
        self.activo_checkbox.setChecked(waypoint.activo)
        self.re_triggerable_checkbox.setChecked(waypoint.re_triggerable)

        if waypoint.imagen:
            filename = Path(waypoint.imagen).name
            index = self.imagen_selector.findText(filename)
            if index >= 0:
                self.imagen_selector.setCurrentIndex(index)

        if waypoint.audio:
            filename = Path(waypoint.audio).name
            index = self.audio_selector.findText(filename)
            if index >= 0:
                self.audio_selector.setCurrentIndex(index)

    def _on_accept(self) -> None:
        if not self.nombre_input.text().strip():
            QMessageBox.warning(self, "Falta el nombre", "El waypoint necesita un nombre.")
            return
        self.accept()

    def get_waypoint(self) -> Waypoint:
        """Construye un ``Waypoint`` a partir de los valores del formulario.

        Returns:
            Instancia de Waypoint con id preservado si se estaba editando.
        """
        imagen_filename = self.imagen_selector.currentData()
        audio_filename = self.audio_selector.currentData()

        imagen = (
            self.resource_manager.to_relative_path("images", imagen_filename)
            if imagen_filename else None
        )
        audio = (
            self.resource_manager.to_relative_path("audio", audio_filename)
            if audio_filename else None
        )

        return Waypoint(
            id=self._waypoint.id if self._waypoint else None,
            nombre=self.nombre_input.text().strip(),
            latitud=self.lat_input.value(),
            longitud=self.lon_input.value(),
            radio=self.radio_input.value(),
            categoria=self.categoria_input.text().strip() or None,
            descripcion=self.descripcion_input.toPlainText().strip() or None,
            prioridad=self.prioridad_input.value(),
            activo=self.activo_checkbox.isChecked(),
            re_triggerable=self.re_triggerable_checkbox.isChecked(),
            imagen=imagen,
            audio=audio,
            velocidad=self._waypoint.velocidad if self._waypoint else None,
            angulo=self._waypoint.angulo if self._waypoint else None,
        )


class WaypointsScreen(QWidget):
    """Pantalla de administración de waypoints (alta/baja/edición).

    Attributes:
        repository: Repositorio de acceso a la tabla waypoints.
    """

    def __init__(
        self,
        repository: WaypointRepository,
        resource_manager: ResourceManager,
        action_repository: ActionRepository,
        parent: QWidget | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.resource_manager = resource_manager
        self.action_repository = action_repository
        self.on_change = on_change
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.doubleClicked.connect(self._on_edit)

        button_bar = QHBoxLayout()
        add_button = QPushButton("Agregar")
        edit_button = QPushButton("Editar")
        delete_button = QPushButton("Eliminar")
        toggle_button = QPushButton("Activar/Desactivar")
        sequence_button = QPushButton("Secuencia de acciones...")

        add_button.clicked.connect(self._on_add)
        edit_button.clicked.connect(self._on_edit)
        delete_button.clicked.connect(self._on_delete)
        toggle_button.clicked.connect(self._on_toggle_active)
        sequence_button.clicked.connect(self._on_edit_sequence)

        for btn in (add_button, edit_button, delete_button, toggle_button, sequence_button):
            button_bar.addWidget(btn)
        button_bar.addStretch()

        layout.addLayout(button_bar)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        """Recarga la tabla desde la base de datos."""
        waypoints = self.repository.list_all()
        self.table.setRowCount(len(waypoints))
        for row, wp in enumerate(waypoints):
            values = [
                str(wp.id),
                wp.nombre,
                wp.categoria or "",
                f"{wp.latitud:.6f}",
                f"{wp.longitud:.6f}",
                f"{wp.radio:.0f}",
                "Sí" if wp.activo else "No",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

    def _selected_waypoint_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        return int(self.table.item(row, 0).text())

    def _on_add(self) -> None:
        dialog = WaypointFormDialog(self.resource_manager, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            waypoint = dialog.get_waypoint()
            self.repository.create(waypoint)
            self.refresh()
            self._notify_change()

    def _on_edit(self) -> None:
        waypoint_id = self._selected_waypoint_id()
        if waypoint_id is None:
            QMessageBox.information(self, "Sin selección", "Seleccioná un waypoint primero.")
            return

        try:
            waypoint = self.repository.get(waypoint_id)
        except WaypointNotFoundError:
            QMessageBox.warning(self, "No encontrado", "El waypoint ya no existe.")
            self.refresh()
            return

        dialog = WaypointFormDialog(self.resource_manager, waypoint=waypoint, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.get_waypoint()
            self.repository.update(updated)
            self.refresh()
            self._notify_change()

    def _on_delete(self) -> None:
        waypoint_id = self._selected_waypoint_id()
        if waypoint_id is None:
            QMessageBox.information(self, "Sin selección", "Seleccioná un waypoint primero.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Eliminar el waypoint seleccionado? Esta acción no se puede deshacer.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.repository.delete(waypoint_id)
            except WaypointNotFoundError:
                pass
            self.refresh()
            self._notify_change()

    def _on_toggle_active(self) -> None:
        waypoint_id = self._selected_waypoint_id()
        if waypoint_id is None:
            QMessageBox.information(self, "Sin selección", "Seleccioná un waypoint primero.")
            return

        try:
            waypoint = self.repository.get(waypoint_id)
            self.repository.set_active(waypoint_id, not waypoint.activo)
        except WaypointNotFoundError:
            pass
        self.refresh()
        self._notify_change()

    def _on_edit_sequence(self) -> None:
        waypoint_id = self._selected_waypoint_id()
        if waypoint_id is None:
            QMessageBox.information(self, "Sin selección", "Seleccioná un waypoint primero.")
            return

        try:
            waypoint = self.repository.get(waypoint_id)
        except WaypointNotFoundError:
            QMessageBox.warning(self, "No encontrado", "El waypoint ya no existe.")
            self.refresh()
            return

        dialog = ActionSequenceDialog(
            waypoint, self.action_repository, self.resource_manager, parent=self
        )
        dialog.exec()

    def _notify_change(self) -> None:
        """Notifica a quien corresponda (ej: recargar NavigationEngine)."""
        if self.on_change is not None:
            self.on_change()
