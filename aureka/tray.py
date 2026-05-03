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
    from aureka._icon import make_tray_icon
    return make_tray_icon()


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

    # Auto-start the daemon when the tray launches and nothing is listening yet.
    # This is what makes `aureka autostart install` (which spawns `aureka tray`
    # at login) result in a working setup without requiring the user to also
    # click "Start daemon" from the menu.
    if not _daemon_running():
        _spawn("daemon", "start")

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

    # macOS: flip NSImage isTemplate after pystray binds the status item so the
    # menu bar auto-tints in light/dark mode. Schedule the shim on a short timer
    # because pystray needs the run loop spinning before _status_item exists.
    def _on_setup(icon):
        from aureka._icon import apply_macos_template
        icon.visible = True
        apply_macos_template(icon)

    icon.run(setup=_on_setup)


if __name__ == "__main__":
    run_tray()
