"""VAD wrapper around silero-vad for streaming ASR segmentation.

Feeds PCM chunks to silero-vad's VADIterator, slices the audio buffer at
detected speech boundaries, and yields completed segments ready for ASR.
"""
from __future__ import annotations

import numpy as np

# silero-vad VADIterator expects fixed-size windows for inference.
VAD_WINDOW_SAMPLES = 512  # 32 ms at 16 kHz
SAMPLE_RATE = 16000


class VadUnavailable(RuntimeError):
    """Raised when silero-vad cannot be loaded (missing dep, network failure, etc.)."""


class VadSegmenter:
    """Stateful VAD-based audio segmenter.

    Usage:
        seg = VadSegmenter()
        for pcm_chunk in audio_stream:        # int16 numpy arrays of any length
            for segment in seg.feed(pcm_chunk):
                run_asr(segment)              # float32 numpy, 16 kHz
        for segment in seg.flush():
            run_asr(segment)
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE,
                 threshold: float = 0.5, min_silence_ms: int = 600):
        try:
            from silero_vad import load_silero_vad, VADIterator
        except ImportError as e:
            raise VadUnavailable(f"silero-vad not installed: {e}") from e
        try:
            self._model = load_silero_vad()
        except Exception as e:
            raise VadUnavailable(f"silero-vad load failed: {e}") from e

        import torch
        self._torch = torch
        self._iterator = VADIterator(
            self._model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=min_silence_ms,
        )
        self._sample_rate = sample_rate
        # All audio samples seen so far (float32 in [-1, 1])
        self._samples = np.zeros(0, dtype=np.float32)
        # Pending samples not yet sliced into VAD windows
        self._pending = np.zeros(0, dtype=np.float32)
        # Index of last returned segment end (samples consumed by ASR already)
        self._last_committed = 0
        # Most recent speech-start index (None = no active speech)
        self._speech_start: int | None = None

    def feed(self, pcm_int16: np.ndarray) -> list[np.ndarray]:
        """Feed a chunk of int16 PCM. Returns list of completed segments (float32, 16k)."""
        if pcm_int16.dtype != np.int16:
            pcm_int16 = pcm_int16.astype(np.int16)
        chunk_f = pcm_int16.astype(np.float32) / 32768.0
        self._samples = np.concatenate([self._samples, chunk_f])
        self._pending = np.concatenate([self._pending, chunk_f])

        completed: list[np.ndarray] = []
        # Slice pending into VAD-sized windows
        while len(self._pending) >= VAD_WINDOW_SAMPLES:
            window = self._pending[:VAD_WINDOW_SAMPLES]
            self._pending = self._pending[VAD_WINDOW_SAMPLES:]
            window_t = self._torch.from_numpy(window)
            event = self._iterator(window_t, return_seconds=False)
            if event is None:
                continue
            if "start" in event and self._speech_start is None:
                self._speech_start = int(event["start"])
            if "end" in event and self._speech_start is not None:
                end_idx = int(event["end"])
                segment = self._samples[self._speech_start:end_idx]
                if len(segment) > 0:
                    completed.append(segment)
                self._last_committed = end_idx
                self._speech_start = None
        return completed

    def flush(self) -> list[np.ndarray]:
        """Return whatever speech is still buffered. Called when client signals end-of-stream."""
        out: list[np.ndarray] = []
        if self._speech_start is not None:
            tail = self._samples[self._speech_start:]
            if len(tail) > 0:
                out.append(tail)
            self._speech_start = None
        # Any samples after _last_committed but never matched as speech are dropped
        # (they were silence). Reset state for re-use.
        self._iterator.reset_states()
        self._samples = np.zeros(0, dtype=np.float32)
        self._pending = np.zeros(0, dtype=np.float32)
        self._last_committed = 0
        return out
