"""Unit tests for aureka.tray — daemon-aware tray entry point.

Focuses on the pure-helper layer: daemon detection, ui-extra detection,
spawn logging. Does not exercise the pystray run loop (that needs a real
display server).
"""
from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ── _daemon_running ─────────────────────────────────────────────────────────

def test_daemon_running_false_when_port_closed(monkeypatch):
    from aureka import tray
    from aureka.config import Config
    cfg = Config()
    cfg.daemon.port = 1  # privileged port: nobody is listening here for us

    monkeypatch.setattr("aureka.tray.get_config", lambda: cfg, raising=False)
    monkeypatch.setattr("aureka.config.get_config", lambda: cfg)
    assert tray._daemon_running() is False


def test_daemon_running_true_when_socket_open(tmp_path, monkeypatch):
    """Open a real TCP listener on a free port, point cfg at it, expect True."""
    from aureka import tray
    from aureka.config import Config

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        cfg = Config()
        cfg.daemon.host = "127.0.0.1"
        cfg.daemon.port = port
        monkeypatch.setattr("aureka.config.get_config", lambda: cfg)
        assert tray._daemon_running() is True
    finally:
        server.close()


# ── _ui_extra_available ─────────────────────────────────────────────────────

def test_ui_extra_available_when_both_imports_succeed():
    from aureka import tray
    # In the test env both libs ship; sanity check matches reality.
    assert tray._ui_extra_available() is True


def test_ui_extra_available_false_when_pywebview_missing():
    """Simulate `[ui]` extra not installed."""
    from aureka import tray
    real_import = __import__

    def selective(name, *a, **kw):
        if name == "webview":
            raise ImportError("pywebview not installed")
        return real_import(name, *a, **kw)

    with patch("builtins.__import__", side_effect=selective):
        assert tray._ui_extra_available() is False


def test_ui_extra_available_false_when_tomlkit_missing():
    from aureka import tray
    real_import = __import__

    def selective(name, *a, **kw):
        if name == "tomlkit":
            raise ImportError("tomlkit not installed")
        return real_import(name, *a, **kw)

    with patch("builtins.__import__", side_effect=selective):
        assert tray._ui_extra_available() is False


# ── _spawn logging ─────────────────────────────────────────────────────────

def test_spawn_writes_log_marker(tmp_path, monkeypatch):
    """Each spawn appends a `=== spawn (...) ===` marker so the log is grep-able."""
    from aureka import tray

    log = tmp_path / "spawn.log"
    monkeypatch.setattr(tray, "_spawn_log_path", lambda: log)

    captured = {}
    class FakePopen:
        def __init__(self, *args, **kwargs):
            captured["args"] = args[0]
            captured["kwargs"] = kwargs

    monkeypatch.setattr(tray.subprocess, "Popen", FakePopen)
    tray._spawn("ui")

    assert log.exists()
    text = log.read_text()
    assert "=== spawn ('ui',) ===" in text
    # The Popen call gets stdout/stderr pointed at the same log file
    assert captured["kwargs"]["stdout"] is captured["kwargs"]["stderr"]
    assert captured["kwargs"]["start_new_session"] is True
    # Argv passes through to a fresh `python -m aureka ui`
    import sys
    assert captured["args"][0] == sys.executable
    assert captured["args"][1:] == ["-m", "aureka", "ui"]
