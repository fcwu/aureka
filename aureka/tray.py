"""System tray entry point.

Menu bar (macOS) / system tray (Windows / Linux). Menu items spawn the
relevant `aureka` CLI subcommand as a subprocess so each window has its
own process and event loop — avoids GUI-toolkit threading constraints
when launching pywebview from inside the tray callback.
"""
from __future__ import annotations

import socket
import subprocess
import sys


def _make_icon():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(45, 127, 249, 255))
    d.text((22, 18), "A", fill="white")
    return img


def _daemon_running() -> bool:
    from aureka.config import get_config
    cfg = get_config()
    try:
        s = socket.create_connection((cfg.daemon.host, cfg.daemon.port), timeout=0.3)
        s.close()
        return True
    except OSError:
        return False


def _spawn(*args: str) -> None:
    subprocess.Popen(
        [sys.executable, "-m", "aureka", *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run_tray() -> None:
    try:
        import pystray
        from pystray import Menu, MenuItem
    except ImportError as e:
        raise SystemExit(
            "pystray not installed. Install with: pip install 'aureka[voice]'"
        ) from e

    def _noop(icon, item):
        pass

    def on_settings(icon, item):
        _spawn("ui")

    def on_start(icon, item):
        _spawn("daemon", "start")

    def on_stop(icon, item):
        _spawn("daemon", "stop")

    def on_quit(icon, item):
        icon.stop()

    def daemon_label(item):
        return "Daemon: running" if _daemon_running() else "Daemon: stopped"

    menu = Menu(
        MenuItem(daemon_label, _noop, enabled=False),
        Menu.SEPARATOR,
        MenuItem("Settings…", on_settings),
        Menu.SEPARATOR,
        MenuItem("Start daemon", on_start),
        MenuItem("Stop daemon", on_stop),
        Menu.SEPARATOR,
        MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon("aureka", _make_icon(), "Aureka", menu)
    icon.run()


if __name__ == "__main__":
    run_tray()
