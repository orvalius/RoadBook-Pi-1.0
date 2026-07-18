"""Tests de core.map_compositor."""

from __future__ import annotations

import io

from PIL import Image

from core.map_compositor import CachedTileSource, compose_map_image, should_redraw


class FakeTileSource:
    """Fuente de tiles falsa: siempre devuelve un PNG sólido de un color."""

    def __init__(self, color: tuple[int, int, int] = (10, 20, 30), tile_size: int = 256) -> None:
        self.color = color
        self.tile_size = tile_size
        self.calls: list[tuple[int, int, int]] = []

    def get_tile(self, zoom: int, x: int, y: int) -> bytes | None:
        self.calls.append((zoom, x, y))
        img = Image.new("RGB", (self.tile_size, self.tile_size), color=self.color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


class EmptyTileSource:
    """Fuente de tiles que nunca tiene el tile pedido (simula zona sin descargar)."""

    def get_tile(self, zoom: int, x: int, y: int) -> bytes | None:
        return None


def test_compose_returns_correct_dimensions() -> None:
    source = FakeTileSource()
    image = compose_map_image(source, -34.6037, -58.3816, zoom=15, width_px=400, height_px=300)
    assert image.size == (400, 300)


def test_compose_with_none_source_returns_placeholder() -> None:
    image = compose_map_image(None, -34.6037, -58.3816, zoom=15, width_px=400, height_px=300)
    assert image.size == (400, 300)


def test_compose_with_empty_tiles_does_not_crash() -> None:
    source = EmptyTileSource()
    image = compose_map_image(source, -34.6037, -58.3816, zoom=15, width_px=400, height_px=300)
    assert image.size == (400, 300)


def test_compose_calls_tile_source_for_visible_area() -> None:
    source = FakeTileSource()
    compose_map_image(source, -34.6037, -58.3816, zoom=15, width_px=512, height_px=512)
    assert len(source.calls) > 0
    # Todos los calls deben ser al zoom pedido
    assert all(call[0] == 15 for call in source.calls)


def test_compose_zero_size_returns_minimal_image() -> None:
    source = FakeTileSource()
    image = compose_map_image(source, 0.0, 0.0, zoom=10, width_px=0, height_px=0)
    assert image.size == (1, 1)


def test_should_redraw_true_on_first_call() -> None:
    assert should_redraw(None, None, -34.6, -58.4) is True


def test_should_redraw_false_when_barely_moved() -> None:
    # Mismo punto -> distancia 0, no debe redibujar
    assert should_redraw(-34.6037, -58.3816, -34.6037, -58.3816, threshold_meters=20.0) is False


def test_should_redraw_true_when_moved_enough() -> None:
    # ~157km de diferencia, muy por encima del threshold
    assert should_redraw(-34.6037, -58.3816, -33.6037, -57.3816, threshold_meters=20.0) is True


def test_cached_tile_source_avoids_redundant_decode() -> None:
    source = FakeTileSource()
    cached = CachedTileSource(source)

    cached.get_tile_image(15, 100, 200, 256)
    cached.get_tile_image(15, 100, 200, 256)  # mismo tile, debe venir de cache

    assert len(source.calls) == 1  # get_tile del origen solo se llamó una vez
    assert cached.cache_size() == 1


def test_cached_tile_source_different_tiles_not_shared() -> None:
    source = FakeTileSource()
    cached = CachedTileSource(source)

    cached.get_tile_image(15, 100, 200, 256)
    cached.get_tile_image(15, 101, 200, 256)

    assert len(source.calls) == 2
    assert cached.cache_size() == 2


def test_cached_tile_source_respects_max_size() -> None:
    source = FakeTileSource()
    cached = CachedTileSource(source, max_cached_tiles=2)

    cached.get_tile_image(15, 0, 0, 256)
    cached.get_tile_image(15, 1, 0, 256)
    cached.get_tile_image(15, 2, 0, 256)  # debe descartar el primero

    assert cached.cache_size() == 2


def test_compose_map_image_uses_cached_tile_source() -> None:
    source = FakeTileSource()
    cached = CachedTileSource(source)

    compose_map_image(cached, -34.6037, -58.3816, zoom=15, width_px=512, height_px=512)
    calls_first_pass = len(source.calls)

    compose_map_image(cached, -34.6037, -58.3816, zoom=15, width_px=512, height_px=512)
    calls_second_pass = len(source.calls)

    # La segunda composición (misma posición/zoom) no debe pedir tiles
    # nuevos al origen: todos ya están en cache.
    assert calls_second_pass == calls_first_pass
