"""Markdown output formatter for batch pipeline results."""
from datetime import datetime
from pathlib import Path

from aureka.asr import Segment


def _seconds_to_mmss(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def _slugify(text: str) -> str:
    import re
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-")[:40] or "output"


def format_output(
    segments: list[Segment],
    frame_descriptions: list[tuple[float, str]],
    summary: dict,
    source_path: str | Path,
    duration: float = 0.0,
) -> str:
    now = datetime.now()
    source_path = Path(source_path)

    title = summary.get("title", source_path.stem)
    s_summary = summary.get("summary", "")
    highlights = summary.get("highlights", [])
    seg_records = summary.get("segments", [])

    dur_str = _seconds_to_mmss(duration) if duration else "未知"

    lines = [
        "---",
        f"source: {'video' if source_path.suffix.lower() in {'.mp4', '.mkv', '.mov'} else 'audio'}",
        f"original_file: {source_path.name}",
        f"duration: {dur_str}",
        f"processed_at: {now.isoformat(timespec='seconds')}",
        "---",
        "",
        f"# {title}",
        "",
        "## 摘要",
        "",
        s_summary,
        "",
        "## 重點",
        "",
    ]

    for h in highlights:
        lines.append(f"- {h}")

    lines += [
        "",
        "## 逐段紀錄",
        "",
        "| 時間 | 內容 |",
        "|------|------|",
    ]
    for rec in seg_records:
        t = rec.get("time", "")
        c = rec.get("content", "").replace("|", "｜")
        lines.append(f"| {t} | {c} |")

    if frame_descriptions:
        lines += [
            "",
            "## 視覺內容",
            "",
            "| 畫面時間點 | 描述 |",
            "|----------|------|",
        ]
        for ts, desc in frame_descriptions:
            t = _seconds_to_mmss(ts)
            d = desc.replace("|", "｜").replace("\n", " ")
            lines.append(f"| {t} | {d} |")

    lines += [
        "",
        "## 原始轉錄",
        "",
    ]
    for seg in segments:
        t = _seconds_to_mmss(seg.start)
        lines.append(f"[{t}] {seg.text}")

    return "\n".join(lines) + "\n"


def output_path(source_path: str | Path, output_dir: str | Path = "output") -> Path:
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    slug = _slugify(source_path.stem)
    return output_dir / f"{date}-{slug}.md"
