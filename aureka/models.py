"""Model registry and pre-download helpers.

`aureka download` uses this module to fetch HuggingFace snapshots without
loading models into memory or spinning up GPU/MPS runtime. The faster-whisper
repo_id is derived from `cfg.asr.model` so download and runtime stay in sync.
"""
from __future__ import annotations

from pathlib import Path


def model_registry() -> dict[str, str]:
    """Return mapping of logical model names to HuggingFace repo IDs.

    faster-whisper's repo follows `cfg.asr.model` so changing the config
    automatically targets the matching model on download.
    """
    from aureka.config import get_config
    cfg = get_config()
    return {
        "kokoro": "hexgrad/Kokoro-82M",
        "faster-whisper": f"Systran/faster-whisper-{cfg.asr.model}",
    }


def _select_models() -> list[str]:
    """Return model keys to download. Always Kokoro + faster-whisper."""
    return ["kokoro", "faster-whisper"]


def download_all(device: str = "auto") -> list[Path]:
    """Download model snapshots for the current environment.

    `device` parameter is accepted for CLI compatibility but does not affect
    selection (faster-whisper is the only ASR backend on all platforms).

    Returns the list of local snapshot paths in the same order as `_select_models`.
    Raises immediately on the first failure (fail-fast). For gated/missing repos,
    raises an error message hinting at `huggingface-cli login`.
    """
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

    registry = model_registry()
    keys = _select_models()
    paths: list[Path] = []
    for key in keys:
        repo_id = registry[key]
        try:
            local_path = snapshot_download(repo_id=repo_id)
        except (GatedRepoError, RepositoryNotFoundError) as e:
            raise RuntimeError(
                f"Cannot access '{repo_id}' ({e.__class__.__name__}). "
                "If this is a gated repo, run `huggingface-cli login` and accept the model terms."
            ) from e
        paths.append(Path(local_path))
    return paths
