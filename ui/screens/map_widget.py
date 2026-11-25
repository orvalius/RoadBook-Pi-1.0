"""Widget Qt del mapa offline.

Única pieza que combina Pillow (composición de tiles) con Qt
(renderizado). El resto de la lógica de mapas (``core/map_manager.py``,
``core/map_compositor.py``) es puro y no sabe que Qt existe.

Dos capas:

- **Base**: los tiles del .mbtiles, compuestos con Pillow. Es lo caro
  (decodificar PNG/JPG), así que solo se recompone cuando el vehículo
  se acerca al borde de la zona visible, cuando cambia el zoom o el
  tamaño. El centro se adelanta en la dirección de marcha para que se
  vea más camino por delante.
- **Encima**, en cada posición GPS: la ruta, las notas (la próxima
  resaltada) y el vehículo, dibujados con QPainter sobre una copia de
  la base. Es barato, así el punto se mueve fluido incluso en una Pi 2.

Sin mapa offline también se dibujan la ruta y el vehículo sobre un
fondo liso: se puede navegar igual, solo falta el fondo.
"""

from __future__ import annotations

import math

from PIL import Image
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QLabel, QWidget

from core.logger import get_logger
from core.map_compositor import (
    CachedTileSource,
    MapViewport,
    compose_map_image,
    look_ahead_center,
)
from core.map_manager import MapManager

logger = get_logger(__name__)

DEFAULT_ZOOM = 15
DEFAULT_REDRAW_THRESHOLD_METERS = 20.0
RECENTER_MARGIN = 0.2
"""Si el vehículo entra en este margen (fracción del lado), se recompone."""

NO_MAP_TEXT = "Sin mapa offline cargado"
NO_MAP_BG = QColor("#e9e6de")
ROUTE = QColor("#ff8a00")
ROUTE_CASING = QColor(40, 30, 20, 170)
VEHICLE = QColor("#1f6fff")
WHITE = QColor("#ffffff")
PASSED = QColor("#8b93a1")


