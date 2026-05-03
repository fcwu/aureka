"""Voice input client: tray icon + hotkey + WebSocket + text injection."""
import asyncio
import base64
import json
import threading
from typing import Any

from aureka.config import get_config
from aureka import injector, recorder as rec_module


def _ws_url() -> str:
    cfg = get_config()
    return f"ws://{cfg.daemon.host}:{cfg.daemon.port}/ws"


async def _voice_session(
    mode: str,
    lang: str,
    audio_source,
    streaming: bool = True,
    topic: str = "",
) -> None:
    """Run a voice session.

    `audio_source` may be:
      - `bytes`: send all at once (legacy / non-streaming)
      - an `asyncio.Queue` yielding bytes chunks; sentinel `None` means end-of-stream
    """
    import sys
    import websockets
    url = _ws_url()
    injected_len = 0
    transcript_buf = ""

    async def _send_loop(ws):
        if isinstance(audio_source, (bytes, bytearray)):
            chunk_size = 16000 * 2  # 0.5s @ 16kHz int16
            for i in range(0, len(audio_source), chunk_size):
                chunk = audio_source[i:i + chunk_size]
                await ws.send(json.dumps({
                    "type": "chunk", "data": base64.b64encode(chunk).decode(),
                }))
        else:
            # asyncio.Queue producing chunks, sentinel None terminates
            while True:
                chunk = await audio_source.get()
                if chunk is None:
                    break
                await ws.send(json.dumps({
                    "type": "chunk", "data": base64.b64encode(chunk).decode(),
                }))
        await ws.send(json.dumps({"type": "end"}))

    async with websockets.connect(url) as ws:
        start_frame = {
            "type": "start", "mode": mode, "lang": lang, "streaming": streaming,
        }
        if topic:
            start_frame["topic"] = topic
        await ws.send(json.dumps(start_frame))

        send_task = asyncio.create_task(_send_loop(ws))

        async for msg_str in ws:
            msg = json.loads(msg_str)
            mtype = msg.get("type")

            if mtype == "transcript":
                seg_text = msg.get("text", "")
                transcript_buf += seg_text
                if msg.get("is_partial"):
                    if mode == "transcribe":
                        # No LLM refine pass; partial IS the final text → inject.
                        injector.inject_text(seg_text)
                        injected_len += len(seg_text)
                    else:
                        # refine / translate: avoid polluting the user's draft
                        # with raw text that will get rewritten. Show progress
                        # in the terminal instead.
                        print(f"[aureka] partial: {seg_text}", file=sys.stderr)
                elif msg.get("final"):
                    print(f"[aureka] transcript: {transcript_buf}", file=sys.stderr)
                    if mode == "transcribe":
                        injector.inject_text(transcript_buf)
                        injected_len = len(transcript_buf)

            elif mtype == "refined":
                new_text = msg.get("text", "")
                if msg.get("final"):
                    print(f"[aureka] refined: {new_text}", file=sys.stderr)
                injector.replace_text(injected_len, new_text)
                injected_len = len(new_text)

            elif mtype == "info":
                phase = msg.get("phase", "")
                phase_label = {
                    "transcribing": "transcribing audio...",
                    "finalizing": "finalizing last segment...",
                    "refining": "refining with LLM...",
                }.get(phase, phase or "(info)")
                print(f"[aureka] {phase_label}", file=sys.stderr)

            elif mtype == "warning":
                print(f"[aureka] {msg.get('message','(warning)')}", file=sys.stderr)

            elif mtype == "error":
                print(f"[aureka] daemon error: {msg.get('message','(no detail)')}", file=sys.stderr)
                break

            elif mtype == "done":
                break

        await send_task

    if transcript_buf == "":
        print("[aureka] (no speech detected)", file=sys.stderr)


def run_voice_session(mode: str = "refine", lang: str = "zh") -> None:
    cfg = get_config()
    recorder = rec_module.Recorder(mode=cfg.hotkey.mode)
    print("[aureka] Recording... (release hotkey to stop)")
    recorder.start()

    import time
    time.sleep(0.1)  # give start() time to set up

    input("Press Enter to stop recording...")
    audio_data = recorder.stop()

    if len(audio_data) == 0:
        print("[aureka] No audio captured.")
        return

    asyncio.run(_voice_session(mode, lang, audio_data.tobytes()))


def start_tray() -> None:
    """Launch system tray icon with voice input hotkey."""
    cfg = get_config()

    from aureka.hotkey import HotkeyManager

    mode_ref = [cfg.hotkey.input_mode]
    lang_ref = [cfg.hotkey.lang]

    recorder = rec_module.Recorder(mode=cfg.hotkey.mode)
    is_recording = threading.Event()

    def on_press():
        if not is_recording.is_set():
            is_recording.set()
            recorder._collected_chunks = []
            recorder.start()

    def on_release():
        if is_recording.is_set():
            is_recording.clear()
            audio_data = recorder.stop()
            if len(audio_data) > 0:
                threading.Thread(
                    target=lambda: asyncio.run(
                        _voice_session(mode_ref[0], lang_ref[0], audio_data.tobytes())
                    ),
                    daemon=True,
                ).start()

    hk = HotkeyManager(cfg.hotkey.trigger, on_press=on_press, on_release=on_release)
    hk.start()

    try:
        import pystray
        from aureka._icon import make_tray_icon, apply_macos_template

        img = make_tray_icon()

        def _make_menu():
            items = []
            for m in ("transcribe", "refine", "translate"):
                def _set_mode(m=m):
                    mode_ref[0] = m
                items.append(pystray.MenuItem(m, _set_mode, checked=lambda item, m=m: mode_ref[0] == m))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("Quit", lambda: icon.stop()))
            return pystray.Menu(*items)

        icon = pystray.Icon("aureka", img, "Aureka", menu=_make_menu())

        def _on_setup(_icon):
            _icon.visible = True
            apply_macos_template(_icon)

        icon.run(setup=_on_setup)
    except ImportError:
        print("[aureka] pystray not available; running without tray icon. Ctrl+C to quit.")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    finally:
        hk.stop()
