"""Shared pytest fixtures."""
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

# Ensure test mode is set for all tests unless explicitly overridden
os.environ.setdefault("AUREKA_TEST_MODE", "1")

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_CONFIG = Path(__file__).parent / "config.test.toml"


@pytest.fixture(autouse=True)
def reset_aureka_config(monkeypatch):
    """Reset config singleton before each test."""
    from aureka import config as cfg_module
    cfg_module.reset_config()
    yield
    cfg_module.reset_config()


@pytest.fixture
def silence_wav() -> Path:
    path = FIXTURES_DIR / "silence-1s.wav"
    if not path.exists():
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "scripts" / "gen-test-audio.py")],
            check=True,
        )
    return path


@pytest.fixture
def test_config_path(tmp_path) -> Path:
    """Write a test config.toml pointing at mock LLM server."""
    config = tmp_path / "config.test.toml"
    config.write_text(
        '[llm]\nbase_url = "http://127.0.0.1:11435/v1"\napi_key = "mock"\nmodel = "mock-model"\n'
        '[vlm]\nbase_url = "http://127.0.0.1:11435/v1"\napi_key = "mock"\nmodel = "mock-vision-model"\n'
    )
    return config


@pytest.fixture(scope="session")
def mock_llm_server():
    """Start mock LLM server for the test session."""
    port = 11435
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "scripts" / "mock-llm-server.py"), "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(0.8)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait()
