"""Integration test for `aureka download` CLI subcommand.

Uses a sitecustomize shim to monkeypatch huggingface_hub.snapshot_download
in the subprocess so no real network calls happen.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def fake_hf_env(tmp_path, monkeypatch):
    """Create a sitecustomize.py that stubs snapshot_download to return tmp paths."""
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    fake_kokoro = tmp_path / "snapshots" / "kokoro"
    fake_fw = tmp_path / "snapshots" / "fw"
    fake_kokoro.mkdir(parents=True)
    fake_fw.mkdir(parents=True)

    shim = shim_dir / "sitecustomize.py"
    shim.write_text(textwrap.dedent(f"""
        import huggingface_hub

        _real = huggingface_hub.snapshot_download

        def _stub(repo_id, **kwargs):
            mapping = {{
                "hexgrad/Kokoro-82M": r"{fake_kokoro}",
                "Systran/faster-whisper-medium": r"{fake_fw}",
            }}
            return mapping[repo_id]

        huggingface_hub.snapshot_download = _stub
        # also patch the import inside aureka.models if already cached
        import sys as _sys
        if "aureka.models" in _sys.modules:
            _sys.modules["aureka.models"].snapshot_download = _stub
    """))

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{shim_dir}{os.pathsep}{existing}" if existing else str(shim_dir)
    )
    env["AUREKA_TEST_MODE"] = "1"
    return env, fake_kokoro, fake_fw


def test_download_command_cpu_succeeds(fake_hf_env):
    env, fake_kokoro, fake_fw = fake_hf_env
    result = subprocess.run(
        [sys.executable, "-m", "aureka", "--device", "cpu", "download"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    assert "hexgrad/Kokoro-82M" in result.stdout
    assert "Systran/faster-whisper-medium" in result.stdout
    assert str(fake_kokoro) in result.stdout
    assert str(fake_fw) in result.stdout
    # TheWhisper has been removed entirely
    assert "thewhisper" not in result.stdout.lower()
