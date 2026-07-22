"""Modelo de dominio Waypoint y Action.

Representan filas de las tablas ``waypoints`` y ``actions``. Son
dataclasses puros, sin dependencias de SQLite ni de la UI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Waypoint:
    """Representa un waypoint geográfico disparador de eventos.

    Attributes:
        id: Identificador único (None si aún no fue persistido).
        nombre: Nombre descriptivo del waypoint.
        latitud: Latitud en grados decimales.
        longitud: Longitud en grados decimales.
        radio: Radio de disparo en metros.
        categoria: Categoría opcional (texto libre por ahora).
        imagen: Ruta relativa a la imagen asociada, si aplica.
        audio: Ruta relativa al audio asociado, si aplica.
        velocidad: Condición opcional de velocidad mínima (km/h).
        angulo: Condición opcional de rumbo de aproximación (grados).
        prioridad: Prioridad de ejecución si varios waypoints coinciden.
        descripcion: Descripción libre del waypoint.
        activo: Si es False, el waypoint no dispara eventos.
        re_triggerable: Si es True, el evento puede volver a dispararse
            en cada re-entrada al radio. Si es False, se dispara una
            única vez por sesión.
        icono: Pictograma a mostrar en la tira del Roadbook Rendering
            Engine (ej: "curva_izq", "peligro", "vado", "largada").
            Puramente visual, no afecta el disparo de eventos.
        orden_ruta: Posición manual de este waypoint dentro de la ruta
            del roadbook, cuando no hay un track GPX que determine el
            orden automáticamente. None = sin definir (se ordena por
            id de creación como último recurso).
    """

    nombre: str
    latitud: float
    longitud: float
    radio: float = 50.0
    categoria: str | None = None
    imagen: str | None = None
    audio: str | None = None
    velocidad: float | None = None
    angulo: float | None = None
    prioridad: int = 0
    descripcion: str | None = None
    activo: bool = True
    re_triggerable: bool = True
    icono: str = "generico"
    orden_ruta: int | None = None
    id: int | None = None

    @classmethod
    def from_row(cls, row) -> "Waypoint":
        """Construye un Waypoint a partir de una fila sqlite3.Row.

        Args:
            row: Fila devuelta por sqlite3 con row_factory=sqlite3.Row.

        Returns:
            Instancia de Waypoint.
        """
        return cls(
            id=row["id"],
            nombre=row["nombre"],
            latitud=row["latitud"],
            longitud=row["longitud"],
            radio=row["radio"],
            categoria=row["categoria"],
            imagen=row["imagen"],
            audio=row["audio"],
            velocidad=row["velocidad"],
            angulo=row["angulo"],
            prioridad=row["prioridad"],
            descripcion=row["descripcion"],
            activo=bool(row["activo"]),
            re_triggerable=bool(row["re_triggerable"]),
            icono=row["icono"] if "icono" in row.keys() else "generico",
            orden_ruta=row["orden_ruta"] if "orden_ruta" in row.keys() else None,
        )


@dataclass
class Action:
    """Representa un paso de una secuencia de acciones de un waypoint.

    Attributes:
        id: Identificador único (None si aún no fue persistido).
        waypoint_id: Id del waypoint dueño de esta acción.
        orden: Posición en la secuencia (0-based, se ejecutan en orden).
        tipo: Uno de los valores de ``core.action_dispatcher.ActionType``
            (ej: "show_image", "wait", "play_audio", "hide_image",
            "log_event", "run_plugin").
        payload: Datos específicos de la acción (ej: {"path": "..."}
            para show_image/play_audio, {"seconds": 5.0} para wait).
        id: Identificador único (None si aún no fue persistido).
    """

    waypoint_id: int
    orden: int
    tipo: str
    payload: dict = field(default_factory=dict)
    id: int | None = None

    @classmethod
    def from_row(cls, row) -> "Action":
        """Construye una Action a partir de una fila sqlite3.Row.

        Args:
            row: Fila devuelta por sqlite3 con row_factory=sqlite3.Row.

        Returns:
            Instancia de Action.
        """
        return cls(
            id=row["id"],
            waypoint_id=row["waypoint_id"],
            orden=row["orden"],
            tipo=row["tipo"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
        )
