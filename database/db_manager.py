"""Database Manager de RoadBook Pi.

Gestiona la conexión SQLite y la creación del schema.

Sprint 11 (Beta): agrega recuperación ante un archivo de base de
datos corrupto — un escenario real en Raspberry Pi (corte de energía
en medio de una escritura, sector dañado de la SD). En vez de
crashear la aplicación entera al arrancar, se detecta la corrupción,
se preserva el archivo dañado con un nombre distinto (para intentar
recuperarlo manualmente después) y se arranca con una base nueva.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from core.logger import get_logger
from database.migration_runner import MigrationRunner

logger = get_logger(__name__)


class DatabaseCorruptionError(Exception):
    """Se lanza si la base de datos está corrupta y no se pudo recuperar."""


class DatabaseManager:
    """Gestiona la conexión a la base de datos SQLite del proyecto.

    Attributes:
        db_path: Ruta al archivo .db de SQLite.
    """

    def __init__(self, db_path: str | Path = "database/roadbook.db") -> None:
        self.db_path = Path(db_path)
        self._connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Abre (o reutiliza) la conexión a la base de datos.

        Si el archivo existe pero está corrupto (no es un SQLite
        válido, o falla la verificación de integridad), lo respalda
        con un sufijo de timestamp y arranca con una base nueva en su
        lugar, en vez de crashear.

        Returns:
            Conexión SQLite activa con row_factory configurado.
        """
        if self._connection is not None:
            return self._connection

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if self.db_path.exists() and not self._is_valid_database(self.db_path):
            self._quarantine_corrupt_database()

        self._connection = self._open_connection(self.db_path)
        return self._connection

    @staticmethod
    def _is_valid_database(path: Path) -> bool:
        """Verifica que un archivo sea una base SQLite legible e íntegra.

        Args:
            path: Ruta al archivo a verificar.

        Returns:
            True si se pudo abrir y `PRAGMA integrity_check` pasó.
        """
        try:
            conn = sqlite3.connect(path)
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                return result is not None and result[0] == "ok"
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            return False

    def _quarantine_corrupt_database(self) -> None:
        """Mueve el archivo corrupto a un nombre de respaldo con timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_path = self.db_path.with_name(
            f"{self.db_path.stem}.corrupt-{timestamp}{self.db_path.suffix}"
        )
        logger.error(
            "Base de datos corrupta detectada en %s. Se preserva como %s "
            "y se arranca con una base nueva.",
            self.db_path,
            quarantine_path,
        )
        shutil.move(str(self.db_path), str(quarantine_path))

    @staticmethod
    def _open_connection(db_path: Path) -> sqlite3.Connection:
        # check_same_thread=False es necesario: el EventEngine consulta
        # ActionRepository desde el hilo del GpsManager (el callback
        # on_waypoint_reached corre ahí, no se marshalea a Qt), mientras
        # que la conexión se abre en el hilo principal. WAL + este flag
        # permiten ese acceso cruzado de forma segura para el patrón de
        # uso de esta app (lecturas ocasionales desde hilos secundarios,
        # escrituras desde la UI); si en el futuro se necesitara más
        # concurrencia de escritura real, conviene pasar a una conexión
        # por hilo o a una cola de escritura dedicada.
        connection = sqlite3.connect(db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # Optimización de Sprint 10, pensada para Raspberry Pi 2:
        # WAL permite lecturas concurrentes mientras hay una escritura
        # en curso (el Event Engine puede estar leyendo `actions` desde
        # un hilo de threading.Timer justo cuando la UI graba un cambio).
        # synchronous=NORMAL reduce los fsync forzados en cada commit,
        # más caros en una tarjeta SD que en un SSD; WAL ya garantiza
        # consistencia ante un corte de energía sin necesitar FULL.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        logger.info("Conectado a la base de datos: %s", db_path)
        return connection

    def initialize_schema(self) -> None:
        """Aplica todas las migraciones pendientes contra la base de datos.

        Cada cambio de schema vive en ``database/migrations/NNN_*.sql``
        y se aplica una sola vez, de forma versionada, sin romper bases
        de datos de instalaciones existentes.
        """
        conn = self.connect()
        runner = MigrationRunner(conn)
        runner.apply_pending()

    def close(self) -> None:
        """Cierra la conexión activa, si existe."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Conexión a base de datos cerrada")

    def __enter__(self) -> DatabaseManager:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
