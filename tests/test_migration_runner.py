"""Tests de MigrationRunner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from database.migration_runner import MigrationRunner


def test_applies_pending_migrations(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    runner = MigrationRunner(conn)
    applied = runner.apply_pending()

    assert 1 in applied
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='waypoints'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_does_not_reapply_migrations(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    runner = MigrationRunner(conn)
    runner.apply_pending()
    second_run = runner.apply_pending()

    assert second_run == []
    conn.close()


def test_waypoints_table_has_re_triggerable_column() -> None:
    conn = sqlite3.connect(":memory:")
    runner = MigrationRunner(conn)
    runner.apply_pending()

    cursor = conn.execute("PRAGMA table_info(waypoints)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "re_triggerable" in columns
    conn.close()
