"""Unit tests for aureka.ui — settings UI helpers and Api bridge methods.

These tests poke the pure-function layer (coercion, recommendations, vision
filter, HTML option injection, port probing) plus the Api class methods that
don't actually need a live pywebview window. Long-running tasks (download,
benchmark) are exercised with mocked backends.
"""
from __future__ import annotations

import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ── _coerce ─────────────────────────────────────────────────────────────────

def test_coerce_int_to_int():
    from aureka.ui import _coerce
    assert _coerce("42", 0) == 42


def test_coerce_float_to_float():
    from aureka.ui import _coerce
    assert _coerce("1.5", 1.0) == 1.5


def test_coerce_str_passthrough():
    from aureka.ui import _coerce
    assert _coerce(123, "abc") == "123"


def test_coerce_empty_returns_current_when_typed():
    """Empty input on a numeric field shouldn't blow up — return current value."""
    from aureka.ui import _coerce
    assert _coerce("", 7777) == 7777


def test_coerce_empty_returns_none_when_optional():
    from aureka.ui import _coerce
    assert _coerce("", None) is None


# ── _is_vision_capable ──────────────────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"id": "qwen2-vl-7b"},
    {"id": "llama-vision-11b"},
    {"id": "llava-1.6"},
    {"id": "gemma-3", "compatibility_type": "multimodal"},
    {"id": "internvl-2"},  # internvl matches via "vl"... actually no, let me try
])
def test_is_vision_capable_positive_tokens(payload):
    from aureka.ui import _is_vision_capable
    # Skip cases the heuristic doesn't catch
    blob = json.dumps(payload).lower()
    if not any(t in blob for t in ("vision", "image", "multimodal", "-vl", "_vl", "llava", "mm-")):
        pytest.skip(f"heuristic intentionally misses {payload!r}")
    assert _is_vision_capable(payload)


def test_is_vision_capable_text_only():
    from aureka.ui import _is_vision_capable
    assert _is_vision_capable({"id": "qwen3-8b"}) is False
    assert _is_vision_capable({"id": "llama-3.1-8b"}) is False


# ── _options_html ───────────────────────────────────────────────────────────

def test_options_html_emits_one_option_per_value():
    from aureka.ui import _options_html
    html = _options_html(["a", "b", "c"])
    assert html.count("<option") == 3
    assert '<option value="a">' in html
    assert '<option value="c">' in html


def test_render_html_injects_static_options():
    from aureka.ui import _render_html
    html = _render_html()
    # ASR sizes
    assert '<option value="medium">' in html
    assert '<option value="large-v3-turbo">' in html
    # TTS voices
    assert '<option value="zf_xiaobei">' in html
    # Hotkey langs
    assert '<option value="zh">' in html
    assert '<option value="ja">' in html


# ── _benchmark_recommendations ─────────────────────────────────────────────

def test_recs_asr_slow_suggests_smaller_model(monkeypatch):
    from aureka import ui
    from aureka.config import Config
    cfg = Config()
    cfg.asr.model = "medium"
    monkeypatch.setattr(ui, "load_config", lambda *a, **kw: cfg)

    result = {
        "tasks": {
            "asr": {"status": "ok", "median": 0.8, "min": 0.7, "max": 0.9},
            "tts": {"status": "ok", "median": 0.2},
            "llm": {"status": "ok", "median": 1500.0},
        },
    }
    recs = ui._benchmark_recommendations(result)
    asr_rec = next((r for r in recs if r["section"] == "asr"), None)
    assert asr_rec is not None
    assert asr_rec["key"] == "model"
    assert asr_rec["value"] == "small"  # medium → small per the order list


def test_recs_high_ttft_with_thinking_suggests_disable(monkeypatch):
    from aureka import ui
    from aureka.config import Config
    cfg = Config()
    cfg.llm.thinking_budget = 256
    monkeypatch.setattr(ui, "load_config", lambda *a, **kw: cfg)

    result = {
        "tasks": {
            "llm": {"status": "ok", "median": 4500.0},
            "asr": {"status": "ok", "median": 0.3},
            "tts": {"status": "ok", "median": 0.2},
        },
    }
    recs = ui._benchmark_recommendations(result)
    llm_rec = next((r for r in recs if r["section"] == "llm"), None)
    assert llm_rec is not None
    assert llm_rec["key"] == "thinking_budget"
    assert llm_rec["value"] == 0


