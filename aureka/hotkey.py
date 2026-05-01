"""Global hotkey management using pynput."""
from typing import Callable


def _parse_hotkey(combo: str):
    """Parse hotkey string like '<ctrl>+<alt>+space' into pynput keys."""
    from pynput import keyboard
    parts = combo.split("+")
    keys = []
    for p in parts:
        p = p.strip()
        if p.startswith("<") and p.endswith(">"):
            name = p[1:-1]
            key = getattr(keyboard.Key, name, None)
            if key is None:
                raise ValueError(f"Unknown key: {p}")
            keys.append(key)
        else:
            keys.append(keyboard.KeyCode.from_char(p))
    return frozenset(keys)


class HotkeyManager:
    def __init__(self, combo: str, on_press: Callable, on_release: Callable | None = None):
        self._combo = combo
        self._on_press = on_press
        self._on_release = on_release
        self._pressed: set = set()
        self._target: frozenset | None = None
        self._listener = None
        self._triggered = False

    def start(self) -> None:
        from pynput import keyboard
        self._target = _parse_hotkey(self._combo)

        def _on_press(key):
            self._pressed.add(key)
            if self._target and self._target.issubset(self._pressed) and not self._triggered:
                self._triggered = True
                self._on_press()

        def _on_release(key):
            if key in self._pressed:
                self._pressed.discard(key)
            if self._triggered and (self._target is None or not self._target.issubset(self._pressed)):
                self._triggered = False
                if self._on_release:
                    self._on_release()

        self._listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
