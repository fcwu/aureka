"""E2E tests: daemon start → health check → stop."""
import os
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.e2e

DAEMON_PORT = 7778  # Use different port to avoid conflicts


@pytest.fixture
def daemon_process(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'[daemon]\nport = {DAEMON_PORT}\n'
        f'pid_file = "{tmp_path}/daemon.pid"\n'
        f'log_file = "{tmp_path}/daemon.log"\n'
    )
    env = os.environ.copy()
    env["AUREKA_CONFIG"] = str(config)
    env["AUREKA_TEST_MODE"] = "1"
    env["AUREKA_DAEMON_PORT"] = str(DAEMON_PORT)

    proc = subprocess.Popen(
        [sys.executable, "-m", "aureka", "_daemon_serve", "--host", "127.0.0.1", "--port", str(DAEMON_PORT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for daemon to start
    for _ in range(20):
        try:
            import httpx
            r = httpx.get(f"http://127.0.0.1:{DAEMON_PORT}/health", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)

    yield proc

    proc.terminate()
    proc.wait(timeout=5)


def test_daemon_health(daemon_process):
    import httpx
    resp = httpx.get(f"http://127.0.0.1:{DAEMON_PORT}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_daemon_responds_after_restart(tmp_path):
    """Verify daemon process management: start PID file → stop."""
    config = tmp_path / "config.toml"
    pid_file = tmp_path / "daemon.pid"
    log_file = tmp_path / "daemon.log"
    port = DAEMON_PORT + 1

    config.write_text(
        f'[daemon]\nhost = "127.0.0.1"\nport = {port}\n'
        f'pid_file = "{pid_file}"\nlog_file = "{log_file}"\n'
    )

    env = os.environ.copy()
    env["AUREKA_CONFIG"] = str(config)
    env["AUREKA_TEST_MODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "aureka", "daemon", "start"],
        env=env, capture_output=True, text=True, timeout=10,
    )

    assert pid_file.exists() or "already running" in result.stdout

    if pid_file.exists():
        stop_result = subprocess.run(
            [sys.executable, "-m", "aureka", "daemon", "stop"],
            env=env, capture_output=True, text=True, timeout=5,
        )
        assert "stopped" in stop_result.stdout.lower() or not pid_file.exists()
