## 1. Audio loopback module

- [x] 1.1 Add `[listen]` extra in `pyproject.toml` with `soundcard>=0.4`
- [x] 1.2 Create `aureka/audio_loopback.py` with `LoopbackStream` class (16 kHz mono int16 output)
- [x] 1.3 Implement `LoopbackStream.detect()` for macOS (BlackHole / Loopback name match)
- [x] 1.4 Implement `LoopbackStream.detect()` for Windows (`soundcard.get_microphone(speaker.name, include_loopback=True)`)
- [x] 1.5 Implement `LoopbackStream.detect()` for Linux (PulseAudio monitor source)
- [x] 1.6 Implement `LoopbackStream.read()` returning bytes; handle resample if device sample rate ≠ 16 kHz

## 2. Config

- [x] 2.1 Add `[listen]` section to `aureka.config`: `device: str = ""`, `input_mode: str = "transcribe"`, `target_lang: str = "zh"`, `window: bool = False`, `out_path: str = ""`, `idle_timeout_seconds: int = 1800`
- [x] 2.2 Update `config.example.toml`

## 3. Daemon /listen endpoint

- [x] 3.1 Add WS `/listen` route in `aureka/daemon.py`
- [x] 3.2 Per-frame schema handler: `start` / `audio` / `end`
- [x] 3.3 Reuse existing VAD segmenter + ASR pipeline; emit `transcript` events with `label` / timestamps
- [x] 3.4 LLM refine / translate path mirrors `/voice` but persists session per-stream
- [x] 3.5 Idle timeout (default 30 min) closes session and releases resources
- [x] 3.6 Multi-stream support: same client may open `system` and `mic` labels concurrently

## 4. CLI

- [x] 4.1 Add `aureka listen` subparser with `--mode`, `--target`, `--out`, `--window`, `--mic`, `--device`
- [x] 4.2 Implement `cmd_listen` orchestration: detect device, open stream(s), feed daemon WS, render output
- [x] 4.3 Add `aureka doctor audio` subparser + `cmd_doctor_audio` printing device list + routing diagnostics

## 5. Listen window (pywebview)

- [x] 5.1 Add a tail-style HTML template in `aureka/listen_window.py` (or extend `ui.py`)
- [x] 5.2 JS polls `Api.tail()` every 200 ms and appends new transcript segments
- [x] 5.3 Window does not steal focus when the audio source app is active
- [x] 5.4 Close action stops the loopback stream cleanly

## 6. Settings UI Listen tab

- [x] 6.1 New tab in sidebar
- [x] 6.2 Device dropdown populated from `LoopbackStream.list_candidates()`
- [x] 6.3 Bindings for `[listen].input_mode`, `target_lang`, `window`, `out_path`
- [x] 6.4 Test capture button: 5 s RMS + waveform sparkline
- [x] 6.5 macOS warning card when no BlackHole detected

## 7. Documentation

- [x] 7.1 README: new "轉錄系統音訊" section with macOS BlackHole + Multi-Output walkthrough
- [x] 7.2 README: Windows / Linux notes (no extra driver needed)
- [x] 7.3 README: add `aureka listen` and `aureka doctor audio` to the CLI block

## 8. Tests

- [x] 8.1 `tests/test_audio_loopback_unit.py`: detect() returns None / candidate per platform; `pactl` parsing
- [x] 8.2 `tests/test_daemon.py`: `/listen` accepts start/audio/end frames; idle timeout fires
- [x] 8.3 `tests/test_main_cli_unit.py`: `aureka listen` registered; `aureka doctor audio` prints device list

## 9. Manual verification

- [x] 9.1 macOS: install BlackHole, route YouTube through Multi-Output, run `aureka listen` and confirm transcripts appear
- [x] 9.2 Windows: run `aureka listen` against system audio (e.g. a YouTube tab); confirm WASAPI loopback works without driver install
- [x] 9.3 Run `aureka listen --mic` during a Zoom call and confirm both labels show transcripts
