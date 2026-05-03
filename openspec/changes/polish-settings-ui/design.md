## Context

`aureka/ui.py` ships a pywebview window with hand-rolled CSS (~80 lines), free-text inputs, no model status, and no benchmark integration. Field semantics are documented in `config.example.toml` and `CLAUDE.md` but not in the UI itself, so anyone who edits via the GUI must already know what to type. Long-running tasks (model download, benchmark) currently exist only as CLI commands; integrating them into the window means juggling background work, progress streaming, and the JS↔Python bridge.

Active constraints:
- Cross-platform desktop app (macOS WKWebView, Windows WebView2). No Linux focus this round.
- Python-only project; no Node toolchain. Anything that requires a build step is a non-starter.
- pywebview's `js_api` calls run synchronously in a worker thread per call; UI updates back to JS go via `window.evaluate_js(...)` from the Python side.
- Existing capabilities in `model-management` and `benchmark` already encapsulate the heavy lifting; the UI is a thin coordinator.

## Goals / Non-Goals

**Goals:**
- Make every input either a dropdown, datalist, or button-assisted field whenever the value space is bounded.
- Provide visible model download state and one-click trigger with progress, without leaving the window.
- Show benchmark numbers in the same window as the settings they would influence, with concrete "apply this value" buttons.
- Look modern. The UI should feel like a 2026 desktop preferences pane, not a 2005 Tk dialog.

**Non-Goals:**
- Replace pywebview with Qt/Toga. Decision was settled in the previous round.
- Add a server-rendered web admin / browser-based UI.
- Localize strings (UI stays bilingual mixed Chinese/English like the rest of the project).
- Rebuild benchmark: this change only consumes structured results.
- Tray merge / autostart-launches-tray (tracked as a separate change; this round only touches `aureka/ui.py`, `aureka/models.py`, `aureka/benchmark.py`).

## Decisions

### 1. Tailwind delivery: Play CDN with inline fallback

Use `<script src="https://cdn.tailwindcss.com">` (Tailwind Play CDN) loaded inline by the HTML embedded in `ui.py`. Ship a small handwritten CSS fallback inside the same HTML so the form remains usable when the CDN can't be reached.

**Why:** No Node toolchain → can't pre-build a static `tailwind.css`. Vendoring a 340 KB JS blob inside `ui.py` bloats the source. Most desktop machines have internet on first launch; offline-first is not required for a settings dialog. Fallback CSS keeps it functional in the airport-Wi-Fi scenario.

**Alternatives considered:**
- Vendored pre-built CSS (`aureka/_ui/tailwind.css`): heavier source tree, requires a generator; rejected.
- Skip Tailwind, write hand-rolled CSS with design tokens: matches the pragmatic choice but the user explicitly asked for Tailwind; rejected.
- Bundle Tailwind as a `[ui]` extra wheel: no such PyPI package exists at a sane version.

### 2. Layout: sidebar nav + content pane, 760×600 default

Switch from horizontal tabs at the top to a left-side rail with the section list (LLM, VLM, ASR, TTS, Models, Hotkey, Daemon, Tools). Content area on the right uses a 2-column grid: label + helper text in left column, input in right column.

**Why:** With helper text per field, horizontal real estate matters more than vertical; sidebar leaves more room for one-line descriptions. Models and Tools tabs need vertical room for status lists / log streams.

### 3. Dropdown vs datalist

- **Static, exhaustive value sets** → `<select>`: `tts.lang_code`, `tts.device`, `hotkey.mode`, `hotkey.input_mode`, `daemon.host`.
- **Static, but user might want a value we don't know about** → `<input list="...">` + `<datalist>`: `asr.model` (size names), `tts.voice` (Kokoro IDs may grow upstream), `hotkey.lang` (ISO codes).
- **Dynamic, fetched at window open** → `<input list="...">` + `<datalist>`: `llm.model`, `vlm.model` from `{base_url}/v1/models`. Combobox preserves "auto" and custom IDs.

**Why:** Datalist is one HTML element away from a select but doesn't trap users in our enum. WebKit/Chromium both render it as a native combobox.

### 4. Model download: background thread + status polling

`Api.start_download(repo_keys)` spawns a daemon thread that drives `huggingface_hub.snapshot_download` per repo and writes phase / current-file / bytes-pulled to a module-level dict guarded by a lock. JS polls `Api.download_progress()` every 500 ms and renders a progress bar; on completion, polls switch to "Downloaded" status.

