"""RoadBook Pi - Punto de entrada de la aplicación.

Inicializa el logging, la configuración, la base de datos y arma el
pipeline completo GPS -> Navigation Engine, y lanza la interfaz
gráfica. Este es el único archivo que "arma" el sistema completo;
ningún módulo del Core o la UI debe hacer este trabajo por su cuenta.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.action_dispatcher import ActionDispatcher
from core.audio_manager import AudioManager
from core.config_manager import ConfigManager
from core.event_engine import EventEngine
from core.gps_manager import GpsManager
from core.logger import configure_logging, get_logger
from core.map_manager import MapManager
from core.navigation_engine import NavigationEngine
from core.plugin_manager import PluginManager
from core.resource_manager import ResourceManager
from database.action_repository import ActionRepository
from database.db_manager import DatabaseManager
from database.waypoint_repository import WaypointRepository
from ui.action_event_adapter import QtActionAdapter
from ui.gps_adapter import QtGpsAdapter
from ui.main_window import MainWindow
from ui.waypoint_event_adapter import WaypointEventAdapter

logger = get_logger(__name__)


def main() -> int:
    """Inicializa RoadBook Pi y ejecuta el loop principal de la aplicación.

    Returns:
        Código de salida del proceso.
    """
    configure_logging()
    logger.info("=== Iniciando RoadBook Pi ===")

    config = ConfigManager("config.json")

    db = DatabaseManager(config.get("database.path", "database/roadbook.db"))
    db.initialize_schema()
    waypoint_repository = WaypointRepository(db)
    action_repository = ActionRepository(db)
    resource_manager = ResourceManager()
    audio_manager = AudioManager(
        enabled=config.get("audio.enabled", True),
        volume=config.get("audio.volume", 0.8),
    )
    map_manager = MapManager(config.get("maps.mbtiles_path", "resources/maps/default.mbtiles"))

    plugin_manager = PluginManager()
    loaded_plugins = plugin_manager.load_from_directory(
        config.get("plugins.directory", "plugins"),
        config.get("plugins.enabled", []),
    )
    if loaded_plugins:
        logger.info("Plugins cargados: %s", loaded_plugins)

    navigation_engine = NavigationEngine(
        heading_tolerance_degrees=config.get("navigation.heading_tolerance_degrees", 45.0)
    )
    navigation_engine.load_waypoints(waypoint_repository.list_all(only_active=True))

    action_dispatcher = ActionDispatcher()
    event_engine = EventEngine(
        action_dispatcher,
        action_repository=action_repository,
        default_image_display_seconds=config.get("graphics.image_display_seconds", 5.0),
    )

    gps_manager = GpsManager(
        backend=config.get("gps.backend", "simulator"),
        gpsd_host=config.get("gps.gpsd_host", "127.0.0.1"),
        gpsd_port=config.get("gps.gpsd_port", 2947),
        serial_port=config.get("gps.serial_port", "/dev/ttyUSB0"),
        serial_baudrate=config.get("gps.serial_baudrate", 9600),
        simulator_interval=config.get("gps.simulator_interval_seconds", 1.0),
        reconnect_interval_seconds=config.get("gps.reconnect_interval_seconds", 5.0),
    )

    app = QApplication(sys.argv)

    gps_adapter = QtGpsAdapter(gps_manager)
    gps_adapter.position_received.connect(navigation_engine.update_position)

    waypoint_adapter = WaypointEventAdapter(navigation_engine)
    waypoint_adapter.waypoint_reached.connect(event_engine.handle_waypoint)

    action_adapter = QtActionAdapter(action_dispatcher)

    window = MainWindow(
        config, waypoint_repository, navigation_engine, resource_manager, audio_manager,
        action_repository, plugin_manager,
        map_manager=map_manager,
    )
    window.show()
    gps_adapter.position_received.connect(window.navigation_screen.update_position)
    action_adapter.action_triggered.connect(window.handle_action)

    gps_adapter.start()

    exit_code = app.exec()

    gps_adapter.stop()
    map_manager.close()
    db.close()
    logger.info("=== RoadBook Pi finalizado (código %s) ===", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
