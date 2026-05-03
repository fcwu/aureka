## 1. Diarization module

- [x] 1.1 Add `[diarize]` extra in `pyproject.toml`: `resemblyzer>=0.1`, `spectralcluster>=0.2`, `librosa>=0.10`
- [x] 1.2 Create `aureka/diarize.py` with `diarize(audio_path, segments, num_speakers=None) -> list[str]`
- [x] 1.3 Per-segment embedding via `resemblyzer.VoiceEncoder.embed_utterance` (load model once, reuse)
- [x] 1.4 Cluster with `spectralcluster.SpectralClusterer`; clamp auto range to `[2, 8]`
- [x] 1.5 Map raw cluster ids to `S1` / `S2` / … based on first-appearance order in segment list
- [x] 1.6 Skip segments < 0.6 s when forming embeddings; assign nearest-neighbor label after clustering

## 2. Pipeline integration

- [x] 2.1 Modify `aureka/pipeline.py` to optionally call `diarize()` after ASR; attach `speaker` to each segment dict
- [x] 2.2 Pass speaker labels into Markdown / SRT / VTT writers; respect `--no-speaker-labels`
- [x] 2.3 Add `--diarize` / `--num-speakers` / `--no-speaker-labels` flags to `aureka process` subparser

## 3. HTML transcript writer

- [x] 3.1 Create `aureka/html_transcript.py` exporting `write_html(segments, audio_path, out_path, speakers_present: bool)`
- [x] 3.2 Compute waveform peaks (1024 columns, min/max per column) using librosa
- [x] 3.3 Render single self-contained HTML: `<audio>`, `<canvas>` waveform, segment list with timestamps + speaker color stripes
- [x] 3.4 Inline JS: click segment → seek; click waveform → seek + scroll into view; play → auto-highlight + auto-scroll (with lock toggle)
- [x] 3.5 Speaker color palette: 6 distinct colors, cycle with shade variation past 6
- [x] 3.6 If input is video, extract audio via ffmpeg to `<basename>.audio.m4a` (AAC, mono, 16 kHz)

## 4. model-management updates

- [x] 4.1 `model_registry()` adds `resemblyzer` key when `[diarize]` is importable; otherwise omits
- [x] 4.2 `model_status()` and `download_all()` handle the new key transparently
- [x] 4.3 Lazy-load: registry computed on each call (cheap), so toggling extra installation post-hoc works without restart

## 5. Settings UI

- [x] 5.1 Models tab dynamically renders resemblyzer row only when registry includes it
- [x] 5.2 Polling / progress bar UX shared with existing models

## 6. CLI

- [x] 6.1 `--format html` accepted (depends on subtitle/format proposal landing first; coordinate or duplicate)
- [x] 6.2 `--diarize` / `--num-speakers` / `--no-speaker-labels` registered
- [x] 6.3 `cmd_process` orchestrates the new code paths

## 7. Documentation

- [x] 7.1 README: new "講者辨識" section with example commands and screenshot of HTML player (placeholder)
- [x] 7.2 README: add `--diarize` / `--num-speakers` to the CLI block
- [x] 7.3 Note in README that `[diarize]` is a one-time `pip install 'aureka[diarize]'`

## 8. Tests

- [x] 8.1 `tests/test_diarize_unit.py`: with mocked encoder + clusterer, verify label sequence ordering and short-segment skip behavior
- [x] 8.2 `tests/test_pipeline.py`: `--diarize` attaches `speaker` to segments; `--no-speaker-labels` strips text prefix but keeps html colors
- [x] 8.3 `tests/test_html_transcript_unit.py`: write_html produces a single file; embedded JS evaluates (smoke test); waveform peaks JSON length == 1024
- [x] 8.4 `tests/test_models_unit.py`: registry with / without `[diarize]` extra
- [x] 8.5 `tests/test_main_cli_unit.py`: new flags wired

## 9. Manual verification

- [x] 9.1 Run `aureka process samples/two_speaker_meeting.mp3 --diarize --format html` and confirm two distinct colors render
- [x] 9.2 Open the generated HTML in Safari + Chrome; confirm seek + scroll behaviors match
