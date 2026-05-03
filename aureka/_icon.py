"""Tray icon factory.

Single source of truth for tray glyphs across `aureka.tray` and
`aureka.client.start_tray`. Visual: line-art "A" with 2–3 sparkle stars.
macOS gets a monochrome black-on-alpha image (set as NSImage template
elsewhere so the system auto-tints in light/dark menu bar). Windows /
Linux get a colored variant in the project accent (`#3b82f6`).
"""
from __future__ import annotations

import platform


_MAC_FG = (0, 0, 0, 255)       # black, alpha 1
_WIN_FG = (59, 130, 246, 255)  # #3b82f6
_TRANSPARENT = (0, 0, 0, 0)

# Render at 4× target then LANCZOS-downsample for cheap anti-aliasing.
_SUPERSAMPLE = 4
_TARGET_MAC = 88
_TARGET_WIN = 64


def _star_polygon(cx: int, cy: int, outer: int, inner_ratio: float = 0.32) -> list[tuple[int, int]]:
    """4-pointed sparkle star with concave edges. Returns 8 vertices."""
    inner = int(outer * inner_ratio)
    return [
        (cx, cy - outer),                   # N tip
        (cx + inner, cy - inner),           # NE waist
        (cx + outer, cy),                   # E tip
        (cx + inner, cy + inner),           # SE waist
        (cx, cy + outer),                   # S tip
        (cx - inner, cy + inner),           # SW waist
        (cx - outer, cy),                   # W tip
        (cx - inner, cy - inner),           # NW waist
    ]


def _draw_glyph(size: int, color: tuple[int, int, int, int]):
    """Render the A + sparkles glyph at canvas size px (square, RGBA)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), _TRANSPARENT)
    d = ImageDraw.Draw(img)

    # Stroke ~12% of canvas for legibility at 22pt menu bar.
    stroke = max(2, round(size * 0.12))

    # "A" occupies the left ~58% horizontally, ~78% vertically.
    a_left = int(size * 0.10)
    a_right = int(size * 0.58)
    a_top = int(size * 0.16)
    a_bottom = int(size * 0.86)
    apex_x = (a_left + a_right) // 2

    # Two legs + crossbar.
    d.line([(a_left, a_bottom), (apex_x, a_top)], fill=color, width=stroke)
    d.line([(apex_x, a_top), (a_right, a_bottom)], fill=color, width=stroke)
    crossbar_y = int(a_top + (a_bottom - a_top) * 0.62)
    inset = (a_right - a_left) // 5
    d.line(
        [(a_left + inset, crossbar_y), (a_right - inset, crossbar_y)],
        fill=color, width=stroke,
    )

    # Sparkle cluster to the right of the A.
    big = (int(size * 0.78), int(size * 0.30), int(size * 0.16))
    mid = (int(size * 0.90), int(size * 0.55), int(size * 0.10))
    small = (int(size * 0.70), int(size * 0.62), int(size * 0.07))
    for cx, cy, r in (big, mid, small):
        d.polygon(_star_polygon(cx, cy, r), fill=color)

    return img


def make_tray_icon():
    """Return a `PIL.Image.Image` suitable for `pystray.Icon(..., icon=img)`.

    Caller doesn't need to know which platform branch fired; the returned
    image is RGBA in either case. macOS template-image flagging happens
    after pystray binds the icon to a `NSStatusItem` (see
    `aureka.tray.run_tray` for the shim).
    """
    is_mac = platform.system() == "Darwin"
    target = _TARGET_MAC if is_mac else _TARGET_WIN
    color = _MAC_FG if is_mac else _WIN_FG
    big = _draw_glyph(target * _SUPERSAMPLE, color)
    from PIL import Image
    return big.resize((target, target), Image.LANCZOS)


def apply_macos_template(icon) -> bool:
    """Mark the pystray macOS NSImage as template image (auto light/dark tint).

    Best-effort: pystray does not expose this in its public API, so we reach
    into `_status_item.button.image` via pyobjc. Returns True on success,
    False (and logs a warning) on failure. No-op on non-macOS.
    """
    if platform.system() != "Darwin":
        return False
    try:
        status_item = getattr(icon, "_status_item", None)
        if status_item is None:
            return False
        button = status_item.button()
        ns_image = button.image()
        ns_image.setTemplate_(True)
        return True
    except Exception as e:
        print(f"[aureka] tray icon: macOS template flag failed: {e}", flush=True)
        return False
