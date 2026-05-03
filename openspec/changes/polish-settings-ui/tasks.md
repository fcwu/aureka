## 1. Backend extensions

- [x] 1.1 Add `model_status() -> dict[str, dict]` to `aureka/models.py` using `huggingface_hub.scan_cache_dir`; covers downloaded flag, byte size, snapshot path
- [x] 1.2 Add optional `progress` callback to `download_all`; emit `start` / `progress` / `done` / `error` phases keyed by repo
- [x] 1.3 Modify `aureka/benchmark.py` `run_benchmark` to also return a structured dict (`{report_path, tasks: {name: {median, min, max, device, status, ...}}}`) without breaking the CLI return type
- [x] 1.4 Add optional `progress: Callable[[str], None]` to `run_benchmark`; route stdout-progress lines through it when supplied

## 2. UI bridge (`aureka.ui.Api`)

- [x] 2.1 Add `Api.list_llm_models()` and `Api.list_vlm_models()`: GET `{base_url}/v1/models`, return `[id]`; VLM filters to vision-capable
- [x] 2.2 Add `Api.model_status()` thin wrapper around `aureka.models.model_status`
- [x] 2.3 Add `Api.start_download(keys: list[str])` spawning a daemon thread that drives `download_all(progress=...)`, writing state to a module-level dict guarded by a lock
- [x] 2.4 Add `Api.download_progress()` returning the current state dict for JS polling
- [x] 2.5 Add `Api.find_free_port(start: int) -> int | None` probing `socket.bind(("127.0.0.1", port))` for `start..start+64`
- [x] 2.6 Add `Api.start_benchmark(quick: bool, skip_llm: bool)` spawning a daemon thread; capture progress lines into a queue
- [x] 2.7 Add `Api.benchmark_progress()` returning `{lines: list[str], done: bool, result: dict | None}` for JS polling
- [x] 2.8 Add `Api.benchmark_recommendations(result)` (or compute inline) returning a list of `{section, key, value, reason, source}`

## 3. UI layout & styling

- [x] 3.1 Embed Tailwind Play CDN script + extend config (light/dark, custom palette token)
- [x] 3.2 Inline a fallback `<style>` block providing layout + form + button readability without Tailwind
- [x] 3.3 Replace top-tab markup with sidebar nav (LLM / VLM / ASR / TTS / Models / Hotkey / Daemon / Tools)
- [x] 3.4 Restructure each section as a 2-column grid: label + helper text on left, input on right
- [x] 3.5 Update header (title + config path) and sticky footer (status text + Close + Save)
- [x] 3.6 Default window size: 760×600

## 4. Field controls per spec

- [x] 4.1 Static `<select>` for `tts.lang_code`, `tts.device`, `hotkey.mode`, `hotkey.input_mode`, `daemon.host`
- [x] 4.2 `<input list="">+<datalist>` for `asr.model`, `tts.voice`, `hotkey.lang`
- [x] 4.3 LLM/VLM model `<datalist>` populated from `Api.list_llm_models` / `Api.list_vlm_models` on window open; fallback `auto` if fetch fails
- [x] 4.4 Helper text per field reflecting `config.example.toml` comments

## 5. Models tab

- [x] 5.1 Render Kokoro and faster-whisper rows from `Api.model_status` (repo id, downloaded badge, size)
- [x] 5.2 Per-row Download / Re-download button → `Api.start_download([key])`
- [x] 5.3 Progress bar bound to `Api.download_progress()` polling at 500 ms; success state shows `Downloaded ✓ <size>`
- [x] 5.4 Error state: red row with exception type + auth hint; polling stops

## 6. Port probe + Hotkey capture

- [x] 6.1 "Auto" button next to `daemon.port` calling `Api.find_free_port(currentValue)`; fill on success, inline message on failure
- [x] 6.2 "Press…" button next to `hotkey.trigger`: JS keydown listener, modifier+key → pynput string, ESC cancels

## 7. Tools tab (benchmark)

- [x] 7.1 "Run benchmark" button (with `--quick` and "include LLM" checkboxes) calls `Api.start_benchmark`
- [x] 7.2 `<pre>` log streaming benchmark progress lines via `Api.benchmark_progress` polling
- [x] 7.3 Recommendation cards rendered from structured result; each card has source numbers + Apply button
- [x] 7.4 Apply switches sidebar to relevant section, fills the field, leaves Save to the user

## 7b. Auto-save (replaces Save button)

- [x] 7b.1 Remove Save and Close buttons from footer; status bar only
- [x] 7b.2 Bind `change` listeners on every `[data-k]` field; `_initialLoadDone` flag suppresses saves during the initial `applyConfig`
- [x] 7b.3 Debounce saves (~350 ms) so rapid edits coalesce into one POST `/reload`
- [x] 7b.4 Programmatic value sets (port Auto, hotkey capture, recommendation Apply) go through `setFieldValue(el, v)` that dispatches a synthetic `change` event

## 7c. Tray as autostart entry point

- [x] 7c.1 `aureka/tray.py:run_tray` checks daemon health on launch and spawns `aureka daemon start` (with `start_new_session=True`) if missing
- [x] 7c.2 `aureka/autostart.py` `_serve_args` and `_win_command` switch from `_daemon_serve` to `tray`
- [x] 7c.3 macOS plist: `ProcessType` flips Background → Adaptive; log path renamed to `tray.{out,err}.log`
- [x] 7c.4 Validate plist round-trip + `plutil -lint` after change

## 7d. README documentation

- [x] 7d.1 Add a section covering `aureka ui`, `aureka tray`, `aureka autostart {install,uninstall,status}` in README.md, ordered after the existing daemon section
- [x] 7d.2 Mention auto-save semantics in the UI section so users don't look for a Save button
- [x] 7d.3 Note that `autostart install` launches `aureka tray`, which auto-starts the daemon

## 8. Tray icon refresh

- [x] 8.1 Create `aureka/_icon.py` with `make_tray_icon() -> PIL.Image.Image`; render "A + sparkles" via ImageDraw at 4× then downsample with LANCZOS
- [x] 8.2 macOS path: black on alpha, ≥88×88; Windows path: `#3b82f6` strokes on alpha, ≥64×64
- [x] 8.3 macOS template-image shim: after `pystray.Icon.run()`, set `_status_item.button.image.setTemplate_(True)` via pyobjc; wrap in try/except, log warning on failure
- [x] 8.4 Replace inline `Image.new(...)` in `aureka/tray.py` with `make_tray_icon()`
- [x] 8.5 Replace inline `Image.new(...)` in `aureka/client.py:start_tray` with `make_tray_icon()`
- [ ] 8.6 Visual check on macOS light + dark menu bar (icon should auto-tint)

## 9. Verification

- [ ] 9.1 Smoke test: open window, edit a value, save → confirm `config.toml` round-tripped with comments preserved
- [ ] 9.2 Models tab smoke test: status renders for both repos (already-downloaded and missing cases via mocked HF cache)
- [ ] 9.3 Tools tab smoke test: run benchmark with `--skip-llm` to bound runtime; verify recommendation cards appear when thresholds hit
- [ ] 9.4 Offline test: kill DNS / block CDN, confirm fallback CSS keeps the form usable
- [ ] 9.5 Visual review on macOS (WKWebView) — compare side-by-side with previous version
