"""Configuration Manager de RoadBook Pi.

Responsable de leer, escribir y exponer la configuración de la
aplicación almacenada en un archivo JSON. Ningún otro módulo debe
leer/escribir el archivo de configuración directamente.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "app_name": "RoadBook Pi",
    "version": "1.2.0",
    "language": "es",
    "gps": {
        "backend": "simulator",
        "gpsd_host": "127.0.0.1",
        "gpsd_port": 2947,
        "serial_port": "/dev/ttyUSB0",
        "serial_baudrate": 9600,
        "simulator_interval_seconds": 1.0,
        "reconnect_interval_seconds": 5.0,
    },
    "navigation": {
        "heading_tolerance_degrees": 45.0,
    },
    "graphics": {
        "image_display_seconds": 5.0,
    },
    "maps": {
        "mbtiles_path": "resources/maps/default.mbtiles",
        "default_zoom": 15,
        "redraw_threshold_meters": 20.0,
    },
    "display": {
        "fullscreen": False,
        "width": 800,
        "height": 480,
    },
    "audio": {
        "enabled": True,
        "volume": 0.8,
    },
    "database": {
        "path": "database/roadbook.db",
    },
    "plugins": {
        "directory": "plugins",
        "enabled": [],
    },
    "roadbook": {
        "gpx_path": None,
    },
}


class ConfigManager:
    """Gestiona la configuración persistente de la aplicación.

    Attributes:
        config_path: Ruta al archivo de configuración JSON.
    """

    def __init__(self, config_path: str | Path = "config.json") -> None:
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Carga la configuración desde disco, creando el archivo
        con valores por defecto si no existe."""
        if not self.config_path.exists():
            logger.info(
                "No existe config en %s, creando con valores por defecto",
                self.config_path,
            )
            self._config = dict(DEFAULT_CONFIG)
            self.save()
            return

        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                self._config = json.load(f)
            logger.info("Configuración cargada desde %s", self.config_path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Error leyendo configuración: %s. Usando defaults.", exc)
            self._config = dict(DEFAULT_CONFIG)

    def save(self) -> None:
        """Persiste la configuración actual a disco."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open("w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.debug("Configuración guardada en %s", self.config_path)
        except OSError as exc:
            logger.error("No se pudo guardar la configuración: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor de configuración por clave.

        Soporta claves anidadas separadas por punto, ej: ``"gps.port"``.

        Args:
            key: Clave de configuración.
            default: Valor a devolver si la clave no existe.

        Returns:
            El valor asociado a la clave, o ``default``.
        """
        parts = key.split(".")
        value: Any = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Establece un valor de configuración por clave (soporta puntos).

        Args:
            key: Clave de configuración, ej: ``"gps.port"``.
            value: Nuevo valor a asignar.
        """
        parts = key.split(".")
        target = self._config
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
        logger.debug("Config actualizada: %s = %s", key, value)

    def as_dict(self) -> dict[str, Any]:
        """Devuelve una copia del diccionario de configuración completo."""
        return dict(self._config)
