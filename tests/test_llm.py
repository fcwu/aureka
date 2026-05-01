"""Integration tests for LLM/VLM client using mock server."""
import asyncio
import os
import tempfile

import pytest

from tests.conftest import FIXTURES_DIR

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def use_mock_llm(mock_llm_server, monkeypatch, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'[llm]\nbase_url = "{mock_llm_server}/v1"\napi_key = "mock"\nmodel = "mock-model"\n'
        f'[vlm]\nbase_url = "{mock_llm_server}/v1"\napi_key = "mock"\nmodel = "mock-vision-model"\n'
    )
    monkeypatch.setenv("AUREKA_CONFIG", str(config))
    from aureka import config as cfg_mod, llm as llm_mod
    cfg_mod.reset_config()
    llm_mod._llm_client = None
    llm_mod._vlm_client = None
    yield
    llm_mod._llm_client = None
    llm_mod._vlm_client = None


def test_describe_frame(tmp_path):
    from aureka.llm import describe_frame
    from PIL import Image

    img_path = str(tmp_path / "frame.jpg")
    Image.new("RGB", (64, 64), color=(100, 100, 100)).save(img_path)

    result = describe_frame(img_path)
    assert isinstance(result, str)
    assert len(result) > 0


def test_llm_refine_stream():
    from aureka.llm import llm_refine_stream

    async def _collect():
        tokens = []
        async for t in llm_refine_stream("嗯、那個、今天天氣很好", mode="refine", lang="zh"):
            tokens.append(t)
        return "".join(tokens)

    result = asyncio.run(_collect())
    assert isinstance(result, str)
    assert len(result) > 0


def test_llm_translate_stream():
    from aureka.llm import llm_refine_stream

    async def _collect():
        tokens = []
        async for t in llm_refine_stream("今天天氣很好", mode="translate", lang="en"):
            tokens.append(t)
        return "".join(tokens)

    result = asyncio.run(_collect())
    assert isinstance(result, str)
    assert len(result) > 0
