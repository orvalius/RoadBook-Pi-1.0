"""Action Repository de RoadBook Pi.

Encapsula todo el acceso SQL a la tabla ``actions``. Ningún otro
módulo debe escribir SQL directamente contra esta tabla.
"""

from __future__ import annotations

import json

from core.logger import get_logger
from database.db_manager import DatabaseManager
from database.models import Action

logger = get_logger(__name__)


class ActionRepository:
    """CRUD de secuencias de acciones sobre SQLite.

    Attributes:
        db: Instancia de ``DatabaseManager`` ya inicializada.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create(self, action: Action) -> Action:
        """Inserta un paso de acción.

        Args:
            action: Acción a crear (su ``id`` se ignora).

        Returns:
            La misma acción, con el ``id`` asignado por la base de datos.
        """
        conn = self.db.connect()
        cursor = conn.execute(
            "INSERT INTO actions (waypoint_id, orden, tipo, payload) VALUES (?, ?, "
            "?, ?)",
            (action.waypoint_id, action.orden, action.tipo, json.dumps(action.payload)),
        )
        conn.commit()
        action.id = cursor.lastrowid
        logger.info(
            "Action creada: id=%s waypoint_id=%s tipo=%s",
            action.id,
            action.waypoint_id,
            action.tipo,
        )
        return action

    def list_for_waypoint(self, waypoint_id: int) -> list[Action]:
        """Lista la secuencia de acciones de un waypoint, en orden.

        Args:
            waypoint_id: Id del waypoint.

        Returns:
            Lista de acciones ordenadas por ``orden`` ascendente. Vacía
            si el waypoint no tiene una secuencia custom definida (en
            cuyo caso el Event Engine usa la secuencia legacy por
            defecto).
        """
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT * FROM actions WHERE waypoint_id = ? ORDER BY orden ASC",
            (waypoint_id,),
        ).fetchall()
        return [Action.from_row(row) for row in rows]

    def replace_sequence(self, waypoint_id: int, actions: list[Action]) -> list[Action]:
        """Reemplaza toda la secuencia de un waypoint de forma atómica.

        Borra las acciones existentes del waypoint e inserta las
        nuevas, re-numerando ``orden`` según la posición en la lista.

        Args:
            waypoint_id: Id del waypoint.
            actions: Nueva secuencia de acciones (el orden de la lista
                determina el orden de ejecución).

        Returns:
            Las acciones insertadas, con sus ids asignados.
        """
        conn = self.db.connect()
        conn.execute("DELETE FROM actions WHERE waypoint_id = ?", (waypoint_id,))
        conn.commit()

        created = []
        for index, action in enumerate(actions):
            action.waypoint_id = waypoint_id
            action.orden = index
            action.id = None
            created.append(self.create(action))

        logger.info(
            "Secuencia de acciones reemplazada para waypoint_id=%s (%d pasos)",
            waypoint_id,
            len(created),
        )
        return created

    def delete_all_for_waypoint(self, waypoint_id: int) -> None:
        """Borra toda la secuencia custom de un waypoint (vuelve al default legacy).

        Args:
            waypoint_id: Id del waypoint.
        """
        conn = self.db.connect()
        conn.execute("DELETE FROM actions WHERE waypoint_id = ?", (waypoint_id,))
        conn.commit()
        logger.info("Secuencia de acciones borrada para waypoint_id=%s", waypoint_id)
