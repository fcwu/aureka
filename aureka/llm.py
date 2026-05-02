"""LLM and VLM client wrappers using OpenAI-compatible API."""
import base64
import pathlib
from typing import AsyncGenerator

import openai

from aureka.config import get_config

_llm_client: openai.OpenAI | None = None
_vlm_client: openai.OpenAI | None = None


def _get_llm() -> openai.OpenAI:
    global _llm_client
    if _llm_client is None:
        cfg = get_config()
        _llm_client = openai.OpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
    return _llm_client


def _get_vlm() -> openai.OpenAI:
    global _vlm_client
    if _vlm_client is None:
        cfg = get_config()
        _vlm_client = openai.OpenAI(base_url=cfg.vlm.base_url, api_key=cfg.vlm.api_key)
    return _vlm_client


def _resolve_model(client: openai.OpenAI, configured: str) -> str:
    if configured != "auto":
        return configured
    models = client.models.list().data
    if not models:
        raise RuntimeError("No models available at endpoint")
    return models[0].id


def describe_frame(image_path: str) -> str:
    cfg = get_config()
    client = _get_vlm()
    model = _resolve_model(client, cfg.vlm.model)
    b64 = base64.b64encode(pathlib.Path(image_path).read_bytes()).decode()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": "請描述這張影片截圖的內容，包含畫面主題、文字、圖表等資訊。"},
        ]}],
        max_tokens=512,
    )
    return resp.choices[0].message.content


def check_vlm_supports_vision(test_image: str | None = None) -> None:
    """Verify VLM supports vision at startup; raises SystemExit on failure."""
    import tempfile
    from PIL import Image

    if test_image is None:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            test_image = f.name
        img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        img.save(test_image)

    try:
        describe_frame(test_image)
    except Exception as e:
        cfg = get_config()
        raise SystemExit(
            f"[fatal] VLM 不支援 vision，請在 {cfg.vlm.base_url} 載入支援視覺的模型。\n{e}"
        )


_REFINE_SYSTEM = (
    "你是文字編輯器，不是助理。\n"
    "規則：\n"
    "1. 修正同音字錯誤、明顯的 ASR 錯字\n"
    "2. 加上中文標點符號（。，？！：；「」《》）\n"
    "3. 自然斷句、適當換行成段落\n"
    "4. 刪掉「嗯」「那個」「就是說」「對」等語氣詞、重複字\n"
    "5. 中英文之間加半形空格\n"
    "6. 不要加註解、不要說明、不要分析、不要思考過程\n"
    "7. 第一個字就直接輸出整理後的全文"
)

# Few-shot examples force the model to output directly without analysis prelude.
# Reasoning models will sometimes still emit <think> blocks, but they then mimic
# the demonstrated terse-output pattern.
_REFINE_FEWSHOT = [
    {
        "role": "user",
        "content": "嗯今天天氣很好就是說我們可以去公園走走然後吃個午餐",
    },
    {
        "role": "assistant",
        "content": "今天天氣很好，我們可以去公園走走，然後吃個午餐。",
    },
    {
        "role": "user",
        "content": "我跟你講喔那個 OLIKA 是個語音工具就是把音檔丟進去她會幫你做筆記",
    },
    {
        "role": "assistant",
        "content": "我跟你講，Aureka 是個語音工具，把音檔丟進去，它會幫你做筆記。",
    },
]

_TRANSLATE_SYSTEM = (
    "你是翻譯器，不是助理。\n"
    "規則：\n"
    "1. 翻譯成{lang}\n"
    "2. 不要加註解、不要說明、不要分析、不要思考過程\n"
    "3. 第一個字就直接輸出譯文"
)


_THINKING_PATTERNS = (
    "thinking process",
    "Self-Correction",
    "**Step ",
    "**Analyze ",
    "1.  **",
)


def _looks_like_unclosed_thinking(s: str) -> bool:
    """Heuristic for 'response is reasoning that got truncated before </think>'."""
    head = s[:600]
    return any(p in head for p in _THINKING_PATTERNS)


def _strip_think_blocks(s: str) -> str:
    """Remove <think>...</think> reasoning blocks. Handles four shapes:
    1. <think>...</think> answer  (full block)
    2. ...</think> answer         (chat template injected the opener; only closer appears in response)
    3. answer                     (no thinking at all)
    4. ...                        (truncated mid-thinking; never reached </think>) → return empty
    """
    import re
    s = re.sub(r"<think>.*?</think>\s*", "", s, flags=re.DOTALL)
    if "</think>" in s:
        s = s.split("</think>", 1)[1]
        return s.strip()
    if _looks_like_unclosed_thinking(s):
        return ""
    return s.strip()


async def llm_refine_stream(
    transcript: str, mode: str = "refine", lang: str = "zh"
) -> AsyncGenerator[str, None]:
    """Async generator yielding refined/translated text tokens."""
    cfg = get_config()
    model = cfg.llm.model

    if model == "auto":
        model = _resolve_model(_get_llm(), "auto")

    if mode == "translate":
        lang_name = {"en": "英文", "zh": "繁體中文", "ja": "日文"}.get(lang, lang)
        system = _TRANSLATE_SYSTEM.format(lang=lang_name)
    else:
        system = _REFINE_SYSTEM

    chat_kwargs: dict = {}
    if cfg.llm.thinking_budget is not None:
        chat_kwargs["thinking_budget"] = cfg.llm.thinking_budget
        # 0 → also flip enable_thinking off so chat templates that respect it skip CoT entirely
        if cfg.llm.thinking_budget == 0:
            chat_kwargs["enable_thinking"] = False

    messages = [{"role": "system", "content": system}]
    if mode == "refine":
        messages.extend(_REFINE_FEWSHOT)
    messages.append({"role": "user", "content": transcript})

    create_kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
    }
    if cfg.llm.max_tokens is not None:
        create_kwargs["max_tokens"] = cfg.llm.max_tokens
    if chat_kwargs:
        create_kwargs["extra_body"] = {"chat_template_kwargs": chat_kwargs}

    async with openai.AsyncOpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key) as client:
        stream = await client.chat.completions.create(**create_kwargs)

        full = ""
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full += delta

        cleaned = _strip_think_blocks(full)
        if cleaned:
            yield cleaned


def summarize_transcript(transcript: str, frame_descriptions: list[str]) -> dict:
    """Generate structured summary from transcript and frame descriptions."""
    cfg = get_config()
    client = _get_llm()
    model = _resolve_model(client, cfg.llm.model)

    frames_text = "\n".join(
        f"[{i+1}] {d}" for i, d in enumerate(frame_descriptions)
    ) if frame_descriptions else "（無畫面資訊）"

    prompt = (
        "根據以下語音轉錄和畫面描述，生成結構化摘要。\n\n"
        f"## 轉錄內容\n{transcript}\n\n"
        f"## 畫面描述\n{frames_text}\n\n"
        "請以 JSON 回傳：{{\"title\": \"...\", \"summary\": \"...\", \"highlights\": [\"...\"], \"segments\": [{{\"time\": \"mm:ss\", \"content\": \"...\"}}]}}"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    import json
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {
            "title": "未知標題",
            "summary": resp.choices[0].message.content,
            "highlights": [],
            "segments": [],
        }
