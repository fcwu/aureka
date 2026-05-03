## Why

Two cheap ergonomic wins from competitor research, bundled because they're independent and each costs a half day:

1. **SRT / VTT output from the batch pipeline.** Today `aureka process` only emits Markdown; video editors and accessibility tooling want timed subtitle files. Adding two writers reuses the timestamps the ASR pipeline already produces.
2. **Pause / resume hotkey during recording.** During longer voice-input sessions or `aureka listen` capture, users sometimes need to step away. Today the only options are Ctrl+C (loses the session) or talking awkwardly. A configurable hotkey toggles capture without ending the session.

Both pieces touch existing capabilities (`batch-pipeline`, `voice-input`); together they round out the day-to-day quality-of-life gaps.

## What Changes

### Subtitle outputs

- `aureka.pipeline` adds two writers: `SrtWriter` and `VttWriter`, both fed from the same per-segment timestamp + text data already used for the Markdown writer.
- `aureka process` gains `--format md|srt|vtt|all` (default `md` — backward compatible). Multiple formats may be requested.
- File names follow the existing convention: `<basename>.srt`, `<basename>.vtt` alongside the `.md`.

### Pause / resume hotkey

- New config field `[hotkey].pause = "<ctrl>+<alt>+p"` (default), recognized by both `aureka type` (when the recorder is live) and `aureka listen`.
- Pressing it toggles the current `Recorder` / `LoopbackStream` between `running` and `paused` states. Paused = audio chunks dropped silently; LLM session (refine / translate) is preserved across the gap.
- Tray menu gains a checkable "Pause capture" item that toggles the same state.
- Status bar / pywebview window indicates the paused state with a small badge.

## Capabilities

### New Capabilities
*(none)*

### Modified Capabilities
- `batch-pipeline`: emit SRT / VTT in addition to Markdown when requested via `--format`.
- `voice-input`: support a configurable Pause/Resume hotkey for `aureka type` and `aureka listen`. Recorder gains `pause()` / `resume()` operations.
- `cli`: `aureka process` accepts `--format` flag; `aureka type` and `aureka listen` honor `[hotkey].pause`.

## Impact

- New file: `aureka/subtitle.py` (thin SRT / VTT formatters; ~80 LOC).
- Modified: `aureka/pipeline.py`, `aureka/recorder.py`, `aureka/hotkey.py`, `aureka/tray.py`, `aureka/__main__.py`, `aureka/config.py`, `aureka/ui.py` (new field).
- No new runtime deps. All deterministic, well-defined formats.
