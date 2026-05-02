"""Aureka CLI entry point."""
import argparse
import os
import sys


def _require_config(args):
    if hasattr(args, "config") and args.config:
        os.environ["AUREKA_CONFIG"] = args.config

    from aureka.config import get_config
    cfg = get_config()
    # config.toml not found is not fatal for most commands; daemon start will use defaults
    return cfg


def cmd_process(args):
    from pathlib import Path
    from aureka.ffmpeg_utils import SUPPORTED_FORMATS
    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        print(f"Error: unsupported format '{path.suffix}'. Supported: {', '.join(SUPPORTED_FORMATS)}", file=sys.stderr)
        sys.exit(1)

    from aureka.pipeline import run_pipeline
    run_pipeline(
        path,
        device=args.device,
        frame_interval=args.frame_interval,
        output_dir=args.output_dir,
    )


def cmd_speak(args):
    if args.file:
        from aureka.tts import strip_markdown
        text = strip_markdown(open(args.file).read())
    elif args.text:
        text = args.text
    else:
        print("Error: provide text or --file", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        return

    from aureka.config import get_config
    cfg = get_config()

    import socket
    daemon_available = False
    try:
        s = socket.create_connection((cfg.daemon.host, cfg.daemon.port), timeout=1)
        s.close()
        daemon_available = True
    except (ConnectionRefusedError, OSError):
        pass

    if daemon_available:
        import io
        import json
        import urllib.request
        url = f"http://{cfg.daemon.host}:{cfg.daemon.port}/speak"
        payload = {"text": text}
        if args.speed is not None:
            payload["speed"] = args.speed
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            wav_bytes = resp.read()

        if args.output:
            with open(args.output, "wb") as f:
                f.write(wav_bytes)
        else:
            import soundfile as sf
            import sounddevice as sd
            data, sr = sf.read(io.BytesIO(wav_bytes))
            sd.play(data, sr)
            sd.wait()
    else:
        print("[aureka] Daemon not running — loading TTS locally (cold start) ...", file=sys.stderr)
        from aureka.tts import speak
        speak(text, args.output, speed=args.speed)


def cmd_type(args):
    import asyncio
    from aureka.client import _voice_session
    from aureka import recorder as rec_module
    from aureka.config import get_config

    cfg = get_config()
    mode = args.mode or cfg.hotkey.input_mode
    lang = args.lang or cfg.hotkey.lang

    # Try to connect to daemon first
    import socket
    daemon_available = False
    try:
        s = socket.create_connection((cfg.daemon.host, cfg.daemon.port), timeout=1)
        s.close()
        daemon_available = True
    except (ConnectionRefusedError, OSError):
        pass

    if not daemon_available:
        print("[aureka] Daemon not running — loading ASR locally (cold start) ...")
        from aureka import asr, llm
        asr.load_asr(device=args.device)

    recorder = rec_module.Recorder(mode=cfg.hotkey.mode)
    print("[aureka] Recording... press Enter to stop.")
    recorder.start()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    audio_data = recorder.stop()

    if len(audio_data) == 0:
        print("[aureka] No audio captured.")
        return

    if daemon_available:
        asyncio.run(_voice_session(mode, lang, audio_data.tobytes()))
    else:
        import numpy as np
        from aureka import asr, injector, llm as llm_mod
        audio = audio_data.astype(np.float32) / 32768.0
        segments = asr.transcribe(audio, 16000)
        transcript = " ".join(s.text for s in segments)
        if mode in ("refine", "translate"):
            import asyncio as aio

            async def _collect():
                result = ""
                async for token in llm_mod.llm_refine_stream(transcript, mode=mode, lang=lang):
                    result += token
                return result

            text = aio.run(_collect())
        else:
            text = transcript
        injector.inject_text(text)


def cmd_download(args):
    from aureka import models
    try:
        paths = models.download_all(device=args.device)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    keys = models._select_models()
    registry = models.model_registry()
    print("\n[aureka] Models ready:")
    for key, path in zip(keys, paths):
        print(f"  {key:16s}  {registry[key]:48s}  {path}")


def cmd_benchmark(args):
    from aureka.benchmark import run_benchmark
    run_benchmark(
        device=args.device,
        quick=args.quick,
        output_path=args.output,
        skip_llm=args.skip_llm,
    )


def cmd_daemon(args):
    from aureka.daemon import start_daemon, stop_daemon, status_daemon
    if args.action == "start":
        start_daemon()
    elif args.action == "stop":
        stop_daemon()
    elif args.action == "status":
        status_daemon()


def cmd_daemon_serve(args):
    """Internal: actually start the uvicorn server (called by start_daemon())."""
    from aureka.daemon import serve
    serve(host=args.host, port=int(args.port))


def main():
    parser = argparse.ArgumentParser(prog="aureka", description="Local AI voice processing platform")
    parser.add_argument("--config", metavar="PATH", help="Path to config.toml (overrides AUREKA_CONFIG)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])

    sub = parser.add_subparsers(dest="command", metavar="command")

    # process
    p_proc = sub.add_parser("process", help="Batch-process video/audio to Markdown")
    p_proc.add_argument("file", help="Input video or audio file")
    p_proc.add_argument("--frame-interval", type=int, default=30, metavar="SECS")
    p_proc.add_argument("--output-dir", default="output", metavar="DIR")

    # speak
    p_speak = sub.add_parser("speak", help="TTS read-aloud")
    p_speak.add_argument("text", nargs="?", help="Text to speak")
    p_speak.add_argument("--file", metavar="PATH", help="Markdown/text file to read")
    p_speak.add_argument("--output", metavar="PATH", help="Save WAV instead of playing")
    p_speak.add_argument("--speed", type=float, default=None,
                         metavar="X", help="Speech rate (1.0 = normal, 1.3 = faster, 0.8 = slower)")

    # type
    p_type = sub.add_parser("type", help="Voice input → text injection")
    p_type.add_argument("--mode", choices=["transcribe", "refine", "translate"])
    p_type.add_argument("--lang", metavar="LANG", help="Language code (e.g. zh, en, ja)")

    # download
    sub.add_parser(
        "download",
        help="Pre-download all model weights (Kokoro TTS + Whisper ASR) used at runtime",
    )

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Measure ASR/TTS/LLM speed and write a Markdown report")
    p_bench.add_argument("--quick", action="store_true",
                         help="1 timed run instead of 5 (faster, less stable)")
    p_bench.add_argument("--output", metavar="PATH",
                         help="Markdown report path (default: ./benchmark-<host>-<date>.md)")
    p_bench.add_argument("--skip-llm", action="store_true",
                         help="Skip LLM benchmark (no LM Studio / Ollama call)")

    # daemon
    p_daemon = sub.add_parser("daemon", help="Manage background daemon")
    p_daemon.add_argument("action", choices=["start", "stop", "status"])

    # _daemon_serve (internal, not shown in help)
    p_serve = sub.add_parser("_daemon_serve", help=argparse.SUPPRESS)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", default="7777")

    args = parser.parse_args()

    # Apply AUREKA_CONFIG env var from --config flag
    if args.config:
        os.environ["AUREKA_CONFIG"] = args.config

    # Check config exists for user-facing commands
    if args.command not in (None, "_daemon_serve", "daemon"):
        cfg_path = os.environ.get("AUREKA_CONFIG", "config.toml")
        import pathlib
        if not pathlib.Path(cfg_path).exists():
            print(
                f"Warning: config file not found: {cfg_path}\n"
                "Create one with: cp config.example.toml config.toml",
                file=sys.stderr,
            )

    dispatch = {
        "process": cmd_process,
        "speak": cmd_speak,
        "type": cmd_type,
        "download": cmd_download,
        "benchmark": cmd_benchmark,
        "daemon": cmd_daemon,
        "_daemon_serve": cmd_daemon_serve,
    }

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    func = dispatch.get(args.command)
    if func:
        func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
