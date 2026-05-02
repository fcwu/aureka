"""Unit tests for aureka.benchmark."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── _time_runs ────────────────────────────────────────────────────────────────

def test_time_runs_excludes_warmup_and_returns_median(monkeypatch):
    from aureka import benchmark as b

    # Warmup is NOT timed (no perf_counter calls). Only 5 timed runs:
    # diffs: 1.0, 1.1, 1.0, 1.2, 1.05
    times = [0.0, 1.0,
             1.0, 2.1,
             2.1, 3.1,
             3.1, 4.3,
             4.3, 5.35]
    it = iter(times)
    monkeypatch.setattr(b.time, "perf_counter", lambda: next(it))

    median, mn, mx = b._time_runs("X", lambda: None, runs=5, warmup=1)
    assert mn == pytest.approx(1.0)
    assert mx == pytest.approx(1.2)
    assert median == pytest.approx(1.05)  # sorted: [1.0, 1.0, 1.05, 1.1, 1.2] → middle = 1.05


def test_time_runs_warmup_not_in_stats(monkeypatch):
    from aureka import benchmark as b
    calls = {"n": 0}

    def fn():
        calls["n"] += 1

    monkeypatch.setattr(b.time, "perf_counter", lambda: 0.0)
    b._time_runs("X", fn, runs=3, warmup=2)
    assert calls["n"] == 5  # 2 warmup + 3 timed


# ── _resolve_sample ──────────────────────────────────────────────────────────

def test_resolve_sample_uses_cache_if_exists(tmp_path, monkeypatch):
    from aureka import benchmark as b

    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(b, "CACHE_DIR", cache)
    monkeypatch.setattr(b, "_kokoro_version", lambda: "0.1.0")
    voice = "zf_xiaobei"
    cache_file = cache / f"sample-zh-kokoro0.1.0-{voice}.wav"
    cache_file.write_bytes(b"fake wav")

    with patch("aureka.tts.synthesize") as syn:
        result = b._resolve_sample(voice)

    assert result == cache_file
    syn.assert_not_called()


def test_resolve_sample_synthesizes_if_missing(tmp_path, monkeypatch):
    from aureka import benchmark as b
    import numpy as np

    monkeypatch.setattr(b, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(b, "_kokoro_version", lambda: "0.1.0")

    fake_audio = np.zeros(16000, dtype=np.float32)
    with patch("aureka.tts.synthesize", return_value=(fake_audio, 24000)) as syn, \
         patch("soundfile.write") as sfw:
        result = b._resolve_sample("zf_xiaobei")

    syn.assert_called_once()
    sfw.assert_called_once()
    assert "sample-zh-kokoro0.1.0-zf_xiaobei.wav" in str(result)


# ── _bench_* fail-soft ────────────────────────────────────────────────────────

def test_bench_asr_failure_returns_failed_status(monkeypatch):
    from aureka import benchmark as b
    with patch.object(b, "_resolve_sample", side_effect=RuntimeError("no kokoro")):
        results = b._bench_asr("cpu", runs=1)
    assert len(results) == 1
    assert results[0].status.startswith("failed:")


def test_bench_tts_failure_returns_failed_status(monkeypatch):
    from aureka import benchmark as b
    with patch("aureka.tts.load_tts", side_effect=RuntimeError("no kokoro")), \
         patch("aureka.tts._pipeline", None):
        results = b._bench_tts("cpu", runs=1)
    assert len(results) == 1
    assert results[0].status.startswith("failed:")


def test_bench_llm_failure_returns_failed_status(monkeypatch):
    from aureka import benchmark as b
    # openai client construction succeeds but model resolution fails
    with patch("aureka.llm._resolve_model", side_effect=RuntimeError("no models")):
        results = b._bench_llm(runs=1)
    assert len(results) == 1
    assert results[0].status.startswith("failed:")


# ── Render helpers ────────────────────────────────────────────────────────────

def test_render_table_includes_all_rows():
    from aureka import benchmark as b
    rep = b.BenchmarkReport(
        results=[
            b.BenchmarkResult("ASR", "RTF", 0.08, 0.07, 0.09, ""),
            b.BenchmarkResult("TTS", "RTF", 0.30, 0.28, 0.34, ""),
            b.BenchmarkResult("LLM", "tokens/s", 48.2, 45.0, 51.0, ""),
        ],
        aureka_env={"hostname": "host", "gpu": "M3", "device_resolved": "mps"},
        llm_env={},
    )
    out = b._render_table(rep)
    assert "ASR" in out and "TTS" in out and "LLM" in out
    assert "0.080" in out  # ASR median formatted
    assert "host" in out


def test_render_markdown_has_required_sections():
    from aureka import benchmark as b
    rep = b.BenchmarkReport(
        results=[b.BenchmarkResult("ASR", "RTF", 0.08, 0.07, 0.09, "")],
        aureka_env={"hostname": "host", "os": "Linux"},
        llm_env={"base_url": "http://x", "configured_model": "m"},
        notes=["runs per task: 5"],
    )
    md = b._render_markdown(rep)
    assert "## Environment" in md
    assert "### Aureka host" in md
    assert "### LLM endpoint" in md
    assert "## Results" in md
    assert "## Notes" in md
    assert "| ASR | RTF |" in md


# ── run_benchmark integration with skip-llm ──────────────────────────────────

def test_run_benchmark_skip_llm_does_not_call_openai(tmp_path, monkeypatch):
    from aureka import benchmark as b

    monkeypatch.setattr(b, "_collect_aureka_env", lambda d: {"hostname": "h"})
    monkeypatch.setattr(b, "_bench_cold_start", lambda d: [])
    monkeypatch.setattr(b, "_bench_asr", lambda d, r: [])
    monkeypatch.setattr(b, "_bench_tts", lambda d, r: [])

    with patch("openai.OpenAI") as openai_ctor, \
         patch.object(b, "_collect_llm_env") as llm_env_fn, \
         patch.object(b, "_bench_llm") as bench_llm_fn:
        out_path = b.run_benchmark(
            device="cpu", quick=True, output_path=str(tmp_path / "r.md"), skip_llm=True
        )

    openai_ctor.assert_not_called()
    llm_env_fn.assert_not_called()
    bench_llm_fn.assert_not_called()
    assert out_path.exists()
    md = out_path.read_text()
    assert "skipped: --skip-llm" in md


def test_run_benchmark_writes_default_output_path(tmp_path, monkeypatch):
    from aureka import benchmark as b

    monkeypatch.setattr(b, "_collect_aureka_env", lambda d: {"hostname": "h"})
    monkeypatch.setattr(b, "_bench_cold_start", lambda d: [])
    monkeypatch.setattr(b, "_bench_asr", lambda d, r: [])
    monkeypatch.setattr(b, "_bench_tts", lambda d, r: [])
    monkeypatch.setattr(b, "_bench_llm", lambda r: [])
    monkeypatch.setattr(b, "_collect_llm_env", lambda: {"base_url": "x"})
    monkeypatch.chdir(tmp_path)

    out_path = b.run_benchmark(device="cpu", quick=True, skip_llm=False)
    assert out_path.parent == tmp_path
    assert out_path.name.startswith("benchmark-")
    assert out_path.name.endswith(".md")
