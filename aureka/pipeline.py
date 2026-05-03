"""Batch pipeline: video/audio → structured Markdown."""
import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from aureka import asr, ffmpeg_utils, formatter, llm


def run_pipeline(
    input_path: str | Path,
    device: str = "auto",
    frame_interval: int = 30,
    output_dir: str | Path = "output",
    check_vlm: bool = True,
    formats: set[str] | None = None,
    diarize: bool = False,
    num_speakers: int | None = None,
    speaker_labels_in_text: bool = True,
) -> Path:
    input_path = Path(input_path)
    if input_path.suffix.lower() not in ffmpeg_utils.SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {input_path.suffix}")

    if check_vlm and os.environ.get("AUREKA_TEST_MODE") != "1":
        llm.check_vlm_supports_vision()

    print(f"[1/5] Extracting audio from {input_path.name} ...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Skip ffmpeg for WAV inputs that are already 16kHz mono
        if input_path.suffix.lower() == ".wav":
            audio_path = input_path
        else:
            audio_path = ffmpeg_utils.extract_audio(input_path, Path(tmpdir) / "audio.wav")
        duration = 0.0
        try:
            duration = ffmpeg_utils.get_duration(input_path)
        except SystemExit:
            pass  # ffmpeg/ffprobe not available; duration unknown

        print(f"[2/5] Extracting keyframes (every {frame_interval}s) ...")
        frames = ffmpeg_utils.extract_keyframes(input_path, Path(tmpdir) / "frames", frame_interval)

        print(f"[3/5] Loading ASR model ...", flush=True)
        asr.load_asr(device=device)
        audio_data, sample_rate = sf.read(str(audio_path), dtype="float32")
        if audio_data.ndim > 1:
            audio_data = audio_data[:, 0]
        print(f"[3/5] Transcribing ({len(audio_data) / sample_rate:.0f}s audio) ...", flush=True)
        segments = []
        for seg in asr.transcribe(audio_data, sample_rate):
            m, s = divmod(int(seg.start), 60)
            print(f"  [{m:02d}:{s:02d}] {seg.text.strip()}", flush=True)
            segments.append(seg)

        print(f"[4/5] Describing frames with VLM ({len(frames)} frames) ...")
        frame_descriptions: list[tuple[float, str]] = []
        for ts, frame_path in frames:
            try:
                desc = llm.describe_frame(str(frame_path))
                frame_descriptions.append((ts, desc))
            except Exception as e:
                frame_descriptions.append((ts, f"[描述失敗: {e}]"))

        print(f"[5/5] Generating summary with LLM ...")
        transcript_text = " ".join(s.text for s in segments)
        desc_texts = [d for _, d in frame_descriptions]
        summary = llm.summarize_transcript(transcript_text, desc_texts)

        out_path = formatter.output_path(input_path, output_dir)
        formats = formats or {"md"}

        speaker_labels: list[str] | None = None
        if diarize:
            print(f"[diarize] running speaker diarization "
                  f"(num_speakers={num_speakers or 'auto'}) ...", flush=True)
            from aureka import diarize as diarize_mod
            speaker_labels = diarize_mod.diarize(
                str(audio_path),
                [(s.start, s.end, s.text) for s in segments],
                num_speakers=num_speakers,
            )
            print(f"[diarize] detected {len(set(speaker_labels))} speakers", flush=True)

        # Build (t0, t1, text, speaker?) tuples used by SRT/VTT/HTML.
        rich_tuples = [
            (s.start, s.end,
             (f"[{speaker_labels[i]}] " if (speaker_labels and speaker_labels_in_text) else "") + s.text,
             speaker_labels[i] if speaker_labels else None)
            for i, s in enumerate(segments)
        ]

        if "md" in formats:
            content = formatter.format_output(segments, frame_descriptions, summary, input_path, duration)
            out_path.write_text(content, encoding="utf-8")
            print(f"Output: {out_path}")
        if "srt" in formats or "vtt" in formats:
            from aureka import subtitle
            seg_tuples = [(t0, t1, text) for t0, t1, text, _ in rich_tuples]
            if "srt" in formats:
                srt_path = out_path.with_suffix(".srt")
                subtitle.write_srt(seg_tuples, srt_path)
                print(f"Output: {srt_path}")
            if "vtt" in formats:
                vtt_path = out_path.with_suffix(".vtt")
                subtitle.write_vtt(seg_tuples, vtt_path)
                print(f"Output: {vtt_path}")
        if "html" in formats:
            from aureka import html_transcript
            html_path = out_path.with_suffix(".html")
            audio_rel = Path(audio_path).name
            try:
                peaks = html_transcript.compute_peaks(audio_path)
            except SystemExit:
                peaks = []
            html_transcript.write_html(
                rich_tuples, audio_relpath=audio_rel, out_path=html_path,
                peaks=peaks, title=Path(input_path).stem,
            )
            print(f"Output: {html_path}")

    return out_path
