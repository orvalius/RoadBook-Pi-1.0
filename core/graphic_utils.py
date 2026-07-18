"""Utilidades puras del Graphic Engine.

Funciones sin dependencias de Qt/PyQt, para mantener la lógica de
cálculo separada y testeable de la renderización real (que sí vive en
``ui/`` porque necesita QPixmap/QLabel).
"""

from __future__ import annotations


def compute_scaled_size(
    original_width: float,
    original_height: float,
    max_width: float,
    max_height: float,
) -> tuple[float, float]:
    """Calcula el tamaño máximo que preserva el aspect ratio original.

    Usado para escalar imágenes de waypoints a distintas resoluciones
    de pantalla (TFT HDMI, TFT DSI, HDMI estándar) sin deformarlas.

    Args:
        original_width: Ancho original de la imagen.
        original_height: Alto original de la imagen.
        max_width: Ancho máximo disponible (ej: ancho del widget).
        max_height: Alto máximo disponible.

    Returns:
        Tupla (ancho, alto) escalada, sin exceder max_width/max_height.

    Raises:
        ValueError: Si alguna dimensión original es <= 0.
    """
    if original_width <= 0 or original_height <= 0:
        raise ValueError("Las dimensiones originales deben ser positivas")
    if max_width <= 0 or max_height <= 0:
        return (0.0, 0.0)

    aspect_ratio = original_width / original_height
    target_ratio = max_width / max_height

    if aspect_ratio > target_ratio:
        # La imagen es relativamente más ancha: el ancho es el límite.
        width = max_width
        height = width / aspect_ratio
    else:
        # La imagen es relativamente más alta: el alto es el límite.
        height = max_height
        width = height * aspect_ratio

    return (width, height)
