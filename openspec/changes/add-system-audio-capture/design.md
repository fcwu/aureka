## Context

`aureka.recorder` reads microphone via `sounddevice` (PortAudio) — a single-direction input pipeline. Loopback (capturing system audio output) is a different beast on every platform, with different driver requirements:

- macOS does not expose system output for capture at the OS level. Users install [BlackHole](https://existential.audio/blackhole/) (a virtual audio device) and route output through a Multi-Output device so audio reaches both speakers and BlackHole. Apps capture from BlackHole as a regular input.
- Windows exposes WASAPI Loopback natively per output device — no driver install. The `soundcard` library wraps this; `sounddevice` can also do it via WASAPI host API.
- Linux exposes a PulseAudio "monitor" pseudo-source per sink — no driver install. Standard `sounddevice` lists `Monitor of …` devices.

The competitor (`jt-live-whisper`) demonstrates this is feasible in pure Python without C extensions, so we follow the same path.

## Goals / Non-Goals

**Goals:**
- A single subcommand (`aureka listen`) that does the obvious thing on each platform.
- Reuse the existing ASR / LLM pipeline; no fork of Whisper integration.
- Clear errors when the OS isn't ready (BlackHole missing, monitor source disabled).
- An always-running tail-style transcript view that doesn't steal focus from whatever app is actually playing the audio.

**Non-Goals:**
- Speaker diarization (covered in a separate proposal).
- Subtitle overlay / always-on-top window (would be its own thing; for now a normal pywebview window is enough).
- Real-time translation of bidirectional meetings as a polished mode (`--mic` provides the dual-input building block; full bidi UX is a follow-up).
- Auto-installing BlackHole. We document, we don't sudo-install drivers.

## Decisions

### 1. Library: `soundcard`, not pyaudio / pure sounddevice

`soundcard` (~0.4.x) is a small, cross-platform, pure-Python wrapper that gives loopback as a first-class concept on macOS / Windows / Linux. `sounddevice` can do loopback on Windows but requires fiddling with WASAPI exclusive flags; on Linux it sees monitor sources but doesn't label them as loopback. `pyaudio` is heavy and abandoned upstream. `soundcard` matches our "small, cross-platform" preference.

Trade-off: `soundcard` is in an `[listen]` extra, not core. If the user only does `aureka type` we don't need it.

### 2. Subcommand UX: `aureka listen`

```
aureka listen                       # default mode from config.toml ([listen].input_mode)
aureka listen --mode transcribe     # raw text
aureka listen --mode refine
aureka listen --mode translate --target zh
aureka listen --window              # open transcript window
aureka listen --out meeting.txt     # append per-segment to file
aureka listen --mic                 # also capture mic, label segments
aureka listen --device "BlackHole 2ch"    # explicit device (overrides auto-detect)
```

Daemon required for refine / translate (LLM lives there). Without daemon: `transcribe` still works, others fall back to local cold-start (same as `aureka type`).

### 3. Auto-detection rules

`aureka.audio_loopback.detect_loopback()` walks platform-specific heuristics:

- macOS: search for any device whose name matches `BlackHole.*` or `Loopback.*`. None found → return `None` and the CLI prints a one-paragraph install snippet (same `brew install --cask blackhole-2ch` line that's in the README).
- Windows: `soundcard.default_speaker().name` returns the active output; pair it with `soundcard.get_microphone(default_speaker.name, include_loopback=True)`.
- Linux: pick the first `*.monitor` source via `pactl list short sources` (or `soundcard`'s equivalent).

CLI / UI exposes this list via a "Detected loopback devices" panel. The user can override with `--device` or via `[listen].device` in config.

### 4. Daemon `/listen` endpoint

Mirrors `/voice` but accepts a continuous PCM stream from the client and never closes by itself. Frame schema:

```
{"type": "start", "mode": "refine", "lang": "zh", "topic": "..."}
{"type": "audio", "data": "<base64 pcm>"}     // repeated
{"type": "audio", ...}
{"type": "end"}                                // optional, on Ctrl+C
```

Server side: VAD-segments the stream into utterances (same `silero-vad` we already use for streaming voice input), runs ASR per utterance, optionally pipes to LLM. Emits `{"type": "transcript", "text": "...", "label": "system|mic", "ts_start": <s>, "ts_end": <s>}` per finalized segment.

Why a separate endpoint and not reusing `/voice`: voice sessions are short, end-of-stream-driven; listen sessions are open-ended and need different timeout / heartbeat semantics. Two endpoints keep the contracts clean.

### 5. Window mode: pywebview tail view

Tab-less, reuse the same Tailwind CDN, single column of timestamped segments scrolling up. Live region uses `aria-live="polite"` so screen readers handle it sensibly. JS calls `window.pywebview.api.tail()` every 200 ms and appends new segments.

Headless `--out FILE` is always available — `--window` is additive.

### 6. Backwards-compatible mic capture path

`--mic` reuses the existing `aureka.recorder.Recorder` instance — does not refactor it. Two streams (loopback + mic) feed two independent VAD segmenters, results merged on the client into the same transcript log with `[system]` / `[mic]` labels.

## Risks / Trade-offs

- **macOS BlackHole user friction** — one-time setup is non-trivial (Multi-Output device, switch system output). README walks through; we cannot remove the friction. Mitigation: very clear error message with deeplink to setup section.
- **Echo from system audio playing through speakers re-entering the mic** when `--mic` is on — common for laptop users. Out of scope to solve programmatically; we recommend headphones in the docs.
- **`soundcard` behavior across platforms not 100% uniform** — Windows may produce odd sample rates from some output devices. Resample to 16 kHz mono on capture.
- **Open-ended sessions and daemon resource use** — long sessions accumulate context in LLM-refine mode. Daemon must reset session state on `{"type": "end"}` and on idle timeout (configurable, default 30 min).

## Migration Plan

Pure additive — no existing functionality changes. Users who don't want this feature don't install `[listen]`. Rollback is `git revert`.

## Open Questions

- Should `aureka listen` write segment-by-segment to the same file format as the future SRT/VTT proposal? Lean yes; coordinate timestamps so the listen output can be played back later. Defer decision until the subtitle proposal lands.
- Is auto-pause-on-silence valuable? Today voice-input has VAD; for listen we segment by VAD but never pause overall capture. Add later if users ask.
