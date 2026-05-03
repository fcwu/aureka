## Why

Multi-speaker recordings (interviews, group meetings, podcasts) become substantially more useful when the transcript labels who said what. The competitor (`jt-live-whisper`) does this with **resemblyzer + spectralcluster** — a lightweight, fully-offline approach that avoids the HuggingFace token / license hassle of `pyannote.audio`. Pairing the diarized transcript with an **interactive HTML player** (waveform + click-to-jump) turns the batch pipeline from a one-shot transcription into a usable review tool.

These two land together because they are most valuable together: speaker labels without timestamps to navigate are hard to verify, and an HTML player without speaker labels just plays text. As one combined change they share a single new capability spec, one round of UI integration, and one set of tests.

## What Changes

- New optional speaker-diarization step in the batch pipeline:
  - `aureka process video.mp4 --diarize` enables it; off by default.
  - `--num-speakers N` overrides automatic speaker count detection.
  - Each output segment gains a `speaker: str` field (e.g. `"S1"`, `"S2"`).
- Markdown / SRT / VTT writers gain a speaker prefix per segment when diarization ran (e.g. `[S1] 今天天氣很好`); when the user wants only-text outputs, `--no-speaker-labels` strips them.
- New HTML transcript writer:
  - Self-contained `.html` next to the source media file.
  - Embedded audio player (audio extracted from the source via ffmpeg if input is video).
  - Waveform thumbnail (`<canvas>` rendered from the audio peaks data we compute once).
  - Click any segment / waveform position to seek; the corresponding segment scrolls into view and highlights.
  - Speaker labels color-coded; the same color appears next to the segment and as a stripe over the waveform region for that speaker's utterances.
- Settings UI Models tab adds the resemblyzer voice-encoder model as a third trackable artifact (auto-download on first diarize run; status surfaced like Kokoro / faster-whisper).

## Capabilities

### New Capabilities
- `speaker-diarization`: extract per-segment speaker labels from a media file using resemblyzer voice embeddings + spectral clustering. Pluggable speaker count (auto / explicit).

### Modified Capabilities
- `batch-pipeline`: optionally run diarization, attach speaker labels to segments, emit a new HTML transcript writer alongside Markdown / SRT / VTT.
- `model-management`: registry covers the resemblyzer voice-encoder weights so `aureka download` / Models tab pre-fetches and reports it.
- `cli`: `aureka process` accepts `--diarize`, `--num-speakers N`, `--no-speaker-labels`.
- `settings-ui`: Models tab lists the resemblyzer model status and download.

## Impact

- New `[diarize]` extra in `pyproject.toml`: `resemblyzer>=0.1`, `spectralcluster>=0.2`, `librosa>=0.10` (for audio loading / peaks).
- New files: `aureka/diarize.py`, `aureka/html_transcript.py`.
- Modified: `aureka/pipeline.py`, `aureka/models.py`, `aureka/__main__.py`, `aureka/ui.py`, `aureka/subtitle.py` (speaker-prefix support).
- HTML output is fully offline (no CDN); waveform JS is ~5 KB hand-rolled `<canvas>` code, no library.
- One-time download for resemblyzer weights (~17 MB).
