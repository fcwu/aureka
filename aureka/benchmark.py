"""Benchmark ASR / TTS / LLM speed on the current platform.

Produces both a stdout table and a Markdown report so users can share
results across machines for hardware comparison.
"""
from __future__ import annotations

import os
import platform
import socket
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

# ── Constants ────────────────────────────────────────────────────────────────

WARMUP_RUNS = 1
DEFAULT_RUNS = 5
QUICK_RUNS = 1

CACHE_DIR = Path.home() / ".cache" / "aureka" / "benchmark"
SAMPLE_TEXT_ZH = (
    "今天天氣很好，陽光從窗外灑進來，微風輕輕吹過，讓人感到心情格外舒暢。"
    "我們決定到附近的公園散步，看看春天盛開的花朵，聽聽鳥兒在樹梢上的鳴唱。"
    "這樣的時光雖然短暫，卻能讓繁忙的生活慢下來，重新感受日常的美好。"
    "回程經過一家小咖啡店，香氣撲鼻而來，於是停下腳步，點了一杯熱拿鐵與一塊司康，"
    "坐在窗邊靜靜地讀著書，度過一個悠閒的下午。"
)
TTS_BENCH_TEXT = (
    "人工智慧正在改變人們的工作與學習方式。"
    "從語音轉文字、即時翻譯到自動化摘要，越來越多的工具走進日常生活。"
    "在這個過程中，硬體的速度直接影響使用體驗。"
    "我們需要可重現的方法量測不同平台上的延遲與吞吐量，才能做出合適的選擇。"
)
LLM_PROMPT = (
    "請將以下文字以相同字數複述一次，不要增刪內容、不要加註解：\n\n" + TTS_BENCH_TEXT
)

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    task: str
    metric: str
    median: float | None
    min_v: float | None
    max_v: float | None
    unit: str
    status: str = "ok"  # "ok" | "failed: <reason>" | "skipped: <reason>"


@dataclass
class BenchmarkReport:
    results: list[BenchmarkResult] = field(default_factory=list)
    aureka_env: dict = field(default_factory=dict)
    llm_env: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# ── Timing harness ────────────────────────────────────────────────────────────

_progress_cb: Callable[[str], None] | None = None


def _print_progress(task: str, label: str, secs: float | None = None) -> None:
    suffix = f" → {secs:.2f}s" if secs is not None else ""
    line = f"[{task}] {label}{suffix}"
    print(line, flush=True)
    if _progress_cb is not None:
        try:
            _progress_cb(line)
        except Exception:
            pass


def _emit(line: str) -> None:
    """Print + forward to progress callback (for non-task lines like banners)."""
    print(line, flush=True)
    if _progress_cb is not None:
        try:
            _progress_cb(line)
        except Exception:
            pass


def _time_runs(
    task_name: str,
    fn: Callable[[], None],
    runs: int,
    warmup: int = WARMUP_RUNS,
) -> tuple[float, float, float]:
    """Run `fn` warmup+runs times. Return (median, min, max) of timed runs only."""
    for _ in range(warmup):
        _print_progress(task_name, "warm-up...")
        fn()
    timings: list[float] = []
    for i in range(1, runs + 1):
        t0 = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - t0
        timings.append(elapsed)
        _print_progress(task_name, f"run {i}/{runs}", elapsed)
    return statistics.median(timings), min(timings), max(timings)


# ── Sample management ────────────────────────────────────────────────────────

def _kokoro_version() -> str:
    try:
        from importlib.metadata import version
        return version("kokoro")
    except Exception:
        return "unknown"


