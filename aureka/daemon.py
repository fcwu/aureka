"""FastAPI daemon: HTTP health/batch + WebSocket voice input."""
import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from aureka import asr
from aureka.config import get_config

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app: FastAPI):
    asr.load_asr()
    yield


app = FastAPI(title="Aureka Daemon", lifespan=_lifespan)


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    from aureka import __version__
    return {"status": "ok", "version": __version__}


@app.post("/reload")
def reload_endpoint():
    """Re-read config.toml and refresh in-memory state.

    Live-applied: llm/vlm endpoints (next call rebuilds client with new
    base_url/api_key/model). Restart-required: asr.model, tts.voice/device,
    daemon.host/port. The response lists what needs a daemon restart so the
    UI can warn the user.
    """
    from aureka import config as cfg_mod
    from aureka import llm as llm_mod

    before = cfg_mod.get_config()
    cfg_mod.reset_config()
    after = cfg_mod.get_config()

    llm_mod._llm_client = None
    llm_mod._vlm_client = None

    needs_restart: list[str] = []
    if before.asr.model != after.asr.model:
        needs_restart.append("asr.model")
    for k in ("voice", "lang_code", "device"):
        if getattr(before.tts, k) != getattr(after.tts, k):
            needs_restart.append(f"tts.{k}")
    for k in ("host", "port"):
        if getattr(before.daemon, k) != getattr(after.daemon, k):
            needs_restart.append(f"daemon.{k}")

    return {"ok": True, "needs_restart": needs_restart}


_tts_lock = asyncio.Lock()
_tts_loaded = False


async def _ensure_tts():
    global _tts_loaded
    async with _tts_lock:
        if not _tts_loaded:
            from aureka import tts
            await asyncio.get_event_loop().run_in_executor(None, tts.load_tts)
            _tts_loaded = True


@app.post("/speak")
async def speak_endpoint(body: dict):
    text = body.get("text", "")
    if not text:
        return JSONResponse({"error": "missing text"}, status_code=400)
    speed = body.get("speed")  # None → use config

    await _ensure_tts()

    from aureka import tts
    audio, sr = await asyncio.get_event_loop().run_in_executor(
        None, lambda: tts.synthesize(text, speed=speed)
    )
    if audio is None:
        return JSONResponse({"error": "no audio produced"}, status_code=500)

    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


@app.post("/process")
async def process(body: dict):
    """Async batch pipeline trigger."""
    input_path = body.get("path")
    if not input_path:
        return JSONResponse({"error": "missing path"}, status_code=400)

    from aureka import pipeline
    import asyncio, uuid
    task_id = str(uuid.uuid4())[:8]

    async def _run():
        device = body.get("device", "auto")
        frame_interval = int(body.get("frame_interval", 30))
        pipeline.run_pipeline(input_path, device=device, frame_interval=frame_interval)

    asyncio.create_task(_run())
    return {"task_id": task_id, "status": "queued"}


# ── WebSocket voice input ─────────────────────────────────────────────────────


async def _voice_input_buffer(ws: WebSocket) -> list[str] | None:
    """Buffer mode: collect everything, transcribe once. Returns transcript_parts or None if empty."""
    audio_chunks: list[np.ndarray] = []
    async for msg in ws.iter_json():
        if msg["type"] == "chunk":
            pcm = np.frombuffer(base64.b64decode(msg["data"]), dtype=np.int16)
            audio_chunks.append(pcm)
        elif msg["type"] == "end":
            break

    if not audio_chunks:
        await ws.send_json({"type": "done"})
        return None

    await ws.send_json({"type": "info", "phase": "transcribing"})
    audio = np.concatenate(audio_chunks).astype(np.float32) / 32768.0
    segments = await asyncio.get_event_loop().run_in_executor(
        None, lambda: list(asr.transcribe(audio, 16000))
    )
    parts: list[str] = []
    for seg in segments:
        await ws.send_json({"type": "transcript", "text": seg.text, "final": seg.is_last})
        parts.append(seg.text)
    return parts


async def _voice_input_streaming(ws: WebSocket) -> list[str] | None:
    """Streaming mode: VAD-segmented incremental ASR. Returns transcript_parts or None if empty."""
    from aureka.vad import VadSegmenter
    seg = VadSegmenter()
    parts: list[str] = []
    loop = asyncio.get_event_loop()

    async def _flush_segment(audio_f32: np.ndarray):
        # Run blocking ASR in a thread so we can keep accepting WS chunks.
        segments = await loop.run_in_executor(
            None, lambda: list(asr.transcribe(audio_f32, 16000))
        )
        text = "".join(s.text for s in segments)
        parts.append(text)
        await ws.send_json({
            "type": "transcript", "text": text, "final": False, "is_partial": True
        })

    async for msg in ws.iter_json():
        if msg["type"] == "chunk":
            pcm = np.frombuffer(base64.b64decode(msg["data"]), dtype=np.int16)
            for audio in seg.feed(pcm):
                await _flush_segment(audio)
        elif msg["type"] == "end":
            break

    leftover = seg.flush()
    if leftover:
        await ws.send_json({"type": "info", "phase": "finalizing"})
        for audio in leftover:
            await _flush_segment(audio)

    if not parts:
        await ws.send_json({"type": "done"})
        return None
    return parts


