"""Tests de importación con progreso (mbtiles grandes) y categoría routes."""

from __future__ import annotations

from pathlib import Path

import pytest

import core.resource_manager as rm_module
from core.resource_manager import ResourceManager


def test_routes_category_exists(tmp_path: Path) -> None:
    manager = ResourceManager(tmp_path / "resources")
    assert (tmp_path / "resources" / "routes").is_dir()
    assert manager.list_resources("routes") == []


def test_import_with_progress_reports_until_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rm_module, "COPY_CHUNK_BYTES", 1000)
    source = tmp_path / "grande.mbtiles"
    source.write_bytes(b"x" * 4500)
    manager = ResourceManager(tmp_path / "resources")
    calls: list[tuple[int, int]] = []

    relative = manager.import_resource(
        source, "maps", progress=lambda c, t: calls.append((c, t))
    )

    assert relative == "resources/maps/grande.mbtiles"
    assert (tmp_path / relative).read_bytes() == source.read_bytes()
    assert calls[0] == (0, 4500)
    assert calls[-1] == (4500, 4500)
    assert len(calls) == 6  # 0 + 5 chunks


def test_failed_copy_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rm_module, "COPY_CHUNK_BYTES", 1000)
    source = tmp_path / "grande.mbtiles"
    source.write_bytes(b"x" * 4500)
    manager = ResourceManager(tmp_path / "resources")

    def cancel_midway(copied: int, _total: int) -> None:
        if copied >= 2000:
            raise RuntimeError("cancelado")

    with pytest.raises(RuntimeError):
        manager.import_resource(source, "maps", progress=cancel_midway)
    assert manager.list_resources("maps") == []
