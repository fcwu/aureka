## 1. Subtitle writers

- [ ] 1.1 Create `aureka/subtitle.py` with `write_srt(segments, path)` and `write_vtt(segments, path)`
- [ ] 1.2 Reuse the segment tuple shape already produced by `aureka.pipeline`
- [ ] 1.3 Use `\n` line endings; SRT uses `,` for ms, VTT uses `.`

## 2. Pipeline integration

- [ ] 2.1 Modify `aureka/pipeline.py` to dispatch on requested `format` set
- [ ] 2.2 Default format is `{"md"}` (preserves backward compat)
- [ ] 2.3 Add `--format` flag to `aureka process` subparser; parse comma list

## 3. Recorder pause state

- [ ] 3.1 Add `_paused: bool` flag and `pause()` / `resume()` methods to `aureka.recorder.Recorder`
- [ ] 3.2 Audio thread checks `_paused` in its loop and drops chunks while True
- [ ] 3.3 `stop()` works regardless of paused / running state

## 4. Hotkey wiring

- [ ] 4.1 Add `pause: str = "<ctrl>+<alt>+p"` to `aureka.config.HotkeyConfig`
- [ ] 4.2 Extend `aureka.hotkey.HotkeyManager` to bind a second key
- [ ] 4.3 Wire `aureka type` cmd handler to register pause hotkey
- [ ] 4.4 Wire `aureka listen` cmd handler likewise (depends on system-audio change being implemented; otherwise skip until then)
- [ ] 4.5 Warn (stderr) when `pause` and `trigger` collide; do not register pause in that case

## 5. Tray menu integration

- [ ] 5.1 Add a checkable "Pause capture" item to the voice-input tray (`aureka.client.start_tray`)
- [ ] 5.2 Bind both directions: hotkey toggles tray check, tray click toggles recorder
- [ ] 5.3 Disable when no recorder is currently running

## 6. UI

- [ ] 6.1 Settings UI Hotkey tab gains a "Pause hotkey" field with the same Press… capture behavior as Trigger
- [ ] 6.2 Helper text mentions auto-detected collision warning

## 7. Documentation

- [ ] 7.1 README: under "批次處理 / 輸出" mention SRT / VTT and `--format` flag
- [ ] 7.2 README: under "錄音模式" mention pause hotkey

## 8. Tests

- [ ] 8.1 `tests/test_subtitle_unit.py`: SRT format spot checks, VTT header, multi-segment indexing, ms precision
- [ ] 8.2 `tests/test_pipeline.py`: `--format all` produces all three files; default format unchanged
- [ ] 8.3 `tests/test_recorder.py`: `pause()` drops chunks; `resume()` continues; `stop()` works from paused
- [ ] 8.4 `tests/test_hotkey_unit.py`: trigger + pause both register; collision logs warning
