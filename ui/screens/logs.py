"""Pantalla de Logs del sistema.

Muestra el contenido de logs/roadbook_pi.log. Visor simple en Sprint 1;
filtros y búsqueda avanzada quedan para sprints posteriores.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from core.logger import LOG_FILE, get_logger

logger = get_logger(__name__)


class LogsScreen(QWidget):
    """Pantalla de visualización de logs del sistema."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self._load_logs)

        layout.addWidget(refresh_button)
        layout.addWidget(self.text_area)

        self._load_logs()

    def _load_logs(self) -> None:
        """Carga el contenido actual del archivo de log en pantalla."""
        if LOG_FILE.exists():
            content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            self.text_area.setPlainText(content[-20_000:])  # últimas líneas
        else:
            self.text_area.setPlainText("Aún no hay logs generados.")
