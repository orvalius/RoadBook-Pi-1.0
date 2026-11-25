"""Widget Qt de la tira de Roadbook (Roadbook Rendering Engine).

Renderiza continuamente la secuencia de ``RoadbookEntry`` de la ruta
activa: tulipa (para qué lado dobla y cuánto) + distancia parcial/total
+ giro en texto + instrucción, con la entrada actual resaltada y con su
propia barra de progreso, las pasadas atenuadas, y auto-scroll para
mantener la actual siempre visible — igual que un libro de ruta de
rally real, pero en vivo. Arriba, una tarjeta grande con la próxima
curva y la distancia que falta para llegar.
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
from ui.screens.tulip_widget import TulipWidget

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


TURN_STYLE = "color: {color}; font-size: 13px; font-weight: 700;"


def _end_kind(entry: RoadbookEntry) -> str:
    """Qué dibujar en una nota sin giro: la primera es largada, el resto llegada."""
    return "largada" if entry.orden == 0 else "llegada"


def turn_caption(entry: RoadbookEntry) -> str:
    """Texto del giro de una nota: 'Derecha 45° · media', 'Largada', etc."""
    icon = ICON_MAP.get(entry.waypoint.icono or "generico", "")
    prefix = "" if entry.waypoint.icono in (None, "generico") else f"{icon} "
    giro = entry.giro
    if giro is None:
        return f"{prefix}{_end_kind(entry).capitalize()}"
    if giro.severidad:
        return f"{prefix}{giro.texto} · {giro.severidad}"
    return f"{prefix}{giro.texto}"


class NextTurnCard(QFrame):
    """Tarjeta grande con la próxima curva: tulipa, giro y distancia que falta."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("nextTurn")
        self.setStyleSheet(
            "QFrame#nextTurn { background: #232935; border-bottom: 1px solid #2a3140; }"
        )
        self.tulip = TulipWidget(64)
        self.tulip.set_tone("current")
        self.turn_label = QLabel("—")
        self.turn_label.setStyleSheet(
            "color: #ff8a00; font-size: 22px; font-weight: 700;"
        )
        self.distance_label = QLabel("")
        self.distance_label.setStyleSheet(
            "color: #e8e6e1; font-size: 15px; font-weight: 600;"
        )
        self.name_label = QLabel("")
        self.name_label.setStyleSheet("color: #8b93a1; font-size: 11.5px;")
        self.name_label.setWordWrap(True)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.setContentsMargins(0, 0, 0, 0)
        texts.addWidget(self.turn_label)
        texts.addWidget(self.distance_label)
        texts.addWidget(self.name_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        layout.addWidget(self.tulip, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(texts, 1)

    def show_entry(self, entry: RoadbookEntry, distance_m: float | None) -> None:
        """Muestra la nota que viene y cuánto falta para llegar."""
        self.tulip.set_turn(entry.giro, kind=_end_kind(entry))
        giro = entry.giro
        self.turn_label.setText(
            _end_kind(entry).capitalize() if giro is None else giro.texto
        )
        parts = [giro.severidad] if giro is not None and giro.severidad else []
        if distance_m is not None:
            parts.append(f"en {_format_distance(distance_m)}")
        self.distance_label.setText(" · ".join(parts))
        self.name_label.setText(entry.waypoint.nombre)


def _format_distance(meters: float) -> str:
    """'350 m' por debajo de 1 km, '12,4 km' por encima."""
    if meters < 1000:
        # Redondeo hacia arriba en .5 (round() de Python redondea al par: 345 -> 340).
        return f"{int(meters / 10 + 0.5) * 10} m"
    return f"{meters / 1000:.1f} km".replace(".", ",")


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
        self.tulip = TulipWidget(40)
        self.tulip.set_turn(self.entry.giro, kind=_end_kind(self.entry))

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

        self.turn_label = QLabel(turn_caption(self.entry))
        self.turn_label.setWordWrap(True)
        self.text_label = QLabel(
            self.entry.waypoint.descripcion or self.entry.waypoint.nombre
        )
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #e8e6e1; font-size: 12.5px;")
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(1)
        text_box.addWidget(self.turn_label)
        text_box.addWidget(self.text_label)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.addWidget(self.tulip, 0, Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(km_container, 0, Qt.AlignmentFlag.AlignTop)
        top_row.addLayout(text_box, 1)

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
            self.turn_label.setStyleSheet(TURN_STYLE.format(color="#ff8a00"))
            self.tulip.set_tone("current")
            self.progress_bar.show()
            self.progress_bar.setValue(int(max(0.0, min(1.0, progress)) * 100))
        elif state == "passed":
            self.setStyleSheet(
                "QFrame#roadbookRow { background: transparent; border-bottom: 1px "
                "solid #2a3140; }"
            )
            self.text_label.setStyleSheet("color: #4a5160; font-size: 12.5px;")
            self.turn_label.setStyleSheet(TURN_STYLE.format(color="#4a5160"))
            self.tulip.set_tone("passed")
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
            self.turn_label.setStyleSheet(TURN_STYLE.format(color="#e8e6e1"))
            self.tulip.set_tone("upcoming")
            self.total_label.setStyleSheet(
                "color: #e8e6e1; font-weight: 600; font-family: monospace; "
                "font-size: 12px;"
            )
            self.progress_bar.hide()


STRIP_BG = "#1c2128"


class RoadbookStripWidget(QWidget):
    """Tira scrolleable con la secuencia completa del roadbook activo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[RoadbookEntryRow] = []
        self._entries: list[RoadbookEntry] = []
        self._build_ui()

    def _build_ui(self) -> None:
        # Reglas con selector a propósito: una regla suelta como
        # "background: transparent" en el QScrollArea se hereda a todas
        # las filas y deja ver el fondo claro de la ventana debajo del
        # texto claro de la tira (ilegible). Ver test_ui_roadbook_strip.
        self.setObjectName("roadbookStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#roadbookStrip, #roadbookContainer {{ background: {STRIP_BG}; }}"
            f"QScrollArea {{ background: {STRIP_BG}; border: none; }}"
            f"QScrollArea > QWidget {{ background: {STRIP_BG}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("ROADBOOK")
        header.setStyleSheet(
            "color: #8b93a1; font-size: 11px; letter-spacing: 2px; "
            "padding: 10px 14px; border-bottom: 1px solid #2a3140;"
        )
        layout.addWidget(header)

        self.next_card = NextTurnCard()
        self.next_card.hide()
        layout.addWidget(self.next_card)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.container = QWidget()
        self.container.setObjectName("roadbookContainer")
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
            # El cartel de "sin ruta" se reutiliza: no destruirlo.
            if widget is not None and widget is not self.empty_label:
                widget.deleteLater()

        self._rows = []
        self._entries = list(entries)

        if not entries:
            self.container_layout.addWidget(self.empty_label)
            self.empty_label.show()
            self.next_card.hide()
            return

        self.empty_label.hide()
        self.next_card.show_entry(entries[0], None)
        self.next_card.show()

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
            self.next_card.show_entry(
                self._entries[state.current_index], state.distance_to_next_m
            )
            current_row = self._rows[state.current_index]
            self.scroll_area.ensureWidgetVisible(current_row, yMargin=80)
