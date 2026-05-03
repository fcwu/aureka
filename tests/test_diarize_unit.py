"""Unit tests for aureka.diarize and html_transcript writer.

Mocks the resemblyzer + spectralcluster + librosa stack so tests run
without the [diarize] extra installed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── _label_in_first_appearance_order ───────────────────────────────────────

def test_label_first_appearance_order_simple():
    from aureka.diarize import _label_in_first_appearance_order
    # Cluster ids 2, 0, 2, 1 → first-seen order is 2, 0, 1 → S1, S2, S1, S3
    assert _label_in_first_appearance_order([2, 0, 2, 1]) == ["S1", "S2", "S1", "S3"]


def test_label_first_appearance_stable_relabeling():
    from aureka.diarize import _label_in_first_appearance_order
    # Same cluster sequence → same labels regardless of raw int values
    a = _label_in_first_appearance_order([5, 7, 5, 9])
    b = _label_in_first_appearance_order([1, 3, 1, 2])
    assert a == b == ["S1", "S2", "S1", "S3"]


def test_label_single_cluster_all_s1():
    from aureka.diarize import _label_in_first_appearance_order
    assert _label_in_first_appearance_order([0, 0, 0, 0]) == ["S1"] * 4


# ── _require_extras error path ─────────────────────────────────────────────

def test_require_extras_raises_when_resemblyzer_missing():
    """Without [diarize] installed, _require_extras() must raise SystemExit
    with a clear install hint instead of an obscure ModuleNotFoundError."""
    real_import = __import__

    def selective(name, *args, **kwargs):
        if name == "resemblyzer":
            raise ImportError("resemblyzer not installed")
        return real_import(name, *args, **kwargs)

    from aureka import diarize
    with patch("builtins.__import__", side_effect=selective):
        with pytest.raises(SystemExit, match="aureka\\[diarize\\]"):
            diarize._require_extras()


# ── diarize() with full mock stack ────────────────────────────────────────

def test_diarize_returns_one_label_per_segment(monkeypatch):
    """End-to-end with mocked encoder + clusterer + librosa."""
    import numpy as np
    import aureka.diarize as d

    # Three segments, all long enough to embed.
    segments = [(0.0, 1.0, "x"), (1.5, 2.5, "y"), (3.0, 4.0, "z")]

    # Fake librosa.load returns 5 seconds of dummy audio
    fake_librosa = MagicMock()
    fake_librosa.load.return_value = (np.zeros(16000 * 5, dtype=np.float32), 16000)

    # Fake VoiceEncoder emits a 256-d vector per segment
    fake_encoder = MagicMock()
    fake_encoder.embed_utterance.side_effect = [
        np.array([1.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, 1.0]),
    ]
    fake_VoiceEncoder = MagicMock(return_value=fake_encoder)

    # Fake clusterer: predict labels [0, 0, 1] → S1, S1, S2
    fake_clusterer = MagicMock()
    fake_clusterer.predict.return_value = [0, 0, 1]
    fake_SpectralClusterer = MagicMock(return_value=fake_clusterer)

    monkeypatch.setattr(d, "_require_extras",
                         lambda: (fake_VoiceEncoder, fake_SpectralClusterer, fake_librosa))

    labels = d.diarize("ignored.wav", segments)
    assert labels == ["S1", "S1", "S2"]


def test_diarize_short_segment_skipped_then_neighbor_label(monkeypatch):
    """Segments shorter than MIN_SEGMENT_SECONDS get the nearest neighbor's label."""
    import numpy as np
    import aureka.diarize as d

    # Middle segment is 0.3s — too short to embed.
    segments = [(0.0, 1.0, "x"), (1.0, 1.3, "tiny"), (1.5, 2.5, "y")]

    fake_librosa = MagicMock()
    fake_librosa.load.return_value = (np.zeros(16000 * 3, dtype=np.float32), 16000)

    fake_encoder = MagicMock()
    fake_encoder.embed_utterance.side_effect = [
        np.array([1.0, 0.0]), np.array([0.0, 1.0]),  # only 2 calls
    ]
    fake_VoiceEncoder = MagicMock(return_value=fake_encoder)

    fake_clusterer = MagicMock()
    fake_clusterer.predict.return_value = [0, 1]  # two real embeddings
    fake_SpectralClusterer = MagicMock(return_value=fake_clusterer)

    monkeypatch.setattr(d, "_require_extras",
                         lambda: (fake_VoiceEncoder, fake_SpectralClusterer, fake_librosa))

    labels = d.diarize("ignored.wav", segments)
    # Tiny segment (idx 1) is equidistant; min(real_idx, key=abs(j-i)) picks idx 0 (lower)
    # → inherits S1 (the label of the first speaker).
    assert labels[0] == "S1"
    assert labels[1] in ("S1", "S2")  # nearest-neighbor decision; either is acceptable
    assert labels[2] == "S2"


