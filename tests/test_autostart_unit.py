"""Unit tests for aureka.autostart — login command builders."""
from __future__ import annotations

import os
import sys

import pytest

pytestmark = pytest.mark.unit

mac_only = pytest.mark.skipif(
    not hasattr(os, "getuid"),
    reason="macOS-specific (uses os.getuid for launchctl bootstrap)",
)


def test_serve_args_targets_aureka_tray():
    """The login command MUST be `python -m aureka tray` so tray boots
    daemon (per voice-input spec) — not `_daemon_serve` which leaves the
    user without a UI."""
    from aureka import autostart
    args = autostart._serve_args("127.0.0.1", 7777)
    assert args[1:] == ["-m", "aureka", "tray"]


def test_serve_args_uses_current_python():
    from aureka import autostart
    import sys
    args = autostart._serve_args("127.0.0.1", 7777)
    assert args[0] == sys.executable


def test_win_command_runs_aureka_tray():
    from aureka import autostart
    cmd = autostart._win_command("127.0.0.1", 7777)
    assert "-m aureka tray" in cmd
    # Wrapped in cmd /c so env var injection works
    assert cmd.startswith("cmd /c ")


def test_win_command_injects_aureka_config_when_present(tmp_path, monkeypatch):
    from aureka import autostart
    cfg = tmp_path / "config.toml"
    cfg.write_text("[llm]\n")
    monkeypatch.setenv("AUREKA_CONFIG", str(cfg))
    cmd = autostart._win_command("127.0.0.1", 7777)
    assert f'set "AUREKA_CONFIG={cfg.resolve()}"' in cmd


@mac_only
def test_mac_install_writes_adaptive_process_type(tmp_path, monkeypatch):
    """The plist that lands at install must declare ProcessType=Adaptive
    (tray needs UI access; Background suppresses NSStatusItem rendering)."""
    import plistlib
    from aureka import autostart

    out = tmp_path / "test.plist"
    monkeypatch.setattr(autostart, "_mac_plist_path", lambda: out)
    monkeypatch.setattr(autostart, "_mac_log_dir", lambda: tmp_path / "logs")
    # Skip the actual launchctl bootstrap — we only validate the file we wrote.
    monkeypatch.setattr(autostart.subprocess, "run",
                        lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())

    autostart._mac_install("127.0.0.1", 7777)

    plist = plistlib.loads(out.read_bytes())
    assert plist["ProgramArguments"][1:] == ["-m", "aureka", "tray"]
    assert plist["ProcessType"] == "Adaptive"
    # KeepAlive: clean exit doesn't respawn, crash does
    assert plist["KeepAlive"]["SuccessfulExit"] is False
    assert plist["KeepAlive"]["Crashed"] is True
    assert plist["RunAtLoad"] is True


def test_mac_status_returns_1_when_plist_missing(tmp_path, monkeypatch):
    from aureka import autostart
    monkeypatch.setattr(autostart, "_mac_plist_path", lambda: tmp_path / "nope.plist")
    rc = autostart._mac_status()
    assert rc == 1
