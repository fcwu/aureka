"""Unit tests for client-side streaming-partial inject behavior.

In refine/translate modes, partial transcripts must NOT be injected into the
cursor (they would be rewritten by the LLM-refined text). Only the final
refined text gets injected. In transcribe mode, partials ARE injected.
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class _FakeWS:
    """Async WS double — feeds canned server messages to client._voice_session."""

    def __init__(self, server_msgs: list[dict]):
        self.sent: list[str] = []
        self._msgs = list(server_msgs)
        self._closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, payload):
        self.sent.append(payload)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._msgs:
            raise StopAsyncIteration
        return json.dumps(self._msgs.pop(0))


def _patch_ws(server_msgs):
    fake = _FakeWS(server_msgs)
    @asyncio.coroutine if False else None  # dummy to keep linter happy
    async def fake_connect(url):
        return fake
    return fake, fake_connect


async def _run_session(mode: str, server_msgs: list[dict], inj):
    """Helper that runs _voice_session against a fake WS + fake injector."""
    from aureka import client as client_mod

    fake = _FakeWS(server_msgs)

    class _ConnCM:
        async def __aenter__(self):
            return fake

        async def __aexit__(self, *exc):
            return False

    fake_websockets = MagicMock()
    fake_websockets.connect = MagicMock(return_value=_ConnCM())

    with patch.dict("sys.modules", {"websockets": fake_websockets}), \
         patch.object(client_mod, "injector", inj):
        await client_mod._voice_session(mode, "zh", b"\x00" * 100, streaming=True)


def test_transcribe_mode_injects_partials():
    inj = MagicMock()
    msgs = [
        {"type": "transcript", "text": "hello ", "is_partial": True},
        {"type": "transcript", "text": "world", "is_partial": True},
        {"type": "done"},
    ]
    asyncio.run(_run_session("transcribe", msgs, inj))
    # inject_text called for each partial
    assert inj.inject_text.call_count == 2
    inj.inject_text.assert_any_call("hello ")
    inj.inject_text.assert_any_call("world")
    inj.replace_text.assert_not_called()


def test_refine_mode_does_not_inject_partials():
    inj = MagicMock()
    msgs = [
        {"type": "transcript", "text": "hello ", "is_partial": True},
        {"type": "transcript", "text": "world", "is_partial": True},
        {"type": "refined", "text": "Hello, world.", "final": True},
        {"type": "done"},
    ]
    asyncio.run(_run_session("refine", msgs, inj))
    # inject_text never called during partial phase
    inj.inject_text.assert_not_called()
    # replace_text called once with the refined text (injected_len=0 → equivalent to inject)
    inj.replace_text.assert_called_once_with(0, "Hello, world.")


def test_translate_mode_does_not_inject_partials():
    inj = MagicMock()
    msgs = [
        {"type": "transcript", "text": "你好", "is_partial": True},
        {"type": "refined", "text": "Hello.", "final": True},
        {"type": "done"},
    ]
    asyncio.run(_run_session("translate", msgs, inj))
    inj.inject_text.assert_not_called()
    inj.replace_text.assert_called_once_with(0, "Hello.")
