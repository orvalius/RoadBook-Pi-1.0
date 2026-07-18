"""Cache LRU genérico de RoadBook Pi.

Utilidad reutilizable para las optimizaciones del Sprint 10 (tiles de
mapa decodificados, sonidos cargados). Implementación simple basada
en ``dict`` con reordenamiento manual (evita depender de
``functools.lru_cache``, que no sirve para cachear por instancia con
tamaño configurable en runtime).
"""

from __future__ import annotations

from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Cache LRU (least-recently-used) de tamaño fijo.

    Attributes:
        max_size: Cantidad máxima de entradas antes de empezar a
            descartar las menos usadas recientemente.
    """

    def __init__(self, max_size: int = 64) -> None:
        if max_size <= 0:
            raise ValueError("max_size debe ser mayor a 0")
        self.max_size = max_size
        self._data: dict[K, V] = {}

    def get(self, key: K) -> V | None:
        """Obtiene un valor y lo marca como usado recientemente.

        Args:
            key: Clave a buscar.

        Returns:
            El valor cacheado, o None si no está (miss).
        """
        if key not in self._data:
            return None
        value = self._data.pop(key)
        self._data[key] = value  # reinsertar al final = más reciente
        return value

    def put(self, key: K, value: V) -> None:
        """Guarda un valor, descartando el menos usado si hace falta espacio.

        Args:
            key: Clave.
            value: Valor a cachear.
        """
        if key in self._data:
            self._data.pop(key)
        elif len(self._data) >= self.max_size:
            oldest_key = next(iter(self._data))
            self._data.pop(oldest_key)
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: K) -> bool:
        return key in self._data

    def clear(self) -> None:
        """Vacía el cache por completo."""
        self._data.clear()
