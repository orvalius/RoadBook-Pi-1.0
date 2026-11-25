"""Cálculo de giros de la ruta: para qué lado dobla y en qué ángulo.

Cada nota del roadbook muestra un "tulipa" (el pictograma clásico de
los libros de ruta de rally): una línea que entra desde abajo y una
flecha que sale con el ángulo del giro. Este módulo calcula ese giro.

Dos fuentes de geometría, de mejor a peor:

1. **Track GPX** (si hay uno activo): el rumbo de entrada y de salida
   se mide sobre el track, unos metros antes y después del punto del
   track más cercano al waypoint. Refleja la curva real del camino.
2. **Solo waypoints**: el rumbo de entrada es el del tramo recto desde
   el waypoint anterior, y el de salida, el del tramo hacia el
   siguiente. Es el cambio de dirección *entre notas*, no la forma de
   cada curva del camino: suficiente para orientarse, pero conviene
   cargar el GPX para que los ángulos sean los del terreno.

Lógica pura: sin Qt ni base de datos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.navigation_engine import NavigationEngine

LatLon = tuple[float, float]

STRAIGHT_THRESHOLD_DEG = 15.0
"""Por debajo de este cambio de rumbo se considera que sigue recto."""

MIN_LEG_M = 15.0
"""Tramos más cortos que esto se ignoran (waypoints casi superpuestos,
como una largada y una PE en el mismo punto): no dan un rumbo confiable."""

TRACK_LOOKAROUND_M = 120.0
"""Distancia sobre el track, antes y después del punto, para medir rumbos."""

# Escala de severidad (límites superiores en grados, inclusive).
SEVERITY_SCALE: tuple[tuple[float, str], ...] = (
    (45.0, "suave"),
    (90.0, "media"),
    (135.0, "cerrada"),
    (180.0, "horquilla"),
)


def bearing_deg(a: LatLon, b: LatLon) -> float:
    """Rumbo inicial de ``a`` hacia ``b`` en grados (0 = norte, 90 = este)."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        dlon
    )
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def signed_turn_deg(bearing_in: float, bearing_out: float) -> float:
    """Cambio de rumbo con signo en (-180, 180]: positivo = derecha."""
    delta = (bearing_out - bearing_in + 180.0) % 360.0 - 180.0
    return 180.0 if delta == -180.0 else delta


@dataclass(frozen=True)
class Turn:
    """Giro en una nota de la ruta.

    Attributes:
        angulo: Cambio de rumbo con signo, en grados (-180 a 180).
            Positivo = derecha, negativo = izquierda. Es el que usa el
            tulipa para dibujar la flecha.
        rumbo_salida: Rumbo absoluto después del giro (0 = norte).
    """

    angulo: float
    rumbo_salida: float

    @property
    def grados(self) -> int:
        """Magnitud del giro, redondeada a 5° como en un libro de ruta."""
        return int(5 * round(abs(self.angulo) / 5))

    @property
    def lado(self) -> str:
        """``"izquierda"``, ``"derecha"`` o ``"recto"``."""
        if abs(self.angulo) < STRAIGHT_THRESHOLD_DEG:
            return "recto"
        return "derecha" if self.angulo > 0 else "izquierda"

    @property
    def severidad(self) -> str:
        """Escala orientativa: suave, media, cerrada u horquilla ("" si es recto).

        Se calcula sobre ``grados`` (el valor redondeado que se muestra),
        para que el cartel nunca diga "45°" y "media" a la vez.
        """
        if self.lado == "recto":
            return ""
        magnitude = self.grados
        for limit, name in SEVERITY_SCALE:
            if magnitude <= limit:
                return name
        return SEVERITY_SCALE[-1][1]  # pragma: no cover - |angulo| <= 180

    @property
    def texto(self) -> str:
        """Texto corto para el cartel: 'Derecha 45°', 'Recto'."""
        if self.lado == "recto":
            return "Recto"
        return f"{self.lado.capitalize()} {self.grados}°"


def _distance(a: LatLon, b: LatLon) -> float:
    return NavigationEngine.haversine_distance(a[0], a[1], b[0], b[1])


def _previous_distinct(points: list[LatLon], i: int) -> LatLon | None:
    for j in range(i - 1, -1, -1):
        if _distance(points[j], points[i]) >= MIN_LEG_M:
            return points[j]
    return None


def _next_distinct(points: list[LatLon], i: int) -> LatLon | None:
    for j in range(i + 1, len(points)):
        if _distance(points[i], points[j]) >= MIN_LEG_M:
            return points[j]
    return None


def _nearest_index(track: list[LatLon], point: LatLon) -> int:
    return min(range(len(track)), key=lambda k: _distance(track[k], point))


def _walk(track: list[LatLon], start: int, step: int, meters: float) -> LatLon | None:
    """Punto del track a ~``meters`` de ``start`` avanzando de a ``step``."""
    walked = 0.0
    k = start
    while 0 <= k + step < len(track):
        walked += _distance(track[k], track[k + step])
        k += step
        if walked >= meters:
            return track[k]
    return track[k] if k != start and walked >= MIN_LEG_M else None


def _turn_from(before: LatLon | None, at: LatLon, after: LatLon | None) -> Turn | None:
    if before is None or after is None:
        return None
    bearing_in = bearing_deg(before, at)
    bearing_out = bearing_deg(at, after)
    return Turn(
        angulo=signed_turn_deg(bearing_in, bearing_out), rumbo_salida=bearing_out
    )


def compute_turns(
    points: list[LatLon], track: list[LatLon] | None = None
) -> list[Turn | None]:
    """Calcula el giro en cada punto de la ruta.

    Args:
        points: Posiciones (lat, lon) de las notas, en orden de ruta.
        track: Puntos de un track GPX de referencia, o None.

    Returns:
        Un ``Turn`` por punto, o None donde no se puede calcular: la
        largada (no hay rumbo de entrada), la llegada (no hay salida) y
        puntos sin tramos de largo suficiente alrededor.
    """
    turns: list[Turn | None] = []
    use_track = bool(track) and len(track or []) >= 3
    for i, point in enumerate(points):
        if i == 0 or i == len(points) - 1:
            turns.append(None)
            continue
        turn: Turn | None = None
        if use_track:
            assert track is not None
            k = _nearest_index(track, point)
            turn = _turn_from(
                _walk(track, k, -1, TRACK_LOOKAROUND_M),
                track[k],
                _walk(track, k, +1, TRACK_LOOKAROUND_M),
            )
        if turn is None:
            turn = _turn_from(
                _previous_distinct(points, i), point, _next_distinct(points, i)
            )
        turns.append(turn)
    return turns
