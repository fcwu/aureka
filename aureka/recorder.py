"""Microphone recording with hold-to-record, toggle, and VAD modes."""
import threading
from typing import Callable

import numpy as np

SAMPLE_RATE = 16000
CHUNK_MS = 100
CHUNK_FRAMES = SAMPLE_RATE * CHUNK_MS // 1000  # 1600 frames per chunk


class Recorder:
    def __init__(
        self,
        mode: str = "hold-to-record",
        vad_silence_ms: int = 1500,
        on_chunk: Callable[[np.ndarray], None] | None = None,
    ):
        self.mode = mode
        self.vad_silence_ms = vad_silence_ms
        self.on_chunk = on_chunk
        self._recording = False
        self._toggle_active = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        """Drop incoming audio chunks until resume() while keeping the stream
        and downstream LLM sessions alive."""
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def start(self) -> None:
        if self._recording:
            return
        self._recording = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self) -> np.ndarray:
        self._stop_event.set()
        self._recording = False
        if self._thread:
            self._thread.join(timeout=3)
        return self._collected()

    def toggle(self) -> bool:
        """Toggle recording state. Returns True if now recording."""
        if self._toggle_active:
            self.stop()
            self._toggle_active = False
            return False
        else:
            self._collected_chunks.clear()
            self.start()
            self._toggle_active = True
            return True

    def _record_loop(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            return

        self._collected_chunks: list[np.ndarray] = []
        silence_chunks = 0
        silence_threshold = self.vad_silence_ms // CHUNK_MS

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=CHUNK_FRAMES) as stream:
            while not self._stop_event.is_set():
                chunk, _ = stream.read(CHUNK_FRAMES)
                chunk = chunk.flatten()
                if self._paused:
                    continue  # drop chunk; do not append, do not VAD-evaluate, do not on_chunk
                self._collected_chunks.append(chunk.copy())

                if self.mode == "vad":
                    rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                    if rms < 300:
                        silence_chunks += 1
                        if silence_chunks >= silence_threshold:
                            self._stop_event.set()
                            break
                    else:
                        silence_chunks = 0

                if self.on_chunk:
                    self.on_chunk(chunk.copy())

    def _collected(self) -> np.ndarray:
        chunks = getattr(self, "_collected_chunks", [])
        if not chunks:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(chunks)
