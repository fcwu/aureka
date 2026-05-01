"""Unified ASR interface supporting TheWhisper and faster-whisper backends."""
import os
from dataclasses import dataclass
from typing import Generator

import numpy as np


@dataclass
class Segment:
    start: float
    end: float
    text: str
    is_last: bool = False


class _TheWhisperBackend:
    def __init__(self, device: str):
        from thestage_speechkit import WhisperPipeline
        self._pipeline = WhisperPipeline.from_pretrained(
            "thestage-ai/thewhisper-large-v3-turbo",
            device=device,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> list[Segment]:
        result = self._pipeline(audio)
        segs = [Segment(s.start, s.end, s.text) for s in result.segments]
        if segs:
            segs[-1].is_last = True
        return segs


class _FasterWhisperBackend:
    def __init__(self, device: str, model_size: str = "large-v3"):
        from faster_whisper import WhisperModel
        compute = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel(model_size, device=device, compute_type=compute)

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> list[Segment]:
        segments_gen, _ = self._model.transcribe(audio, beam_size=5)
        segs = [Segment(s.start, s.end, s.text) for s in segments_gen]
        if segs:
            segs[-1].is_last = True
        return segs


class _MockBackend:
    """Used when AUREKA_TEST_MODE=1 to skip model loading."""

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> list[Segment]:
        return [Segment(0.0, 1.0, "[mock transcript]", is_last=True)]


_backend = None


def load_asr(device: str = "auto", backend_name: str | None = None) -> None:
    """Pre-load ASR backend into module-level singleton."""
    global _backend
    if os.environ.get("AUREKA_TEST_MODE") == "1":
        _backend = _MockBackend()
        return

    from aureka.device import resolve_device, resolve_asr_backend
    dev = resolve_device(device)
    bname = backend_name or resolve_asr_backend(dev)

    if bname == "thewhisper":
        _backend = _TheWhisperBackend(dev)
    else:
        _backend = _FasterWhisperBackend(dev)


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> list[Segment]:
    """Transcribe audio using the loaded backend. Call load_asr() first."""
    global _backend
    if _backend is None:
        load_asr()
    return _backend.transcribe(audio, sample_rate)
