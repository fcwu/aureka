"""Configuration loader for config.toml."""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMConfig:
    base_url: str = "http://127.0.0.1:1234/v1"
    api_key: str = "lm-studio"
    model: str = "auto"


@dataclass
class VLMConfig:
    base_url: str = "http://127.0.0.1:1234/v1"
    api_key: str = "lm-studio"
    model: str = "auto"


@dataclass
class AsrConfig:
    # faster-whisper model name. Accepts standard sizes (tiny / base / small /
    # medium / large-v2 / large-v3 / large-v3-turbo), HuggingFace repo IDs, or
    # local paths. Default `medium` is a sweet spot between accuracy and speed.
    model: str = "medium"


@dataclass
class TTSConfig:
    voice: str = "zf_xiaobei"
    lang_code: str = "z"
    device: str = "auto"


@dataclass
class DaemonConfig:
    host: str = "127.0.0.1"
    port: int = 7777
    pid_file: str = "/tmp/aureka-daemon.pid"
    log_file: str = "/tmp/aureka-daemon.log"


@dataclass
class HotkeyConfig:
    trigger: str = "<ctrl>+<alt>+space"
    mode: str = "hold-to-record"
    input_mode: str = "refine"
    lang: str = "zh"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _apply(base, data: dict):
    """Apply dict values to a dataclass instance."""
    for k, v in data.items():
        if hasattr(base, k):
            setattr(base, k, v)


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        path = os.environ.get("AUREKA_CONFIG", "config.toml")
    path = Path(path)

    cfg = Config()
    if not path.exists():
        return cfg

    raw = _load_toml(path)
    if "llm" in raw:
        _apply(cfg.llm, raw["llm"])
    if "vlm" in raw:
        _apply(cfg.vlm, raw["vlm"])
    if "asr" in raw:
        _apply(cfg.asr, raw["asr"])
    if "tts" in raw:
        _apply(cfg.tts, raw["tts"])
    if "daemon" in raw:
        _apply(cfg.daemon, raw["daemon"])
    if "hotkey" in raw:
        _apply(cfg.hotkey, raw["hotkey"])
    return cfg


# Global singleton — loaded lazily on first access
_cfg: Config | None = None


def get_config() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


def reset_config():
    """Reset global config (for tests)."""
    global _cfg
    _cfg = None