class MapWidget(QLabel):
    """Mapa offline con la ruta y el vehículo en vivo.

    Attributes:
        map_manager: Fuente de tiles (None o sin mbtiles = fondo liso).
        zoom: Nivel de zoom actual.
        redraw_threshold_meters: Se conserva por compatibilidad con la
            configuración (``maps.redraw_threshold_meters``); el
            recompuesto ahora lo decide la cercanía al borde.
    """

    def __init__(
        self,
        map_manager: MapManager | None,
        zoom: int = DEFAULT_ZOOM,
        redraw_threshold_meters: float = DEFAULT_REDRAW_THRESHOLD_METERS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.map_manager = map_manager
        self._tile_source = (
            CachedTileSource(map_manager) if map_manager is not None else None
        )
        self.zoom = zoom
        self.redraw_threshold_meters = redraw_threshold_meters

        self._last_lat: float | None = None
        self._last_lon: float | None = None
        self._heading: float | None = None
        self._route: list[tuple[float, float]] = []
        self._current_index = 0
        self._base: QPixmap | None = None
        self._viewport: MapViewport | None = None

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #dedede; color: #666;")
        self.setMinimumSize(200, 200)

        if not self.has_map:
            self.setText(NO_MAP_TEXT)

    @property
    def has_map(self) -> bool:
        """True si hay un mbtiles cargado y disponible."""
        return self.map_manager is not None and self.map_manager.is_available

    @property
    def viewport(self) -> MapViewport | None:
        """Zona del mundo que muestra la base actual (None si no hay base)."""
        return self._viewport

    # ----------------------------------------------------------- API

    def set_route(
        self, points: list[tuple[float, float]], current_index: int = 0
    ) -> None:
        """Define la ruta a dibujar (notas en orden) y cuál es la próxima."""
        self._route = list(points)
        self._current_index = current_index
        self._render()

    def set_current_index(self, index: int) -> None:
        """Marca qué nota es la próxima (se resalta en el mapa)."""
        if index != self._current_index:
            self._current_index = index
            self._render()

    def update_vehicle(
        self, lat: float, lon: float, heading: float | None = None
    ) -> None:
        """Mueve el vehículo; recompone la base solo si hace falta."""
        self._heading = heading
        self.update_center(lat, lon)

    def update_center(self, lat: float, lon: float, force: bool = False) -> None:
        """Ubica el vehículo en ``lat, lon`` y redibuja.

        Args:
            lat: Latitud del vehículo.
            lon: Longitud del vehículo.
            force: Si True, recompone la base aunque no haga falta.
        """
        self._last_lat, self._last_lon = lat, lon
        if force or self._needs_recompose(lat, lon):
            self._compose_base(lat, lon)
        self._render()

    def set_zoom(self, zoom: int) -> None:
        """Cambia el nivel de zoom y fuerza un redibujo."""
        self.zoom = zoom
        if self._last_lat is not None and self._last_lon is not None:
            self.update_center(self._last_lat, self._last_lon, force=True)

    def reload_source(self) -> None:
        """Rearma la fuente de tiles tras cambiar el archivo del MapManager.

        Descarta el cache de tiles decodificados (pertenecen al mapa
        anterior) y redibuja en la última posición conocida.
        """
        self._tile_source = (
            CachedTileSource(self.map_manager) if self.map_manager is not None else None
        )
        self._base = None
        self._viewport = None
        self.clear()
        if self._last_lat is not None and self._last_lon is not None:
            self.update_center(self._last_lat, self._last_lon, force=True)
        elif not self.has_map:
            self.setText(NO_MAP_TEXT)

    # ----------------------------------------------------------- Interno

    def _needs_recompose(self, lat: float, lon: float) -> bool:
        view = self._viewport
        return (
            view is None
            or view.zoom != self.zoom
            or (view.width, view.height) != (self.width(), self.height())
            or not view.contains_inner(lat, lon, RECENTER_MARGIN)
        )

    def _compose_base(self, lat: float, lon: float) -> None:
        width, height = max(self.width(), 100), max(self.height(), 100)
        center = look_ahead_center(lat, lon, self._heading, self.zoom, width, height)
        self._viewport = MapViewport(center[0], center[1], self.zoom, width, height)
        ratio = self.devicePixelRatioF()
        if self.has_map:
            image = compose_map_image(
                self._tile_source, center[0], center[1], self.zoom, width, height
            )
            pixmap = pil_to_pixmap(image)
            # La base se escala a la densidad de la pantalla; lo que se dibuja
            # encima (ruta, vehículo) queda nítido.
            if ratio != 1.0:
                pixmap = pixmap.scaled(
                    int(width * ratio),
                    int(height * ratio),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        else:
            pixmap = QPixmap(int(width * ratio), int(height * ratio))
            pixmap.fill(NO_MAP_BG)
        pixmap.setDevicePixelRatio(ratio)
        self._base = pixmap

    def _render(self) -> None:
        if self._base is None or self._viewport is None:
            return
        frame = self._base.copy()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_route(painter)
        self._draw_vehicle(painter)
        if not self.has_map:
            self._draw_no_map_note(painter)
        painter.end()
        self.setPixmap(frame)

    def _px(self, lat: float, lon: float) -> QPointF:
        assert self._viewport is not None
        return QPointF(*self._viewport.to_pixel(lat, lon))

    def _draw_route(self, painter: QPainter) -> None:
        if len(self._route) < 1:
            return
        points = [self._px(lat, lon) for lat, lon in self._route]
        if len(points) >= 2:
            line = QPolygonF(points)
            painter.setPen(_pen(ROUTE_CASING, 7))
            painter.drawPolyline(line)
            painter.setPen(_pen(ROUTE, 4))
            painter.drawPolyline(line)

        font = QFont(painter.font())
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        for i, point in enumerate(points):
            if i == self._current_index:
                continue
            fill = PASSED if i < self._current_index else WHITE
            painter.setPen(QPen(QColor("#1c2128"), 2))
            painter.setBrush(fill)
            painter.drawEllipse(point, 5.5, 5.5)
        if 0 <= self._current_index < len(points):
            target = points[self._current_index]
            painter.setPen(QPen(WHITE, 3))
            painter.setBrush(ROUTE)
            painter.drawEllipse(target, 9, 9)
            painter.setPen(QColor("#1c2128"))
            painter.drawText(
                QRectF(target.x() - 9, target.y() - 9, 18, 18),
                Qt.AlignmentFlag.AlignCenter,
                str(self._current_index + 1),
            )

    def _draw_vehicle(self, painter: QPainter) -> None:
        if self._last_lat is None or self._last_lon is None:
            return
        center = self._px(self._last_lat, self._last_lon)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(31, 111, 255, 55))
        painter.drawEllipse(center, 22, 22)
        if self._heading is None:
            painter.setPen(QPen(WHITE, 3))
            painter.setBrush(VEHICLE)
            painter.drawEllipse(center, 9, 9)
            return
        rad = math.radians(self._heading)

        def rot(dx: float, dy: float) -> QPointF:
            # (dx, dy) en el sistema del vehículo: y negativo = hacia adelante.
            return QPointF(
                center.x() + dx * math.cos(rad) - dy * math.sin(rad),
                center.y() + dx * math.sin(rad) + dy * math.cos(rad),
            )

        arrow = QPolygonF([rot(0, -16), rot(11, 11), rot(0, 5), rot(-11, 11)])
        painter.setPen(
            QPen(
                WHITE,
                3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(VEHICLE)
        painter.drawPolygon(arrow)

    def _draw_no_map_note(self, painter: QPainter) -> None:
        font = QFont(painter.font())
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#6b6f78"))
        painter.drawText(
            QRectF(10, 8, self.width() - 20, 20),
            Qt.AlignmentFlag.AlignLeft,
            "Sin mapa offline: solo ruta y posición",
        )


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    """Convierte una imagen de Pillow a QPixmap con copia profunda.

    ``QPixmap.fromImage(ImageQt(img))`` puede quedar apuntando al buffer
    del objeto ``ImageQt`` temporal: cuando Python lo libera, parte del
    mapa se ve como franjas de basura. Acá los bytes se copian a un
    ``QImage`` propio antes de soltar el buffer.
    """
    rgb = image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimage = QImage(
        data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888
    ).copy()
    return QPixmap.fromImage(qimage)


def _pen(color: QColor, width: float) -> QPen:
    return QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
