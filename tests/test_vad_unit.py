"""Unit tests for aureka.vad — VadSegmenter wrapper around silero-vad."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


def _mock_silero():
    """Return a (load, VADIterator) pair where the iterator yields canned events."""
    fake_model = MagicMock()

    class FakeIter:
        events: list[dict | None] = []
        cursor = 0

        def __init__(self, model, **kw):
            self.cursor = 0

        def __call__(self, window, return_seconds=False):
            if FakeIter.cursor < len(FakeIter.events):
                ev = FakeIter.events[FakeIter.cursor]
                FakeIter.cursor += 1
                return ev
            return None

        def reset_states(self):
            FakeIter.cursor = 0

    return MagicMock(return_value=fake_model), FakeIter


def test_vad_unavailable_when_silero_missing(monkeypatch):
    import sys
    from aureka.vad import VadUnavailable
    monkeypatch.setitem(sys.modules, "silero_vad", None)
    # Reimport to pick up the missing module
    import importlib, aureka.vad as vad_mod
    importlib.reload(vad_mod)
    with pytest.raises(vad_mod.VadUnavailable):
        vad_mod.VadSegmenter()
    # Restore so other tests can run
    sys.modules.pop("silero_vad", None)
    importlib.reload(vad_mod)


def test_segmenter_returns_segment_on_speech_end():
    """When VADIterator emits a start then an end, feed should return one segment."""
    load, FakeIter = _mock_silero()
    FakeIter.events = [
        {"start": 0},   # window 0
        None,           # window 1
        None,           # window 2
        {"end": 1024},  # window 3 (segment ends at sample 1024)
    ]
    with patch("silero_vad.load_silero_vad", load), \
         patch("silero_vad.VADIterator", FakeIter):
        import importlib, aureka.vad as vad_mod
        importlib.reload(vad_mod)
        seg = vad_mod.VadSegmenter()

        # 4 windows × 512 samples = 2048 samples total
        chunk = np.zeros(2048, dtype=np.int16)
        out = seg.feed(chunk)

    assert len(out) == 1
    assert len(out[0]) == 1024  # segment from sample 0 to 1024


def test_segmenter_flush_returns_open_speech():
    """If speech started but never ended, flush should return what's buffered."""
    load, FakeIter = _mock_silero()
    FakeIter.events = [
        {"start": 0},   # window 0
        None,           # window 1
    ]
    with patch("silero_vad.load_silero_vad", load), \
         patch("silero_vad.VADIterator", FakeIter):
        import importlib, aureka.vad as vad_mod
        importlib.reload(vad_mod)
        seg = vad_mod.VadSegmenter()
        seg.feed(np.zeros(1024, dtype=np.int16))  # 2 windows
        flushed = seg.flush()

    assert len(flushed) == 1
    assert len(flushed[0]) > 0  # tail from speech-start to end of buffer
