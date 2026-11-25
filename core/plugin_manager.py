"""Plugin Manager de RoadBook Pi.

Permite extender el sistema con módulos de terceros sin modificar el
core. Los plugins viven como archivos ``.py`` sueltos en una carpeta
(por defecto ``plugins/`` en la raíz del proyecto) y solo se cargan
si su ``name`` aparece explícitamente en ``plugins.enabled`` en la
configuración — un archivo presente en la carpeta no se ejecuta por
el solo hecho de estar ahí, hay que habilitarlo a propósito.

Nota de seguridad: los plugins corren con privilegios completos de
Python, sin sandboxing de sistema operativo. Es una decisión
consciente para un proyecto donde el usuario instala sus propios
plugins de confianza — no está pensado para cargar plugins de
terceros no confiables sin revisar el código primero.
"""

from __future__ import annotations

import importlib.util
import inspect
from abc import ABC, abstractmethod
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)


class RoadBookPlugin(ABC):
    """Contrato base que todo plugin de RoadBook Pi debe implementar."""

    name: str = "unnamed_plugin"

    @abstractmethod
    def on_load(self) -> None:
        """Se invoca cuando el plugin se carga en el sistema."""

    @abstractmethod
    def execute(self, payload: dict) -> None:
        """Se invoca cuando una acción ``run_plugin`` lo dispara.

        Args:
            payload: Datos de contexto para la ejecución del plugin
                (incluye al menos ``plugin_name``; puede tener claves
                adicionales según cómo se haya configurado el paso).
        """


def discover_plugin_classes(directory: str | Path) -> dict[str, type[RoadBookPlugin]]:
    """Escanea una carpeta y encuentra clases de plugin válidas.

    Solo descubre e importa los módulos; no instancia ni registra
    nada. Un archivo con error de sintaxis o de import se loguea y se
    saltea, sin interrumpir el descubrimiento de los demás.

    Args:
        directory: Carpeta con archivos ``.py`` de plugins.

    Returns:
        Diccionario {nombre_del_plugin: clase}, uno por archivo (se
        toma la primera clase que herede de ``RoadBookPlugin``
        encontrada en cada módulo).
    """
    directory = Path(directory)
    discovered: dict[str, type[RoadBookPlugin]] = {}

    if not directory.exists():
        logger.debug("PluginManager: carpeta de plugins inexistente: %s", directory)
        return discovered

    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue

        module_name = f"roadbook_plugin_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"No se pudo crear el spec de import para {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            logger.exception("Error cargando el archivo de plugin %s, se omite", path)
            continue

        plugin_class = next(
            (
                obj
                for _, obj in inspect.getmembers(module, inspect.isclass)
                if issubclass(obj, RoadBookPlugin) and obj is not RoadBookPlugin
            ),
            None,
        )
        if plugin_class is None:
            logger.warning("%s no define ninguna clase RoadBookPlugin, se omite", path)
            continue

        discovered[plugin_class.name] = plugin_class

    return discovered


class PluginManager:
    """Descubre, carga y ejecuta plugins registrados."""

    def __init__(self) -> None:
        self._plugins: dict[str, RoadBookPlugin] = {}
        logger.info("PluginManager inicializado")

    def register(self, plugin: RoadBookPlugin) -> None:
        """Registra un plugin ya instanciado en el sistema.

        Args:
            plugin: Instancia que implementa ``RoadBookPlugin``.
        """
        self._plugins[plugin.name] = plugin
        plugin.on_load()
        logger.info("Plugin registrado: %s", plugin.name)

    def load_from_directory(
        self, directory: str | Path, enabled_names: list[str]
    ) -> list[str]:
        """Descubre plugins en una carpeta y carga solo los habilitados.

        Args:
            directory: Carpeta con archivos ``.py`` de plugins.
            enabled_names: Nombres de plugins a cargar (de
                ``config.get("plugins.enabled")``). Un plugin presente
                en la carpeta pero no listado acá nunca se instancia
                ni se ejecuta.

        Returns:
            Nombres de los plugins efectivamente cargados.
        """
        discovered = discover_plugin_classes(directory)
        loaded: list[str] = []

        for name in enabled_names:
            plugin_class = discovered.get(name)
            if plugin_class is None:
                logger.warning(
                    "Plugin habilitado '%s' no se encontró en %s (¿nombre "
                    "correcto? ¿archivo presente?)",
                    name,
                    directory,
                )
                continue

            try:
                instance = plugin_class()
                self.register(instance)
                loaded.append(name)
            except Exception:
                logger.exception("Error instanciando/cargando el plugin '%s'", name)

        return loaded

    def get(self, name: str) -> RoadBookPlugin | None:
        """Obtiene un plugin registrado por nombre.

        Args:
            name: Nombre del plugin.

        Returns:
            La instancia del plugin, o ``None`` si no está registrado
            (no cargado, deshabilitado, o nombre inexistente).
        """
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        """Devuelve los nombres de todos los plugins registrados."""
        return list(self._plugins.keys())
