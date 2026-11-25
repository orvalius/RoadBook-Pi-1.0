"""Tests de core.plugin_manager."""

from __future__ import annotations

from pathlib import Path

from core.plugin_manager import PluginManager, RoadBookPlugin, discover_plugin_classes

VALID_PLUGIN_SOURCE = """
from core.plugin_manager import RoadBookPlugin

class SamplePlugin(RoadBookPlugin):
    name = "sample_plugin"

    def on_load(self):
        self.loaded = True

    def execute(self, payload):
        self.last_payload = payload
"""

BROKEN_SYNTAX_SOURCE = "def esto no es python valido(((( :"

INCOMPLETE_PLUGIN_SOURCE = """
from core.plugin_manager import RoadBookPlugin

class IncompletePlugin(RoadBookPlugin):
    name = "incomplete_plugin"

    def on_load(self):
        pass
    # falta implementar execute() -> no debe poder instanciarse (ABC)
"""

NO_PLUGIN_CLASS_SOURCE = """
x = 1  # archivo sin ninguna clase RoadBookPlugin
"""


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_discover_finds_valid_plugin(tmp_path: Path) -> None:
    _write(tmp_path / "sample.py", VALID_PLUGIN_SOURCE)
    discovered = discover_plugin_classes(tmp_path)
    assert "sample_plugin" in discovered
    assert issubclass(discovered["sample_plugin"], RoadBookPlugin)


def test_discover_skips_file_with_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path / "broken.py", BROKEN_SYNTAX_SOURCE)
    _write(tmp_path / "sample.py", VALID_PLUGIN_SOURCE)
    discovered = discover_plugin_classes(tmp_path)
    # El archivo roto no debe tumbar el descubrimiento del resto
    assert "sample_plugin" in discovered
    assert len(discovered) == 1


def test_discover_skips_file_without_plugin_class(tmp_path: Path) -> None:
    _write(tmp_path / "empty.py", NO_PLUGIN_CLASS_SOURCE)
    discovered = discover_plugin_classes(tmp_path)
    assert discovered == {}


def test_discover_ignores_underscore_prefixed_files(tmp_path: Path) -> None:
    _write(tmp_path / "_helper.py", VALID_PLUGIN_SOURCE)
    discovered = discover_plugin_classes(tmp_path)
    assert discovered == {}


def test_discover_missing_directory_returns_empty(tmp_path: Path) -> None:
    discovered = discover_plugin_classes(tmp_path / "no_existe")
    assert discovered == {}


def test_load_from_directory_only_loads_enabled(tmp_path: Path) -> None:
    _write(tmp_path / "sample.py", VALID_PLUGIN_SOURCE)
    manager = PluginManager()

    loaded = manager.load_from_directory(tmp_path, enabled_names=[])

    assert loaded == []
    assert manager.get("sample_plugin") is None


def test_load_from_directory_loads_enabled_plugin(tmp_path: Path) -> None:
    _write(tmp_path / "sample.py", VALID_PLUGIN_SOURCE)
    manager = PluginManager()

    loaded = manager.load_from_directory(tmp_path, enabled_names=["sample_plugin"])

    assert loaded == ["sample_plugin"]
    plugin = manager.get("sample_plugin")
    assert plugin is not None
    assert plugin.loaded is True  # on_load() se ejecutó al registrar


def test_load_from_directory_unknown_enabled_name_does_not_crash(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "sample.py", VALID_PLUGIN_SOURCE)
    manager = PluginManager()

    loaded = manager.load_from_directory(tmp_path, enabled_names=["no_existe"])

    assert loaded == []
    assert manager.get("no_existe") is None


def test_load_from_directory_skips_incomplete_plugin(tmp_path: Path) -> None:
    """Una clase que no implementa execute() no puede instanciarse (ABC);
    el loader debe loguear y seguir, no crashear."""
    _write(tmp_path / "incomplete.py", INCOMPLETE_PLUGIN_SOURCE)
    manager = PluginManager()

    loaded = manager.load_from_directory(tmp_path, enabled_names=["incomplete_plugin"])

    assert loaded == []


def test_plugin_execute_receives_payload(tmp_path: Path) -> None:
    _write(tmp_path / "sample.py", VALID_PLUGIN_SOURCE)
    manager = PluginManager()
    manager.load_from_directory(tmp_path, enabled_names=["sample_plugin"])

    plugin = manager.get("sample_plugin")
    plugin.execute({"plugin_name": "sample_plugin", "foo": "bar"})

    assert plugin.last_payload == {"plugin_name": "sample_plugin", "foo": "bar"}


def test_list_plugins() -> None:
    manager = PluginManager()
    assert manager.list_plugins() == []
