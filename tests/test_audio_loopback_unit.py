"""Unit tests for aureka.audio_loopback (cross-platform loopback detection)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── detect() / list_candidates() ───────────────────────────────────────────

def test_install_hint_macos(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al.platform, "system", lambda: "Darwin")
    hint = al.install_hint()
    assert "BlackHole" in hint or "blackhole" in hint
    assert "brew install" in hint


def test_install_hint_windows(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al.platform, "system", lambda: "Windows")
    hint = al.install_hint()
    assert "WASAPI" in hint
    assert "aureka[listen]" in hint


def test_install_hint_linux(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al.platform, "system", lambda: "Linux")
    hint = al.install_hint()
    assert "monitor" in hint.lower()


def test_list_candidates_macos_filters_blackhole(monkeypatch):
    """macOS path picks devices whose name starts with BlackHole / Loopback."""
    from aureka import audio_loopback as al

    monkeypatch.setattr(al.platform, "system", lambda: "Darwin")

    fake_sc = MagicMock()
    fake_sc.all_microphones.return_value = [
        MagicMock(name="MacBook Pro Microphone"),
        MagicMock(name="BlackHole 2ch"),
        MagicMock(name="Loopback"),
        MagicMock(name="External"),
    ]
    # set the .name attribute on each (MagicMock(name=) sets the mock's repr name, not the attr)
    for m, n in zip(fake_sc.all_microphones.return_value,
                    ["MacBook Pro Microphone", "BlackHole 2ch", "Loopback", "External"]):
        m.name = n
    with patch.dict("sys.modules", {"soundcard": fake_sc}):
        cands = al.list_candidates()

    names = [c.name for c in cands]
    assert "BlackHole 2ch" in names
    assert "Loopback" in names
    assert "MacBook Pro Microphone" not in names
    assert "External" not in names


def test_list_candidates_windows_one_per_speaker(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al.platform, "system", lambda: "Windows")

    spk = MagicMock(); spk.name = "Speakers (Realtek)"; spk.id = "spk-id"
    mic = MagicMock(); mic.name = "Speakers (Realtek)"
    fake_sc = MagicMock()
    fake_sc.all_speakers.return_value = [spk]
    fake_sc.get_microphone.return_value = mic
    with patch.dict("sys.modules", {"soundcard": fake_sc}):
        cands = al.list_candidates()
    assert len(cands) == 1
    assert cands[0].backend == "wasapi-loopback"


def test_list_candidates_linux_filters_monitor(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al.platform, "system", lambda: "Linux")

    fake_sc = MagicMock()
    fake_sc.all_microphones.return_value = [MagicMock(), MagicMock(), MagicMock()]
    for m, n in zip(fake_sc.all_microphones.return_value, [
        "alsa_input.usb-Webcam.analog-mono",
        "alsa_output.pci.analog-stereo.monitor",
        "alsa_input.pci-builtin.analog-stereo",
    ]):
        m.name = n
    with patch.dict("sys.modules", {"soundcard": fake_sc}):
        cands = al.list_candidates()
    names = [c.name for c in cands]
    assert any("monitor" in n.lower() for n in names)
    assert "alsa_input.usb-Webcam.analog-mono" not in names


def test_detect_returns_none_when_no_candidates(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al, "list_candidates", lambda: [])
    assert al.detect() is None


def test_detect_returns_first_candidate(monkeypatch):
    from aureka import audio_loopback as al
    fake = al.LoopbackDevice(name="X", backend="blackhole")
    monkeypatch.setattr(al, "list_candidates", lambda: [fake])
    assert al.detect() is fake


# ── ListenConfig defaults ──────────────────────────────────────────────────

def test_listen_config_defaults():
    from aureka.config import ListenConfig
    cfg = ListenConfig()
    assert cfg.device == ""
    assert cfg.input_mode == "transcribe"
    assert cfg.target_lang == "zh"
    assert cfg.window is False
    assert cfg.out_path == ""
    assert cfg.idle_timeout_seconds == 1800


def test_listen_config_loads_from_toml(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("""
[listen]
device = "BlackHole 2ch"
input_mode = "refine"
""")
    monkeypatch.setenv("AUREKA_CONFIG", str(cfg_file))
    from aureka.config import load_config
    cfg = load_config(cfg_file)
    assert cfg.listen.device == "BlackHole 2ch"
    assert cfg.listen.input_mode == "refine"


# ── CLI registration ──────────────────────────────────────────────────────

def test_listen_subcommand_registered():
    """`aureka listen --help` should not error and should mention loopback."""
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "aureka", "listen", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "loopback" in r.stdout.lower() or "system audio" in r.stdout.lower()


def test_doctor_audio_subcommand_registered():
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "aureka", "doctor", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "audio" in r.stdout.lower()
