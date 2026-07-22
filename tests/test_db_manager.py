"""Tests de DatabaseManager."""

from __future__ import annotations

from pathlib import Path

from database.db_manager import DatabaseManager


def test_initialize_schema_creates_waypoints_table(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize_schema()

    conn = db.connect()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='waypoints'"
    )
    assert cursor.fetchone() is not None
    db.close()


def test_waypoints_table_has_expected_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize_schema()

    conn = db.connect()
    cursor = conn.execute("PRAGMA table_info(waypoints)")
    columns = {row["name"] for row in cursor.fetchall()}
    db.close()

    expected = {
        "id", "nombre", "latitud", "longitud", "radio", "categoria",
        "imagen", "audio", "velocidad", "angulo", "prioridad",
        "descripcion", "activo", "re_triggerable", "icono", "orden_ruta",
    }
    assert expected.issubset(columns)


def test_context_manager_closes_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with DatabaseManager(db_path) as db:
        db.initialize_schema()
        assert db._connection is not None
    assert db._connection is None
