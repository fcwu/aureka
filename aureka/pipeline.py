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
        content = formatter.format_output(segments, frame_descriptions, summary, input_path, duration)
        out_path.write_text(content, encoding="utf-8")

    print(f"Output: {out_path}")
    return out_path