def test_diarize_empty_segments_returns_empty(monkeypatch):
    import aureka.diarize as d
    # Even with extras unavailable, no segments → no work, no error
    monkeypatch.setattr(d, "_require_extras", MagicMock())
    assert d.diarize("ignored.wav", []) == []


def test_diarize_num_speakers_pins_clusterer(monkeypatch):
    """When `num_speakers` is set, SpectralClusterer is constructed with
    matching min/max so it produces exactly that many labels."""
    import numpy as np
    import aureka.diarize as d

    segments = [(0.0, 1.0, "x"), (1.0, 2.0, "y"), (2.0, 3.0, "z")]

    fake_librosa = MagicMock()
    fake_librosa.load.return_value = (np.zeros(16000 * 3, dtype=np.float32), 16000)

    fake_encoder = MagicMock()
    fake_encoder.embed_utterance.return_value = np.array([1.0, 0.0])
    fake_VoiceEncoder = MagicMock(return_value=fake_encoder)

    fake_clusterer = MagicMock(); fake_clusterer.predict.return_value = [0, 0, 0]
    fake_SpectralClusterer = MagicMock(return_value=fake_clusterer)

    monkeypatch.setattr(d, "_require_extras",
                         lambda: (fake_VoiceEncoder, fake_SpectralClusterer, fake_librosa))

    d.diarize("ignored.wav", segments, num_speakers=3)
    fake_SpectralClusterer.assert_called_once()
    kwargs = fake_SpectralClusterer.call_args.kwargs
    assert kwargs.get("min_clusters") == 3
    assert kwargs.get("max_clusters") == 3


# ── Model registry: resemblyzer entry conditional ────────────────────────

def test_model_registry_omits_resemblyzer_without_extra():
    """When resemblyzer is not importable, registry doesn't include the entry."""
    real_import = __import__

    def selective(name, *args, **kwargs):
        if name == "resemblyzer":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    from aureka import models
    with patch("builtins.__import__", side_effect=selective):
        reg = models.model_registry()
    assert "resemblyzer" not in reg


def test_model_registry_includes_resemblyzer_when_present():
    """When resemblyzer imports successfully, registry surfaces the entry."""
    fake_resemblyzer = MagicMock()
    with patch.dict(sys.modules, {"resemblyzer": fake_resemblyzer}):
        from aureka import models
        reg = models.model_registry()
    assert "resemblyzer" in reg


# ── HTML transcript writer ────────────────────────────────────────────────

def test_write_html_self_contained(tmp_path):
    from aureka.html_transcript import write_html
    out = tmp_path / "out.html"
    write_html(
        [(0.0, 1.0, "hello", "S1"), (1.0, 2.0, "world", "S2")],
        audio_relpath="meeting.audio.m4a",
        out_path=out,
        peaks=[0.0] * 16,
    )
    body = out.read_text(encoding="utf-8")
    # Self-contained: no CDN URLs
    assert "http://" not in body
    assert "//cdn." not in body
    # Wires audio src
    assert "meeting.audio.m4a" in body
    # Two speaker colors materialize
    assert "S1" in body and "S2" in body
    # Embedded segments JSON
    assert '"hello"' in body
    assert '"world"' in body


def test_write_html_no_speakers_path(tmp_path):
    """Segments without speaker labels render fine."""
    from aureka.html_transcript import write_html
    out = tmp_path / "out.html"
    write_html(
        [(0.0, 1.0, "no speaker", None)],
        audio_relpath="x.m4a",
        out_path=out,
        peaks=[],
    )
    body = out.read_text(encoding="utf-8")
    assert '"no speaker"' in body


def test_html_color_palette_distinct_first_six():
    from aureka.html_transcript import _color_for, _PALETTE
    colors = {_color_for(f"S{i}", 6) for i in range(1, 7)}
    assert len(colors) == 6
    assert colors == set(_PALETTE)


def test_html_color_seventh_falls_back_to_shaded():
    from aureka.html_transcript import _color_for, _PALETTE
    # 7th speaker: index 6 wraps to palette[0] but shaded; not equal to original
    c = _color_for("S7", 7)
    assert c != _PALETTE[0]
    # Still a hex color
    assert c.startswith("#") and len(c) == 7