**Why:** pywebview's JS API calls are synchronous from JS's perspective and run on a worker thread per call — kicking off a multi-minute snapshot_download from the API method itself would block any subsequent call (including a Cancel button). Polling keeps the JS↔Python bridge cheap and responsive.

**Trade-off:** Polling has 500 ms granularity; we do not stream individual file events. For a UI that only shows a progress bar this is fine.

### 5. Model status query

Add `aureka.models.model_status() -> dict[str, dict]` returning `{repo_key: {"downloaded": bool, "size_bytes": int, "snapshot_path": str|None}}`. Implemented via `huggingface_hub.scan_cache_dir()` filtered by repo_id.

**Why:** UI needs cheap "is it cached?" checks at window open. Avoiding a full `snapshot_download` for the answer is essential — that's what we're trying to gate.

### 6. Port auto-detect

Adjacent button calls `Api.find_free_port(start: int) -> int` which loops `socket.bind(("127.0.0.1", port))` from `start` up to `start + 64`, returns the first one that succeeds. UI fills the field; user still has to Save.

**Why:** No magic write-on-click — the user might be probing rather than committing.

### 7. Hotkey capture

UI button toggles a "press a key" state in JS: listens for the next `keydown` event, captures `event.code` plus modifier flags, converts to pynput's `<ctrl>+<alt>+space` syntax via a small mapping table in JS, fills the field. ESC cancels.

**Why:** No round-trip to Python needed for the capture itself. JS fires keys reliably inside the webview context.

### 8. Benchmark integration

`Api.start_benchmark(quick: bool, skip_llm: bool)` runs `aureka.benchmark.run_benchmark(...)` in a daemon thread. New `run_benchmark` overload takes a `progress_callback(line: str)` that the UI uses to stream stdout into a `<pre>` log. On completion, the structured result dict (median ASR RTF, TTS RTF, LLM TTFT, etc.) drives a "Recommendations" card.

**Recommendation rules (initial cut, easy to evolve):**
- If `mps` was tested and `mps.median < cpu.median * 0.7` → recommend `tts.device = mps`.
- ASR median RTF over `0.5` and current model is `medium`/larger → recommend dropping one size.
- LLM TTFT > 3 s with thinking enabled → recommend `thinking_budget = 0`.

**Why:** Rules are conservative thresholds users can argue with via "Apply" / "Dismiss" buttons. We do not auto-apply.

### 9. Tray icon: platform-conditional rendering + macOS template image

Centralize icon generation in a new `aureka/_icon.py` exposing `make_tray_icon() -> PIL.Image.Image`. The function dispatches on `platform.system()`:
- **macOS**: render a 88×88 RGBA glyph in pure black on transparent (a stylized microphone or single letter), then ask pystray for the icon and follow up with a tiny pyobjc shim that flips `NSImage.setTemplate_(True)` on the underlying `_status_item.button.image` — this is what makes macOS auto-tint the icon in light/dark menu bar without us drawing two variants.
- **Windows**: render a 64×64 RGBA color glyph (rounded square background, white foreground) for visibility against varied taskbar themes.
- **Linux / other**: fall back to the Windows color glyph.

Both `aureka/tray.py` (daemon-control tray) and `aureka/client.py:start_tray` (voice input tray) replace their inline `Image.new(...)` blocks with `from aureka._icon import make_tray_icon; img = make_tray_icon()`.

**Why pyobjc shim instead of a pystray subclass:** pystray has no public API for `isTemplate`; the shim is ~5 lines and only runs on macOS, gated by a try/import to keep Linux/Windows untouched. Subclassing `pystray._darwin.Icon` couples us to private internals and breaks on minor pystray bumps.

**Why centralize in `_icon.py` rather than inline in each tray:** today both files draw subtly different icons (blue circle with white inner circle vs. blue circle with white "A"). Visually inconsistent, and any tweak has to be made twice. One helper, one source of truth.

**Glyph choice:** an "A" outline with two or three small 4-pointed sparkle stars to its right, matching the reference design (Aureka brand letter + AI sparkle motif). Drawn via `ImageDraw` line / polygon primitives at 4× target size and downsampled with LANCZOS for anti-aliasing.

- macOS template: black strokes (`#000`), transparent background, sparkles included as part of the same glyph so the system's auto-tint applies uniformly.
- Windows color: blue strokes (`#3b82f6`) over a transparent background; no rounded backplate (the system tray supplies its own contrast). If contrast turns out poor on light/dark themes, fall back to a 64×64 rounded-square plate at `#3b82f6` with white strokes.

