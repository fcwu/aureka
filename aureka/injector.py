"""Text injection into the current cursor position, platform-aware."""
import platform
import shutil
import subprocess
import time

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore

try:
    import pyperclip
except ImportError:
    pyperclip = None  # type: ignore


def _platform() -> str:
    return platform.system()


def save_clipboard() -> str:
    try:
        if pyperclip is None:
            return ""
        return pyperclip.paste() or ""
    except Exception:
        return ""


def restore_clipboard(text: str) -> None:
    try:
        if pyperclip is not None:
            pyperclip.copy(text)
    except Exception:
        pass


def inject_text(text: str) -> None:
    """Inject text at current cursor position."""
    sys = _platform()
    if sys == "Linux":
        _inject_linux(text)
    elif sys == "Darwin":
        _inject_macos(text)
    else:
        _inject_clipboard(text, "ctrl+v")


def _inject_linux(text: str) -> None:
    if shutil.which("xdotool"):
        try:
            # xdotool type handles Unicode better than bare type
            result = subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return
        except Exception:
            pass
    # Fallback: clipboard injection
    _inject_clipboard(text, "ctrl+v")


def _inject_macos(text: str) -> None:
    _inject_clipboard(text, "command+v")


def _inject_clipboard(text: str, paste_key: str) -> None:
    import sys
    original = save_clipboard()
    pasted = False
    try:
        if pyperclip is None:
            print("[aureka] pyperclip not installed; cannot inject text.", file=sys.stderr)
            return
        pyperclip.copy(text)
        time.sleep(0.05)
        if pyautogui is None:
            print(f"[aureka] pyautogui not installed; text copied to clipboard. Paste with {paste_key}.", file=sys.stderr)
            return
        try:
            pyautogui.hotkey(*paste_key.split("+"))
            pasted = True
        except Exception as e:
            print(
                f"[aureka] could not send {paste_key} ({type(e).__name__}: {e}). "
                "On macOS grant Accessibility permission to the terminal in "
                "System Settings → Privacy & Security → Accessibility. "
                "Text is on the clipboard — paste manually.",
                file=sys.stderr,
            )
        time.sleep(0.05)
    finally:
        if pasted:
            restore_clipboard(original)


def replace_text(prev_len: int, new_text: str) -> None:
    """Replace prev_len characters before cursor with new_text."""
    if prev_len > 0:
        try:
            if pyautogui is not None:
                pyautogui.press("backspace", presses=prev_len, interval=0.01)
        except Exception:
            pass
    inject_text(new_text)
