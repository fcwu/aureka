"""Model registry and pre-download helpers.

`aureka download` uses this module to fetch HuggingFace snapshots without
loading models into memory or spinning up GPU/MPS runtime. The faster-whisper
repo_id is derived from `cfg.asr.model` so download and runtime stay in sync.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


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


def download_all(
    device: str = "auto",
    progress: Callable[[dict], None] | None = None,
    keys: list[str] | None = None,
) -> list[Path]:
    """Download model snapshots for the current environment.

    `device` parameter is accepted for CLI compatibility but does not affect
    selection (faster-whisper is the only ASR backend on all platforms).

    `progress`, when provided, is invoked at each phase transition with a dict
    containing at least `phase` (`"start" | "done" | "error"`), `repo_key`,
    `repo_id`, and on error `error: str`. Callers using this for UI can poll
    a separate state dict; the callback itself is synchronous.

    `keys` lets callers narrow the download to a subset of registry entries
    (used by the settings UI's per-row Download button). Default is all.

    Returns the list of local snapshot paths in the same order as `keys`.
    Raises immediately on the first failure (fail-fast). For gated/missing repos,
    raises an error message hinting at `huggingface-cli login`.
    """
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

    registry = model_registry()
    selected = keys if keys is not None else _select_models()
    paths: list[Path] = []
    for key in selected:
        repo_id = registry[key]
        if progress:
            progress({"phase": "start", "repo_key": key, "repo_id": repo_id})
        try:
            local_path = snapshot_download(repo_id=repo_id)
        except (GatedRepoError, RepositoryNotFoundError) as e:
            err = (
                f"Cannot access '{repo_id}' ({e.__class__.__name__}). "
                "If this is a gated repo, run `huggingface-cli login` and accept the model terms."
            )
            if progress:
                progress({"phase": "error", "repo_key": key, "repo_id": repo_id, "error": err})
            raise RuntimeError(err) from e
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if progress:
                progress({"phase": "error", "repo_key": key, "repo_id": repo_id, "error": err})
            raise
        paths.append(Path(local_path))
        if progress:
            progress({"phase": "done", "repo_key": key, "repo_id": repo_id, "path": str(local_path)})
    return paths


def model_status() -> dict[str, dict]:
    """Return per-model download state without triggering any downloads.

    Reads HuggingFace's local cache via `scan_cache_dir`. Each entry returned
    is `{"repo_id": str, "downloaded": bool, "size_bytes": int,
    "snapshot_path": str | None}`.
    """
    registry = model_registry()
    out: dict[str, dict] = {
        key: {
            "repo_id": repo_id,
            "downloaded": False,
            "size_bytes": 0,
            "snapshot_path": None,
        }
        for key, repo_id in registry.items()
    }
    try:
        from huggingface_hub import scan_cache_dir
    except ImportError:
        return out

    try:
        cache = scan_cache_dir()
    except Exception:
        return out

    by_repo = {repo.repo_id: repo for repo in cache.repos}
    for key, repo_id in registry.items():
        repo = by_repo.get(repo_id)
        if repo is None or not repo.revisions:
            continue
        # Pick the most recently modified revision as the canonical snapshot
        rev = max(repo.revisions, key=lambda r: r.last_modified)
        out[key]["downloaded"] = True
        out[key]["size_bytes"] = int(repo.size_on_disk)
        out[key]["snapshot_path"] = str(rev.snapshot_path)
    return out