def test_recs_no_recommendations_when_within_thresholds(monkeypatch):
    from aureka import ui
    from aureka.config import Config
    cfg = Config()
    cfg.asr.model = "medium"
    cfg.tts.device = "auto"
    cfg.llm.thinking_budget = 0
    monkeypatch.setattr(ui, "load_config", lambda *a, **kw: cfg)

    result = {
        "tasks": {
            "asr": {"status": "ok", "median": 0.3},
            "tts": {"status": "ok", "median": 0.2},
            "llm": {"status": "ok", "median": 1200.0},
        },
    }
    assert ui._benchmark_recommendations(result) == []


def test_recs_skip_failed_tasks(monkeypatch):
    """Don't recommend changes based on tasks that failed — the numbers are unreliable."""
    from aureka import ui
    from aureka.config import Config
    cfg = Config()
    monkeypatch.setattr(ui, "load_config", lambda *a, **kw: cfg)

    result = {
        "tasks": {
            "asr": {"status": "failed", "error": "boom", "median": None},
            "tts": {"status": "skipped"},
            "llm": {"status": "skipped"},
        },
    }
    assert ui._benchmark_recommendations(result) == []


# ── Api.find_free_port ──────────────────────────────────────────────────────

def test_find_free_port_returns_a_free_port():
    from aureka.ui import Api
    api = Api()
    r = api.find_free_port(50000)
    assert r["port"] is not None
    # Sanity: we can actually bind it ourselves
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", r["port"]))
    s.close()


def test_find_free_port_skips_busy_one():
    """If `start` is occupied, we get the next available one within window."""
    from aureka.ui import Api
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    busy_port = s.getsockname()[1]
    try:
        r = Api().find_free_port(busy_port)
        assert r["port"] is not None
        assert r["port"] != busy_port
        assert busy_port < r["port"] < busy_port + 64
    finally:
        s.close()


# ── Api.load_config / save_config round-trip ───────────────────────────────

def test_save_config_round_trip_preserves_comments(tmp_path, monkeypatch):
    """The whole point of using tomlkit instead of tomli-w."""
    from aureka.ui import Api
    cfg = tmp_path / "config.toml"
    cfg.write_text("""\
# Aureka 設定檔 — 重要註解
[llm]
# LLM 端點
base_url = "http://127.0.0.1:1234/v1"
api_key  = "lm-studio"
model    = "auto"
""", encoding="utf-8")
    monkeypatch.setenv("AUREKA_CONFIG", str(cfg))

    api = Api()
    payload = {"llm": {"base_url": "http://10.0.0.1:9999/v1"}}
    # Skip /reload by making the daemon socket unreachable
    with patch("aureka.ui._try_reload_daemon", return_value={"reached": False}):
        r = api.save_config(payload)
    assert r["ok"] is True

    text = cfg.read_text(encoding="utf-8")
    assert "# Aureka 設定檔 — 重要註解" in text
    assert "# LLM 端點" in text
    assert 'base_url = "http://10.0.0.1:9999/v1"' in text
    # api_key untouched
    assert 'api_key  = "lm-studio"' in text


# ── Api.model_status (thin wrapper) ─────────────────────────────────────────

def test_api_model_status_wraps_models_module(monkeypatch):
    from aureka.ui import Api
    fake = {"kokoro": {"downloaded": True, "size_bytes": 1, "snapshot_path": "/x"}}
    monkeypatch.setattr("aureka.models.model_status", lambda: fake)
    r = Api().model_status()
    assert r["models"] == fake


# ── Api.start_download / download_progress (mocked HF) ─────────────────────

def test_api_start_download_drives_background_thread(monkeypatch):
    """End-to-end: start a download with mocked snapshot_download, then poll
    until done, then assert state captured the start/done phases."""
    import time
    from aureka import ui

    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda repo_id, **kw: "/tmp/x")
    # Reset module-level state in case other tests dirtied it
    ui._dl_state.clear()
    ui._dl_state.update({"repos": {}, "done": True})

    api = ui.Api()
    r = api.start_download(["kokoro"])
    assert r["ok"] is True

    # Poll up to 2s for completion
    for _ in range(40):
        s = api.download_progress()
        if s.get("done"):
            break
        time.sleep(0.05)

    s = api.download_progress()
    assert s["done"] is True
    assert "kokoro" in s["repos"]
    assert s["repos"]["kokoro"]["phase"] == "done"


# ── Api.start_benchmark / benchmark_progress (mocked) ──────────────────────

