"""Pantalla de Configuración.

A diferencia de otras pantallas stub, esta ya es funcional en Sprint 1:
permite ver y guardar configuración básica a través de ConfigManager,
sin acceder nunca al archivo JSON directamente.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger(__name__)


class SettingsScreen(QWidget):
    """Pantalla de configuración general de la aplicación.

    Attributes:
        config: Instancia compartida de ``ConfigManager``.
    """

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.gps_backend_input = QLineEdit(self.config.get("gps.backend", "simulator"))
        self.gps_serial_port_input = QLineEdit(self.config.get("gps.serial_port", ""))
        self.fullscreen_checkbox = QCheckBox()
        self.fullscreen_checkbox.setChecked(
            bool(self.config.get("display.fullscreen", False))
        )

        form.addRow("Backend GPS (gpsd/serial/simulator):", self.gps_backend_input)
        form.addRow("Puerto serie GPS:", self.gps_serial_port_input)
        form.addRow("Pantalla completa:", self.fullscreen_checkbox)

        save_button = QPushButton("Guardar configuración")
        save_button.clicked.connect(self._on_save)

        layout.addLayout(form)
        layout.addWidget(save_button)
        layout.addStretch()

    def _on_save(self) -> None:
        """Persiste los cambios de configuración hechos en la UI."""
        self.config.set("gps.backend", self.gps_backend_input.text().strip())
        self.config.set("gps.serial_port", self.gps_serial_port_input.text().strip())
        self.config.set("display.fullscreen", self.fullscreen_checkbox.isChecked())
        self.config.save()
        logger.info("Configuración guardada desde SettingsScreen")
