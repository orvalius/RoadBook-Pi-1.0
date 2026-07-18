"""Tests de WaypointRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from database.db_manager import DatabaseManager
from database.models import Waypoint
from database.waypoint_repository import WaypointNotFoundError, WaypointRepository


def _make_repo(tmp_path: Path) -> WaypointRepository:
    db = DatabaseManager(tmp_path / "test.db")
    db.initialize_schema()
    return WaypointRepository(db)


def test_create_assigns_id(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    wp = Waypoint(nombre="Curva peligrosa", latitud=-34.6, longitud=-58.4)
    created = repo.create(wp)
    assert created.id is not None


def test_get_returns_created_waypoint(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    created = repo.create(Waypoint(nombre="Puente", latitud=-34.6, longitud=-58.4, radio=80))
    fetched = repo.get(created.id)
    assert fetched.nombre == "Puente"
    assert fetched.radio == 80


def test_get_missing_raises(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    with pytest.raises(WaypointNotFoundError):
        repo.get(999)


def test_list_all_orders_by_priority(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    repo.create(Waypoint(nombre="Baja", latitud=0, longitud=0, prioridad=1))
    repo.create(Waypoint(nombre="Alta", latitud=0, longitud=0, prioridad=10))
    result = repo.list_all()
    assert result[0].nombre == "Alta"


def test_list_all_only_active(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    repo.create(Waypoint(nombre="Activo", latitud=0, longitud=0, activo=True))
    repo.create(Waypoint(nombre="Inactivo", latitud=0, longitud=0, activo=False))
    result = repo.list_all(only_active=True)
    assert len(result) == 1
    assert result[0].nombre == "Activo"


def test_update_persists_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    wp = repo.create(Waypoint(nombre="Original", latitud=0, longitud=0))
    wp.nombre = "Modificado"
    repo.update(wp)
    assert repo.get(wp.id).nombre == "Modificado"


def test_update_missing_raises(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    wp = Waypoint(nombre="Fantasma", latitud=0, longitud=0, id=999)
    with pytest.raises(WaypointNotFoundError):
        repo.update(wp)


def test_delete_removes_waypoint(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    wp = repo.create(Waypoint(nombre="Borrar", latitud=0, longitud=0))
    repo.delete(wp.id)
    with pytest.raises(WaypointNotFoundError):
        repo.get(wp.id)


def test_set_active_toggles_flag(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    wp = repo.create(Waypoint(nombre="Toggle", latitud=0, longitud=0, activo=True))
    repo.set_active(wp.id, False)
    assert repo.get(wp.id).activo is False
