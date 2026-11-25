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
from core.roadbook_engine import RoadbookEngine, build_entries
from core.route import resolve_route_order
from database.action_repository import ActionRepository
from database.db_manager import DatabaseManager
from database.waypoint_repository import WaypointRepository
from ui.action_event_adapter import QtActionAdapter
from ui.gps_adapter import QtGpsAdapter
from ui.main_window import MainWindow
from ui.signal_handler import GracefulShutdown
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
    active_waypoints = waypoint_repository.list_all(only_active=True)
    navigation_engine.load_waypoints(active_waypoints)

    # Roadbook Rendering Engine: arma la ruta (GPX si está configurado,
    # si no, conectando los waypoints activos) y el motor que resuelve
    # qué mostrar en la tira ante cada posición GPS.
    ordered_waypoints = resolve_route_order(
        active_waypoints, config.get("roadbook.gpx_path", None)
    )
    roadbook_engine = RoadbookEngine(build_entries(ordered_waypoints))

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
        roadbook_engine=roadbook_engine,
    )
    window.show()
    gps_adapter.position_received.connect(window.navigation_screen.update_position)
    action_adapter.action_triggered.connect(window.handle_action)

    # Debe instalarse después de AudioManager: pygame/SDL pisa los
    # handlers de SIGTERM/SIGINT al inicializarse (ver ui/signal_handler.py).
    shutdown = GracefulShutdown(on_shutdown=app.quit)
    shutdown.install()

    gps_adapter.start()

    exit_code = 1
    try:
        exit_code = app.exec()
    finally:
        _shutdown_services(gps_adapter, audio_manager, map_manager, db)
        shutdown.uninstall()
    logger.info("=== RoadBook Pi finalizado (código %s) ===", exit_code)
    return exit_code


def _shutdown_services(
    gps_adapter: QtGpsAdapter,
    audio_manager: AudioManager,
    map_manager: MapManager,
    db: DatabaseManager,
) -> None:
    """Libera recursos en orden inverso al arranque.

    Cada paso es independiente: si uno falla, se loguea y se sigue con
    el resto, para no dejar la base de datos abierta por un error en el
    GPS (relevante si el cierre viene de un apagado de la Raspberry Pi).
    """
    steps = (
        ("GPS", gps_adapter.stop),
        ("audio", audio_manager.stop_all),
        ("mapas", map_manager.close),
        ("base de datos", db.close),
    )
    for name, step in steps:
        try:
            step()
        except Exception:  # noqa: BLE001 - el cierre debe completarse igual
            logger.exception("Error cerrando %s", name)


if __name__ == "__main__":
    sys.exit(main())
