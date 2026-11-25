"""Widget Qt de la tira de Roadbook (Roadbook Rendering Engine).

Renderiza continuamente la secuencia de ``RoadbookEntry`` de la ruta
activa: ícono + distancia parcial/total + texto de instrucción, con la
entrada actual resaltada y con su propia barra de progreso, las
pasadas atenuadas, y auto-scroll para mantener la actual siempre
visible — igual que un libro de ruta de rally real, pero en vivo.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.roadbook_engine import RoadbookEntry, RoadbookState

# Pictogramas de relleno (símbolos Unicode). Corresponden al campo
# Waypoint.icono; se puede ampliar sin tocar el resto del widget.
ICON_MAP: dict[str, str] = {
    "curva_izq": "↰",
    "curva_der": "↱",
    "peligro": "⚠",
    "vado": "〜",
    "recta": "↑",
    "largada": "🏁",
    "llegada": "🏁",
    "stop": "■",
    "fuente": "⛽",
    "generico": "●",
}


def _format_km(meters: float) -> str:
    """Formatea metros como kilómetros con coma decimal, estilo libro de ruta."""
    return f"{meters / 1000:.2f}".replace(".", ",")


class RoadbookEntryRow(QFrame):
    """Una fila de la tira: ícono + distancia parcial/total + texto.

    Attributes:
        entry: La ``RoadbookEntry`` que representa esta fila.
    """

    def __init__(self, entry: RoadbookEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("roadbookRow")
        self._build_ui()
        self.set_state("upcoming")

    def _build_ui(self) -> None:
        icon_text = ICON_MAP.get(self.entry.waypoint.icono or "generico", "●")

        self.icon_label = QLabel(icon_text)
        self.icon_label.setFixedSize(34, 34)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(
            "background: #232935; border: 1px solid #2a3140; border-radius: 8px; "
            "font-size: 16px;"
        )

        km_layout = QVBoxLayout()
        km_layout.setSpacing(0)
        km_layout.setContentsMargins(0, 0, 0, 0)
        self.total_label = QLabel(_format_km(self.entry.distancia_total_m))
        self.total_label.setStyleSheet(
            "color: #e8e6e1; font-weight: 600; font-family: monospace; font-size: 12px;"
        )
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.parcial_label = QLabel(_format_km(self.entry.distancia_parcial_m))
        self.parcial_label.setStyleSheet(
            "color: #8b93a1; font-size: 10px; font-family: monospace;"
        )
        self.parcial_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        km_layout.addWidget(self.total_label)
        km_layout.addWidget(self.parcial_label)
        km_container = QWidget()
        km_container.setLayout(km_layout)
        km_container.setFixedWidth(60)

        self.text_label = QLabel(
            self.entry.waypoint.descripcion or self.entry.waypoint.nombre
        )
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #e8e6e1; font-size: 12.5px;")

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.addWidget(self.icon_label)
        top_row.addWidget(km_container)
        top_row.addWidget(self.text_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background: #6b4118; border: none; }"
            "QProgressBar::chunk { background: #ff8a00; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 6)
        outer.setSpacing(6)
        outer.addLayout(top_row)
        outer.addWidget(self.progress_bar)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QFrame#roadbookRow { border-bottom: 1px solid #2a3140; }")

    def set_state(self, state: str, progress: float = 0.0) -> None:
        """Aplica el estado visual de la fila.

        Args:
            state: Uno de ``"passed"``, ``"current"``, ``"upcoming"``.
            progress: Fracción 0.0-1.0 (solo se usa si state=="current").
        """
        if state == "current":
            self.setStyleSheet(
                "QFrame#roadbookRow { background: rgba(255,138,0,0.14); "
                "border-left: 3px solid #ff8a00; border-bottom: 1px solid #2a3140; }"
            )
            self.text_label.setStyleSheet(
                "color: #e8e6e1; font-size: 12.5px; font-weight: 600;"
            )
            self.total_label.setStyleSheet(
                "color: #ff8a00; font-weight: 600; font-family: monospace; "
                "font-size: 12px;"
            )
            self.progress_bar.show()
            self.progress_bar.setValue(int(max(0.0, min(1.0, progress)) * 100))
        elif state == "passed":
            self.setStyleSheet(
                "QFrame#roadbookRow { background: transparent; border-bottom: 1px "
                "solid #2a3140; }"
            )
            self.text_label.setStyleSheet("color: #4a5160; font-size: 12.5px;")
            self.total_label.setStyleSheet(
                "color: #4a5160; font-weight: 600; font-family: monospace; "
                "font-size: 12px;"
            )
            self.progress_bar.hide()
        else:  # upcoming
            self.setStyleSheet(
                "QFrame#roadbookRow { background: transparent; border-bottom: 1px "
                "solid #2a3140; }"
            )
            self.text_label.setStyleSheet("color: #e8e6e1; font-size: 12.5px;")
            self.total_label.setStyleSheet(
                "color: #e8e6e1; font-weight: 600; font-family: monospace; "
                "font-size: 12px;"
            )
            self.progress_bar.hide()


class RoadbookStripWidget(QWidget):
    """Tira scrolleable con la secuencia completa del roadbook activo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[RoadbookEntryRow] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet("background: #1c2128;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("ROADBOOK")
        header.setStyleSheet(
            "color: #8b93a1; font-size: 11px; letter-spacing: 2px; "
            "padding: 10px 14px; border-bottom: 1px solid #2a3140;"
        )
        layout.addWidget(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.container_layout.addStretch()

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area, 1)

        self.empty_label = QLabel("Sin ruta de roadbook activa")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #565d6b; font-size: 12px; padding: 20px;"
        )
        self.container_layout.insertWidget(0, self.empty_label)

    def set_entries(self, entries: list[RoadbookEntry]) -> None:
        """(Re)construye las filas para una nueva lista de entradas.

        Args:
            entries: Entradas de la ruta activa, en orden. Lista vacía
                muestra el mensaje de "sin ruta activa".
        """
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._rows = []

        if not entries:
            self.container_layout.addWidget(self.empty_label)
            return

        for entry in entries:
            row = RoadbookEntryRow(entry)
            self.container_layout.addWidget(row)
            self._rows.append(row)
        self.container_layout.addStretch()

    def update_state(self, state: RoadbookState) -> None:
        """Actualiza el resaltado, atenuado y auto-scroll según el estado actual.

        Args:
            state: Snapshot devuelto por ``RoadbookEngine.update_position``.
        """
        if not self._rows:
            return

        for i, row in enumerate(self._rows):
            if i < state.current_index:
                row.set_state("passed")
            elif i == state.current_index:
                row.set_state("current", progress=state.progress_fraction)
            else:
                row.set_state("upcoming")

        if 0 <= state.current_index < len(self._rows):
            current_row = self._rows[state.current_index]
            self.scroll_area.ensureWidgetVisible(current_row, yMargin=80)
