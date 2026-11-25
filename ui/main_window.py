"""Main Window de RoadBook Pi.

Ventana principal de la aplicación. Contiene un QStackedWidget que
aloja cada pantalla (Inicio, Navegación, Waypoints, Biblioteca,
Configuración, Logs). Esta ventana nunca accede al GPS ni a la base
de datos directamente: todo pasa por el Core inyectado.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from core.action_dispatcher import ActionType
from core.audio_manager import AudioManager
from core.config_manager import ConfigManager
from core.logger import get_logger
from core.map_manager import MapManager
from core.navigation_engine import NavigationEngine
from core.plugin_manager import PluginManager
from core.resource_manager import ResourceManager
from core.roadbook_engine import RoadbookEngine, build_entries
from core.route import resolve_route_order
from database.action_repository import ActionRepository
from database.waypoint_repository import WaypointRepository
from ui.screens.library import LibraryScreen
from ui.screens.logs import LogsScreen
from ui.screens.navigation import NavigationScreen
from ui.screens.settings import SettingsScreen
from ui.screens.waypoints import WaypointsScreen

logger = get_logger(__name__)

SCREEN_NAMES = ["Navegación", "Waypoints", "Biblioteca", "Configuración", "Logs"]


class MainWindow(QMainWindow):
    """Ventana principal de RoadBook Pi.

    Attributes:
        config: Instancia de ``ConfigManager`` compartida por toda la UI.
    """

    def __init__(
        self,
        config: ConfigManager,
        waypoint_repository: WaypointRepository,
        navigation_engine: NavigationEngine,
        resource_manager: ResourceManager,
        audio_manager: AudioManager,
        action_repository: ActionRepository,
        plugin_manager: PluginManager,
        map_manager: MapManager | None = None,
        roadbook_engine: RoadbookEngine | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.waypoint_repository = waypoint_repository
        self.navigation_engine = navigation_engine
        self.resource_manager = resource_manager
        self.audio_manager = audio_manager
        self.action_repository = action_repository
        self.plugin_manager = plugin_manager
        self.map_manager = map_manager
        self.roadbook_engine = roadbook_engine

        self.setWindowTitle(self.config.get("app_name", "RoadBook Pi"))
        width = self.config.get("display.width", 800)
        height = self.config.get("display.height", 480)
        self.resize(width, height)
        if self.config.get("display.fullscreen", False):
            self.showFullScreen()

        self._build_ui()
        logger.info("MainWindow inicializada")

    def _build_ui(self) -> None:
        """Construye el layout principal: menú lateral + stack de pantallas."""
        central = QWidget()
        layout = QHBoxLayout(central)

        self.menu_list = QListWidget()
        self.menu_list.addItems(SCREEN_NAMES)
        self.menu_list.setFixedWidth(160)
        self.menu_list.currentRowChanged.connect(self._on_menu_selected)

        self.stack = QStackedWidget()
        self.navigation_screen = NavigationScreen(
            map_manager=self.map_manager,
            map_zoom=self.config.get("maps.default_zoom", 15),
            map_redraw_threshold_meters=self.config.get(
                "maps.redraw_threshold_meters", 20.0
            ),
            image_display_seconds=self.config.get(
                "graphics.image_display_seconds", 5.0
            ),
            roadbook_engine=self.roadbook_engine,
        )
        self.stack.addWidget(self.navigation_screen)
        self.stack.addWidget(
            WaypointsScreen(
                self.waypoint_repository,
                self.resource_manager,
                self.action_repository,
                on_change=self._reload_navigation_waypoints,
            )
        )
        self.stack.addWidget(LibraryScreen(self.resource_manager, self.audio_manager))
        self.stack.addWidget(SettingsScreen(self.config))
        self.stack.addWidget(LogsScreen())

        layout.addWidget(self.menu_list)
        layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)
        self.menu_list.setCurrentRow(0)

    def _on_menu_selected(self, index: int) -> None:
        """Cambia de pantalla según la selección del menú lateral.

        Args:
            index: Índice de la pantalla seleccionada.
        """
        if index >= 0:
            self.stack.setCurrentIndex(index)
            logger.debug("Pantalla cambiada a: %s", SCREEN_NAMES[index])

    def _reload_navigation_waypoints(self) -> None:
        """Recarga los waypoints activos en el NavigationEngine y reconstruye
        la ruta del RoadbookEngine.

        Se invoca cada vez que la UI crea, edita, borra o activa/
        desactiva un waypoint, para que tanto el disparo de eventos
        como la tira de roadbook reflejen siempre el conjunto correcto,
        sin reiniciar la aplicación.
        """
        waypoints = self.waypoint_repository.list_all(only_active=True)
        self.navigation_engine.load_waypoints(waypoints)
        logger.info(
            "NavigationEngine recargado con %d waypoints activos", len(waypoints)
        )

        gpx_path = self.config.get("roadbook.gpx_path", None)
        ordered = resolve_route_order(waypoints, gpx_path)
        entries = build_entries(ordered)
        self.roadbook_engine = RoadbookEngine(entries)
        self.navigation_screen.set_roadbook_engine(self.roadbook_engine)
        logger.info("RoadbookEngine reconstruido con %d entradas", len(entries))

    def handle_action(self, action_type: ActionType, payload: dict) -> None:
        """Ejecuta la reacción de UI/Audio para una acción despachada.

        Conectado a ``QtActionAdapter.action_triggered``. Cada acción
        llega desde el ``EventEngine`` (que puede correr en el hilo
        del GPS o en un hilo de ``threading.Timer``); Qt garantiza que
        este método se ejecuta en el hilo principal.

        Args:
            action_type: Tipo de acción a ejecutar.
            payload: Datos de la acción (ej: {"path": "..."}).
        """
        if action_type is ActionType.SHOW_IMAGE:
            self._handle_show_image(payload)
        elif action_type is ActionType.HIDE_IMAGE:
            self.navigation_screen.hide_image()
        elif action_type is ActionType.PLAY_AUDIO:
            self._handle_play_audio(payload)
        elif action_type is ActionType.LOG_EVENT:
            logger.info("EVENTO: %s", payload.get("message", ""))
        elif action_type is ActionType.RUN_PLUGIN:
            self._handle_run_plugin(payload)
        else:
            logger.warning(
                "handle_action: tipo de acción no reconocido: %s", action_type
            )

    def _handle_show_image(self, payload: dict) -> None:
        relative_path = payload.get("path")
        if not relative_path:
            logger.warning("Acción show_image sin 'path' en el payload")
            return

        image_path = self.resource_manager.resolve_relative_path(relative_path)
        if not image_path.exists():
            logger.warning("Acción show_image: archivo inexistente: %s", image_path)
            return

        # Llevar al usuario a la pantalla de navegación para que vea el evento
        self.menu_list.setCurrentRow(0)
        # auto_hide=False: el ocultado lo controla la propia secuencia de
        # acciones (WAIT + HIDE_IMAGE), no el timer interno de la pantalla.
        self.navigation_screen.show_image(image_path, auto_hide=False)

    def _handle_play_audio(self, payload: dict) -> None:
        relative_path = payload.get("path")
        if not relative_path:
            logger.warning("Acción play_audio sin 'path' en el payload")
            return

        audio_path = self.resource_manager.resolve_relative_path(relative_path)
        if not audio_path.exists():
            logger.warning("Acción play_audio: archivo inexistente: %s", audio_path)
            return

        self.audio_manager.play(audio_path)

    def _handle_run_plugin(self, payload: dict) -> None:
        plugin_name = payload.get("plugin_name")
        if not plugin_name:
            logger.warning("Acción run_plugin sin 'plugin_name' en el payload")
            return

        plugin = self.plugin_manager.get(plugin_name)
        if plugin is None:
            logger.warning(
                "Plugin '%s' no está cargado (¿falta en plugins.enabled de "
                "la config, o el archivo no existe en plugins/?)",
                plugin_name,
            )
            return

        try:
            plugin.execute(payload)
        except Exception:
            logger.exception("Error ejecutando el plugin '%s'", plugin_name)
