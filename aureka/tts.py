"""TTS backend using Kokoro."""
import re

from aureka.config import get_config
from aureka.device import resolve_device

_pipeline = None


def load_tts(device: str = "auto"):
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    from kokoro import KPipeline
    cfg = get_config()
    dev = resolve_device(device if device != "auto" else cfg.tts.device)
    _pipeline = KPipeline(lang_code=cfg.tts.lang_code, device=dev)
    return _pipeline


def strip_markdown(text: str) -> str:
    """Remove YAML frontmatter and Markdown markup, returning plain text."""
    # Strip YAML frontmatter
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    # Remove headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove images (must come before links to avoid partial match)
    text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", text)
    # Remove links, keep text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)
    # Remove inline code
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove table separators
    text = re.sub(r"^\|[-| :]+\|$", "", text, flags=re.MULTILINE)
    # Clean up extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def synthesize(text: str, speed: float | None = None):
    """Run Kokoro on `text`, return (numpy float32 array, sample_rate) or (None, sr).

    speed: 1.0 = normal; <1 slower, >1 faster. None → use config.tts.speed.
    """
    import numpy as np
    pipeline = load_tts()
    cfg = get_config()
    spd = cfg.tts.speed if speed is None else speed
    collected = []
    for _, _, audio in pipeline(text, voice=cfg.tts.voice, speed=spd):
        collected.append(audio)
    if not collected:
        return None, 24000
    return np.concatenate(collected), 24000


def play_or_save(audio, sample_rate: int, output_path: str | None) -> None:
    if audio is None:
        return
    if output_path:
        import soundfile as sf
        sf.write(output_path, audio, sample_rate)
    else:
        import sounddevice as sd
        sd.play(audio, sample_rate)
        sd.wait()


def speak(text: str, output_path: str | None = None, speed: float | None = None) -> None:
    audio, sr = synthesize(text, speed=speed)
    play_or_save(audio, sr, output_path)


def speak_file(path: str, output_path: str | None = None, speed: float | None = None) -> None:
    text = open(path).read()
    text = strip_markdown(text)
    if text:
        speak(text, output_path, speed=speed)
