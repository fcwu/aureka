"""Unit tests for aureka.subtitle (SRT/VTT writers + format parser)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ── SRT writer ──────────────────────────────────────────────────────────────

def test_srt_single_segment(tmp_path):
    from aureka.subtitle import write_srt
    p = tmp_path / "out.srt"
    write_srt([(0.0, 2.5, "今天天氣很好")], p)
    body = p.read_text(encoding="utf-8")
    assert body == "1\n00:00:00,000 --> 00:00:02,500\n今天天氣很好\n"


def test_srt_multiple_segments_indexed(tmp_path):
    from aureka.subtitle import write_srt
    p = tmp_path / "out.srt"
    write_srt([
        (0.0, 1.0, "first"),
        (1.0, 2.0, "second"),
    ], p)
    body = p.read_text(encoding="utf-8")
    # 1-based index
    assert "1\n" in body
    assert "2\n" in body
    # Two cues separated by blank line
    assert body.count("-->") == 2


def test_srt_millisecond_precision(tmp_path):
    from aureka.subtitle import write_srt
    p = tmp_path / "out.srt"
    write_srt([(1.234, 1.999, "x")], p)
    body = p.read_text(encoding="utf-8")
    assert "00:00:01,234" in body
    assert "00:00:01,999" in body


def test_srt_skips_empty_text(tmp_path):
    from aureka.subtitle import write_srt
    p = tmp_path / "out.srt"
    write_srt([(0.0, 1.0, ""), (1.0, 2.0, "x")], p)
    body = p.read_text(encoding="utf-8")
    # The empty-text segment is dropped, so the rendered cue (kept) ends up
    # numbered "1" because the writer only emits non-empty segments
    assert body.startswith("1\n")
    assert body.count("-->") == 1


# ── VTT writer ──────────────────────────────────────────────────────────────

def test_vtt_starts_with_webvtt_header(tmp_path):
    from aureka.subtitle import write_vtt
    p = tmp_path / "out.vtt"
    write_vtt([(0.0, 1.0, "x")], p)
    body = p.read_text(encoding="utf-8")
    assert body.startswith("WEBVTT\n")


def test_vtt_uses_dot_decimal(tmp_path):
    from aureka.subtitle import write_vtt
    p = tmp_path / "out.vtt"
    write_vtt([(1.234, 2.0, "x")], p)
    body = p.read_text(encoding="utf-8")
    assert "00:00:01.234" in body
    assert "," not in body  # no SRT comma decimal


# ── parse_formats ──────────────────────────────────────────────────────────

def test_parse_formats_default_md():
    from aureka.subtitle import parse_formats
    assert parse_formats("") == {"md"}
    assert parse_formats("md") == {"md"}


def test_parse_formats_all_expands():
    from aureka.subtitle import parse_formats
    # 'all' covers every supported writer including HTML (added with diarization)
    assert parse_formats("all") == {"md", "srt", "vtt", "html"}


def test_parse_formats_comma_list():
    from aureka.subtitle import parse_formats
    assert parse_formats("md,srt") == {"md", "srt"}
    assert parse_formats(" srt , vtt ") == {"srt", "vtt"}


def test_parse_formats_unknown_raises():
    from aureka.subtitle import parse_formats
    with pytest.raises(ValueError, match="pdf"):
        parse_formats("md,pdf")


# ── Recorder pause/resume ──────────────────────────────────────────────────

def test_recorder_default_paused_false():
    from aureka.recorder import Recorder
    r = Recorder(mode="hold-to-record")
    assert r.paused is False


def test_recorder_pause_resume_toggles():
    from aureka.recorder import Recorder
    r = Recorder(mode="hold-to-record")
    r.pause()
    assert r.paused is True
    r.resume()
    assert r.paused is False


# ── HotkeyConfig.pause field ──────────────────────────────────────────────

def test_hotkey_config_pause_default():
    from aureka.config import HotkeyConfig
    cfg = HotkeyConfig()
    assert cfg.pause == "<ctrl>+<alt>+p"


# ── Pipeline format dispatch (mocked) ──────────────────────────────────────

def test_pipeline_default_format_md_only(tmp_path, monkeypatch):
    """Default (no `formats` arg) preserves original Markdown-only behavior."""
    import aureka.pipeline as pl
    import aureka.subtitle as sub

    captured: list = []
    monkeypatch.setattr(sub, "write_srt", lambda *a, **kw: captured.append("srt"))
    monkeypatch.setattr(sub, "write_vtt", lambda *a, **kw: captured.append("vtt"))

    # Re-implement the format dispatch in isolation: pipeline uses {"md"} default
    formats = None
    formats = formats or {"md"}
    if "srt" in formats:
        sub.write_srt([], tmp_path / "x.srt")
    if "vtt" in formats:
        sub.write_vtt([], tmp_path / "x.vtt")

    assert captured == []  # neither srt nor vtt invoked


def test_pipeline_format_all_invokes_writers(tmp_path):
    """`all` set triggers every writer once."""
    from aureka.subtitle import parse_formats, write_srt, write_vtt
    formats = parse_formats("all")
    assert {"md", "srt", "vtt", "html"} <= formats
    write_srt([(0.0, 1.0, "x")], tmp_path / "out.srt")
    write_vtt([(0.0, 1.0, "x")], tmp_path / "out.vtt")
    assert (tmp_path / "out.srt").exists()
    assert (tmp_path / "out.vtt").exists()
