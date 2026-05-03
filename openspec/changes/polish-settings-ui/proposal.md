## Why

The settings UI shipped in the previous change is functional but ugly and under-guided: every field is a free-text input, the user has to know valid values (Kokoro voice IDs, Whisper sizes, pynput key strings), there is no visibility into model download state, and benchmark numbers live in standalone Markdown reports disconnected from configuration. This change closes the UX gap so a non-expert can configure Aureka end-to-end without reading docs or grepping the codebase.

## What Changes

- Redesign the pywebview settings window with Tailwind: sidebar navigation, helper text per field, dark-mode aware, consistent typography and spacing.
- Replace free-text inputs with **dropdowns / datalists** wherever the value space is known:
  - Static: ASR model size, Kokoro voice ID, TTS device, hotkey mode, hotkey input mode, daemon host
  - Dynamic: LLM/VLM model — fetched live from `{base_url}/v1/models`; VLM further filtered to vision-capable
- Add a **Models tab** that shows download status for Kokoro + faster-whisper, file size on disk, and a per-model Download / Re-download button with live progress bar.
- Add a **port auto-detect** helper next to `daemon.port` that probes a free port via `socket.bind(0)`.
- Add a **hotkey capture** helper next to `hotkey.trigger` that records the next key combo and converts it to pynput format.
- Add a **Tools tab** with a "Run benchmark" button that streams `aureka benchmark --quick` output into the window and surfaces concrete configuration recommendations (device, ASR model size, thinking_budget) the user can apply with one click.
- Extend `aureka.models` with a `model_status() -> dict` query so the UI can render "Downloaded / Missing" without triggering a download.
- Extend `aureka.benchmark` with a structured-result return so the UI can read metrics programmatically rather than parsing the Markdown report.
- Refresh the tray icon to follow platform convention: monochrome + alpha "template image" on macOS so it auto-tints in light/dark menu bar; full-color glyph on Windows tray. Both `aureka/tray.py` (daemon control) and `aureka/client.py:start_tray` (voice input) share a single `_make_icon()` helper.

## Capabilities

### New Capabilities
- `settings-ui`: pywebview window backed by `config.toml`, exposes load / save / reload-daemon, model status & download, port probe, hotkey capture, and benchmark integration.

### Modified Capabilities
- `model-management`: add programmatic "is downloaded + size" query and a progress-callback signature for `download_all`, both consumed by the settings UI.
- `benchmark`: add structured result return alongside the existing Markdown report so callers can inspect metrics without parsing the file.
- `voice-input`: introduce an explicit requirement that the tray icon follows platform convention (template image on macOS, color glyph on Windows).

## Impact

- New file: `aureka/_ui/` for any vendored static assets if Tailwind ends up bundled (Play CDN is the default; vendored is the offline fallback).
- New file: `aureka/_icon.py` exposing a `make_tray_icon() -> PIL.Image.Image` helper used by both tray entry points; macOS path produces a template-style image and registers `isTemplate` via a small pyobjc shim.
- Modified files: `aureka/ui.py` (largest delta), `aureka/models.py` (new query + progress), `aureka/benchmark.py` (return shape), `aureka/tray.py` and `aureka/client.py:start_tray` (call the new icon helper).
- No new top-level dependencies — Tailwind comes from CDN; everything else is stdlib + libraries already declared in the `[ui]` extra.
- No CLI surface change in this round; tray-merge and autostart-launches-tray are tracked separately.
