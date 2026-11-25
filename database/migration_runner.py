"""Migration Runner de RoadBook Pi.

Aplica migraciones SQL versionadas a la base de datos, en orden, sin
reaplicar las ya ejecutadas. Registra el estado en la tabla
``schema_version``. Este es el único mecanismo autorizado para
modificar el schema de la base de datos: ningún módulo debe ejecutar
``CREATE TABLE`` ni ``ALTER TABLE`` fuera de un archivo de migración.

Convención de nombres: ``NNN_descripcion.sql``, con NNN incremental
de 3 dígitos (001, 002, ...). Se aplican en orden alfabético/numérico.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class MigrationRunner:
    """Aplica migraciones SQL pendientes contra una conexión SQLite."""

    def __init__(
        self, connection: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR
    ) -> None:
        self.connection = connection
        self.migrations_dir = migrations_dir

    def _ensure_version_table(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version    INTEGER PRIMARY KEY,
                filename   TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """)
        self.connection.commit()

    def _applied_versions(self) -> set[int]:
        cursor = self.connection.execute("SELECT version FROM schema_version")
        return {row[0] for row in cursor.fetchall()}

    def _discover_migrations(self) -> list[tuple[int, Path]]:
        """Devuelve las migraciones disponibles ordenadas por versión.

        Returns:
            Lista de tuplas (número de versión, ruta al archivo .sql).
        """
        migrations: list[tuple[int, Path]] = []
        for path in sorted(self.migrations_dir.glob("*.sql")):
            try:
                version = int(path.stem.split("_", 1)[0])
            except ValueError:
                logger.warning("Archivo de migración con nombre inválido: %s", path)
                continue
            migrations.append((version, path))
        return sorted(migrations, key=lambda item: item[0])

    def apply_pending(self) -> list[int]:
        """Aplica todas las migraciones pendientes en orden.

        Returns:
            Lista de números de versión que se aplicaron en esta corrida.
        """
        self._ensure_version_table()
        applied = self._applied_versions()
        newly_applied: list[int] = []

        for version, path in self._discover_migrations():
            if version in applied:
                continue

            logger.info("Aplicando migración %03d (%s)", version, path.name)
            sql = path.read_text(encoding="utf-8")
            try:
                self.connection.executescript(sql)
                self.connection.execute(
                    "INSERT INTO schema_version (version, filename) VALUES (?, ?)",
                    (version, path.name),
                )
                self.connection.commit()
                newly_applied.append(version)
            except sqlite3.Error as exc:
                self.connection.rollback()
                logger.error("Error aplicando migración %03d: %s", version, exc)
                raise

        if newly_applied:
            logger.info("Migraciones aplicadas: %s", newly_applied)
        else:
            logger.info("Base de datos ya al día, sin migraciones pendientes")

        return newly_applied
