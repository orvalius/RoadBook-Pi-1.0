"""Tests de ConfigManager."""

from __future__ import annotations

from pathlib import Path

from core.config_manager import ConfigManager


def test_creates_default_config_if_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config = ConfigManager(config_path)

    assert config_path.exists()
    assert config.get("app_name") == "RoadBook Pi"


def test_get_with_nested_key() -> None:
    config = ConfigManager(Path("/tmp/roadbook_test_config.json"))
    assert config.get("gps.backend") is not None


def test_get_returns_default_for_missing_key(tmp_path: Path) -> None:
    config = ConfigManager(tmp_path / "config.json")
    assert config.get("no.existe", "fallback") == "fallback"


def test_set_and_persist(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config = ConfigManager(config_path)

    config.set("gps.backend", "serial")
    config.save()

    reloaded = ConfigManager(config_path)
    assert reloaded.get("gps.backend") == "serial"


def test_set_creates_nested_keys(tmp_path: Path) -> None:
    config = ConfigManager(tmp_path / "config.json")
    config.set("nuevo.valor.anidado", 42)
    assert config.get("nuevo.valor.anidado") == 42