def _resolve_sample(voice: str) -> Path:
    """Return path to a ~30s zh sample WAV. Generate via Kokoro if missing.

    Falls back to tests/fixtures/speech-zh.wav if Kokoro is unavailable.
    Raises if no sample can be obtained.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"sample-zh-kokoro{_kokoro_version()}-{voice}.wav"
    if cache_file.exists():
        return cache_file

    try:
        from aureka.tts import synthesize
        import soundfile as sf
        print("[sample] Generating ~30s Kokoro sample (one-time)...", flush=True)
        audio, sr = synthesize(SAMPLE_TEXT_ZH)
        if audio is None:
            raise RuntimeError("Kokoro returned empty audio")
        sf.write(cache_file, audio, sr)
        return cache_file
    except Exception as e:
        # fallback 1: repo fixture (dev environment)
        fallback = Path(__file__).parent.parent / "tests" / "fixtures" / "speech-zh.wav"
        if fallback.exists():
            print(f"[sample] Kokoro unavailable ({e}), using fallback {fallback}", flush=True)
            return fallback
        # fallback 2: synthetic noise (e.g. Windows without TTS)
        synthetic = CACHE_DIR / "sample-synthetic-30s.wav"
        if not synthetic.exists():
            print(f"[sample] Kokoro unavailable ({e}), generating synthetic 30s audio...", flush=True)
            import numpy as np
            import soundfile as sf
            _sr = 16000
            rng = np.random.default_rng(42)
            _audio = rng.uniform(-0.05, 0.05, _sr * 30).astype(np.float32)
            sf.write(synthetic, _audio, _sr)
        return synthetic


# ── Per-task benchmarks ──────────────────────────────────────────────────────

def _bench_cold_start(device: str) -> list[BenchmarkResult]:
    out: list[BenchmarkResult] = []
    # ASR cold-start
    try:
        from aureka import asr as asr_mod
        asr_mod._backend = None  # force reload
        t0 = time.perf_counter()
        asr_mod.load_asr(device=device)
        elapsed = time.perf_counter() - t0
        out.append(BenchmarkResult("Cold start", "ASR load", elapsed, None, None, "s"))
        _print_progress("Cold-start ASR", "load", elapsed)
    except Exception as e:
        out.append(BenchmarkResult("Cold start", "ASR load", None, None, None, "s",
                                   status=f"failed: {e}"))

    # TTS cold-start
    try:
        from aureka import tts as tts_mod
        tts_mod._pipeline = None  # force reload
        t0 = time.perf_counter()
        tts_mod.load_tts(device=device)
        elapsed = time.perf_counter() - t0
        out.append(BenchmarkResult("Cold start", "TTS load", elapsed, None, None, "s"))
        _print_progress("Cold-start TTS", "load", elapsed)
    except Exception as e:
        out.append(BenchmarkResult("Cold start", "TTS load", None, None, None, "s",
                                   status=f"failed: {e}"))
    return out


def _bench_asr(device: str, runs: int) -> list[BenchmarkResult]:
    try:
        import numpy as np
        import soundfile as sf
        from aureka.config import get_config
        from aureka import asr as asr_mod

        cfg = get_config()
        sample_path = _resolve_sample(cfg.tts.voice)
        audio, sr = sf.read(sample_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        # resample if needed (Whisper expects 16k)
        if sr != 16000:
            ratio = 16000 / sr
            new_len = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio), new_len, endpoint=False),
                np.arange(len(audio)), audio,
            ).astype(np.float32)
            sr = 16000
        duration = len(audio) / sr

        if asr_mod._backend is None:
            asr_mod.load_asr(device=device)

        last_text_chars = {"n": 0}

        def fn():
            segs = list(asr_mod.transcribe(audio, sr))
            text = "".join(s.text for s in segs)
            last_text_chars["n"] = len(text)

        median, mn, mx = _time_runs("ASR", fn, runs)
        rtf_med = median / duration
        rtf_mn = mn / duration
        rtf_mx = mx / duration
        cps_med = last_text_chars["n"] / median if median > 0 else 0.0
        return [
            BenchmarkResult("ASR", "RTF", rtf_med, rtf_mn, rtf_mx, ""),
            BenchmarkResult("ASR", "chars/s", cps_med, None, None, ""),
        ]
    except Exception as e:
        return [BenchmarkResult("ASR", "RTF", None, None, None, "", status=f"failed: {e}")]


def _bench_tts(device: str, runs: int) -> list[BenchmarkResult]:
    try:
        from aureka import tts as tts_mod
        if tts_mod._pipeline is None:
            tts_mod.load_tts(device=device)

        out_state = {"audio_secs": 0.0}

        def fn():
            audio, sr = tts_mod.synthesize(TTS_BENCH_TEXT)
            if audio is None:
                raise RuntimeError("Kokoro returned empty audio")
            out_state["audio_secs"] = len(audio) / sr

        median, mn, mx = _time_runs("TTS", fn, runs)
        audio_secs = out_state["audio_secs"]
        rtf_med = median / audio_secs if audio_secs > 0 else 0.0
        rtf_mn = mn / audio_secs if audio_secs > 0 else 0.0
        rtf_mx = mx / audio_secs if audio_secs > 0 else 0.0
        cps_med = len(TTS_BENCH_TEXT) / median if median > 0 else 0.0
        return [
            BenchmarkResult("TTS", "RTF", rtf_med, rtf_mn, rtf_mx, ""),
            BenchmarkResult("TTS", "chars/s", cps_med, None, None, ""),
        ]
    except Exception as e:
        return [BenchmarkResult("TTS", "RTF", None, None, None, "", status=f"failed: {e}")]


def _bench_llm(runs: int) -> list[BenchmarkResult]:
    try:
        import openai
        from aureka.config import get_config
        from aureka.llm import _resolve_model
        cfg = get_config()
        client = openai.OpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
        model = _resolve_model(client, cfg.llm.model)

        ttft_state = {"v": 0.0}
        tps_state = {"v": 0.0}

        def fn():
            t0 = time.perf_counter()
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": LLM_PROMPT + " /no_think"}],
                stream=True,
                stream_options={"include_usage": True},
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            ttft = None
            total_tokens = 0
            for chunk in stream:
                if ttft is None and chunk.choices and chunk.choices[0].delta.content:
                    ttft = (time.perf_counter() - t0) * 1000  # ms
                if chunk.usage and chunk.usage.completion_tokens:
                    total_tokens = chunk.usage.completion_tokens
            elapsed = time.perf_counter() - t0
            ttft_state["v"] = ttft if ttft is not None else 0.0
            tps_state["v"] = total_tokens / elapsed if elapsed > 0 else 0.0

        ttfts: list[float] = []
        tpss: list[float] = []

        def fn_capture():
            fn()
            ttfts.append(ttft_state["v"])
            tpss.append(tps_state["v"])

        # warmup once, then `runs` capture
        _print_progress("LLM", "warm-up...")
        fn()
        for i in range(1, runs + 1):
            t0 = time.perf_counter()
            fn_capture()
            elapsed = time.perf_counter() - t0
            _print_progress("LLM", f"run {i}/{runs}", elapsed)

        return [
            BenchmarkResult("LLM", "tokens/s", statistics.median(tpss), min(tpss), max(tpss), ""),
            BenchmarkResult("LLM", "TTFT", statistics.median(ttfts), min(ttfts), max(ttfts), "ms"),
        ]
    except Exception as e:
        return [BenchmarkResult("LLM", "tokens/s", None, None, None, "", status=f"failed: {e}")]


# ── Environment collection ───────────────────────────────────────────────────

def _pkg_version(name: str) -> str:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return "unknown"


def _gpu_name() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        if torch.backends.mps.is_available():
            return "Apple Silicon (MPS)"
    except Exception:
        pass
    return "—"


def _torch_summary() -> str:
    try:
        import torch
        backend = "cpu"
        if torch.cuda.is_available():
            backend = f"cuda {torch.version.cuda}"
        elif torch.backends.mps.is_available():
            backend = "mps"
        return f"{torch.__version__} ({backend})"
    except Exception:
        return "not installed"


def _collect_aureka_env(device: str) -> dict:
    from aureka.config import get_config
    from aureka.device import resolve_device
    cfg = get_config()
    dev = resolve_device(device)
    return {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": platform.python_version(),
        "torch": _torch_summary(),
        "gpu": _gpu_name(),
        "aureka": _pkg_version("aureka"),
        "device_resolved": dev,
        "asr_model": cfg.asr.model,
        "tts_voice": f"{cfg.tts.voice} (lang={cfg.tts.lang_code})",
        "kokoro": _pkg_version("kokoro"),
        "faster_whisper": _pkg_version("faster-whisper"),
    }


def _collect_llm_env() -> dict:
    from aureka.config import get_config
    cfg = get_config()
    out = {
        "base_url": cfg.llm.base_url,
        "configured_model": cfg.llm.model,
        "resolved_model": "unavailable",
        "owned_by": "unavailable",
    }
    try:
        import openai
        client = openai.OpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
        models = client.models.list().data
        if models:
            target = cfg.llm.model
            picked = next((m for m in models if m.id == target), models[0])
            out["resolved_model"] = picked.id
            out["owned_by"] = getattr(picked, "owned_by", "unknown")
    except Exception as e:
        out["error"] = str(e)
    return out


# ── Rendering ────────────────────────────────────────────────────────────────

def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.3f}"


def _render_table(report: BenchmarkReport) -> str:
    headers = ["Task", "Metric", "Median", "Min", "Max", "Unit", "Status"]
    rows = [
        [r.task, r.metric, _fmt(r.median), _fmt(r.min_v), _fmt(r.max_v), r.unit, r.status]
        for r in report.results
    ]
    widths = [max([len(h)] + [len(row[i]) for row in rows]) for i, h in enumerate(headers)]
    sep = "  ".join("-" * w for w in widths)
    lines = []
    title = (
        f"Aureka Benchmark — {report.aureka_env.get('hostname', '?')}"
        f" / {report.aureka_env.get('gpu', '?')} ({report.aureka_env.get('device_resolved', '?')})"
    )
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    lines.append(sep)
    for row in rows:
        lines.append("  ".join(c.ljust(w) for c, w in zip(row, widths)))
    return "\n".join(lines)


def _render_markdown(report: BenchmarkReport) -> str:
    md = []
    md.append(f"# Aureka Benchmark — {report.aureka_env.get('hostname', '?')}")
    md.append(f"_Date: {date.today().isoformat()}_\n")

    md.append("## Environment\n")
    md.append("### Aureka host\n")
    for k, v in report.aureka_env.items():
        md.append(f"- **{k}**: {v}")
    md.append("\n### LLM endpoint\n")
    for k, v in report.llm_env.items():
        md.append(f"- **{k}**: {v}")

    md.append("\n## Results\n")
    md.append("| Task | Metric | Median | Min | Max | Unit | Status |")
    md.append("|------|--------|--------|-----|-----|------|--------|")
    for r in report.results:
        md.append(
            f"| {r.task} | {r.metric} | {_fmt(r.median)} | {_fmt(r.min_v)} "
            f"| {_fmt(r.max_v)} | {r.unit} | {r.status} |"
        )

    md.append("\n## Notes\n")
    if report.notes:
        for n in report.notes:
            md.append(f"- {n}")
    else:
        md.append("- (none)")
    md.append("")
    return "\n".join(md)


# ── Entry ────────────────────────────────────────────────────────────────────

def _default_output_path() -> Path:
    return Path.cwd() / f"benchmark-{socket.gethostname()}-{date.today().isoformat()}.md"


def _structured_result(report: BenchmarkReport, report_path: Path) -> dict:
    """Project the BenchmarkReport into a UI-friendly dict.

    Tasks are keyed by lowercase name (`asr`, `tts`, `llm`); each value is
    `{median, min, max, unit, device, status, metric}`. Per-task entries with
    multiple metrics (e.g. ASR: RTF + chars/s) keep the primary metric (RTF
    for ASR/TTS, TTFT for LLM) and tuck secondary metrics under `extra`.
    """
    primary_metric = {"ASR": "RTF", "TTS": "RTF", "LLM": "TTFT"}
    by_task: dict[str, dict] = {}

    for r in report.results:
        if r.task not in primary_metric:
            continue
        key = r.task.lower()
        slot = by_task.setdefault(key, {
            "device": report.aureka_env.get("device_resolved", "?"),
            "status": "ok",
            "extra": {},
        })
        is_primary = r.metric == primary_metric[r.task]
        target = slot if is_primary else slot["extra"].setdefault(r.metric, {})
        target["median"] = r.median
        target["min"] = r.min_v
        target["max"] = r.max_v
        target["unit"] = r.unit
        if is_primary:
            target["metric"] = r.metric
            if r.status.startswith("failed"):
                target["status"] = "failed"
                target["error"] = r.status.split("failed:", 1)[-1].strip()
            elif r.status.startswith("skipped"):
                target["status"] = "skipped"
            # "ok" stays as default

    return {
        "report_path": report_path,
        "tasks": by_task,
        "aureka_env": report.aureka_env,
        "llm_env": report.llm_env,
    }


def run_benchmark(
    device: str = "auto",
    quick: bool = False,
    output_path: str | None = None,
    skip_llm: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Run the benchmark suite. Returns a structured dict (also writes Markdown).

    The dict includes `report_path: Path` so callers that previously used the
    return value as a path can transition with `result["report_path"]`.

    `progress`, when supplied, receives every progress line that goes to stdout.
    """
    global _progress_cb
    _progress_cb = progress
    try:
        runs = QUICK_RUNS if quick else DEFAULT_RUNS
        notes = []
        notes.append(f"runs per task: {runs} (warm-up: {WARMUP_RUNS}); mode: {'quick' if quick else 'default'}")
        if skip_llm:
            notes.append("LLM tasks skipped via --skip-llm")

        report = BenchmarkReport(notes=notes)
        report.aureka_env = _collect_aureka_env(device)

        _emit(f"[aureka] Benchmark starting (runs={runs}, device={device})")
        report.results.extend(_bench_cold_start(device))
        report.results.extend(_bench_asr(device, runs))
        report.results.extend(_bench_tts(device, runs))

        if skip_llm:
            report.results.append(
                BenchmarkResult("LLM", "tokens/s", None, None, None, "", status="skipped: --skip-llm")
            )
            report.results.append(
                BenchmarkResult("LLM", "TTFT", None, None, None, "ms", status="skipped: --skip-llm")
            )
            report.llm_env = {"base_url": "(skipped)", "configured_model": "(skipped)"}
        else:
            report.llm_env = _collect_llm_env()
            report.results.extend(_bench_llm(runs))

        _emit("")
        _emit(_render_table(report))

        out = Path(output_path) if output_path else _default_output_path()
        out.write_text(_render_markdown(report), encoding="utf-8")
        _emit(f"\nReport saved: {out}")
        return _structured_result(report, out)
    finally:
        _progress_cb = None
