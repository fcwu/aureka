"""Unit tests for aureka.models (model registry + pre-download helpers)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_registry_contains_required_keys():
    from aureka.models import MODEL_REGISTRY
    for key in ("kokoro", "faster-whisper", "thewhisper"):
        assert key in MODEL_REGISTRY
        assert "/" in MODEL_REGISTRY[key]


# ── _select_models ────────────────────────────────────────────────────────────

def test_select_models_cpu_excludes_thewhisper():
    from aureka import models
    with patch("aureka.device.resolve_device", return_value="cpu"):
        keys = models._select_models("cpu")
    assert keys == ["kokoro", "faster-whisper"]


def test_select_models_cuda_with_thewhisper():
    from aureka import models
    with patch("aureka.device.resolve_device", return_value="cuda"), \
         patch.object(models, "_thewhisper_available", return_value=True):
        keys = models._select_models("cuda")
    assert keys == ["kokoro", "faster-whisper", "thewhisper"]


def test_select_models_cuda_without_thewhisper():
    from aureka import models
    with patch("aureka.device.resolve_device", return_value="cuda"), \
         patch.object(models, "_thewhisper_available", return_value=False):
        keys = models._select_models("cuda")
    assert keys == ["kokoro", "faster-whisper"]


def test_select_models_mps_with_thewhisper():
    from aureka import models
    with patch("aureka.device.resolve_device", return_value="mps"), \
         patch.object(models, "_thewhisper_available", return_value=True):
        keys = models._select_models("mps")
    assert keys == ["kokoro", "faster-whisper", "thewhisper"]


# ── download_all ──────────────────────────────────────────────────────────────

def test_download_all_returns_paths_matching_selection(tmp_path):
    from aureka import models

    fake_paths = {
        "hexgrad/Kokoro-82M": str(tmp_path / "kokoro"),
        "Systran/faster-whisper-large-v3": str(tmp_path / "fw"),
    }

    def fake_snapshot_download(repo_id, **kwargs):
        return fake_paths[repo_id]

    with patch("aureka.device.resolve_device", return_value="cpu"), \
         patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download) as m:
        paths = models.download_all("cpu")

    assert m.call_count == 2
    assert paths == [Path(fake_paths["hexgrad/Kokoro-82M"]),
                     Path(fake_paths["Systran/faster-whisper-large-v3"])]


def test_download_all_fail_fast_stops_on_first_error():
    from aureka import models

    calls = {"n": 0}

    def fake_snapshot_download(repo_id, **kwargs):
        calls["n"] += 1
        raise OSError("network down")

    with patch("aureka.device.resolve_device", return_value="cpu"), \
         patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
        with pytest.raises(OSError):
            models.download_all("cpu")

    assert calls["n"] == 1, "should not attempt second download after first failure"


def test_download_all_gated_repo_hints_login():
    from aureka import models
    from huggingface_hub.utils import GatedRepoError

    fake_response = MagicMock()
    fake_response.headers = {"x-request-id": "test"}

    def fake_snapshot_download(repo_id, **kwargs):
        raise GatedRepoError("forbidden", response=fake_response)

    with patch("aureka.device.resolve_device", return_value="cpu"), \
         patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
        with pytest.raises(RuntimeError, match="huggingface-cli login"):
            models.download_all("cpu")
