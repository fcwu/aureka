## Context

`aureka.pipeline` already produces a structured `[(t_start, t_end, text), ...]` segment stream from the ASR pass. Diarization slots in *between* ASR finalization and writer dispatch: it consumes the same audio file plus segment timestamps, returns a parallel `[label, ...]` list, and the writers absorb that as a new column.

`resemblyzer` is the same encoder used widely in the open-source community (umbrella around the GE2E loss model). It produces 256-d voice embeddings from raw waveform, no HF token needed. `spectralcluster` (Google) clusters those embeddings; both are pure-pip installable and small.

The HTML transcript needs to (a) play the source audio and (b) jump between transcript and waveform position. This is solved by `<audio>` element + a `<canvas>`-rendered waveform + a small piece of JS that maps timestamps to canvas pixels and back.

## Goals / Non-Goals

**Goals:**
- Diarization runs entirely offline and requires no HF token / account.
- Speaker labels survive into Markdown, SRT, VTT, and HTML outputs.
- HTML transcript is a single file (besides the audio extracted from the source) — emailable, viewable in any browser, no internet needed.
- Pipeline cost when diarization is *off* is unchanged (no new imports loaded).

**Non-Goals:**
- Real-time / streaming diarization. This is batch-only.
- Speaker identification (matching to known voices). Labels are anonymous `S1`, `S2`, …
- Replacing ASR. Diarization complements but doesn't change the ASR output.
- Cross-language voice matching tweaks. resemblyzer is language-agnostic enough; we don't tune it.

## Decisions

### 1. Diarization pipeline shape

```
audio.wav (mono 16k)  +  ASR segments [(t0, t1), ...]
        │
        ▼
resemblyzer.VoiceEncoder.embed_utterance per segment    ← per-segment embedding
        │
        ▼
spectralcluster.SpectralClusterer.predict(embeddings)   ← labels [0, 1, 0, 2, ...]
        │
        ▼
Map labels to S1, S2, S3 in order of first appearance
        │
        ▼
Attach to segments as `speaker` column
```

Cluster count: if `--num-speakers N` given, pin `min_clusters = max_clusters = N`. Otherwise let spectralcluster auto-pick from `[2, 8]` (typical meeting size) — clamped because unbounded clustering is unreliable.

### 2. resemblyzer weights via `model-management`

Add `"resemblyzer": "Comma-separated/voice-encoder"` (or whatever the upstream cache key is — verify) to the `model_registry()`. Lazy-loaded — only instantiated when `--diarize` is requested. Settings UI Models tab gets a third row that shares the same status / download UX as Kokoro and faster-whisper.

### 3. HTML transcript layout

Single self-contained file, no JS framework, no Tailwind. Hand-rolled because:
- ~150 LOC total
- Loaded from disk (file:// URLs); CDN deps mean it breaks offline
- The canvas waveform is the only "library-shaped" piece, and it's 60 LOC

Layout:

```
┌────────────────────────────────────────────────┐
│ <audio controls>                               │
│ <canvas id="waveform">  + speaker color stripe │
├────────────────────────────────────────────────┤
│ Segments scroll panel:                         │
│   [S1 timestamp] segment text  ← clickable     │
│   [S2 timestamp] segment text                  │
│   ...                                          │
└────────────────────────────────────────────────┘
```

Interactions:
- Click segment → audio seeks, segment highlights, waveform cursor moves.
- Click waveform → audio seeks, the segment containing that timestamp highlights and scrolls into view.
- Audio play → cursor advances, current segment auto-highlights, panel auto-scrolls (with a "lock scroll" toggle).

Speaker color palette: 6 distinct colors; if more than 6 speakers, the 7th wraps with a different shade for distinguishability. Colors chosen for ≥3:1 contrast against both light and dark themes (`prefers-color-scheme`).

### 4. Audio asset for HTML

If input is video, extract audio via ffmpeg to `<basename>.audio.m4a` (AAC 128 kbps, mono, 16 kHz) next to the HTML. If input is already audio, link directly. The HTML uses a relative `src` so the user can move the pair together.

Why m4a: small file size, ubiquitous browser support, ffmpeg can produce it from any input we accept.

### 5. Waveform peaks computed once

We compute peaks (min/max per pixel-column) at HTML write time, embed as a JSON array in the page (typically 1024–2048 floats — small). Browser canvas reads from the embedded array — no fetching, no CORS.

Resolution: target 1024 columns wide. For a 60-min recording that's ~3.5 sec/column, plenty for click-precision purposes.

### 6. Speaker labels in subtitle outputs

SRT / VTT cues prefix the text with `[S1] `, `[S2] `, etc. This is a non-standard convention but tools (DaVinci Resolve, Premiere) handle it cleanly. `--no-speaker-labels` strips the prefix for users who want clean translation tracks.

Markdown output uses the existing per-segment header style with the speaker as a soft heading: `**[00:01:23] S1:** segment text`.

## Risks / Trade-offs

- **resemblyzer upstream maintenance** — the project hasn't seen frequent updates. Mitigation: pin to a known-working version in `[diarize]` extra; if upstream goes stale, swap to an alternative encoder behind the same `aureka.diarize.embed_segments()` interface.
- **Spectral clustering brittleness on short segments** — embeddings on <1s utterances are noisy and may cluster wrong. Mitigation: skip segments shorter than 0.6s for clustering (assign to nearest neighbor's label) so the noise doesn't distort centroids.
- **HTML waveform is a custom mini-implementation** — could grow if we want fancier UX. Acceptable for now; if requirements grow we'll swap to wavesurfer.js (vendored).
- **Offline model download size** — resemblyzer adds ~17 MB to the install. Lazy-loaded behind the `[diarize]` extra; users who don't diarize don't pay.

## Migration Plan

Pure additive. Existing `aureka process video.mp4` keeps producing only `.md` (no diarization, no HTML). Users who want the new outputs opt in via flags. Tests must be added to confirm regression-free behavior of the no-flag path.

## Open Questions

- Should diarization labels be persistent across re-runs of the same file? (Today, S1/S2 ordering depends on which speaker speaks first in the segment list — re-runs are stable as long as segments don't move.) Likely fine; document the behavior.
- Should we expose a "merge speaker N → speaker M" UI in the HTML transcript? Out of scope for this round; track for a future polish.
