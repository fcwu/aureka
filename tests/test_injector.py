"""Unit tests for injector text replacement logic."""
from unittest.mock import MagicMock, call, patch

import pytest

pytestmark = pytest.mark.unit


def test_replace_text_calls_backspace_then_inject():
    with patch("aureka.injector.inject_text") as mock_inject, \
         patch("aureka.injector.pyautogui") as mock_pyautogui:
        # pyautogui might not be importable in CI; patch it at module level
        import aureka.injector as inj_mod
        inj_mod.replace_text(5, "新文字")
        mock_pyautogui.press.assert_called_once_with("backspace", presses=5, interval=0.01)
        mock_inject.assert_called_once_with("新文字")


def test_replace_text_zero_prev_len():
    with patch("aureka.injector.inject_text") as mock_inject, \
         patch("aureka.injector.pyautogui") as mock_pyautogui:
        import aureka.injector as inj_mod
        inj_mod.replace_text(0, "新文字")
        mock_pyautogui.press.assert_not_called()
        mock_inject.assert_called_once_with("新文字")


def test_save_restore_clipboard():
    mock_pyperclip = MagicMock()
    mock_pyperclip.paste.return_value = "original text"
    with patch("aureka.injector.pyperclip", mock_pyperclip):
        import aureka.injector as inj_mod
        saved = inj_mod.save_clipboard()
        assert saved == "original text"
        inj_mod.restore_clipboard(saved)
        mock_pyperclip.copy.assert_called_once_with("original text")


def test_inject_linux_xdotool_success():
    with patch("aureka.injector._platform", return_value="Linux"), \
         patch("shutil.which", return_value="/usr/bin/xdotool"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        import aureka.injector as inj_mod
        inj_mod.inject_text("hello 世界")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "xdotool" in args[0]
        assert "hello 世界" in args


def test_inject_linux_xdotool_fallback_to_clipboard():
    with patch("aureka.injector._platform", return_value="Linux"), \
         patch("shutil.which", return_value=None), \
         patch("aureka.injector._inject_clipboard") as mock_clip:
        import aureka.injector as inj_mod
        inj_mod.inject_text("hello")
        mock_clip.assert_called_once()
