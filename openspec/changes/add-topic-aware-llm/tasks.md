## 1. Config + plumbing

- [ ] 1.1 Add `topic: str = ""` to `aureka.config.HotkeyConfig`
- [ ] 1.2 Update `config.example.toml` with the new key + comment

## 2. LLM prompt builder

- [ ] 2.1 Modify `aureka.llm.llm_refine_stream` (and `llm_translate_stream` if separate) to accept an optional `topic: str = ""`; prepend a system-message prefix only when non-empty
- [ ] 2.2 Verify prompts when `topic == ""` are byte-identical to the existing version (`difflib`-style assertion in tests)

## 3. CLI flag

- [ ] 3.1 Add `--topic STRING` to the `aureka type` subparser in `aureka/__main__.py`
- [ ] 3.2 Resolve precedence in `cmd_type`: flag → cfg.hotkey.topic → ""
- [ ] 3.3 Pass resolved topic into the daemon WebSocket start frame and the local-fallback path

## 4. Daemon passthrough

- [ ] 4.1 Update `/voice` start-frame schema to accept optional `topic: str`
- [ ] 4.2 Forward the topic into the LLM helpers
- [ ] 4.3 Confirm wire-compat: clients that don't send `topic` still work

## 5. Settings UI

- [ ] 5.1 Add a Topic field to the Hotkey panel in `aureka/ui.py` HTML
- [ ] 5.2 Helper text quoting the spec scenario
- [ ] 5.3 Verify `Api.save_config` round-trips the new key

## 6. Tests

- [ ] 6.1 `tests/test_llm_unit.py` (or similar): topic empty → prompt matches snapshot; non-empty → topic appears in system message
- [ ] 6.2 `tests/test_main_cli_unit.py` (or extend existing): `--topic` flag overrides config
- [ ] 6.3 `tests/test_ui_unit.py`: Topic field round-trips via save_config

## 7. Documentation

- [ ] 7.1 README: add `--topic` to the `aureka type` example block
- [ ] 7.2 README: mention Hotkey/Topic in the settings UI section
