"""Pantalla de Biblioteca de recursos (imágenes, audio, iconos).

Permite importar recursos externos (se copian dentro del proyecto,
nunca se guardan rutas absolutas), listarlos por categoría, previsualizar
imágenes, reproducir audio y eliminarlos. Todo el acceso a archivos
pasa por ``ResourceManager``; esta pantalla nunca usa ``shutil`` ni
``pathlib`` para tocar ``resources/`` directamente.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.audio_manager import AudioManager
from core.logger import get_logger
from core.resource_manager import ResourceManager

logger = get_logger(__name__)

CATEGORY_LABELS = {
    "images": "Imágenes",
    "audio": "Audio",
    "icons": "Iconos",
}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg")


class LibraryScreen(QWidget):
    """Pantalla de administración de la biblioteca de recursos.

    Attributes:
        resource_manager: Repositorio de acceso a archivos de recursos.
        audio_manager: Usado para previsualizar audio.
    """

    def __init__(
        self,
        resource_manager: ResourceManager,
        audio_manager: AudioManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.resource_manager = resource_manager
        self.audio_manager = audio_manager or AudioManager(enabled=False)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.category_selector = QComboBox()
        for key, label in CATEGORY_LABELS.items():
            self.category_selector.addItem(label, userData=key)
        self.category_selector.currentIndexChanged.connect(self.refresh)
        top_bar.addWidget(QLabel("Categoría:"))
        top_bar.addWidget(self.category_selector)
        top_bar.addStretch()

        content = QHBoxLayout()

        self.file_list = QListWidget()
        self.file_list.currentTextChanged.connect(self._on_selection_changed)

        preview_panel = QVBoxLayout()
        self.preview_label = QLabel("Sin selección")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(200, 200)
        self.preview_label.setStyleSheet("border: 1px solid palette(mid);")

        self.play_button = QPushButton("Reproducir")
        self.play_button.clicked.connect(self._on_play)
        self.play_button.setEnabled(False)

        preview_panel.addWidget(self.preview_label)
        preview_panel.addWidget(self.play_button)
        preview_panel.addStretch()

        content.addWidget(self.file_list, stretch=1)
        content.addLayout(preview_panel, stretch=1)

        button_bar = QHBoxLayout()
        import_button = QPushButton("Importar...")
        delete_button = QPushButton("Eliminar")
        import_button.clicked.connect(self._on_import)
        delete_button.clicked.connect(self._on_delete)
        button_bar.addWidget(import_button)
        button_bar.addWidget(delete_button)
        button_bar.addStretch()

        layout.addLayout(top_bar)
        layout.addLayout(content)
        layout.addLayout(button_bar)

    def _current_category(self) -> str:
        return self.category_selector.currentData()

    def refresh(self) -> None:
        """Recarga la lista de archivos de la categoría seleccionada."""
        category = self._current_category()
        self.file_list.clear()
        self.preview_label.setText("Sin selección")
        self.preview_label.setPixmap(QPixmap())
        self.play_button.setEnabled(False)

        if category is None:
            return

        for filename in self.resource_manager.list_resources(category):
            self.file_list.addItem(filename)

    def _on_selection_changed(self, filename: str) -> None:
        category = self._current_category()
        self.play_button.setEnabled(False)
        self.preview_label.setPixmap(QPixmap())

        if not filename:
            self.preview_label.setText("Sin selección")
            return

        path = self.resource_manager.get_absolute_path(category, filename)

        if category == "images" or category == "icons":
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.preview_label.setPixmap(
                    pixmap.scaled(
                        200,
                        200,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.preview_label.setText("")
            else:
                self.preview_label.setText("No se pudo previsualizar")
        elif category == "audio":
            self.preview_label.setText(filename)
            self.play_button.setEnabled(True)

    def _on_import(self) -> None:
        category = self._current_category()
        if category == "audio":
            file_filter = "Audio (*.wav *.mp3 *.ogg)"
        else:
            file_filter = "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif)"

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Importar recurso", "", file_filter
        )
        if not file_path:
            return

        try:
            self.resource_manager.import_resource(file_path, category)
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Error al importar", str(exc))
            return

        self.refresh()

    def _on_delete(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "Sin selección", "Seleccioná un recurso primero."
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar '{item.text()}'? Esta acción no se puede deshacer.\n\n"
            "Si algún waypoint lo está usando, quedará con una referencia rota.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.resource_manager.delete_resource(self._current_category(), item.text())
        except FileNotFoundError:
            pass
        self.refresh()

    def _on_play(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            return
        path = self.resource_manager.get_absolute_path("audio", item.text())
        self.audio_manager.play(path)
