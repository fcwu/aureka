## Why

LLM-driven refine / translate produces flat, generic results when fed domain-specific transcripts ("ZFS storage administration", "QTS firmware compatibility matrix") because the model has no signal about which jargon should stay verbatim and which translation conventions apply. Borrowing jt-live-whisper's `--topic` idea: a single short string prepended to the LLM prompt nudges the model toward the right vocabulary at near-zero implementation cost.

## What Changes

- Add an optional **topic / context string** to the user-visible config and runtime arguments. Empty by default.
- `aureka type --topic "ZFS storage"` (CLI) and a "Topic / context" field in the settings UI Hotkey tab feed the same value; CLI flag overrides config for a single invocation.
- `aureka.llm.llm_refine_stream` and `llm_translate_stream` (or whichever entry path the daemon uses) inject the topic into the system / user prompt when non-empty. When empty the prompt is byte-identical to today.
- Topic is plumbed end-to-end through the daemon's `/voice` WebSocket so the daemon-aware fast path also picks it up.

## Capabilities

### New Capabilities
*(none)*

### Modified Capabilities
- `voice-input`: `refine` and `translate` modes' LLM prompts SHALL include the topic string when configured. Empty topic preserves existing prompt verbatim.
- `cli`: `aureka type` accepts a `--topic STRING` flag that overrides the config value for one invocation.
- `settings-ui`: Hotkey tab gains a "Topic / context" field bound to `cfg.hotkey.topic`.

## Impact

- New config field: `aureka.config.HotkeyConfig.topic: str = ""`.
- Modified files: `aureka/llm.py` (prompt builder), `aureka/config.py` (new field), `aureka/__main__.py` (CLI flag), `aureka/ui.py` (form field + helper text), `aureka/client.py` and/or `aureka/daemon.py` (passthrough).
- No new dependencies, no protocol break — clients that don't supply a topic see the same behavior as today.
