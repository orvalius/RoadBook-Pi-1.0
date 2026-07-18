"""Event Engine de RoadBook Pi.

Punto central de la arquitectura: recibe el waypoint alcanzado desde
el Navigation Engine y ejecuta su secuencia de acciones a través del
Action Dispatcher.

Arquitectura (ver especificación):
    GPS -> Navigation Engine -> Event Engine -> Action Dispatcher ->
    UI / Audio / Logger / Plugins

Es una máquina de estados **asincrónica**: los pasos ``WAIT`` se
resuelven con ``threading.Timer`` (nunca con ``time.sleep``), así una
secuencia larga en un waypoint nunca bloquea el hilo del GPS ni el de
la UI. Cada waypoint alcanzado corre su propia secuencia de forma
independiente — varios waypoints pueden estar ejecutando su secuencia
al mismo tiempo sin interferirse.

Retrocompatibilidad: si un waypoint no tiene una secuencia custom
definida en la tabla ``actions`` (Sprint 8), el Event Engine sintetiza
una secuencia por defecto a partir de sus columnas legacy
``imagen``/``audio`` (comportamiento idéntico al de los Sprints 6-7).
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from core.action_dispatcher import ActionDispatcher, ActionType
from core.logger import get_logger
from database.models import Action, Waypoint

logger = get_logger(__name__)

WaypointCallback = Callable[[Waypoint], None]


class ActionSequenceRunner:
    """Ejecuta una secuencia de acciones, paso a paso, sin bloquear.

    Los pasos que no son ``WAIT`` se ejecutan inmediatamente uno tras
    otro; un paso ``WAIT`` programa la continuación con
    ``threading.Timer`` y libera el hilo actual hasta que se cumpla.

    Attributes:
        actions: Secuencia de acciones a ejecutar, en orden.
        dispatcher: Dispatcher que ejecuta cada acción no-WAIT.
    """

    def __init__(
        self,
        actions: list[Action],
        dispatcher: ActionDispatcher,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.actions = actions
        self.dispatcher = dispatcher
        self.on_complete = on_complete
        self._index = 0
        self._timer: threading.Timer | None = None
        self._cancelled = False

    def start(self) -> None:
        """Inicia la ejecución de la secuencia desde el primer paso."""
        self._run_next()

    def cancel(self) -> None:
        """Cancela la secuencia (si hay un WAIT pendiente, no continúa)."""
        self._cancelled = True
        if self._timer is not None:
            self._timer.cancel()

    def _run_next(self) -> None:
        if self._cancelled:
            return

        if self._index >= len(self.actions):
            if self.on_complete is not None:
                self.on_complete()
            return

        action = self.actions[self._index]
        self._index += 1

        if action.tipo == ActionType.WAIT.value:
            seconds = float(action.payload.get("seconds", 0))
            self._timer = threading.Timer(seconds, self._run_next)
            self._timer.daemon = True
            self._timer.start()
        else:
            try:
                self.dispatcher.execute(ActionType(action.tipo), action.payload)
            except ValueError:
                logger.warning("Tipo de acción desconocido: %s", action.tipo)
            self._run_next()


class EventEngine:
    """Motor de eventos: resuelve y ejecuta la secuencia de un waypoint.

    Attributes:
        action_dispatcher: Dispatcher usado para ejecutar cada paso.
        default_image_display_seconds: Duración por defecto de la
            secuencia legacy sintetizada (imagen visible antes de
            ocultarse), usada solo cuando el waypoint no tiene una
            secuencia custom en la tabla ``actions``.
    """

    def __init__(
        self,
        action_dispatcher: ActionDispatcher,
        action_repository=None,
        default_image_display_seconds: float = 5.0,
    ) -> None:
        self.action_dispatcher = action_dispatcher
        self.action_repository = action_repository
        self.default_image_display_seconds = default_image_display_seconds
        self._active_runners: list[ActionSequenceRunner] = []
        self._lock = threading.Lock()
        logger.info("EventEngine inicializado")

    def handle_waypoint(self, waypoint: Waypoint) -> None:
        """Resuelve y ejecuta la secuencia de acciones de un waypoint.

        Args:
            waypoint: Waypoint que acaba de alcanzarse (viene del
                callback ``NavigationEngine.on_waypoint_reached``,
                típicamente a través de un adapter Qt).
        """
        actions = self._resolve_actions(waypoint)
        if not actions:
            logger.debug("Waypoint %s sin acciones para ejecutar", waypoint.id)
            return

        runner = ActionSequenceRunner(actions, self.action_dispatcher)
        runner.on_complete = lambda: self._cleanup(runner)

        with self._lock:
            self._active_runners.append(runner)

        logger.info(
            "EventEngine: ejecutando secuencia de %d paso(s) para waypoint %s",
            len(actions), waypoint.nombre,
        )
        runner.start()

    def _cleanup(self, runner: ActionSequenceRunner) -> None:
        with self._lock:
            if runner in self._active_runners:
                self._active_runners.remove(runner)

    def _resolve_actions(self, waypoint: Waypoint) -> list[Action]:
        """Obtiene la secuencia custom del waypoint, o la legacy por defecto."""
        if self.action_repository is not None and waypoint.id is not None:
            custom = self.action_repository.list_for_waypoint(waypoint.id)
            if custom:
                return custom

        return self._default_actions(waypoint)

    def _default_actions(self, waypoint: Waypoint) -> list[Action]:
        """Sintetiza la secuencia legacy: mostrar imagen + audio, sin cambios
        de comportamiento respecto a los Sprints 6-7."""
        actions: list[Action] = []
        order = 0
        wp_id = waypoint.id if waypoint.id is not None else -1

        if waypoint.imagen:
            actions.append(
                Action(waypoint_id=wp_id, orden=order, tipo=ActionType.SHOW_IMAGE.value,
                       payload={"path": waypoint.imagen})
            )
            order += 1

        if waypoint.audio:
            actions.append(
                Action(waypoint_id=wp_id, orden=order, tipo=ActionType.PLAY_AUDIO.value,
                       payload={"path": waypoint.audio})
            )
            order += 1

        if waypoint.imagen:
            actions.append(
                Action(waypoint_id=wp_id, orden=order, tipo=ActionType.WAIT.value,
                       payload={"seconds": self.default_image_display_seconds})
            )
            order += 1
            actions.append(
                Action(waypoint_id=wp_id, orden=order, tipo=ActionType.HIDE_IMAGE.value, payload={})
            )
            order += 1

        actions.append(
            Action(
                waypoint_id=wp_id, orden=order, tipo=ActionType.LOG_EVENT.value,
                payload={"message": f"Waypoint alcanzado: {waypoint.nombre}"},
            )
        )
        return actions
