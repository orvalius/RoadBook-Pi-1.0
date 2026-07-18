"""Tests de core.time_format."""

from __future__ import annotations

from core.time_format import format_duration_seconds


def test_seconds_only() -> None:
    assert format_duration_seconds(5) == "5s"
    assert format_duration_seconds(59) == "59s"


def test_minutes_and_seconds() -> None:
    assert format_duration_seconds(90) == "1m 30s"
    assert format_duration_seconds(125) == "2m 5s"


def test_exact_minutes_no_seconds_shown() -> None:
    assert format_duration_seconds(120) == "2m"


def test_hours_and_minutes() -> None:
    assert format_duration_seconds(3665) == "1h 1m"


def test_exact_hours_no_minutes_shown() -> None:
    assert format_duration_seconds(7200) == "2h"


def test_negative_clamped_to_zero() -> None:
    assert format_duration_seconds(-5) == "0s"


def test_zero() -> None:
    assert format_duration_seconds(0) == "0s"
