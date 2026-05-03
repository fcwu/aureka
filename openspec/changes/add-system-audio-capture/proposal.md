## Why

Today Aureka can only transcribe sound coming from the user's microphone. The biggest unlock from competitor research (`jt-live-whisper`) is **system audio loopback** — capturing the audio that the OS is sending to speakers (Zoom / Teams / Meet calls, YouTube, podcasts, recorded lectures). With this, the same Whisper backend that powers `aureka type` becomes a meeting-transcription tool, an "explain this video" workflow, and a study aid — all without changing how the user already records voice input.

The change is **additive**: it does not replace `aureka type`. A new parallel subcommand `aureka listen` consumes a system-audio stream, runs the same ASR/refine pipeline, and writes results to a streaming transcript window or file. The existing voice-input flow is unchanged.

## What Changes

- New subcommand `aureka listen` that captures system audio and streams transcripts.
  - Output sinks: `--out FILE` (append text per segment), `--window` (open a tail-style transcript window via pywebview), or both.
  - Modes: `transcribe` (raw text), `refine` (LLM cleanup), `translate --target zh|en` — same semantics as `aureka type`.
  - Optional `--mic` adds a second capture channel for the user's microphone, multiplexed by speaker label (`[system]` / `[mic]`) — enables transcribing two-way meetings without speaker diarization.
- New backend module `aureka.audio_loopback` that abstracts platform capture:
  - **macOS**: instruct user to install / select [BlackHole](https://existential.audio/blackhole/); auto-detect once present. Provide `aureka doctor audio` to verify the routing.
  - **Windows**: WASAPI Loopback via `soundcard` (preferred) or `sounddevice` (fallback) — built into the OS, no extra driver needed.
  - **Linux**: PulseAudio monitor source via `parec` / `sounddevice`.
- Settings UI gets a new "Listen" tab showing detected loopback devices, current sink configuration, and a "Test capture" button that streams 5 seconds of waveform / RMS to verify routing before live use.
- README adds a "Transcribe system audio" section with the BlackHole + Multi-Output setup walkthrough.

## Capabilities

### New Capabilities
- `system-audio`: cross-platform loopback capture and streaming transcription pipeline. Wraps platform-specific input drivers behind a uniform `LoopbackStream` interface.

### Modified Capabilities
- `cli`: add `aureka listen` subcommand and `aureka doctor audio` diagnostic.
- `daemon`: add `/listen` WebSocket endpoint mirroring `/voice` but consuming a continuous loopback stream instead of a single voice session.
- `settings-ui`: add a Listen tab plus device selection / capture probe.

## Impact

- New deps in a new `[listen]` extra: `soundcard>=0.4` (cross-platform loopback), platform-conditional install of nothing extra (PulseAudio / BlackHole are user-installed system components).
- New file: `aureka/audio_loopback.py`.
- Modified: `aureka/__main__.py`, `aureka/daemon.py`, `aureka/ui.py`, `aureka/config.py` (new `[listen]` section).
- BlackHole is **not auto-installed** — install steps live in README; we surface clear error messages with install instructions when the device is missing.
- No protocol break for existing clients — `/voice` keeps current behavior, `/listen` is additive.