# silero-vad availability is checked once at startup. If unavailable, all clients
# fall through to buffer mode (silently, after a single warning log).
_vad_available: bool | None = None
_vad_warned = False


def _check_vad() -> bool:
    """Lazy-check silero-vad. Logs a single warning on failure."""
    global _vad_available, _vad_warned
    if _vad_available is not None:
        return _vad_available
    try:
        from aureka.vad import VadSegmenter  # noqa: F401
        _vad_available = True
    except Exception as e:
        _vad_available = False
        if not _vad_warned:
            print(f"[aureka] streaming ASR unavailable, falling back to buffer mode: {e}",
                  flush=True)
            _vad_warned = True
    return _vad_available


@app.websocket("/ws")
async def voice_input(ws: WebSocket):
    await ws.accept()
    try:
        config_msg = await ws.receive_json()
        mode = config_msg.get("mode", "transcribe")
        lang = config_msg.get("lang", "zh")
        topic = config_msg.get("topic", "") or ""
        streaming = bool(config_msg.get("streaming", False)) and _check_vad()

        if streaming:
            transcript_parts = await _voice_input_streaming(ws)
        else:
            transcript_parts = await _voice_input_buffer(ws)

        if transcript_parts is None:
            return  # empty session, done already sent

        if mode in ("refine", "translate"):
            from aureka.llm import llm_refine_stream
            transcript = " ".join(transcript_parts)
            await ws.send_json({"type": "info", "phase": "refining"})
            accumulated = ""
            llm_failed = False
            try:
                async for token in llm_refine_stream(transcript, mode=mode, lang=lang, topic=topic):
                    accumulated += token
                    await ws.send_json({"type": "refined", "text": accumulated, "final": False})
            except Exception as e:
                import traceback
                traceback.print_exc()
                llm_failed = True
                await ws.send_json({"type": "warning", "message": f"LLM {type(e).__name__}: {e}"})

            if not accumulated.strip():
                # Refine produced nothing (truncated CoT, LLM error, etc.) — fall back to raw transcript
                accumulated = transcript
                if not llm_failed:
                    await ws.send_json({
                        "type": "warning",
                        "message": "refine returned empty (likely thinking-model CoT truncated); falling back to transcript",
                    })
            await ws.send_json({"type": "refined", "text": accumulated, "final": True})

        await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await ws.send_json({"type": "error", "message": f"{type(e).__name__}: {e}"})
        except Exception:
            pass


# ── Process management ────────────────────────────────────────────────────────

def _pid_file() -> Path:
    return Path(get_config().daemon.pid_file)


def _log_file() -> Path:
    return Path(get_config().daemon.log_file)


def start_daemon() -> None:
    pid_path = _pid_file()
    if pid_path.exists():
        pid = int(pid_path.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Daemon already running (PID {pid})")
            return
        except ProcessLookupError:
            pid_path.unlink()

    log_path = _log_file()
    cfg = get_config()
    env = os.environ.copy()

    with open(log_path, "a") as log:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "aureka", "_daemon_serve",
                "--host", cfg.daemon.host,
                "--port", str(cfg.daemon.port),
            ],
            stdout=log, stderr=log,
            env=env,
            start_new_session=True,
        )

    pid_path.write_text(str(proc.pid))
    time.sleep(1.5)  # brief wait for startup
    print(f"Daemon started (PID {proc.pid}) → http://{cfg.daemon.host}:{cfg.daemon.port}")
    print(f"Log: {log_path}")


def stop_daemon() -> None:
    pid_path = _pid_file()
    if not pid_path.exists():
        print("Daemon is not running.")
        return
    pid = int(pid_path.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        pid_path.unlink()
        print(f"Daemon stopped (PID {pid})")
    except ProcessLookupError:
        pid_path.unlink()
        print("Daemon was not running (stale PID file removed)")


def status_daemon() -> None:
    pid_path = _pid_file()
    cfg = get_config()
    if not pid_path.exists():
        print("Daemon: not running")
        return
    pid = int(pid_path.read_text().strip())
    try:
        os.kill(pid, 0)
        print(f"Daemon: running (PID {pid}) → http://{cfg.daemon.host}:{cfg.daemon.port}")
    except ProcessLookupError:
        pid_path.unlink()
        print("Daemon: not running (stale PID file removed)")


def serve(host: str = "127.0.0.1", port: int = 7777) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level=os.environ.get("AUREKA_LOG_LEVEL", "info"))