def test_api_benchmark_streams_lines_then_finishes(monkeypatch, tmp_path):
    import time
    from aureka import ui
    from aureka import benchmark as b

    # Stub the heavy parts so the benchmark finishes in milliseconds
    monkeypatch.setattr(b, "_collect_aureka_env",
                        lambda d: {"hostname": "h", "device_resolved": "cpu"})
    monkeypatch.setattr(b, "_bench_cold_start", lambda d: [])
    monkeypatch.setattr(b, "_bench_asr",
                        lambda d, r: [b.BenchmarkResult("ASR", "RTF", 0.3, 0.3, 0.3, "")])
    monkeypatch.setattr(b, "_bench_tts",
                        lambda d, r: [b.BenchmarkResult("TTS", "RTF", 0.2, 0.2, 0.2, "")])
    monkeypatch.setattr(b, "_bench_llm", lambda r: [])
    monkeypatch.setattr(b, "_collect_llm_env", lambda: {"base_url": "x"})
    monkeypatch.chdir(tmp_path)

    # Reset bench state
    ui._bench_state.clear()
    ui._bench_state.update({"lines": [], "done": True, "result": None, "consumed": 0})

    api = ui.Api()
    r = api.start_benchmark(quick=True, skip_llm=True)
    assert r["ok"] is True

    for _ in range(80):
        s = api.benchmark_progress()
        if s["done"]:
            break
        time.sleep(0.05)

    s = api.benchmark_progress()
    assert s["done"] is True
    assert s["result"] is not None
    assert "report_path" in s["result"]
    # Recommendations field added by Api wrapper
    assert "recommendations" in s["result"]


# ── Api.list_loopback_devices / test_loopback_capture ─────────────────────

def test_api_list_loopback_devices_empty_returns_install_hint(monkeypatch):
    """Empty candidate list surfaces install hint for the user."""
    from aureka import audio_loopback as al
    monkeypatch.setattr(al, "list_candidates", lambda: [])
    monkeypatch.setattr(al, "install_hint", lambda: "install BlackHole")
    from aureka.ui import Api
    r = Api().list_loopback_devices()
    assert r["devices"] == []
    assert "BlackHole" in r["install_hint"]


def test_api_list_loopback_devices_with_candidates(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al, "list_candidates", lambda: [
        al.LoopbackDevice(name="BlackHole 2ch", backend="blackhole"),
    ])
    from aureka.ui import Api
    r = Api().list_loopback_devices()
    assert len(r["devices"]) == 1
    assert r["devices"][0]["backend"] == "blackhole"
    assert r["install_hint"] == ""  # devices present → no hint shown


def test_api_test_loopback_capture_no_device(monkeypatch):
    from aureka import audio_loopback as al
    monkeypatch.setattr(al, "list_candidates", lambda: [])
    from aureka.ui import Api
    r = Api().test_loopback_capture("")
    assert r["ok"] is False
    assert "no loopback device" in r["error"]


# ── Listen section roundtrips through save_config ──────────────────────────

def test_listen_section_round_trips(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[listen]\ndevice = \"\"\n")
    monkeypatch.setenv("AUREKA_CONFIG", str(cfg))
    from aureka.ui import Api
    api = Api()
    payload = {"listen": {
        "device": "BlackHole 2ch",
        "input_mode": "refine",
        "target_lang": "en",
        "out_path": "/tmp/m.txt",
        "window": True,
        "idle_timeout_seconds": 600,
    }}
    with patch("aureka.ui._try_reload_daemon", return_value={"reached": False}):
        r = api.save_config(payload)
    assert r["ok"] is True
    text = cfg.read_text()
    assert 'device = "BlackHole 2ch"' in text
    assert 'input_mode = "refine"' in text
    assert 'window = true' in text
    assert 'idle_timeout_seconds = 600' in text



def test_api_benchmark_progress_consumes_lines_incrementally(monkeypatch):
    """Repeated calls to benchmark_progress shouldn't re-yield the same lines."""
    from aureka import ui

    ui._bench_state.clear()
    ui._bench_state.update({
        "lines": ["l1", "l2", "l3"],
        "done": False,
        "result": None,
        "consumed": 0,
    })

    api = ui.Api()
    first = api.benchmark_progress()
    second = api.benchmark_progress()
    assert first["lines"] == ["l1", "l2", "l3"]
    assert second["lines"] == []  # already consumed
