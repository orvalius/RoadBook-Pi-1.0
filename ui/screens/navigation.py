"""Pantalla de Navegación (modo conducción).

Rediseño del Graphic Engine (Sprint 6) como **Roadbook Rendering
Engine**: en vez de limitarse a mostrar/ocultar una imagen puntual,
la pantalla ahora tiene una tira de roadbook continua (estilo rally
raid) que se renderiza en vivo junto al mapa, sincronizada con la
posición GPS.

Capas (de abajo hacia arriba):

1. Fila principal: mapa offline (izquierda) + tira de roadbook
   (derecha) — el "split" característico de un navegador de rally.
2. Readout de posición/velocidad/rumbo (semi-transparente), superpuesto.
3. Overlay de imagen que dispara un waypoint al ser alcanzado
   (Event Engine, Sprint 8), sin cambios: sigue siendo una acción más
   entre varias, ahora coexistiendo con la tira en vez de ser el
   centro del sistema.

Importante: el ``RoadbookEngine`` (qué mostrar en la tira, avance
secuencial) es independiente del ``NavigationEngine``/``EventEngine``
(qué acciones disparar). Esta pantalla no dispara ninguna acción por
sí misma; solo visualiza.
"""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QStackedLayout, QVBoxLayout, QWidget

from core.gps_manager import GpsPosition
from core.graphic_utils import compute_scaled_size
from core.logger import get_logger
from core.map_manager import MapManager
from core.roadbook_engine import RoadbookEngine
from core.time_format import format_duration_seconds
from ui.screens.map_widget import MapWidget
from ui.screens.roadbook_strip_widget import RoadbookStripWidget

logger = get_logger(__name__)


def _route_points(entries: list) -> list[tuple[float, float]]:
    """Posiciones de las notas de la ruta, en orden, para dibujar en el mapa."""
    return [(e.waypoint.latitud, e.waypoint.longitud) for e in entries]


DEFAULT_IMAGE_DISPLAY_SECONDS = 5.0


