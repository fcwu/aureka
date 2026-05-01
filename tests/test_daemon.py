"""Integration tests for daemon HTTP and WebSocket endpoints."""
import asyncio
import base64
import json
import os

import httpx
import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def daemon_test_env(monkeypatch, mock_llm_server, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'[llm]\nbase_url = "{mock_llm_server}/v1"\napi_key = "mock"\nmodel = "mock-model"\n'
        f'[vlm]\nbase_url = "{mock_llm_server}/v1"\napi_key = "mock"\nmodel = "mock-vision-model"\n'
    )
    monkeypatch.setenv("AUREKA_CONFIG", str(config))
    monkeypatch.setenv("AUREKA_TEST_MODE", "1")

    from aureka import config as cfg_mod, asr as asr_mod, llm as llm_mod
    cfg_mod.reset_config()
    asr_mod._backend = None
    llm_mod._llm_client = None
    llm_mod._vlm_client = None
    yield
    asr_mod._backend = None
    llm_mod._llm_client = None
    llm_mod._vlm_client = None


def _make_pcm_bytes(duration_s: float = 0.1, sample_rate: int = 16000) -> bytes:
    import numpy as np
    n = int(sample_rate * duration_s)
    return (np.zeros(n, dtype=np.int16)).tobytes()


def test_health():
    from aureka.daemon import app
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def _ws_session(app, mode: str, pcm: bytes) -> list[dict]:
    """Run a WS voice session and collect all server messages."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "mode": mode, "lang": "zh"})
            ws.send_json({
                "type": "chunk",
                "data": base64.b64encode(pcm).decode(),
            })
            ws.send_json({"type": "end"})

            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "done":
                    break
    return messages


def test_websocket_transcribe():
    from aureka.daemon import app
    pcm = _make_pcm_bytes(0.2)
    messages = _ws_session(app, "transcribe", pcm)
    types = [m["type"] for m in messages]
    assert "transcript" in types
    assert "done" in types


def test_websocket_refine():
    from aureka.daemon import app
    pcm = _make_pcm_bytes(0.2)
    messages = _ws_session(app, "refine", pcm)
    types = [m["type"] for m in messages]
    assert "transcript" in types
    assert "refined" in types
    assert "done" in types
