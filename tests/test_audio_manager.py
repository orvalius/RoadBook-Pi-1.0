"""Tests del cache de sonidos de AudioManager (Sprint 10)."""

from __future__ import annotations


class FakeSound:
    """Sonido falso: solo registra si se le pidió reproducir/volumen."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.play_count = 0
        self.volume = None

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def play(self) -> None:
        self.play_count += 1


def _make_manager(cache_size: int = 20):
    from core.audio_manager import AudioManager

    load_calls: list[str] = []

    def factory(path: str) -> FakeSound:
        load_calls.append(path)
        return FakeSound(path)

    manager = AudioManager(enabled=True, cache_size=cache_size, sound_factory=factory)
    return manager, load_calls


def test_play_loads_sound_via_factory() -> None:
    manager, load_calls = _make_manager()
    manager.play("audio/beep.wav")
    assert load_calls == ["audio/beep.wav"]


def test_play_same_file_twice_loads_only_once() -> None:
    manager, load_calls = _make_manager()
    manager.play("audio/beep.wav")
    manager.play("audio/beep.wav")
    manager.play("audio/beep.wav")

    assert load_calls == ["audio/beep.wav"]  # el factory se llamó una sola vez
    assert manager.cache_size() == 1


def test_play_calls_play_on_sound_each_time() -> None:
    manager, _ = _make_manager()
    manager.play("audio/beep.wav")
    manager.play("audio/beep.wav")

    sound = manager._get_or_load_sound("audio/beep.wav")
    # _get_or_load_sound solo lee del cache: no reproduce.
    assert sound.play_count == 2


def test_different_files_are_cached_separately() -> None:
    manager, load_calls = _make_manager()
    manager.play("a.wav")
    manager.play("b.wav")

    assert set(load_calls) == {"a.wav", "b.wav"}
    assert manager.cache_size() == 2


def test_cache_respects_max_size() -> None:
    manager, load_calls = _make_manager(cache_size=2)
    manager.play("a.wav")
    manager.play("b.wav")
    manager.play("c.wav")  # debe descartar "a.wav" del cache

    assert manager.cache_size() == 2
    manager.play("a.wav")  # se vuelve a cargar, ya no estaba en cache
    assert load_calls.count("a.wav") == 2


def test_disabled_manager_never_loads_sounds() -> None:
    from core.audio_manager import AudioManager

    load_calls: list[str] = []
    manager = AudioManager(enabled=False, sound_factory=lambda p: load_calls.append(p))
    manager.play("audio/beep.wav")

    assert load_calls == []
    assert manager.cache_size() == 0


def test_volume_applied_on_each_play() -> None:
    manager, _ = _make_manager()
    manager.volume = 0.3
    manager.play("audio/beep.wav")

    sound = manager._get_or_load_sound("audio/beep.wav")
    assert sound.volume == 0.3
