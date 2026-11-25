"""Tulipa: el pictograma de giro de los libros de ruta de rally.

Se lee siempre "desde abajo": un punto donde está el vehículo, una
línea que sube hasta el cruce, y una flecha que sale con el ángulo
real del giro (derecha = sentido horario). Así se ve de un vistazo
para qué lado dobla y qué tan cerrado es, sin leer texto.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QWidget

from core.turns import Turn

INK = QColor("#e8e6e1")
HOT = QColor("#ff8a00")
DIM = QColor("#4a5160")
BOX = QColor("#232935")
EDGE = QColor("#2a3140")


def _pen(color: QColor, width: float) -> QPen:
    return QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )


class TulipWidget(QWidget):
    """Dibuja el giro de una nota.

    Attributes:
        turn: Giro a dibujar, o None.
        kind: Qué dibujar cuando no hay giro: ``"largada"`` (flecha recta
            desde un punto) o ``"llegada"`` (línea que termina en una barra).
    """

    def __init__(self, size: int = 40, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.turn: Turn | None = None
        self.kind = "largada"
        self._accent = INK
        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_turn(self, turn: Turn | None, kind: str = "largada") -> None:
        """Cambia el giro que se dibuja."""
        self.turn = turn
        self.kind = kind
        self.update()

    def set_tone(self, tone: str) -> None:
        """``"current"`` (naranja), ``"passed"`` (apagado) o ``"upcoming"``."""
        self._accent = {"current": HOT, "passed": DIM}.get(tone, INK)
        self.update()

    def exit_angle_deg(self) -> float:
        """Ángulo de la flecha de salida respecto de "arriba" (para tests)."""
        return self.turn.angulo if self.turn is not None else 0.0

    def paintEvent(self, _event) -> None:  # noqa: N802 - override de Qt
        size = float(min(self.width(), self.height()))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(EDGE, 1))
        painter.setBrush(BOX)
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, size - 1, size - 1), size * 0.2, size * 0.2
        )

        center = QPointF(size / 2, size * 0.47)
        origin = QPointF(size / 2, size * 0.88)
        arm = size * 0.36
        stroke = max(2.0, size * 0.075)
        # La entrada va más fina y apagada que la salida: en una horquilla
        # la flecha vuelve al lado de la línea de entrada y deben distinguirse.
        muted = DIM if self._accent is DIM else QColor("#8b93a1")

        painter.setPen(_pen(muted, stroke))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.turn is None and self.kind == "llegada":
            painter.drawLine(origin, QPointF(size / 2, size * 0.3))
            painter.setPen(_pen(self._accent, stroke * 1.4))
            painter.drawLine(
                QPointF(size * 0.3, size * 0.25), QPointF(size * 0.7, size * 0.25)
            )
            painter.end()
            return

        # Entrada: punto del vehículo + línea hasta el cruce.
        painter.setBrush(muted)
        painter.drawEllipse(origin, stroke * 0.9, stroke * 0.9)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.turn is None:  # largada: recta hacia adelante
            tip = QPointF(size / 2, size * 0.18)
            painter.setPen(_pen(self._accent, stroke))
            painter.drawLine(origin, tip)
            self._arrow_head(painter, tip, 0.0, size)
            painter.end()
            return
        painter.setPen(_pen(muted, stroke * 0.7))
        painter.drawLine(origin, center)

        # Salida: rumbo relativo (0 = seguir derecho hacia arriba). Se dibuja
        # curva, saliendo hacia adelante y girando: en una horquilla forma
        # una U que se separa de la línea de entrada, como en los roadbooks.
        rad = math.radians(self.turn.angulo)
        # Pasados los 90° la salida vuelve hacia atrás: se corre hacia el
        # lado del giro para que baje en paralelo y no pise la entrada.
        side = math.copysign(1.0, rad) * max(0.0, abs(self.turn.angulo) - 90) / 90
        tip = QPointF(
            center.x() + arm * math.sin(rad) + arm * 0.55 * side,
            center.y() - arm * math.cos(rad),
        )
        # Punto de control a mitad del giro: abre la curva hacia el lado
        # en que dobla (en una horquilla, la U queda bien separada).
        half = rad / 2
        control = QPointF(
            center.x() + arm * 0.75 * math.sin(half),
            center.y() - arm * 0.75 * math.cos(half),
        )
        path = QPainterPath(center)
        path.quadTo(control, tip)
        painter.setPen(_pen(self._accent, stroke * 1.15))
        painter.drawPath(path)
        end_angle = math.degrees(
            math.atan2(tip.x() - control.x(), control.y() - tip.y())
        )
        self._arrow_head(painter, tip, end_angle, size)
        painter.end()

    def _arrow_head(
        self, painter: QPainter, tip: QPointF, angle: float, size: float
    ) -> None:
        head = size * 0.16
        rad = math.radians(angle)
        back = QPointF(tip.x() - head * math.sin(rad), tip.y() + head * math.cos(rad))
        perp = QPointF(math.cos(rad) * head * 0.55, math.sin(rad) * head * 0.55)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._accent)
        painter.drawPolygon(QPolygonF([tip, back + perp, back - perp]))
