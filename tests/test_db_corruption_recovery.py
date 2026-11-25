"""Tests de recuperación de DatabaseManager ante corrupción (Sprint 11)."""

from __future__ import annotations

from pathlib import Path

from database.db_manager import DatabaseManager


def test_valid_database_is_not_touched(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize_schema()
    db.close()

    # Reabrir: no debe generar ningún archivo de cuarentena
    db2 = DatabaseManager(db_path)
    db2.connect()
    db2.close()

    quarantine_files = list(tmp_path.glob("*.corrupt-*"))
    assert quarantine_files == []


def test_corrupt_file_is_quarantined_and_recreated(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    # Un archivo que NO es un sqlite válido (texto plano)
    db_path.write_text("esto no es una base de datos sqlite", encoding="utf-8")

    db = DatabaseManager(db_path)
    db.initialize_schema()  # no debe lanzar excepción

    # La base nueva debe ser válida y tener el schema aplicado
    conn = db.connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='waypoints'"
    ).fetchone()
    assert row is not None
    db.close()

    # El archivo original corrupto debe seguir existiendo, renombrado
    quarantine_files = list(tmp_path.glob("test.corrupt-*.db"))
    assert len(quarantine_files) == 1
    assert (
        quarantine_files[0].read_text(encoding="utf-8")
        == "esto no es una base de datos sqlite"
    )


def test_recreated_database_is_usable(tmp_path: Path) -> None:
    from database.models import Waypoint
    from database.waypoint_repository import WaypointRepository

    db_path = tmp_path / "test.db"
    db_path.write_bytes(b"\x00\x01\x02basura-binaria-no-sqlite")

    db = DatabaseManager(db_path)
    db.initialize_schema()
    repo = WaypointRepository(db)

    created = repo.create(Waypoint(nombre="Post-recuperación", latitud=0, longitud=0))
    assert created.id is not None
    assert repo.get(created.id).nombre == "Post-recuperación"

    db.close()
