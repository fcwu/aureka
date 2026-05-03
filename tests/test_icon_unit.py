"""Unit tests for aureka._icon — tray icon factory."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ── make_tray_icon — shape and pixels ──────────────────────────────────────

def test_make_tray_icon_returns_rgba(monkeypatch):
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Darwin")
    img = _icon.make_tray_icon()
    assert img.mode == "RGBA"


def test_make_tray_icon_macos_88px(monkeypatch):
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Darwin")
    img = _icon.make_tray_icon()
    assert img.size == (_icon._TARGET_MAC, _icon._TARGET_MAC)


def test_make_tray_icon_windows_64px(monkeypatch):
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Windows")
    img = _icon.make_tray_icon()
    assert img.size == (_icon._TARGET_WIN, _icon._TARGET_WIN)


def test_make_tray_icon_macos_is_monochrome(monkeypatch):
    """Template image: black foreground only, no chromatic pixels."""
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Darwin")
    img = _icon.make_tray_icon()

    has_color = False
    for r, g, b, a in img.getdata():
        if a == 0:
            continue
        if not (r == g == b):
            has_color = True
            break
    assert has_color is False, "macOS template image must be grayscale + alpha"


def test_make_tray_icon_windows_uses_accent_blue(monkeypatch):
    """Windows path renders in #3b82f6 (allowing some LANCZOS bleed)."""
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Windows")
    img = _icon.make_tray_icon()

    saw_blue = False
    for r, g, b, a in img.getdata():
        if a < 128:
            continue
        # Loose match: dominant channel is blue, near #3b82f6
        if b > r and b > g and b > 200:
            saw_blue = True
            break
    assert saw_blue, "Windows icon should contain visible blue pixels"


def test_make_tray_icon_has_visible_glyph(monkeypatch):
    """Sanity: the canvas isn't accidentally fully transparent."""
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Darwin")
    img = _icon.make_tray_icon()
    n_opaque = sum(1 for px in img.getdata() if px[3] > 0)
    total = img.size[0] * img.size[1]
    assert 0.05 * total < n_opaque < 0.7 * total, (
        f"glyph should fill 5–70% of canvas, got {n_opaque}/{total}"
    )


# ── apply_macos_template ────────────────────────────────────────────────────

def test_apply_macos_template_no_op_on_non_mac(monkeypatch):
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Linux")
    assert _icon.apply_macos_template(object()) is False


def test_apply_macos_template_handles_missing_status_item(monkeypatch):
    """If pystray's `_status_item` private attr is gone (refactor), don't crash."""
    from aureka import _icon
    monkeypatch.setattr(_icon.platform, "system", lambda: "Darwin")

    class FakeIcon:
        pass
    assert _icon.apply_macos_template(FakeIcon()) is False
