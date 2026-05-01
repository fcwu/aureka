#!/usr/bin/env python3
"""Generate test audio fixtures."""
import os
import struct
import wave
import numpy as np
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FIXTURES_DIR.mkdir(exist_ok=True)

SAMPLE_RATE = 16000


def write_wav(path: Path, samples: np.ndarray, rate: int = SAMPLE_RATE):
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((samples * 32767).astype(np.int16).tobytes())
    print(f"Written: {path}")


# 1 秒靜音
silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
write_wav(FIXTURES_DIR / "silence-1s.wav", silence)

# 3 秒簡單語音模擬（440Hz tone，模擬有聲音但非真實語音）
t = np.linspace(0, 3, SAMPLE_RATE * 3, endpoint=False)
tone = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
write_wav(FIXTURES_DIR / "tone-3s.wav", tone)

# speech-zh.wav：若有 speech-zh-source.wav 則複製，否則用 tone 替代（ASR 輸出測試用 mock）
source = FIXTURES_DIR / "speech-zh-source.wav"
target = FIXTURES_DIR / "speech-zh.wav"
if source.exists():
    import shutil
    shutil.copy(source, target)
    print(f"Copied {source} → {target}")
else:
    write_wav(target, tone)
    print(f"Note: {target} is a tone placeholder. Replace with real Chinese speech for accurate ASR tests.")

print("Done.")
