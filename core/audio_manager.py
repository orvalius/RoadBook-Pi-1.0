"""Audio Manager de RoadBook Pi.

Encapsula la reproducción de audio (pygame). Ningún otro módulo debe
importar pygame directamente.

Optimización de Sprint 10: cachea los objetos ``Sound`` ya cargados en
un ``LRUCache``. Sin esto, cada disparo de un waypoint con audio
releería y decodificaría el archivo desde la tarjeta SD, algo caro en
una Raspberry Pi 2 que además puede repetirse muchas veces por
sesión (ej: un mismo aviso de "curva peligrosa" en varios puntos).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.logger import get_logger
from core.lru_cache import LRUCache

logger = get_logger(__name__)

DEFAULT_SOUND_CACHE_SIZE = 20

# Firma inyectable para tests: recibe una ruta de archivo y devuelve un
# objeto "sonido" (en producción, pygame.mixer.Sound). Permite testear
# la lógica de cache sin necesitar pygame ni hardware de audio real.
SoundFactory = Callable[[str], Any]


class AudioManager:
    """Gestiona la reproducción de efectos de audio del sistema.

    Attributes:
        enabled: Si False, todas las llamadas son no-op (útil para
            tests o entornos sin salida de audio).
        volume: Volumen entre 0.0 y 1.0.
    """

    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.8,
        cache_size: int = DEFAULT_SOUND_CACHE_SIZE,
        sound_factory: SoundFactory | None = None,
    ) -> None:
        self.enabled = enabled
        self.volume = volume
        self._mixer_ready = False
        self._sound_cache: LRUCache[str, Any] = LRUCache(cache_size)
        self._sound_factory = sound_factory

        if self.enabled and self._sound_factory is None:
            try:
                import pygame

                pygame.mixer.init()
                self._mixer_ready = True
                self._sound_factory = pygame.mixer.Sound
                logger.info("AudioManager: mixer de pygame inicializado")
            except Exception as exc:  # noqa: BLE001 - hardware/env dependiente
                logger.warning(
                    "No se pudo inicializar el mixer de audio (%s). "
                    "AudioManager funcionará en modo silencioso.",
                    exc,
                )
                self._mixer_ready = False
        elif self._sound_factory is not None:
            # Factory inyectado (tests, u otro backend de audio futuro)
            self._mixer_ready = True

    def play(self, audio_path: str | Path) -> None:
        """Reproduce un archivo de audio.

        Reutiliza el objeto ``Sound`` desde cache si ya se había
        cargado antes; solo lee/decodifica desde disco la primera vez.

        Args:
            audio_path: Ruta al archivo de audio a reproducir.
        """
        if not self.enabled or not self._mixer_ready:
            logger.debug("play() ignorado (audio deshabilitado o sin mixer)")
            return

        path_key = str(audio_path)
        try:
            sound = self._get_or_load_sound(path_key)
            sound.set_volume(self.volume)
            sound.play()
            logger.info("Reproduciendo audio: %s", audio_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error reproduciendo audio %s: %s", audio_path, exc)

    def _get_or_load_sound(self, path_key: str) -> Any:
        """Obtiene un Sound desde cache, o lo carga y cachea si es la
        primera vez que se reproduce ese archivo."""
        cached = self._sound_cache.get(path_key)
        if cached is not None:
            return cached

        sound = self._sound_factory(path_key)
        self._sound_cache.put(path_key, sound)
        return sound

    def cache_size(self) -> int:
        """Cantidad de sonidos actualmente cacheados (para tests/diagnóstico)."""
        return len(self._sound_cache)

    def stop_all(self) -> None:
        """Detiene toda la reproducción de audio activa."""
        if self._mixer_ready:
            import pygame

            pygame.mixer.stop()
            logger.info("Audio detenido")
