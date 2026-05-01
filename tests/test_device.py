"""Unit tests for device detection and ASR backend selection."""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── resolve_device ─────────────────────────────────────────────────────────────

def test_resolve_device_explicit_cuda():
    from aureka.device import resolve_device
    assert resolve_device("cuda") == "cuda"


def test_resolve_device_explicit_cpu():
    from aureka.device import resolve_device
    assert resolve_device("cpu") == "cpu"


def test_resolve_device_auto_cuda():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    with patch.dict(sys.modules, {"torch": mock_torch}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_device("auto") == "cuda"


def test_resolve_device_auto_mps():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = True
    with patch.dict(sys.modules, {"torch": mock_torch}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_device("auto") == "mps"


def test_resolve_device_auto_cpu_fallback():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = False
    with patch.dict(sys.modules, {"torch": mock_torch}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_device("auto") == "cpu"


def test_resolve_device_no_torch():
    with patch.dict(sys.modules, {"torch": None}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_device("auto") == "cpu"


# ── resolve_asr_backend ───────────────────────────────────────────────────────

def test_resolve_asr_backend_cuda_with_thewhisper():
    mock_sk = MagicMock()
    with patch.dict(sys.modules, {"thestage_speechkit": mock_sk}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_asr_backend("cuda") == "thewhisper"


def test_resolve_asr_backend_cuda_without_thewhisper():
    with patch.dict(sys.modules, {"thestage_speechkit": None}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_asr_backend("cuda") == "faster-whisper"


def test_resolve_asr_backend_mps_with_thewhisper():
    mock_sk = MagicMock()
    with patch.dict(sys.modules, {"thestage_speechkit": mock_sk}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_asr_backend("mps") == "thewhisper"


def test_resolve_asr_backend_cpu_always_faster_whisper():
    mock_sk = MagicMock()
    with patch.dict(sys.modules, {"thestage_speechkit": mock_sk}):
        from aureka import device as dev_mod
        import importlib; importlib.reload(dev_mod)
        assert dev_mod.resolve_asr_backend("cpu") == "faster-whisper"
