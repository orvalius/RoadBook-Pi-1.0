"""Waypoint Repository de RoadBook Pi.

Encapsula todo el acceso SQL a la tabla ``waypoints``. Ningún otro
módulo (UI incluida) debe escribir SQL directamente contra esta
tabla; siempre pasa por este repositorio.
"""

from __future__ import annotations

from database.db_manager import DatabaseManager
from database.models import Waypoint
from core.logger import get_logger

logger = get_logger(__name__)


class WaypointNotFoundError(Exception):
    """Se lanza cuando se busca un waypoint por id inexistente."""


class WaypointRepository:
    """CRUD de waypoints sobre SQLite.

    Attributes:
        db: Instancia de ``DatabaseManager`` ya inicializada.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create(self, waypoint: Waypoint) -> Waypoint:
        """Inserta un nuevo waypoint.

        Args:
            waypoint: Waypoint a crear (su ``id`` se ignora).

        Returns:
            El mismo waypoint, con el ``id`` asignado por la base de datos.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            """
            INSERT INTO waypoints
                (nombre, latitud, longitud, radio, categoria, imagen,
                 audio, velocidad, angulo, prioridad, descripcion,
                 activo, re_triggerable)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                waypoint.nombre,
                waypoint.latitud,
                waypoint.longitud,
                waypoint.radio,
                waypoint.categoria,
                waypoint.imagen,
                waypoint.audio,
                waypoint.velocidad,
                waypoint.angulo,
                waypoint.prioridad,
                waypoint.descripcion,
                int(waypoint.activo),
                int(waypoint.re_triggerable),
            ),
        )
        conn.commit()
        waypoint.id = cursor.lastrowid
        logger.info("Waypoint creado: id=%s nombre=%s", waypoint.id, waypoint.nombre)
        return waypoint

    def get(self, waypoint_id: int) -> Waypoint:
        """Obtiene un waypoint por id.

        Args:
            waypoint_id: Identificador del waypoint.

        Returns:
            El waypoint encontrado.

        Raises:
            WaypointNotFoundError: Si no existe un waypoint con ese id.
        """
        conn = self.db.connect()
        row = conn.execute(
            "SELECT * FROM waypoints WHERE id = ?", (waypoint_id,)
        ).fetchone()
        if row is None:
            raise WaypointNotFoundError(f"No existe waypoint con id={waypoint_id}")
        return Waypoint.from_row(row)

    def list_all(self, only_active: bool = False) -> list[Waypoint]:
        """Lista todos los waypoints.

        Args:
            only_active: Si es True, filtra solo los waypoints activos.

        Returns:
            Lista de waypoints ordenados por prioridad descendente.
        """
        conn = self.db.connect()
        query = "SELECT * FROM waypoints"
        if only_active:
            query += " WHERE activo = 1"
        query += " ORDER BY prioridad DESC, nombre ASC"
        rows = conn.execute(query).fetchall()
        return [Waypoint.from_row(row) for row in rows]

    def update(self, waypoint: Waypoint) -> Waypoint:
        """Actualiza un waypoint existente.

        Args:
            waypoint: Waypoint con ``id`` seteado y los nuevos valores.

        Returns:
            El waypoint actualizado.

        Raises:
            WaypointNotFoundError: Si ``waypoint.id`` es None o no existe.
        """
        if waypoint.id is None:
            raise WaypointNotFoundError("No se puede actualizar un waypoint sin id")

        conn = self.db.connect()
        cursor = conn.execute(
            """
            UPDATE waypoints SET
                nombre = ?, latitud = ?, longitud = ?, radio = ?,
                categoria = ?, imagen = ?, audio = ?, velocidad = ?,
                angulo = ?, prioridad = ?, descripcion = ?, activo = ?,
                re_triggerable = ?
            WHERE id = ?
            """,
            (
                waypoint.nombre,
                waypoint.latitud,
                waypoint.longitud,
                waypoint.radio,
                waypoint.categoria,
                waypoint.imagen,
                waypoint.audio,
                waypoint.velocidad,
                waypoint.angulo,
                waypoint.prioridad,
                waypoint.descripcion,
                int(waypoint.activo),
                int(waypoint.re_triggerable),
                waypoint.id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise WaypointNotFoundError(f"No existe waypoint con id={waypoint.id}")
        logger.info("Waypoint actualizado: id=%s", waypoint.id)
        return waypoint

    def delete(self, waypoint_id: int) -> None:
        """Elimina un waypoint por id.

        Args:
            waypoint_id: Identificador del waypoint a eliminar.

        Raises:
            WaypointNotFoundError: Si no existe un waypoint con ese id.
        """
        conn = self.db.connect()
        cursor = conn.execute("DELETE FROM waypoints WHERE id = ?", (waypoint_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise WaypointNotFoundError(f"No existe waypoint con id={waypoint_id}")
        logger.info("Waypoint eliminado: id=%s", waypoint_id)

    def set_active(self, waypoint_id: int, activo: bool) -> None:
        """Activa o desactiva un waypoint sin tocar el resto de sus datos.

        Args:
            waypoint_id: Identificador del waypoint.
            activo: Nuevo estado activo/inactivo.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            "UPDATE waypoints SET activo = ? WHERE id = ?",
            (int(activo), waypoint_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise WaypointNotFoundError(f"No existe waypoint con id={waypoint_id}")
        logger.info("Waypoint id=%s activo=%s", waypoint_id, activo)
