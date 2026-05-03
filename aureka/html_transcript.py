"""Self-contained HTML transcript with embedded audio + canvas waveform.

No external CDN, no JS framework. Everything inlined. The waveform peaks
are computed once at write time and embedded as a JSON array; the canvas
draws them at load and a small JS interaction layer maps clicks ↔ time.

Speaker colors come from a fixed 6-color palette plus a shading fallback
past 6.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable


# Colorblind-friendly palette with high-contrast against light/dark themes.
_PALETTE = [
    "#3b82f6", "#ef4444", "#10b981", "#f59e0b",
    "#8b5cf6", "#ec4899",
]
_PEAK_COLUMNS = 1024


def _color_for(label: str, total_known: int) -> str:
    """Map S1/S2/... to one of the palette colors. Repeats with a darker
    shade once we exceed the palette length."""
    try:
        idx = int(label.lstrip("Ss")) - 1
    except ValueError:
        idx = abs(hash(label)) % len(_PALETTE)
    if idx < len(_PALETTE):
        return _PALETTE[idx]
    # Darken every 6 to give a distinguishable fallback.
    base = _PALETTE[idx % len(_PALETTE)]
    return _shade(base, factor=max(0.5, 1 - 0.15 * (idx // len(_PALETTE))))


def _shade(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def compute_peaks(audio_path: str | Path, columns: int = _PEAK_COLUMNS) -> list[float]:
    """Reduce the audio file to `columns` peak amplitudes for the waveform.

    Lazy-imports librosa so this module loads without the [diarize] extra.
    """
    try:
        import librosa
        import numpy as np
    except ImportError as e:
        raise SystemExit(
            "compute_peaks() needs librosa (ships with the [diarize] extra)."
        ) from e
    wav, sr = librosa.load(str(audio_path), sr=16000, mono=True)
    if len(wav) == 0:
        return [0.0] * columns
    chunks = np.array_split(wav, columns)
    peaks = [float(np.max(np.abs(c))) if len(c) else 0.0 for c in chunks]
    return peaks


def write_html(
    segments: Iterable[tuple[float, float, str, str | None]],
    audio_relpath: str,
    out_path: str | Path,
    peaks: list[float] | None = None,
    title: str = "Aureka Transcript",
) -> Path:
    """Write a self-contained HTML transcript.

    `segments`: iterable of (t_start, t_end, text, speaker_label_or_None).
    `audio_relpath`: relative path the <audio> element should `src` to.
    `peaks`: optional pre-computed peak array; if None, the canvas just
             renders silence (caller should pre-compute via `compute_peaks`).
    """
    out_path = Path(out_path)
    seg_list = list(segments)
    speaker_set = sorted({s for *_, s in seg_list if s})
    color_map = {s: _color_for(s, len(speaker_set)) for s in speaker_set}

    # Build the segments JSON the JS layer consumes.
    json_segments = [
        {
            "t0": float(t0),
            "t1": float(t1),
            "text": str(text),
            "speaker": str(spk) if spk else None,
            "color": color_map.get(spk, "") if spk else "",
        }
        for t0, t1, text, spk in seg_list
    ]
    peaks_json = json.dumps(peaks or [])
    segs_json = json.dumps(json_segments, ensure_ascii=False)

    body = _TEMPLATE.format(
        title=html.escape(title),
        audio_relpath=html.escape(audio_relpath),
        peaks_json=peaks_json,
        segs_json=segs_json,
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; --bg: #fafafa; --fg: #111; --muted: #777; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #0f0f10; --fg: #e5e5e5; --muted: #aaa; }}
  }}
  body {{ background: var(--bg); color: var(--fg); font: 14px -apple-system, "Segoe UI", system-ui; margin: 0; padding: 16px; }}
  header {{ position: sticky; top: 0; background: var(--bg); padding-bottom: 8px; z-index: 1; }}
  audio {{ width: 100%; margin: 6px 0; }}
  canvas#waveform {{ display: block; width: 100%; height: 80px; cursor: pointer; background: rgba(128,128,128,0.08); border-radius: 6px; }}
  .controls {{ display: flex; gap: 8px; align-items: center; margin: 8px 0 12px; font-size: 12px; color: var(--muted); }}
  .controls label {{ display: flex; gap: 4px; align-items: center; }}
  .seg {{ display: grid; grid-template-columns: 90px 60px 1fr; gap: 12px; padding: 10px 8px; border-radius: 6px; cursor: pointer; }}
  .seg:hover {{ background: rgba(128,128,128,0.12); }}
  .seg.active {{ background: rgba(59,130,246,0.18); }}
  .seg .ts {{ font-family: ui-monospace, Menlo, monospace; color: var(--muted); font-size: 12px; padding-top: 2px; }}
  .seg .spk {{ font-weight: 600; padding-top: 2px; }}
  .seg .text {{ line-height: 1.5; }}
</style>
</head>
<body>
<header>
  <h1 style="margin:0 0 6px 0; font-size:15px;">{title}</h1>
  <audio id="audio" controls preload="metadata" src="{audio_relpath}"></audio>
  <canvas id="waveform" width="2048" height="160"></canvas>
  <div class="controls">
    <label><input type="checkbox" id="follow" checked> auto-scroll while playing</label>
  </div>
</header>
<main id="segments"></main>

<script>
const SEGMENTS = {segs_json};
const PEAKS = {peaks_json};

const audio = document.getElementById('audio');
const canvas = document.getElementById('waveform');
const ctx = canvas.getContext('2d');
const follow = document.getElementById('follow');
const root = document.getElementById('segments');

function fmtTs(t) {{
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${{m.toString().padStart(2, '0')}}:${{s.toString().padStart(2, '0')}}`;
}}

function renderSegments() {{
  SEGMENTS.forEach((seg, i) => {{
    const div = document.createElement('div');
    div.className = 'seg'; div.dataset.idx = i;
    const ts = document.createElement('div'); ts.className = 'ts'; ts.textContent = fmtTs(seg.t0);
    const spk = document.createElement('div'); spk.className = 'spk'; spk.textContent = seg.speaker || '';
    if (seg.color) spk.style.color = seg.color;
    const txt = document.createElement('div'); txt.className = 'text'; txt.textContent = seg.text;
    div.appendChild(ts); div.appendChild(spk); div.appendChild(txt);
    div.onclick = () => {{ audio.currentTime = seg.t0; audio.play(); }};
    root.appendChild(div);
  }});
}}

function drawWaveform() {{
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!PEAKS.length) return;
  const colW = W / PEAKS.length;
  // Speaker stripe (per-segment color block underlay)
  if (audio.duration) {{
    SEGMENTS.forEach(seg => {{
      if (!seg.color) return;
      const x0 = (seg.t0 / audio.duration) * W;
      const x1 = (seg.t1 / audio.duration) * W;
      ctx.fillStyle = seg.color + '33';
      ctx.fillRect(x0, 0, Math.max(1, x1 - x0), H);
    }});
  }}
  ctx.fillStyle = '#888';
  PEAKS.forEach((p, i) => {{
    const h = Math.max(1, p * H * 0.9);
    ctx.fillRect(i * colW, (H - h) / 2, Math.max(1, colW - 0.5), h);
  }});
  // Cursor
  if (audio.duration) {{
    const x = (audio.currentTime / audio.duration) * W;
    ctx.fillStyle = '#3b82f6';
    ctx.fillRect(x - 1, 0, 2, H);
  }}
}}

canvas.addEventListener('click', e => {{
  if (!audio.duration) return;
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const t = (x / rect.width) * audio.duration;
  audio.currentTime = t;
  // Find segment containing t
  const seg = SEGMENTS.findIndex(s => s.t0 <= t && t <= s.t1);
  if (seg >= 0) {{
    const el = root.children[seg];
    if (el && follow.checked) el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
  }}
}});

let activeIdx = -1;
audio.addEventListener('timeupdate', () => {{
  drawWaveform();
  const t = audio.currentTime;
  const idx = SEGMENTS.findIndex(s => s.t0 <= t && t <= s.t1);
  if (idx !== activeIdx) {{
    if (activeIdx >= 0) root.children[activeIdx]?.classList.remove('active');
    if (idx >= 0) {{
      const el = root.children[idx];
      el?.classList.add('active');
      if (follow.checked) el?.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
    }}
    activeIdx = idx;
  }}
}});
audio.addEventListener('loadedmetadata', drawWaveform);

renderSegments();
drawWaveform();
</script>
</body>
</html>
"""
