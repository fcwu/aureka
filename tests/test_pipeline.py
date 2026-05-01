"""Integration tests for batch pipeline using mock ASR and mock LLM."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def use_mock_llm_and_asr(mock_llm_server, monkeypatch, tmp_path, silence_wav):
    config = tmp_path / "config.toml"
    config.write_text(
        f'[llm]\nbase_url = "{mock_llm_server}/v1"\napi_key = "mock"\nmodel = "mock-model"\n'
        f'[vlm]\nbase_url = "{mock_llm_server}/v1"\napi_key = "mock"\nmodel = "mock-vision-model"\n'
    )
    monkeypatch.setenv("AUREKA_CONFIG", str(config))
    monkeypatch.setenv("AUREKA_TEST_MODE", "1")

    from aureka import config as cfg_mod, llm as llm_mod, asr as asr_mod
    cfg_mod.reset_config()
    llm_mod._llm_client = None
    llm_mod._vlm_client = None
    asr_mod._backend = None
    yield
    llm_mod._llm_client = None
    llm_mod._vlm_client = None
    asr_mod._backend = None


def test_pipeline_audio_only(tmp_path, silence_wav):
    from aureka.pipeline import run_pipeline

    out = run_pipeline(
        silence_wav,
        device="cpu",
        frame_interval=30,
        output_dir=tmp_path / "output",
        check_vlm=False,
    )
    assert out.exists()
    content = out.read_text()
    assert "---" in content
    assert "## 摘要" in content
    assert "## 原始轉錄" in content


def test_pipeline_output_naming(tmp_path, silence_wav):
    from aureka.pipeline import run_pipeline
    from datetime import datetime

    out = run_pipeline(
        silence_wav,
        device="cpu",
        output_dir=tmp_path / "output",
        check_vlm=False,
    )
    date_prefix = datetime.now().strftime("%Y%m%d")
    assert out.name.startswith(date_prefix)
    assert out.suffix == ".md"


def test_pipeline_unsupported_format(tmp_path):
    from aureka.pipeline import run_pipeline

    bad_file = tmp_path / "note.txt"
    bad_file.write_text("hello")

    with pytest.raises(ValueError, match="Unsupported format"):
        run_pipeline(bad_file, check_vlm=False)
