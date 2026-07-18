"""Tests de ActionRepository."""

from __future__ import annotations

from pathlib import Path

from database.action_repository import ActionRepository
from database.db_manager import DatabaseManager
from database.models import Action, Waypoint
from database.waypoint_repository import WaypointRepository


def _make_repos(tmp_path: Path) -> tuple[WaypointRepository, ActionRepository]:
    db = DatabaseManager(tmp_path / "test.db")
    db.initialize_schema()
    return WaypointRepository(db), ActionRepository(db)


def test_create_and_list_for_waypoint(tmp_path: Path) -> None:
    wp_repo, action_repo = _make_repos(tmp_path)
    wp = wp_repo.create(Waypoint(nombre="Test", latitud=0, longitud=0))

    action_repo.create(Action(waypoint_id=wp.id, orden=0, tipo="show_image", payload={"path": "a.jpg"}))
    action_repo.create(Action(waypoint_id=wp.id, orden=1, tipo="wait", payload={"seconds": 3}))

    actions = action_repo.list_for_waypoint(wp.id)
    assert len(actions) == 2
    assert actions[0].tipo == "show_image"
    assert actions[1].tipo == "wait"
    assert actions[1].payload == {"seconds": 3}


def test_list_for_waypoint_without_actions_returns_empty(tmp_path: Path) -> None:
    wp_repo, action_repo = _make_repos(tmp_path)
    wp = wp_repo.create(Waypoint(nombre="Sin acciones", latitud=0, longitud=0))
    assert action_repo.list_for_waypoint(wp.id) == []


def test_actions_ordered_by_orden(tmp_path: Path) -> None:
    wp_repo, action_repo = _make_repos(tmp_path)
    wp = wp_repo.create(Waypoint(nombre="Test", latitud=0, longitud=0))

    action_repo.create(Action(waypoint_id=wp.id, orden=2, tipo="log_event", payload={}))
    action_repo.create(Action(waypoint_id=wp.id, orden=0, tipo="show_image", payload={}))
    action_repo.create(Action(waypoint_id=wp.id, orden=1, tipo="wait", payload={}))

    actions = action_repo.list_for_waypoint(wp.id)
    assert [a.tipo for a in actions] == ["show_image", "wait", "log_event"]


def test_replace_sequence_deletes_old_and_renumbers(tmp_path: Path) -> None:
    wp_repo, action_repo = _make_repos(tmp_path)
    wp = wp_repo.create(Waypoint(nombre="Test", latitud=0, longitud=0))

    action_repo.create(Action(waypoint_id=wp.id, orden=0, tipo="show_image", payload={}))

    new_sequence = [
        Action(waypoint_id=0, orden=99, tipo="play_audio", payload={"path": "b.wav"}),
        Action(waypoint_id=0, orden=99, tipo="log_event", payload={"message": "hola"}),
    ]
    action_repo.replace_sequence(wp.id, new_sequence)

    actions = action_repo.list_for_waypoint(wp.id)
    assert len(actions) == 2
    assert [a.tipo for a in actions] == ["play_audio", "log_event"]
    assert [a.orden for a in actions] == [0, 1]


def test_delete_all_for_waypoint(tmp_path: Path) -> None:
    wp_repo, action_repo = _make_repos(tmp_path)
    wp = wp_repo.create(Waypoint(nombre="Test", latitud=0, longitud=0))
    action_repo.create(Action(waypoint_id=wp.id, orden=0, tipo="show_image", payload={}))

    action_repo.delete_all_for_waypoint(wp.id)

    assert action_repo.list_for_waypoint(wp.id) == []


def test_actions_deleted_when_waypoint_deleted_cascade(tmp_path: Path) -> None:
    wp_repo, action_repo = _make_repos(tmp_path)
    wp = wp_repo.create(Waypoint(nombre="Test", latitud=0, longitud=0))
    action_repo.create(Action(waypoint_id=wp.id, orden=0, tipo="show_image", payload={}))

    wp_repo.delete(wp.id)

    assert action_repo.list_for_waypoint(wp.id) == []
