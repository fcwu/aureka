"""Cross-platform system-audio loopback capture.

Wraps platform-specific drivers behind a uniform `LoopbackStream` that
yields 16 kHz mono int16 PCM frames — the same shape `aureka.recorder`
already feeds the ASR pipeline.

- macOS  → BlackHole / Loopback (user installs the virtual device)
- Windows → WASAPI Loopback (built-in, no driver install)
- Linux  → PulseAudio monitor source

Heavy lifting is delegated to the `soundcard` library (in the `[listen]`
extra). When that import fails or no loopback device is found, helpers
return clear instructions instead of cryptic errors.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Iterator


SAMPLE_RATE = 16000
CHANNELS = 1
DEFAULT_BLOCK_SAMPLES = 1600  # 100 ms @ 16 kHz


@dataclass
class LoopbackDevice:
    """Platform-neutral descriptor of a loopback-capable input device."""
    name: str
    backend: str  # "blackhole" | "wasapi-loopback" | "pulse-monitor"
    raw: object | None = None  # platform-specific handle (soundcard.Microphone, etc.)


def list_candidates() -> list[LoopbackDevice]:
    """Return every loopback-capable input device the OS exposes.

    Empty list means none are configured (macOS without BlackHole, Linux
    without monitor sources). The caller is expected to surface install
    instructions to the user."""
    sysname = platform.system()
    if sysname == "Darwin":
        return _list_macos()
    if sysname == "Windows":
        return _list_windows()
    return _list_linux()


def detect() -> LoopbackDevice | None:
    """Return the first loopback candidate, or None when none is configured.

    Used by `aureka listen` when the user does not pin `--device`."""
    cands = list_candidates()
    return cands[0] if cands else None


def install_hint() -> str:
    """Platform-specific one-liner shown when `detect()` returns None."""
    sysname = platform.system()
    if sysname == "Darwin":
        return (
            "No loopback device detected.\n"
            "Install BlackHole and route system output through a Multi-Output Device:\n"
            "  brew install --cask blackhole-2ch\n"
            "Then see README → 「轉錄系統音訊」 for the routing walkthrough."
        )
    if sysname == "Windows":
        return (
            "No loopback device detected.\n"
            "WASAPI Loopback is built in but the `soundcard` library is required:\n"
            "  pip install 'aureka[listen]'"
        )
    return (
        "No loopback device detected.\n"
        "On Linux, ensure PulseAudio / PipeWire is running and at least one\n"
        "`*.monitor` source is exposed (run `pactl list short sources`)."
    )


# ── Platform implementations ────────────────────────────────────────────────

def _list_macos() -> list[LoopbackDevice]:
    """macOS: pick virtual audio devices whose names look like BlackHole or Loopback."""
    try:
        import soundcard as sc
    except ImportError:
        return []
    out: list[LoopbackDevice] = []
    for mic in sc.all_microphones(include_loopback=False):
        name = (mic.name or "")
        if name.lower().startswith(("blackhole", "loopback", "soundflower")):
            out.append(LoopbackDevice(name=name, backend="blackhole", raw=mic))
    return out


def _list_windows() -> list[LoopbackDevice]:
    """Windows: every speaker can be captured back via WASAPI Loopback."""
    try:
        import soundcard as sc
    except ImportError:
        return []
    out: list[LoopbackDevice] = []
    for spk in sc.all_speakers():
        try:
            mic = sc.get_microphone(spk.id, include_loopback=True)
        except Exception:
            continue
        out.append(LoopbackDevice(name=spk.name, backend="wasapi-loopback", raw=mic))
    return out


def _list_linux() -> list[LoopbackDevice]:
    """Linux: PulseAudio monitor sources are loopback by definition."""
    try:
        import soundcard as sc
    except ImportError:
        return []
    out: list[LoopbackDevice] = []
    for mic in sc.all_microphones(include_loopback=True):
        name = (mic.name or "")
        if "monitor" in name.lower() or name.endswith(".monitor"):
            out.append(LoopbackDevice(name=name, backend="pulse-monitor", raw=mic))
    return out


# ── Streaming wrapper ───────────────────────────────────────────────────────

class LoopbackStream:
    """Block-by-block reader. Yields int16 mono 16 kHz PCM.

    Subclassing-free: `iter()` produces an infinite iterator (until `close()`).
    Implementation defers to `soundcard` for the heavy lifting and resamples
    when the source rate doesn't match `SAMPLE_RATE`.
    """

    def __init__(self, device: LoopbackDevice, block_samples: int = DEFAULT_BLOCK_SAMPLES,
                 source_rate: int | None = None):
        self.device = device
        self.block_samples = block_samples
        # If source_rate is None, soundcard pulls a sensible default (44.1k or 48k).
        self.source_rate = source_rate
        self._stream = None

    def __enter__(self) -> "LoopbackStream":
        self._open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _open(self) -> None:
        if self.device.raw is None:
            raise RuntimeError("LoopbackDevice has no underlying handle (likely soundcard import failed)")
        rate = self.source_rate or SAMPLE_RATE
        # soundcard's recorder context manager is the standard pattern.
        self._stream = self.device.raw.recorder(samplerate=rate, channels=CHANNELS).__enter__()

    def close(self) -> None:
        if self._stream is not None:
            try:
                self.device.raw.recorder(samplerate=self.source_rate or SAMPLE_RATE,
                                          channels=CHANNELS).__exit__(None, None, None)
            except Exception:
                pass
            self._stream = None

    def __iter__(self) -> Iterator[bytes]:
        if self._stream is None:
            self._open()
        import numpy as np
        rate = self.source_rate or SAMPLE_RATE
        while True:
            frame = self._stream.record(numframes=self.block_samples)
            if frame is None or len(frame) == 0:
                return
            # soundcard returns float32 in [-1, 1]
            mono = frame.mean(axis=1) if frame.ndim > 1 else frame
            if rate != SAMPLE_RATE:
                ratio = SAMPLE_RATE / rate
                idx = np.linspace(0, len(mono), int(len(mono) * ratio), endpoint=False)
                mono = np.interp(idx, np.arange(len(mono)), mono).astype("float32")
            int16 = (mono.clip(-1.0, 1.0) * 32767).astype("int16")
            yield int16.tobytes()
