"""UI de autoría de secuencias de acciones por waypoint (Sprint 8, pendiente).

Dos diálogos:

- ``ActionStepDialog``: configura un único paso (tipo + payload).
- ``ActionSequenceDialog``: arma/edita la secuencia completa de un
  waypoint (agregar, editar, reordenar, borrar pasos), y la persiste
  vía ``ActionRepository.replace_sequence`` o la borra para volver al
  comportamiento legacy por defecto.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.action_descriptions import ACTION_TYPE_LABELS, describe_action
from core.action_dispatcher import ActionType
from core.logger import get_logger
from core.resource_manager import ResourceManager
from database.action_repository import ActionRepository
from database.models import Action, Waypoint

logger = get_logger(__name__)

# Orden en que se ofrecen los tipos de acción en el combo del paso
ACTION_TYPE_ORDER = [
    ActionType.SHOW_IMAGE,
    ActionType.PLAY_AUDIO,
    ActionType.WAIT,
    ActionType.HIDE_IMAGE,
    ActionType.LOG_EVENT,
    ActionType.RUN_PLUGIN,
]


class ActionStepDialog(QDialog):
    """Configura un único paso de la secuencia (tipo + payload)."""

    def __init__(
        self,
        resource_manager: ResourceManager,
        action: Action | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar paso" if action else "Nuevo paso")
        self.resource_manager = resource_manager
        self._existing_action = action
        self._build_ui()
        if action is not None:
            self._load_from_action(action)
        else:
            self._on_type_changed(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_selector = QComboBox()
        for action_type in ACTION_TYPE_ORDER:
            self.type_selector.addItem(
                ACTION_TYPE_LABELS[action_type.value], userData=action_type.value
            )
        self.type_selector.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Tipo de acción:", self.type_selector)

        self.pages = QStackedWidget()

        self.image_selector = QComboBox()
        for filename in self.resource_manager.list_resources("images"):
            self.image_selector.addItem(filename, userData=filename)
        self.pages.addWidget(self._wrap("Imagen:", self.image_selector))

        self.audio_selector = QComboBox()
        for filename in self.resource_manager.list_resources("audio"):
            self.audio_selector.addItem(filename, userData=filename)
        self.pages.addWidget(self._wrap("Audio:", self.audio_selector))

        self.wait_seconds = QDoubleSpinBox()
        self.wait_seconds.setRange(0.1, 3600.0)
        self.wait_seconds.setValue(3.0)
        self.wait_seconds.setSuffix(" s")
        self.pages.addWidget(self._wrap("Duración:", self.wait_seconds))

        self.pages.addWidget(QLabel("Este paso no necesita parámetros."))

        self.log_message = QLineEdit()
        self.pages.addWidget(self._wrap("Mensaje:", self.log_message))

        self.plugin_name = QLineEdit()
        self.plugin_name.setPlaceholderText(
            "Nombre del plugin (ver plugins.enabled en config.json)"
        )
        self.pages.addWidget(self._wrap("Nombre del plugin:", self.plugin_name))

        form.addRow(self.pages)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _wrap(label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(label_text))
        row.addWidget(widget, stretch=1)
        return container

    def _on_type_changed(self, index: int) -> None:
        self.pages.setCurrentIndex(index)

    def _load_from_action(self, action: Action) -> None:
        index = next(
            (i for i, t in enumerate(ACTION_TYPE_ORDER) if t.value == action.tipo), 0
        )
        self.type_selector.setCurrentIndex(index)
        self.pages.setCurrentIndex(index)

        if action.tipo == ActionType.SHOW_IMAGE.value:
            filename = action.payload.get("path", "").rsplit("/", 1)[-1]
            found = self.image_selector.findText(filename)
            if found >= 0:
                self.image_selector.setCurrentIndex(found)
        elif action.tipo == ActionType.PLAY_AUDIO.value:
            filename = action.payload.get("path", "").rsplit("/", 1)[-1]
            found = self.audio_selector.findText(filename)
            if found >= 0:
                self.audio_selector.setCurrentIndex(found)
        elif action.tipo == ActionType.WAIT.value:
            self.wait_seconds.setValue(float(action.payload.get("seconds", 3.0)))
        elif action.tipo == ActionType.LOG_EVENT.value:
            self.log_message.setText(action.payload.get("message", ""))
        elif action.tipo == ActionType.RUN_PLUGIN.value:
            self.plugin_name.setText(action.payload.get("plugin_name", ""))

    def _on_accept(self) -> None:
        tipo = self.type_selector.currentData()

        if tipo == ActionType.SHOW_IMAGE.value and self.image_selector.count() == 0:
            QMessageBox.warning(
                self,
                "Sin imágenes",
                "No hay imágenes en la Biblioteca. Importá alguna primero.",
            )
            return
        if tipo == ActionType.PLAY_AUDIO.value and self.audio_selector.count() == 0:
            QMessageBox.warning(
                self,
                "Sin audios",
                "No hay audios en la Biblioteca. Importá alguno primero.",
            )
            return
        if tipo == ActionType.LOG_EVENT.value and not self.log_message.text().strip():
            QMessageBox.warning(
                self, "Falta el mensaje", "Escribí un mensaje para el log."
            )
            return
        if tipo == ActionType.RUN_PLUGIN.value and not self.plugin_name.text().strip():
            QMessageBox.warning(
                self, "Falta el nombre", "Escribí el nombre del plugin."
            )
            return

        self.accept()

    def get_payload(self) -> tuple[str, dict]:
        """Construye (tipo, payload) a partir de la selección actual.

        Returns:
            Tupla (tipo de acción, diccionario de payload).
        """
        tipo = self.type_selector.currentData()

        if tipo == ActionType.SHOW_IMAGE.value:
            filename = self.image_selector.currentData()
            path = self.resource_manager.to_relative_path("images", filename)
            return tipo, {"path": path}

        if tipo == ActionType.PLAY_AUDIO.value:
            filename = self.audio_selector.currentData()
            path = self.resource_manager.to_relative_path("audio", filename)
            return tipo, {"path": path}

        if tipo == ActionType.WAIT.value:
            return tipo, {"seconds": self.wait_seconds.value()}

        if tipo == ActionType.LOG_EVENT.value:
            return tipo, {"message": self.log_message.text().strip()}

        if tipo == ActionType.RUN_PLUGIN.value:
            return tipo, {"plugin_name": self.plugin_name.text().strip()}

        return tipo, {}  # HIDE_IMAGE


class ActionSequenceDialog(QDialog):
    """Arma/edita la secuencia completa de acciones de un waypoint.

    Attributes:
        waypoint: Waypoint cuya secuencia se está editando.
    """

    def __init__(
        self,
        waypoint: Waypoint,
        action_repository: ActionRepository,
        resource_manager: ResourceManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Secuencia de acciones — {waypoint.nombre}")
        self.resize(480, 420)
        self.waypoint = waypoint
        self.action_repository = action_repository
        self.resource_manager = resource_manager

        existing = (
            action_repository.list_for_waypoint(waypoint.id) if waypoint.id else []
        )
        # Copia de trabajo en memoria: no se toca la base hasta "Guardar"
        self._steps: list[Action] = [
            Action(
                waypoint_id=waypoint.id,
                orden=a.orden,
                tipo=a.tipo,
                payload=dict(a.payload),
            )
            for a in existing
        ]
        self._is_custom = len(existing) > 0

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.step_list = QListWidget()
        layout.addWidget(self.step_list, stretch=1)

        step_buttons = QHBoxLayout()
        add_button = QPushButton("Agregar paso")
        edit_button = QPushButton("Editar paso")
        delete_button = QPushButton("Eliminar paso")
        up_button = QPushButton("Subir")
        down_button = QPushButton("Bajar")

        add_button.clicked.connect(self._on_add_step)
        edit_button.clicked.connect(self._on_edit_step)
        delete_button.clicked.connect(self._on_delete_step)
        up_button.clicked.connect(lambda: self._move_step(-1))
        down_button.clicked.connect(lambda: self._move_step(1))

        for btn in (add_button, edit_button, delete_button, up_button, down_button):
            step_buttons.addWidget(btn)
        layout.addLayout(step_buttons)

        reset_button = QPushButton("Restablecer a comportamiento por defecto")
        reset_button.clicked.connect(self._on_reset_to_default)
        layout.addWidget(reset_button)

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self._on_save)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def _refresh_list(self) -> None:
        self.step_list.clear()
        for i, action in enumerate(self._steps, start=1):
            self.step_list.addItem(
                f"{i}. {describe_action(action.tipo, action.payload)}"
            )

        if self._steps:
            self.status_label.setText(
                "Secuencia custom: se ejecuta esta lista en vez del comportamiento "
                "por defecto."
            )
        else:
            self.status_label.setText(
                "Sin secuencia custom: este waypoint usa el comportamiento por defecto "
                "(mostrar imagen/audio legacy, si tiene)."
            )

    def _on_add_step(self) -> None:
        dialog = ActionStepDialog(self.resource_manager, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tipo, payload = dialog.get_payload()
            self._steps.append(
                Action(
                    waypoint_id=self.waypoint.id,
                    orden=len(self._steps),
                    tipo=tipo,
                    payload=payload,
                )
            )
            self._refresh_list()

    def _on_edit_step(self) -> None:
        index = self.step_list.currentRow()
        if index < 0:
            QMessageBox.information(
                self, "Sin selección", "Seleccioná un paso primero."
            )
            return

        current = self._steps[index]
        dialog = ActionStepDialog(self.resource_manager, action=current, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tipo, payload = dialog.get_payload()
            self._steps[index] = Action(
                waypoint_id=self.waypoint.id, orden=index, tipo=tipo, payload=payload
            )
            self._refresh_list()

    def _on_delete_step(self) -> None:
        index = self.step_list.currentRow()
        if index < 0:
            QMessageBox.information(
                self, "Sin selección", "Seleccioná un paso primero."
            )
            return
        del self._steps[index]
        self._refresh_list()

    def _move_step(self, delta: int) -> None:
        index = self.step_list.currentRow()
        new_index = index + delta
        if index < 0 or not (0 <= new_index < len(self._steps)):
            return
        self._steps[index], self._steps[new_index] = (
            self._steps[new_index],
            self._steps[index],
        )
        self._refresh_list()
        self.step_list.setCurrentRow(new_index)

    def _on_reset_to_default(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Restablecer",
            "¿Borrar la secuencia custom y volver al comportamiento por defecto "
            "(imagen/audio legacy)? Esto se aplica al guardar.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._steps = []
            self._refresh_list()

    def _on_save(self) -> None:
        if self.waypoint.id is None:
            return

        if self._steps:
            self.action_repository.replace_sequence(self.waypoint.id, self._steps)
        else:
            self.action_repository.delete_all_for_waypoint(self.waypoint.id)

        self.accept()
