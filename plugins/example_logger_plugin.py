"""Plugin de ejemplo: registra cada ejecución en un archivo de texto.

Sirve como plantilla mínima para escribir plugins propios de RoadBook
Pi. Para crear uno nuevo:

1. Copiar este archivo con otro nombre dentro de ``plugins/``.
2. Cambiar el valor de ``name`` (debe ser único).
3. Implementar ``execute()`` con la lógica deseada.
4. Agregar el nombre a ``plugins.enabled`` en ``config.json``.

Un plugin presente en esta carpeta pero no listado en
``plugins.enabled`` nunca se carga ni se ejecuta.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.plugin_manager import RoadBookPlugin

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "plugin_events.log"


class ExampleLoggerPlugin(RoadBookPlugin):
    """Plugin de ejemplo: anota cada ejecución con fecha/hora en un archivo."""

    name = "example_logger"

    def on_load(self) -> None:
        """Se asegura de que exista la carpeta de logs."""
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def execute(self, payload: dict) -> None:
        """Escribe una línea en ``logs/plugin_events.log`` con el payload recibido.

        Args:
            payload: Datos de la acción `run_plugin` que lo disparó.
        """
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat(timespec="seconds")
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} | plugin '{self.name}' ejecutado | payload={payload}\n")
