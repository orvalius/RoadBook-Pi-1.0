"""Logger centralizado de RoadBook Pi.

Todos los módulos del sistema deben obtener su logger a través de
``get_logger`` para garantizar un formato y destino consistentes.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "roadbook_pi.log"
_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configura el logging global de la aplicación.

    Debe llamarse una única vez, típicamente desde ``main.py``.
    Crea un handler de consola y un handler rotativo en archivo.

    Args:
        level: Nivel mínimo de logging (por defecto INFO).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger nombrado para un módulo.

    Args:
        name: Nombre del módulo (usar ``__name__``).

    Returns:
        Instancia de ``logging.Logger`` configurada.
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
