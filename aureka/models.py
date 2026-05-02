"""Model registry and pre-download helpers.

`aureka download` uses this module to fetch HuggingFace snapshots without
loading models into memory or spinning up GPU/MPS runtime.
"""
from __future__ import annotations

from pathlib import Path

MODEL_REGISTRY: dict[str, str] = {
    "kokoro": "hexgrad/Kokoro-82M",
    "faster-whisper": "Systran/faster-whisper-large-v3",
    "thewhisper": "thestage-ai/thewhisper-large-v3-turbo",
}


def _thewhisper_available() -> bool:
    try:
        import thestage_speechkit  # noqa: F401
        return True
    except ImportError:
        return False


def _select_models(device: str = "auto") -> list[str]:
    """Return model keys to download for the given device.

    Always includes Kokoro (TTS) and faster-whisper (universal ASR fallback).
    Adds TheWhisper only when device is cuda/mps AND thestage_speechkit is importable.
    """
    from aureka.device import resolve_device

    dev = resolve_device(device)
    keys = ["kokoro", "faster-whisper"]
    if dev in ("cuda", "mps") and _thewhisper_available():
        keys.append("thewhisper")
    return keys


def download_all(device: str = "auto") -> list[Path]:
    """Download model snapshots for the current environment.

    Returns the list of local snapshot paths in the same order as `_select_models`.
    Raises immediately on the first failure (fail-fast); does not continue downloading
    remaining models. For gated/missing repos, raises an error message hinting at
    `huggingface-cli login`.
    """
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

    keys = _select_models(device)
    paths: list[Path] = []
    for key in keys:
        repo_id = MODEL_REGISTRY[key]
        try:
            local_path = snapshot_download(repo_id=repo_id)
        except (GatedRepoError, RepositoryNotFoundError) as e:
            raise RuntimeError(
                f"Cannot access '{repo_id}' ({e.__class__.__name__}). "
                "If this is a gated repo, run `huggingface-cli login` and accept the model terms."
            ) from e
        paths.append(Path(local_path))
    return paths