Strokes target ~12% of canvas width to stay legible at 22pt menu bar size.

### 10. Auto-save: drop the Save button entirely

Field commits trigger save automatically. Implementation:
- For every `[data-k]` input/select, register a JS `change` listener; selects fire instantly, inputs fire on blur or Enter (the standard "commit" semantics).
- Listener calls a debounced `scheduleSave()` (350 ms) → POST through the same `Api.save_config(payload)` path that the Save button previously used.
- A short `_initialLoadDone` guard suppresses saves during the initial `applyConfig()` pass on window open.
- Programmatic value sets (port Auto button, hotkey capture, recommendation Apply) go through `setFieldValue(el, v)` which dispatches a synthetic `change` event so the same auto-save listener fires.

**Why drop Save:** the manual Save button created an extra step and an inconsistency window between "edited" and "applied". For a small settings dialog where every field maps 1:1 to a config key, autosave is the macOS / iOS preferences norm.

**Why no in-window Close button:** removing Save means the only remaining footer button was Close, which duplicated the OS window frame. We keep the footer (status text only) and let users close via the native chrome (red traffic light on macOS, X on Windows). This also dodges the worker-thread `Window.destroy()` quirk that made the previous Close button unreliable on macOS.

**Trade-off:** typos persist immediately. Mitigation: every save also POSTs `/reload` to the daemon, and the status bar surfaces "needs restart" warnings in the same place. The user can always undo by editing again.

### 11. Tray as the autostart entry point

The previous round's `aureka autostart install` wired `aureka _daemon_serve` directly. That gave a working daemon at login but no UI to control it. Switch the login command to `aureka tray`:

- `aureka tray` (`aureka/tray.py:run_tray`) on launch checks whether the daemon is reachable on `(cfg.daemon.host, cfg.daemon.port)` and, if not, calls `_spawn("daemon", "start")`. Spawn uses `start_new_session=True` so the daemon survives the tray's lifetime.
- macOS plist: `ProcessType` flips from `Background` (correct for a headless service) to `Adaptive` (correct for a menu-bar GUI). `KeepAlive: {SuccessfulExit: False, Crashed: True}` already does the right thing — Quit-from-menu exits cleanly and is not respawned; an actual crash gets restarted.
- Windows: schtasks command becomes `cmd /c "set AUREKA_CONFIG=… && python -m aureka tray"`. Same `/sc onlogon` schedule as before.

**Why tray-as-entry instead of two separate launch agents:** one entry point keeps the user mental model simple ("Aureka starts at login = tray icon + working hotkey"). Two LaunchAgents (one per process) doubles the install / uninstall surface and creates a state machine where the daemon could be running without the tray.

**Why tray spawns daemon (not the reverse):** the daemon is a long-lived service; the tray is the user-facing client. The dependency direction matches: client launches and verifies its server. If the user later runs `aureka daemon stop` from the tray, the tray stays alive and shows "Daemon: stopped" — a clear state signal.

## Risks / Trade-offs

- **Tailwind CDN unreachable** → Form still functions via inline fallback CSS but looks utilitarian. Acceptable; Settings is rarely a first-impression surface.
- **`scan_cache_dir` slow on huge HF caches** → Cache-scan happens once per window open; tens of ms in practice.
- **Model download progress polling can lag visually** at 500 ms intervals → User sees a progress bar that updates twice a second; matches OS-level Finder/Explorer behavior.
- **JS hotkey capture differs across WebKit / WebView2** for some non-printable keys → Mapping table covers the modifiers + common keys; rare edge cases (media keys) fall through to "Press another combination".
- **Benchmark recommendation thresholds are opinionated** → Each recommendation has source numbers visible alongside; user can dismiss without applying. Thresholds live in one constant table for easy tuning.
- **macOS template-image shim depends on pystray internals (`_status_item.button.image`)** → If pystray refactors the macOS backend, the shim breaks silently (icon goes back to fixed-color). Mitigation: wrap in try/except, log warning, fall back to monochrome non-template image which is still readable on both light and dark menu bars.

## Migration Plan

This is additive UI work — no breaking changes, no data migrations. Existing `config.toml` files load unchanged. Users who never open the new tabs see no difference except the visual refresh. Rollback is `git revert` of the single feature commit.

## Open Questions

- Should hotkey capture validate that the captured combo isn't already used by the OS / another app? Defer; OS will surface conflicts at registration time.
- Should the benchmark log persist across window reopens? Defer; rerunning is cheap in `--quick` mode.
