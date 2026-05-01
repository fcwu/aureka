#!/usr/bin/env python3
"""WebSocket client for manual E2E testing of voice input daemon."""
import argparse
import asyncio
import base64
import json
import sys
import wave
from pathlib import Path

import websockets


async def run(url: str, mode: str, lang: str, audio_path: str):
    print(f"Connecting to {url} ...")
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "start", "mode": mode, "lang": lang}))
        print(f"[→] start mode={mode} lang={lang}")

        with wave.open(audio_path) as f:
            pcm = f.readframes(f.getnframes())

        chunk_size = 16000 * 2 * 1  # 0.5s @ 16kHz mono int16
        for i in range(0, len(pcm), chunk_size):
            chunk = pcm[i:i + chunk_size]
            await ws.send(json.dumps({
                "type": "chunk",
                "data": base64.b64encode(chunk).decode(),
            }))

        await ws.send(json.dumps({"type": "end"}))
        print("[→] end")

        async for msg_str in ws:
            msg = json.loads(msg_str)
            print(f"[←] {json.dumps(msg, ensure_ascii=False)}")
            if msg["type"] == "done":
                break

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:7777/ws")
    parser.add_argument("--mode", default="transcribe", choices=["transcribe", "refine", "translate"])
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--audio", required=True)
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"Audio file not found: {args.audio}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run(args.url, args.mode, args.lang, args.audio))
