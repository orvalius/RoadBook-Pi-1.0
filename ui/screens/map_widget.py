"""Widget Qt del mapa offline.

Única pieza que combina Pillow (composición de tiles) con Qt
(renderizado). El resto de la lógica de mapas (``core/map_manager.py``,
``core/map_compositor.py``) es puro y no sabe que Qt existe.
"""

from __future__ import annotations

from PIL.ImageQt import ImageQt
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget

from core.logger import get_logger
from core.map_compositor import CachedTileSource, compose_map_image, should_redraw
from core.map_manager import MapManager

logger = get_logger(__name__)

DEFAULT_ZOOM = 15
DEFAULT_REDRAW_THRESHOLD_METERS = 20.0


class MapWidget(QLabel):
    """Muestra el mapa offline centrado en la posición actual del vehículo.

    Attributes:
        map_manager: Fuente de tiles (None o sin mbtiles = placeholder).
        zoom: Nivel de zoom actual.
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

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #dedede; color: #666;")
        self.setMinimumSize(200, 200)

        if map_manager is None or not map_manager.is_available:
            self.setText("Sin mapa offline cargado")

    def update_center(self, lat: float, lon: float, force: bool = False) -> None:
        """Recompone el mapa centrado en una nueva posición, con throttling.

        Args:
            lat: Latitud del centro deseado.
            lon: Longitud del centro deseado.
            force: Si True, ignora el throttling y redibuja siempre.
        """
        if self.map_manager is None or not self.map_manager.is_available:
            return

        if not force and not should_redraw(
            self._last_lat, self._last_lon, lat, lon, self.redraw_threshold_meters
        ):
            return

        width = max(self.width(), 100)
        height = max(self.height(), 100)

        pil_image = compose_map_image(
            self._tile_source, lat, lon, self.zoom, width, height
        )
        qt_image = ImageQt(pil_image)
        pixmap = QPixmap.fromImage(qt_image)
        self.setPixmap(pixmap)

        self._last_lat = lat
        self._last_lon = lon

    def reload_source(self) -> None:
        """Rearma la fuente de tiles tras cambiar el archivo del MapManager.

        Descarta el cache de tiles decodificados (pertenecen al mapa
        anterior) y redibuja en la última posición conocida.
        """
        self._tile_source = (
            CachedTileSource(self.map_manager) if self.map_manager is not None else None
        )
        self.clear()
        if self.map_manager is None or not self.map_manager.is_available:
            self.setText("Sin mapa offline cargado")
            return
        self.setText("")
        if self._last_lat is not None and self._last_lon is not None:
            self.update_center(self._last_lat, self._last_lon, force=True)

    def set_zoom(self, zoom: int) -> None:
        """Cambia el nivel de zoom y fuerza un redibujo.

        Args:
            zoom: Nuevo nivel de zoom.
        """
        self.zoom = zoom
        if self._last_lat is not None and self._last_lon is not None:
            self.update_center(self._last_lat, self._last_lon, force=True)
