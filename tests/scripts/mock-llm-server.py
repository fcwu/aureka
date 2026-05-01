#!/usr/bin/env python3
"""Mock OpenAI-compatible LLM server for testing."""
import argparse
import json
import time
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any

app = FastAPI()

MOCK_MODELS = [
    {"id": "mock-model", "object": "model", "owned_by": "mock"},
    {"id": "mock-vision-model", "object": "model", "owned_by": "mock"},
]

MOCK_REFINE_RESPONSE = "這是一段經過整理的文字。"
MOCK_DESCRIBE_RESPONSE = "這是一張包含文字和圖表的截圖。"


@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": MOCK_MODELS}


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-llm-server"}


class ChatRequest(BaseModel):
    model: str = "mock-model"
    messages: list[dict[str, Any]]
    stream: bool = False
    max_tokens: int = 512


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    has_image = any(
        isinstance(m.get("content"), list) and
        any(c.get("type") == "image_url" for c in m["content"])
        for m in req.messages
    )
    content = MOCK_DESCRIBE_RESPONSE if has_image else MOCK_REFINE_RESPONSE

    if req.stream:
        async def stream_response():
            tokens = content.split("。")
            for i, token in enumerate(tokens):
                if not token:
                    continue
                chunk = {
                    "id": "mock-chunk",
                    "object": "chat.completion.chunk",
                    "choices": [{"delta": {"content": token + ("。" if i < len(tokens) - 1 else "")}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                time.sleep(0.05)
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    return {
        "id": "mock-completion",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=11434)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
