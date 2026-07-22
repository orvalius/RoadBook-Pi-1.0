"""Tests de core.roadbook_engine (Roadbook Rendering Engine)."""

from __future__ import annotations

from core.gps_manager import GpsPosition
from core.roadbook_engine import RoadbookEngine, build_entries
from database.models import Waypoint


def _sample_entries():
    wp1 = Waypoint(id=1, nombre="Largada", latitud=0.00, longitud=0.00, radio=50)
    wp2 = Waypoint(id=2, nombre="Medio", latitud=0.01, longitud=0.00, radio=50)
    wp3 = Waypoint(id=3, nombre="Llegada", latitud=0.02, longitud=0.00, radio=50)
    return build_entries([wp1, wp2, wp3])


def test_build_entries_computes_distances() -> None:
    entries = _sample_entries()
    assert entries[0].distancia_parcial_m == 0.0
    assert entries[1].distancia_parcial_m > 1000  # ~1.1km entre paralelos de 0.01°
    assert entries[2].distancia_total_m > entries[1].distancia_total_m


def test_build_entries_empty_list() -> None:
    assert build_entries([]) == []


def test_stays_on_first_entry_when_far_from_everything() -> None:
    engine = RoadbookEngine(_sample_entries())
    state = engine.update_position(GpsPosition(latitude=-1.0, longitude=-1.0, has_fix=True))
    assert state.current_index == 0


def test_advances_when_entering_current_entry_radius() -> None:
    engine = RoadbookEngine(_sample_entries())
    engine.update_position(GpsPosition(latitude=-1.0, longitude=-1.0, has_fix=True))
    state = engine.update_position(GpsPosition(latitude=0.00, longitude=0.00, has_fix=True))
    assert state.current_index == 1


def test_progress_fraction_mid_segment() -> None:
    engine = RoadbookEngine(_sample_entries())
    engine.update_position(GpsPosition(latitude=0.00, longitude=0.00, has_fix=True))  # -> idx 1
    state = engine.update_position(GpsPosition(latitude=0.005, longitude=0.00, has_fix=True))
    assert 0.3 < state.progress_fraction < 0.7


def test_no_fix_does_not_advance_or_crash() -> None:
    engine = RoadbookEngine(_sample_entries())
    engine.update_position(GpsPosition(latitude=0.00, longitude=0.00, has_fix=True))  # -> idx 1
    before = engine.update_position(GpsPosition(latitude=0.005, longitude=0.00, has_fix=True))
    after = engine.update_position(GpsPosition(latitude=0.01, longitude=0.00, has_fix=False))
    assert after.current_index == before.current_index
    assert after.distance_to_next_m is None


def test_does_not_advance_past_last_entry() -> None:
    engine = RoadbookEngine(_sample_entries())
    engine.update_position(GpsPosition(latitude=0.00, longitude=0.00, has_fix=True))
    engine.update_position(GpsPosition(latitude=0.01, longitude=0.00, has_fix=True))
    state = engine.update_position(GpsPosition(latitude=0.02, longitude=0.00, has_fix=True))
    assert state.current_index == 2

    state2 = engine.update_position(GpsPosition(latitude=0.02, longitude=0.00, has_fix=True))
    assert state2.current_index == 2


def test_reset_returns_to_first_entry() -> None:
    engine = RoadbookEngine(_sample_entries())
    engine.update_position(GpsPosition(latitude=0.00, longitude=0.00, has_fix=True))
    assert engine.update_position(
        GpsPosition(latitude=-1.0, longitude=-1.0, has_fix=True)
    ).current_index == 1

    engine.reset()
    state = engine.update_position(GpsPosition(latitude=-1.0, longitude=-1.0, has_fix=True))
    assert state.current_index == 0


def test_empty_engine_does_not_crash() -> None:
    engine = RoadbookEngine([])
    state = engine.update_position(GpsPosition(latitude=0, longitude=0, has_fix=True))
    assert state.entries == []
    assert state.current_index == 0
