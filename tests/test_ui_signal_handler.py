"""Tests de ui.signal_handler: cierre ordenado ante SIGTERM/SIGINT.

Incluye una prueba de punta a punta en un proceso aparte con pygame
inicializado: es exactamente el caso que fallaba antes (SDL se tragaba
SIGTERM y el proceso no terminaba nunca bajo systemd).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")

from ui.signal_handler import GracefulShutdown  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="señales POSIX (SIGTERM real) solo en Linux/macOS"
)


@posix_only
def test_sigterm_invokes_callback_inside_qt_loop(qtbot) -> None:
    calls: list[str] = []
    shutdown = GracefulShutdown(on_shutdown=lambda: calls.append("quit"))
    shutdown.install()
    try:
        os.kill(os.getpid(), signal.SIGTERM)
        qtbot.waitUntil(lambda: calls == ["quit"], timeout=2000)
        assert shutdown.received_signal == signal.SIGTERM
    finally:
        shutdown.uninstall()


@posix_only
def test_second_signal_does_not_repeat_shutdown(qtbot) -> None:
    calls: list[str] = []
    shutdown = GracefulShutdown(on_shutdown=lambda: calls.append("quit"))
    shutdown.install()
    try:
        os.kill(os.getpid(), signal.SIGTERM)
        qtbot.waitUntil(lambda: len(calls) == 1, timeout=2000)
        os.kill(os.getpid(), signal.SIGINT)
        qtbot.wait(100)
        assert calls == ["quit"]
    finally:
        shutdown.uninstall()


def test_uninstall_restores_previous_handlers(qtbot) -> None:
    before = signal.getsignal(signal.SIGTERM)
    shutdown = GracefulShutdown(on_shutdown=lambda: None)
    shutdown.install()
    assert signal.getsignal(signal.SIGTERM) != before
    shutdown.uninstall()
    assert signal.getsignal(signal.SIGTERM) == before


@posix_only
def test_process_with_pygame_exits_cleanly_on_sigterm() -> None:
    script = textwrap.dedent("""
        import sys
        from PyQt6.QtWidgets import QApplication
        from core.audio_manager import AudioManager
        from ui.signal_handler import GracefulShutdown

        audio = AudioManager()            # inicializa pygame/SDL
        app = QApplication(sys.argv)
        shutdown = GracefulShutdown(on_shutdown=app.quit)
        shutdown.install()
        print("ready", flush=True)
        code = app.exec()
        print("clean-exit", flush=True)
        sys.exit(code)
        """)
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "SDL_AUDIODRIVER": "dummy",
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:  # saltear cualquier banner de librerías
            if line.strip() == "ready":
                break
        else:
            pytest.fail("el proceso terminó antes de estar listo")
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=5) == 0
        assert "clean-exit" in proc.stdout.read()
    finally:
        if proc.poll() is None:
            proc.kill()
