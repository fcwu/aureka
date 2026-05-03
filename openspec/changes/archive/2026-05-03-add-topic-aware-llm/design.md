## Context

`aureka.llm` builds prompts in two streaming entry points: `llm_refine_stream` and `llm_translate_stream`. Both currently take only `(transcript, mode, lang)` — no domain hint. The daemon's `/voice` WebSocket relays voice sessions and forwards mode/lang to these functions. Adding a topic threads the same way, but the value source has three potential origins (most-specific wins): explicit `--topic` flag → live config → empty.

## Goals / Non-Goals

**Goals:**
- Single optional string influences refine / translate output without changing any other knob.
- Config-driven for daily use; CLI override for one-off invocations.
- Preserves byte-for-byte today's prompt when the topic is empty (regression-safe for existing tests).

**Non-Goals:**
- Multi-topic / topic libraries / per-language topics. Keep one string.
- Auto-detected topic (clustering recent transcripts). Out of scope.
- Different topic for refine vs translate. Same string for both modes.

## Decisions

### 1. Where the topic goes in the prompt

System message, leading sentence:

```
You are a transcription editor. The user is working on the topic of "ZFS storage administration". Preserve domain-specific terms verbatim where they appear in the original recording; do not translate jargon that has no canonical Chinese equivalent.
```

Refine mode appends this guidance; translate mode reuses the same line and adds language directives after.

**Why system message, not user message:** the topic is a long-lived hint, not a per-request instruction. Putting it in the system slot keeps it consistent across multi-turn sessions if we ever add them, and lets prompt caching (when supported by the backend) reuse the prefix.

### 2. Override precedence

```
CLI flag --topic   (one-off)
   ↓ falls back to
config.toml [hotkey].topic
   ↓ falls back to
"" (no-op, original prompt)
```

Resolved at the start of `cmd_type` and stamped onto the WebSocket session payload (`{type: "start", mode, lang, topic}`). Client doesn't keep mutable topic state — fresh resolution per session.

### 3. Daemon passthrough

`aureka/daemon.py` `/voice` handler reads the optional `topic` field from the start frame and passes it to the LLM helpers. Default-empty preserves wire compatibility with older clients.

## Risks / Trade-offs

- **Token budget eaten by topic** — adds ~20–40 tokens to every request. Acceptable; far smaller than `max_tokens`. No mitigation.
- **Long topic strings** — UI doesn't truncate; if user pastes a paragraph, the LLM may treat it as instructions. Document a soft 200-char guideline in the helper text. Don't enforce.
- **Mode mismatch** — topic mostly helps `refine`/`translate`. For `transcribe` the topic is unused; we still allow setting it (no-op) so the user doesn't have to clear it when switching modes.

## Migration Plan

Pure additive. No config migration needed: missing `[hotkey].topic` falls through to default `""`. No daemon API break: clients that never send `topic` keep working.
