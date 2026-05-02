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
    "你是專業文字編輯。將以下語音轉錄文字整理成自然流暢的書面文字：\n"
    "- 移除重複、語氣詞（嗯、那個、就是說）\n"
    "- 修正明顯語音辨識錯誤\n"
    "- 保持原意，不要添加內容\n"
    "- 直接輸出結果，不要解釋"
)

_TRANSLATE_SYSTEM = (
    "你是專業翻譯。請將以下文字翻譯成{lang}，保持原意，直接輸出翻譯結果，不要解釋。"
)


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

    async with openai.AsyncOpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key) as client:
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": transcript},
            ],
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


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