class NavigationScreen(QWidget):
    """Pantalla principal de navegación / modo conducción."""

    def __init__(
        self,
        map_manager: MapManager | None = None,
        map_zoom: int = 15,
        map_redraw_threshold_meters: float = 20.0,
        image_display_seconds: float = DEFAULT_IMAGE_DISPLAY_SECONDS,
        roadbook_engine: RoadbookEngine | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.image_display_seconds = image_display_seconds
        self.roadbook_engine = roadbook_engine
        self._current_pixmap: QPixmap | None = None
        self._last_fix_time: float | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_image)

        self._build_ui(map_manager, map_zoom, map_redraw_threshold_meters)

        if self.roadbook_engine is not None:
            self.roadbook_strip.set_entries(self.roadbook_engine.entries)
            self.map_widget.set_route(_route_points(self.roadbook_engine.entries))

    def _build_ui(
        self,
        map_manager: MapManager | None,
        map_zoom: int,
        map_redraw_threshold_meters: float,
    ) -> None:
        outer_layout = QVBoxLayout(self)

        self._overlay_container = QWidget()
        self._overlay_layout = QStackedLayout(self._overlay_container)
        self._overlay_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        # Capa 1 (fondo): mapa + tira de roadbook, lado a lado
        main_split = QWidget()
        split_layout = QHBoxLayout(main_split)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(0)

        self.map_widget = MapWidget(
            map_manager,
            zoom=map_zoom,
            redraw_threshold_meters=map_redraw_threshold_meters,
        )
        self.roadbook_strip = RoadbookStripWidget()

        split_layout.addWidget(self.map_widget, 3)  # 1.5fr aprox
        split_layout.addWidget(self.roadbook_strip, 2)  # 1fr aprox

        # Capa 2: readout de texto, con fondo transparente para dejar ver el mapa
        readout_widget = QWidget()
        readout_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        readout_widget.setStyleSheet("background: transparent;")
        # Barra de lectura abajo y solo sobre la columna del mapa (mismas
        # proporciones 3:2 que el split): no tapa la tira ni el vehículo.
        readout_outer = QHBoxLayout(readout_widget)
        readout_outer.setContentsMargins(8, 8, 0, 8)
        readout_column = QWidget()
        readout_layout = QVBoxLayout(readout_column)
        readout_layout.setContentsMargins(0, 0, 0, 0)
        readout_layout.setSpacing(4)
        readout_outer.addWidget(readout_column)
        readout_outer.addStretch(1)
        self._readout_column = readout_column

        self.status_label = QLabel("Esperando señal GPS...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 140); color: white; padding: 6px; "
            "border-radius: 6px;"
        )
        font = self.status_label.font()
        font.setPointSize(13)
        self.status_label.setFont(font)

        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 140); color: white; padding: 4px; "
            "border-radius: 6px;"
        )

        readout_layout.addStretch()
        readout_layout.addWidget(self.status_label)
        readout_layout.addWidget(self.detail_label)

        # Capa 3 (frente): overlay de imagen de waypoints (Event Engine)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")
        self.image_label.hide()

        self._overlay_layout.addWidget(main_split)
        self._overlay_layout.addWidget(readout_widget)
        self._overlay_layout.addWidget(self.image_label)

        # En modo StackAll, QStackedLayout sube al frente el widget
        # "actual" (el índice 0: mapa + tira), que tapaba el readout y
        # la imagen de los waypoints. El orden visual se fija a mano.
        # El readout no debe capturar toques: si no, bloquea el scroll
        # de la tira que queda debajo.
        readout_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._readout_widget = readout_widget
        readout_widget.raise_()
        self.image_label.raise_()

        outer_layout.addWidget(self._overlay_container)

    def set_roadbook_engine(self, roadbook_engine: RoadbookEngine | None) -> None:
        """Reemplaza el motor de roadbook activo (ej: al cargar otra ruta).

        Args:
            roadbook_engine: Nuevo motor, o None para vaciar la tira.
        """
        self.roadbook_engine = roadbook_engine
        entries = roadbook_engine.entries if roadbook_engine is not None else []
        self.roadbook_strip.set_entries(entries)
        self.map_widget.set_route(_route_points(entries))

    @pyqtSlot(object)
    def update_position(self, position: GpsPosition) -> None:
        """Actualiza el readout, el mapa y la tira de roadbook con la posición GPS.

        Se conecta típicamente a ``QtGpsAdapter.position_received``.
        Al estar conectado desde un QWidget viviendo en el hilo
        principal, Qt encola automáticamente la entrega en ese hilo
        aunque la señal se emita desde el hilo del GPS. El
        ``RoadbookEngine`` se actualiza acá mismo, siempre en el hilo
        principal, sin necesitar un adapter propio.

        Args:
            position: Última posición GPS conocida.
        """
        if not position.has_fix:
            if self._last_fix_time is not None:
                elapsed = time.monotonic() - self._last_fix_time
                self.status_label.setText(
                    f"Sin fix GPS (última posición hace "
                    f"{format_duration_seconds(elapsed)})"
                )
            else:
                self.status_label.setText("Sin fix GPS")
            self.detail_label.setText("")
            return

        self._last_fix_time = time.monotonic()
        self.status_label.setText(f"{position.latitude:.6f}, {position.longitude:.6f}")
        heading_text = (
            f"{position.heading:.0f}°" if position.heading is not None else "—"
        )
        self.detail_label.setText(
            f"Velocidad: {position.speed:.0f} km/h    Rumbo: {heading_text}"
        )
        if self.roadbook_engine is not None:
            state = self.roadbook_engine.update_position(position)
            self.roadbook_strip.update_state(state)
            self.map_widget.set_current_index(state.current_index)
        self.map_widget.update_vehicle(
            position.latitude, position.longitude, position.heading
        )

    def show_image(
        self,
        image_path: str | Path,
        duration_seconds: float | None = None,
        auto_hide: bool = True,
    ) -> None:
        """Muestra una imagen a pantalla completa.

        Si ya había una imagen visible, la reemplaza y reinicia el
        timer de ocultado (no se acumulan imágenes ni timers viejos).

        Args:
            image_path: Ruta absoluta a la imagen a mostrar.
            duration_seconds: Tiempo antes de ocultarla automáticamente.
                Si es None, usa ``self.image_display_seconds``. Se
                ignora si ``auto_hide`` es False.
            auto_hide: Si es False, la imagen queda visible hasta que
                se llame explícitamente a ``hide_image()``. Lo usa el
                Event Engine (Sprint 8) cuando la secuencia de
                acciones controla el ocultado con sus propios pasos
                WAIT + HIDE_IMAGE, para no tener dos timers compitiendo.
        """
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            logger.warning("No se pudo cargar la imagen: %s", image_path)
            return

        self._current_pixmap = pixmap
        self._apply_scaled_pixmap()
        self.image_label.show()
        self.image_label.raise_()

        self._hide_timer.stop()
        if auto_hide:
            wait_ms = int((duration_seconds or self.image_display_seconds) * 1000)
            self._hide_timer.start(wait_ms)
        logger.info("Mostrando imagen: %s (auto_hide=%s)", image_path, auto_hide)

    def hide_image(self) -> None:
        """Oculta la imagen actual, si hay alguna visible."""
        self._hide_timer.stop()
        self._current_pixmap = None
        self.image_label.hide()
        self.image_label.clear()

    def _apply_scaled_pixmap(self) -> None:
        """Reescala el pixmap actual al tamaño disponible del label."""
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return

        target_width, target_height = compute_scaled_size(
            self._current_pixmap.width(),
            self._current_pixmap.height(),
            max(self.image_label.width(), 1),
            max(self.image_label.height(), 1),
        )
        scaled = self._current_pixmap.scaled(
            int(target_width),
            int(target_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: N802 - override de Qt
        """Reescala la imagen activa y ajusta la barra de lectura al mapa."""
        super().resizeEvent(event)
        self._apply_scaled_pixmap()
        self._fit_readout()

    def showEvent(self, event) -> None:  # noqa: N802 - override de Qt
        super().showEvent(event)
        self._fit_readout()

    def _fit_readout(self) -> None:
        # La barra de lectura ocupa exactamente el ancho del mapa.
        self._readout_column.setFixedWidth(max(self.map_widget.width() - 16, 120))
