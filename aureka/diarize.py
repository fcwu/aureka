"""Speaker diarization using resemblyzer + spectralcluster (offline).

Lazy-imports the heavy deps so the module is safe to import without the
`[diarize]` extra installed; only `diarize()` actually calls into the
ML libraries. Returns one speaker label per input segment (`"S1"`, `"S2"`...),
ordered by first appearance so re-runs against the same input are stable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence


MIN_SEGMENT_SECONDS = 0.6
MIN_AUTO_SPEAKERS = 2
MAX_AUTO_SPEAKERS = 8


def _require_extras() -> tuple:
    """Return (VoiceEncoder, SpectralClusterer, librosa) or raise SystemExit
    with a clear install hint when the [diarize] extra isn't installed."""
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "Speaker diarization requires the [diarize] extra:\n"
            "  pip install 'aureka[diarize]'"
        ) from e
    try:
        from spectralcluster import SpectralClusterer
    except ImportError as e:
        raise SystemExit(
            "spectralcluster missing despite resemblyzer present.\n"
            "  pip install spectralcluster"
        ) from e
    try:
        import librosa
    except ImportError as e:
        raise SystemExit(
            "librosa missing despite resemblyzer present.\n"
            "  pip install librosa"
        ) from e
    return VoiceEncoder, SpectralClusterer, librosa


def _label_in_first_appearance_order(raw_labels: Sequence[int]) -> list[str]:
    """Map cluster ids (0/1/2 in arbitrary order) to S1, S2, S3 ordered by
    the first time each id appears in the segment list. Stable across reruns."""
    seen: dict[int, str] = {}
    next_idx = 1
    out: list[str] = []
    for raw in raw_labels:
        if raw not in seen:
            seen[raw] = f"S{next_idx}"
            next_idx += 1
        out.append(seen[raw])
    return out


def diarize(
    audio_path: str | Path,
    segments: Iterable[tuple[float, float, str]],
    num_speakers: int | None = None,
) -> list[str]:
    """Return one speaker label per segment, fully offline.

    `segments` carries (t_start, t_end, text); only timestamps are used here.
    Short segments (< MIN_SEGMENT_SECONDS) are not embedded — they inherit the
    label of the nearest neighbor with an embedding so noisy short clips don't
    pull cluster centroids around.
    """
    audio_path = Path(audio_path)
    seg_list = [(float(t0), float(t1)) for t0, t1, _ in segments]
    if not seg_list:
        return []  # avoid loading the ML stack when there's nothing to do
    VoiceEncoder, SpectralClusterer, librosa = _require_extras()
    import numpy as np

    wav, sr = librosa.load(str(audio_path), sr=16000, mono=True)
    encoder = VoiceEncoder(verbose=False)

    embeddings: list[np.ndarray | None] = []
    for t0, t1 in seg_list:
        if t1 - t0 < MIN_SEGMENT_SECONDS:
            embeddings.append(None)
            continue
        clip = wav[int(t0 * sr): int(t1 * sr)]
        if len(clip) < int(MIN_SEGMENT_SECONDS * sr):
            embeddings.append(None)
            continue
        emb = encoder.embed_utterance(clip)
        embeddings.append(emb)

    real_idx = [i for i, e in enumerate(embeddings) if e is not None]
    if not real_idx:
        return ["S1"] * len(seg_list)

    real_emb = np.stack([embeddings[i] for i in real_idx])

    if num_speakers is not None:
        clusterer = SpectralClusterer(min_clusters=num_speakers, max_clusters=num_speakers)
    else:
        clusterer = SpectralClusterer(min_clusters=MIN_AUTO_SPEAKERS,
                                       max_clusters=MAX_AUTO_SPEAKERS)
    raw = list(clusterer.predict(real_emb))

    # Map embedded segments → label; nearest-neighbor for short segments.
    labels_by_idx: dict[int, int] = dict(zip(real_idx, raw))
    full_raw: list[int] = []
    for i in range(len(seg_list)):
        if i in labels_by_idx:
            full_raw.append(labels_by_idx[i])
            continue
        # Short segment: inherit label from nearest indexed neighbor.
        nearest = min(real_idx, key=lambda j: abs(j - i))
        full_raw.append(labels_by_idx[nearest])

    return _label_in_first_appearance_order(full_raw)
