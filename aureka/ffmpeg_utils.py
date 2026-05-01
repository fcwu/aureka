"""ffmpeg utilities for audio extraction and keyframe capture."""
import shutil
import subprocess
import tempfile
from pathlib import Path


SUPPORTED_FORMATS = {".mp4", ".mkv", ".mov", ".mp3", ".wav", ".m4a", ".webm", ".flac"}
AUDIO_ONLY_FORMATS = {".mp3", ".wav", ".m4a", ".flac"}


def _check_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit(
            "[fatal] ffmpeg not found. Install it:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS:         brew install ffmpeg\n"
            "  Fedora/RHEL:   sudo dnf install ffmpeg"
        )


def extract_audio(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Extract 16kHz mono WAV audio track from input file."""
    _check_ffmpeg()
    input_path = Path(input_path)
    if input_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {input_path.suffix}")

    if output_path is None:
        tmp = tempfile.mktemp(suffix=".wav")
        output_path = Path(tmp)
    else:
        output_path = Path(output_path)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-ar", "16000", "-ac", "1", "-f", "wav",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed:\n{result.stderr}")
    return output_path


def extract_keyframes(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    frame_interval: int = 30,
) -> list[tuple[float, Path]]:
    """Extract one JPEG frame every frame_interval seconds.

    Returns list of (timestamp_seconds, frame_path).
    Returns empty list for audio-only inputs.
    """
    input_path = Path(input_path)
    if input_path.suffix.lower() in AUDIO_ONLY_FORMATS:
        return []

    _check_ffmpeg()

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = str(output_dir / "frame_%06d.jpg")
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", f"fps=1/{frame_interval}",
        "-q:v", "2",
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg keyframe extraction failed:\n{result.stderr}")

    frames = sorted(output_dir.glob("frame_*.jpg"))
    return [(i * frame_interval, f) for i, f in enumerate(frames)]


def get_duration(input_path: str | Path) -> float:
    """Return media duration in seconds using ffprobe."""
    _check_ffmpeg()
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
