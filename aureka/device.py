"""Platform device detection and ASR backend selection."""


def resolve_device(preference: str = "auto") -> str:
    if preference != "auto":
        return preference
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def resolve_asr_backend(device: str) -> str:
    """TheWhisper preferred on NVIDIA/Apple Silicon; faster-whisper otherwise."""
    if device in ("cuda", "mps"):
        try:
            import thestage_speechkit  # noqa: F401
            return "thewhisper"
        except ImportError:
            pass
    return "faster-whisper"
