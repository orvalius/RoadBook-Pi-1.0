"""Tests de core.lru_cache."""

from __future__ import annotations

import pytest

from core.lru_cache import LRUCache


def test_get_miss_returns_none() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=3)
    assert cache.get("a") is None


def test_put_and_get() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=3)
    cache.put("a", 1)
    assert cache.get("a") == 1


def test_evicts_least_recently_used() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)  # debe descartar "a" (el menos usado)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_refreshes_recency() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")  # "a" pasa a ser el más reciente
    cache.put("c", 3)  # debe descartar "b", no "a"

    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_put_existing_key_updates_value_without_growing() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("a", 99)
    assert cache.get("a") == 99
    assert len(cache) == 1


def test_len_and_contains() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=5)
    cache.put("a", 1)
    assert len(cache) == 1
    assert "a" in cache
    assert "b" not in cache


def test_clear() -> None:
    cache: LRUCache[str, int] = LRUCache(max_size=5)
    cache.put("a", 1)
    cache.clear()
    assert len(cache) == 0
    assert cache.get("a") is None


def test_invalid_max_size_raises() -> None:
    with pytest.raises(ValueError):
        LRUCache(max_size=0)
    with pytest.raises(ValueError):
        LRUCache(max_size=-1)
