"""Unit tests for aureka.models (model registry + pre-download helpers)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── model_registry ───────────────────────────────────────────────────────────

def test_registry_contains_required_keys():
    from aureka.models import model_registry
    reg = model_registry()
    assert set(reg.keys()) == {"kokoro", "faster-whisper"}
    for v in reg.values():
        assert "/" in v


def test_registry_faster_whisper_follows_config_default():
    from aureka.models import model_registry
    # default cfg.asr.model is "medium"
    reg = model_registry()
    assert reg["faster-whisper"] == "Systran/faster-whisper-medium"


def test_registry_faster_whisper_switches_with_config():
    from aureka import models, config as cfg_mod
    cfg_mod.reset_config()
    with patch.object(cfg_mod, "_cfg", None), \
         patch("aureka.config.load_config") as load:
        fake_cfg = cfg_mod.Config()
        fake_cfg.asr.model = "large-v3"
        load.return_value = fake_cfg
        cfg_mod._cfg = fake_cfg
        reg = models.model_registry()
    cfg_mod.reset_config()
    assert reg["faster-whisper"] == "Systran/faster-whisper-large-v3"


def test_select_models_returns_kokoro_and_faster_whisper():
    from aureka import models
    assert models._select_models() == ["kokoro", "faster-whisper"]


# ── download_all ──────────────────────────────────────────────────────────────

def test_download_all_returns_paths_matching_selection(tmp_path):
    from aureka import models

    fake_paths = {
        "hexgrad/Kokoro-82M": str(tmp_path / "kokoro"),
        "Systran/faster-whisper-medium": str(tmp_path / "fw"),
    }

    def fake_snapshot_download(repo_id, **kwargs):
        return fake_paths[repo_id]

    with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download) as m:
        paths = models.download_all("cpu")

    assert m.call_count == 2
    assert paths == [Path(fake_paths["hexgrad/Kokoro-82M"]),
                     Path(fake_paths["Systran/faster-whisper-medium"])]


def test_download_all_fail_fast_stops_on_first_error():
    from aureka import models
    calls = {"n": 0}

    def fake_snapshot_download(repo_id, **kwargs):
        calls["n"] += 1
        raise OSError("network down")

    with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
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

    with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
        with pytest.raises(RuntimeError, match="huggingface-cli login"):
            models.download_all("cpu")
