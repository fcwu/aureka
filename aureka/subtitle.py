"""SRT and WebVTT subtitle writers.

Tiny stateless module: given a list of `(t_start, t_end, text)` segments —
the same shape `aureka.pipeline` already produces for the Markdown writer —
emit a .srt or .vtt file. No deps beyond stdlib.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence


Segment = tuple[float, float, str]


def _ts_srt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:  # rounded up to next second
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(seconds: float) -> str:
    return _ts_srt(seconds).replace(",", ".")


def _ensure_segments(segments: Iterable[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for s in segments:
        t0, t1, text = s[0], s[1], s[2]
        out.append((float(t0), float(t1), str(text).strip()))
    return out


def write_srt(segments: Iterable[Segment], path: str | Path) -> Path:
    """Write SubRip Subtitle (.srt) file. Uses 1-based index, comma-decimal ms.

    Empty-text segments are silently dropped; cue numbering reflects only the
    cues actually emitted (no gaps). Trailing blank line is canonical SRT."""
    path = Path(path)
    items = _ensure_segments(segments)
    parts: list[str] = []
    idx = 0
    for t0, t1, text in items:
        if not text:
            continue
        idx += 1
        parts.append(f"{idx}\n{_ts_srt(t0)} --> {_ts_srt(t1)}\n{text}\n")
    body = "\n".join(parts)
    path.write_text(body, encoding="utf-8")
    return path


def write_vtt(segments: Iterable[Segment], path: str | Path) -> Path:
    """Write WebVTT (.vtt) file with `WEBVTT` header and dot-decimal ms."""
    path = Path(path)
    items = _ensure_segments(segments)
    parts: list[str] = ["WEBVTT\n"]
    for t0, t1, text in items:
        if not text:
            continue
        parts.append(f"{_ts_vtt(t0)} --> {_ts_vtt(t1)}\n{text}\n")
    body = "\n".join(parts)
    path.write_text(body, encoding="utf-8")
    return path


# Format set parser: "md,srt,all" → set
ALL_FORMATS = {"md", "srt", "vtt"}


def parse_formats(spec: str) -> set[str]:
    """Parse a comma list (or 'all') into a normalized set of format names."""
    spec = (spec or "").strip().lower()
    if not spec:
        return {"md"}
    if spec == "all":
        return set(ALL_FORMATS)
    out: set[str] = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok not in ALL_FORMATS:
            raise ValueError(f"Unknown format '{tok}'. Valid: md, srt, vtt, all")
        out.add(tok)
    return out or {"md"}
