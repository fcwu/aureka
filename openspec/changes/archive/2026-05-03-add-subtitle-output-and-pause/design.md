## Context

`aureka.pipeline` produces a structured intermediate representation (timestamps + text per segment, plus VLM frame captions when applicable) before invoking a single Markdown writer. Adding subtitle formats is a writer-only change — no upstream pipeline restructuring needed.

`aureka.recorder.Recorder` is a single-state machine (start / stop). Pause is currently absent, but the underlying audio stream loop already runs in a dedicated thread, so toggling a `paused` flag that drops chunks is mechanically simple.

`aureka.hotkey.HotkeyManager` already binds the trigger key for record-start / record-stop. Binding a second hotkey is a one-liner.

## Goals / Non-Goals

**Goals:**
- Subtitle files are byte-identical to what video editors expect (DaVinci Resolve, Premiere, Subtitle Edit, FFmpeg's `-c copy`).
- Pause hotkey is unambiguous: same UX in `aureka type`, `aureka listen`, and the tray menu.
- No change to existing one-format behavior — `aureka process` without `--format` still emits Markdown only.

**Non-Goals:**
- Restyled / multi-line subtitle formatting (e.g. CPS / line-length rules). Output one segment per cue, that's enough for video editors to refine downstream.
- Translated subtitle tracks. We only emit the language the ASR/LLM already produced.
- Pause-as-time-marker (inserting `[pause]` markers in transcripts). Pause silently drops audio.

## Decisions

### 1. SRT and VTT writers in one tiny module

`aureka/subtitle.py` exposes `write_srt(segments, path)` and `write_vtt(segments, path)` taking the same `[(t_start, t_end, text), ...]` tuple list the Markdown writer already consumes. ~30 LOC each. No state, no dependencies.

Format reference:
- SRT: 1-based index, `HH:MM:SS,mmm` timestamps, blank line separator.
- VTT: `WEBVTT` header, `HH:MM:SS.mmm` timestamps, blank line separator.

Both use `\n` line endings (consumers are tolerant; `\r\n` causes weirdness in some Linux tools).

### 2. Multi-format CLI flag

```
aureka process video.mp4                    # md only (default, unchanged)
aureka process video.mp4 --format srt       # srt only
aureka process video.mp4 --format md,srt    # both
aureka process video.mp4 --format all       # md + srt + vtt
```

Implemented as a comma-separated `--format` string parsed into a set. Default is `md` for backward compatibility — existing users see no change.

### 3. Recorder pause state machine

```
running ── pause hotkey ──▶ paused
running ── stop ──────────▶ stopped
paused  ── pause hotkey ──▶ running
paused  ── stop ──────────▶ stopped
```

`Recorder.pause()` flips an `_paused = True` flag checked in the audio thread's tight loop. When True, incoming chunks are dropped, the buffer / VAD state is left untouched. `Recorder.resume()` clears the flag.

LLM session state (refine / translate) lives downstream of the recorder in the daemon — paused recorder means daemon stops getting audio frames, but its WebSocket session and LLM context stay alive. On resume, we don't insert a synthetic gap; LLM picks up wherever ASR resumes.

### 4. Hotkey binding

`aureka.hotkey.HotkeyManager` is extended to bind a second key. `aureka type` and `aureka listen` both register the same handler that flips recorder state and prints a small `[paused]` / `[resumed]` line to stderr.

### 5. Tray "Pause capture" menu item

When tray's voice-input client is running, the menu shows a checkable "Pause capture" item bound to the same toggle. Default keyboard shortcut is `<ctrl>+<alt>+p`; the tray entry mirrors the underlying state.

### 6. UI surfacing

The settings window's Hotkey tab gains a new "Pause hotkey" field next to the existing trigger field, with the same "Press…" capture button pattern.

## Risks / Trade-offs

- **Subtitle timestamp drift on long files** — if ASR timestamps drift relative to wall clock (rare with faster-whisper), subtitle cues may desync. We don't post-process; the upstream `aureka process` pipeline already returns aligned timestamps. Document the dependency.
- **Pause races with VAD finalization** — if the user pauses mid-utterance, the in-flight VAD segment may close mid-sentence. Mitigation: drain the current segment one tick after `pause()` so it finalizes naturally.
- **Hotkey collision** — pause hotkey may collide with the trigger hotkey on some keyboards if user picks the same combo. Document the constraint; surface a warning in UI when both fields share a value.

## Migration Plan

Pure additive:
- Existing `aureka process video.mp4` → still emits `.md` only (default `--format md`).
- Existing `[hotkey]` config without `pause` field → falls back to the new default; no upgrade ceremony required.
