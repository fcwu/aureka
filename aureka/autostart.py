"""Cross-platform autostart for the Aureka daemon.

macOS  -> launchd user agent (~/Library/LaunchAgents/com.aureka.daemon.plist)
Windows -> Task Scheduler at logon (schtasks /sc onlogon)
Linux  -> not implemented yet
"""
from __future__ import annotations

import getpass
import os
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.aureka.daemon"
WIN_TASK = "Aureka"


def _python() -> str:
    return sys.executable


def _config_path() -> str | None:
    p = os.environ.get("AUREKA_CONFIG")
    if p:
        return str(Path(p).resolve())
    cwd = Path.cwd() / "config.toml"
    return str(cwd.resolve()) if cwd.exists() else None


def _serve_args(host: str, port: int) -> list[str]:
    return [_python(), "-m", "aureka", "_daemon_serve", "--host", host, "--port", str(port)]


# ── macOS ────────────────────────────────────────────────────────────────────

def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _mac_log_dir() -> Path:
    d = Path.home() / "Library" / "Logs" / "Aureka"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mac_install(host: str, port: int) -> None:
    plist_path = _mac_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    log_dir = _mac_log_dir()
    cfg_path = _config_path()
    env = {"PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"}
    if cfg_path:
        env["AUREKA_CONFIG"] = cfg_path

    plist = {
        "Label": LABEL,
        "ProgramArguments": _serve_args(host, port),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False, "Crashed": True},
        "StandardOutPath": str(log_dir / "daemon.out.log"),
        "StandardErrorPath": str(log_dir / "daemon.err.log"),
        "EnvironmentVariables": env,
        "WorkingDirectory": str(Path.home()),
        "ProcessType": "Background",
    }
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

    uid = os.getuid()
    # Bootstrap (idempotent: bootout first if already loaded)
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}/{LABEL}"],
        capture_output=True, check=False,
    )
    r = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"launchctl bootstrap failed: {r.stderr.strip() or r.stdout.strip()}")

    print(f"[autostart] installed launch agent: {plist_path}")
    print(f"[autostart] logs: {log_dir}/daemon.{{out,err}}.log")


def _mac_uninstall() -> None:
    plist_path = _mac_plist_path()
    uid = os.getuid()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}/{LABEL}"],
        capture_output=True, check=False,
    )
    if plist_path.exists():
        plist_path.unlink()
        print(f"[autostart] removed: {plist_path}")
    else:
        print("[autostart] no launch agent installed")


def _mac_status() -> int:
    plist_path = _mac_plist_path()
    if not plist_path.exists():
        print("autostart: not installed")
        return 1

    uid = os.getuid()
    r = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{LABEL}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"autostart: plist present but not loaded ({plist_path})")
        return 1

    state = "unknown"
    pid = "-"
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith("state ="):
            state = s.split("=", 1)[1].strip()
        elif s.startswith("pid ="):
            pid = s.split("=", 1)[1].strip()
    print(f"autostart: installed (state={state}, pid={pid})")
    print(f"  plist: {plist_path}")
    return 0


# ── Windows ──────────────────────────────────────────────────────────────────

def _win_command(host: str, port: int) -> str:
    cfg_path = _config_path()
    parts = []
    if cfg_path:
        # `cmd /c "set X=Y && python ..."` to inject the env var
        parts.append(f'set "AUREKA_CONFIG={cfg_path}" && ')
    parts.append('"' + _python() + '"')
    parts.append(' -m aureka _daemon_serve')
    parts.append(f' --host {host} --port {port}')
    inner = "".join(parts)
    return f'cmd /c "{inner}"'


def _win_install(host: str, port: int) -> None:
    cmd = _win_command(host, port)
    user = getpass.getuser()
    r = subprocess.run(
        [
            "schtasks", "/create", "/f",
            "/tn", WIN_TASK,
            "/sc", "onlogon",
            "/ru", user,
            "/rl", "LIMITED",
            "/tr", cmd,
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"schtasks /create failed: {r.stderr.strip() or r.stdout.strip()}")
    print(f"[autostart] installed scheduled task: {WIN_TASK}")
    print(f"[autostart] command: {cmd}")


def _win_uninstall() -> None:
    r = subprocess.run(
        ["schtasks", "/delete", "/f", "/tn", WIN_TASK],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"[autostart] removed scheduled task: {WIN_TASK}")
    else:
        msg = (r.stderr or r.stdout).strip()
        if "ERROR: The system cannot find the file specified" in msg or "does not exist" in msg.lower():
            print("[autostart] no scheduled task installed")
        else:
            raise RuntimeError(f"schtasks /delete failed: {msg}")


def _win_status() -> int:
    r = subprocess.run(
        ["schtasks", "/query", "/tn", WIN_TASK, "/v", "/fo", "LIST"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("autostart: not installed")
        return 1
    next_run = "-"
    last_result = "-"
    for line in r.stdout.splitlines():
        if line.startswith("Next Run Time:"):
            next_run = line.split(":", 1)[1].strip()
        elif line.startswith("Last Result:"):
            last_result = line.split(":", 1)[1].strip()
    print(f"autostart: installed (next_run={next_run}, last_result={last_result})")
    return 0


# ── Dispatch ─────────────────────────────────────────────────────────────────

def install(host: str = "127.0.0.1", port: int = 7777) -> None:
    sysname = platform.system()
    if sysname == "Darwin":
        _mac_install(host, port)
    elif sysname == "Windows":
        _win_install(host, port)
    else:
        raise SystemExit(f"autostart not implemented on {sysname} (PRs welcome)")


def uninstall() -> None:
    sysname = platform.system()
    if sysname == "Darwin":
        _mac_uninstall()
    elif sysname == "Windows":
        _win_uninstall()
    else:
        raise SystemExit(f"autostart not implemented on {sysname}")


def status() -> int:
    sysname = platform.system()
    if sysname == "Darwin":
        return _mac_status()
    elif sysname == "Windows":
        return _win_status()
    else:
        print(f"autostart: not implemented on {sysname}")
        return 1
