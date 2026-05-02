"""Integration tests for daemon WS streaming mode.

Verifies that streaming=true triggers the VAD-segmented path and emits
partial transcripts with is_partial=true, while streaming=false (or absent)
preserves the legacy buffer behavior.
"""
import base64

import numpy as np
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

    from aureka import config as cfg_mod, asr as asr_mod, daemon as dmn_mod
    cfg_mod.reset_config()
    asr_mod._backend = None
    # Reset daemon's VAD-availability cache between tests
    dmn_mod._vad_available = None
    dmn_mod._vad_warned = False
    yield
    asr_mod._backend = None
    dmn_mod._vad_available = None


def _pcm(duration_s: float = 1.0) -> bytes:
    n = int(16000 * duration_s)
    return np.zeros(n, dtype=np.int16).tobytes()


def _run_session(app, *, streaming: bool, mode: str = "transcribe") -> list[dict]:
    msgs: list[dict] = []
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({
                "type": "start", "mode": mode, "lang": "zh",
                "streaming": streaming,
            })
            ws.send_json({"type": "chunk", "data": base64.b64encode(_pcm(0.5)).decode()})
            ws.send_json({"type": "end"})
            while True:
                msg = ws.receive_json()
                msgs.append(msg)
                if msg["type"] == "done":
                    break
    return msgs


def test_streaming_false_uses_buffer_path():
    """Backward-compat: streaming=false sends transcript without is_partial flag."""
    from aureka.daemon import app
    msgs = _run_session(app, streaming=False)
    transcripts = [m for m in msgs if m["type"] == "transcript"]
    assert all("is_partial" not in m for m in transcripts), \
        "buffer mode must not emit is_partial flag"
    assert msgs[-1]["type"] == "done"


def test_streaming_true_with_vad_unavailable_falls_back_silently(monkeypatch):
    """If silero-vad isn't loadable, streaming=true silently uses buffer path."""
    from aureka import daemon as dmn_mod
    dmn_mod._vad_available = False  # simulate unavailable
    from aureka.daemon import app
    msgs = _run_session(app, streaming=True)
    # Same observable behavior as buffer path
    transcripts = [m for m in msgs if m["type"] == "transcript"]
    assert all("is_partial" not in m for m in transcripts)
    assert msgs[-1]["type"] == "done"


def test_streaming_true_with_vad_available_uses_streaming_path(monkeypatch):
    """When VAD is available and we feed a segment-end, partial transcript should appear."""
    from aureka import daemon as dmn_mod
    # Force VAD available
    dmn_mod._vad_available = True

    # Replace VadSegmenter so we don't depend on real silero-vad model behavior
    class FakeSegmenter:
        def __init__(self):
            self._fed = False
        def feed(self, pcm):
            # Always return one segment per feed call
            import numpy as np
            return [np.zeros(8000, dtype=np.float32)]
        def flush(self):
            return []

    import aureka.vad as vad_mod
    monkeypatch.setattr(vad_mod, "VadSegmenter", FakeSegmenter)

    from aureka.daemon import app
    msgs = _run_session(app, streaming=True)
    partials = [m for m in msgs if m["type"] == "transcript" and m.get("is_partial")]
    assert len(partials) >= 1, f"expected partial transcript(s), got: {msgs}"
    assert msgs[-1]["type"] == "done"
