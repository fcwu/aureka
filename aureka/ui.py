"""Settings UI: pywebview window backed by config.toml.

Launched via `aureka ui`. Reads/writes the same config.toml that daemon and CLI use.
"""
import json
import os
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path

from aureka.config import Config, load_config


_HTML = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Aureka Settings</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    font: 13px -apple-system, "Segoe UI", system-ui, sans-serif;
    margin: 0; padding: 16px;
  }
  .tabs { display: flex; gap: 4px; border-bottom: 1px solid #8884; margin-bottom: 16px; }
  .tab {
    padding: 8px 14px; cursor: pointer; border-radius: 6px 6px 0 0;
    border: 1px solid transparent;
  }
  .tab.active { background: #8881; border-color: #8884; border-bottom-color: transparent; }
  .panel { display: none; }
  .panel.active { display: block; }
  .row { display: grid; grid-template-columns: 160px 1fr; gap: 12px; align-items: center; margin-bottom: 10px; }
  label { color: #888; }
  input, select {
    padding: 6px 8px; border-radius: 6px; border: 1px solid #8886;
    background: transparent; color: inherit; font: inherit; width: 100%;
  }
  .footer {
    display: flex; justify-content: flex-end; align-items: center; gap: 8px;
    margin-top: 20px; padding-top: 12px; border-top: 1px solid #8884;
  }
  .status { color: #888; margin-right: auto; font-size: 12px; }
  .status.ok { color: #2a8; }
  .status.err { color: #c44; }
  button {
    padding: 7px 14px; border-radius: 6px; border: 1px solid #8886;
    background: transparent; color: inherit; font: inherit; cursor: pointer;
  }
  button.primary { background: #2d7ff9; border-color: #2d7ff9; color: white; }
</style>
</head>
<body>
  <div class="tabs">
    <div class="tab active" data-tab="llm">LLM</div>
    <div class="tab" data-tab="vlm">VLM</div>
    <div class="tab" data-tab="asr">ASR</div>
    <div class="tab" data-tab="tts">TTS</div>
    <div class="tab" data-tab="hotkey">Hotkey</div>
    <div class="tab" data-tab="daemon">Daemon</div>
  </div>

  <div class="panel active" id="llm">
    <div class="row"><label>Base URL</label><input data-k="llm.base_url"></div>
    <div class="row"><label>API key</label><input data-k="llm.api_key"></div>
    <div class="row"><label>Model</label><input data-k="llm.model"></div>
    <div class="row"><label>Max tokens</label><input type="number" data-k="llm.max_tokens"></div>
    <div class="row"><label>Thinking budget</label><input type="number" data-k="llm.thinking_budget"></div>
  </div>
  <div class="panel" id="vlm">
    <div class="row"><label>Base URL</label><input data-k="vlm.base_url"></div>
    <div class="row"><label>API key</label><input data-k="vlm.api_key"></div>
    <div class="row"><label>Model</label><input data-k="vlm.model"></div>
  </div>
  <div class="panel" id="asr">
    <div class="row"><label>Model</label><input data-k="asr.model"></div>
  </div>
  <div class="panel" id="tts">
    <div class="row"><label>Voice</label><input data-k="tts.voice"></div>
    <div class="row"><label>Lang code</label>
      <select data-k="tts.lang_code"><option>z</option><option>a</option></select>
    </div>
    <div class="row"><label>Device</label>
      <select data-k="tts.device">
        <option>auto</option><option>cuda</option><option>mps</option><option>cpu</option>
      </select>
    </div>
    <div class="row"><label>Speed</label><input type="number" step="0.1" data-k="tts.speed"></div>
  </div>
  <div class="panel" id="hotkey">
    <div class="row"><label>Trigger</label><input data-k="hotkey.trigger"></div>
    <div class="row"><label>Mode</label>
      <select data-k="hotkey.mode">
        <option>hold-to-record</option><option>toggle</option><option>vad</option>
      </select>
    </div>
    <div class="row"><label>Input mode</label>
      <select data-k="hotkey.input_mode">
        <option>transcribe</option><option>refine</option><option>translate</option>
      </select>
    </div>
    <div class="row"><label>Lang</label><input data-k="hotkey.lang"></div>
  </div>
  <div class="panel" id="daemon">
    <div class="row"><label>Host</label><input data-k="daemon.host"></div>
    <div class="row"><label>Port</label><input type="number" data-k="daemon.port"></div>
    <div class="row"><label>PID file</label><input data-k="daemon.pid_file"></div>
    <div class="row"><label>Log file</label><input data-k="daemon.log_file"></div>
  </div>

  <div class="footer">
    <span class="status" id="status"></span>
    <button onclick="window.pywebview.api.close()">Close</button>
    <button class="primary" onclick="save()">Save</button>
  </div>

<script>
  document.querySelectorAll('.tab').forEach(t => {
    t.onclick = () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      document.getElementById(t.dataset.tab).classList.add('active');
    };
  });

  function setStatus(msg, kind) {
    const el = document.getElementById('status');
    el.textContent = msg || '';
    el.className = 'status' + (kind ? ' ' + kind : '');
  }

  function applyConfig(cfg) {
    document.querySelectorAll('[data-k]').forEach(el => {
      const [section, key] = el.dataset.k.split('.');
      const v = cfg?.[section]?.[key];
      if (v === undefined || v === null) { el.value = ''; return; }
      el.value = String(v);
    });
  }

  function collect() {
    const data = {};
    document.querySelectorAll('[data-k]').forEach(el => {
      const [section, key] = el.dataset.k.split('.');
      data[section] = data[section] || {};
      let v = el.value;
      if (el.type === 'number') v = (v === '' ? null : Number(v));
      data[section][key] = v;
    });
    return data;
  }

  async function save() {
    setStatus('Saving…');
    const r = await window.pywebview.api.save_config(collect());
    if (!r || !r.ok) {
      setStatus('Error: ' + (r && r.error || 'unknown'), 'err');
      return;
    }
    let msg = 'Saved';
    const rl = r.reload;
    if (rl && rl.reached) {
      if (rl.ok && (rl.needs_restart || []).length === 0) {
        msg += ' · daemon reloaded';
      } else if (rl.needs_restart && rl.needs_restart.length) {
        msg += ' · daemon restart needed for: ' + rl.needs_restart.join(', ');
      } else if (!rl.ok) {
        msg += ' · reload failed: ' + (rl.error || 'unknown');
      }
    } else {
      msg += ' · daemon not running';
    }
    setStatus(msg, 'ok');
  }

  window.addEventListener('pywebviewready', async () => {
    const cfg = await window.pywebview.api.load_config();
    applyConfig(cfg);
    setStatus('Loaded from ' + cfg.__path__);
  });
</script>
</body>
</html>
"""


def _config_path() -> Path:
    return Path(os.environ.get("AUREKA_CONFIG", "config.toml")).resolve()


def _config_to_dict(cfg: Config) -> dict:
    out = {}
    for f in fields(cfg):
        v = getattr(cfg, f.name)
        out[f.name] = asdict(v) if is_dataclass(v) else v
    return out


def _try_reload_daemon() -> dict:
    """POST /reload to a running daemon. Returns a small status dict;
    'skipped' if daemon isn't reachable (not an error)."""
    import json
    import socket
    import urllib.request
    cfg = load_config(_config_path())
    host, port = cfg.daemon.host, cfg.daemon.port
    try:
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
    except OSError:
        return {"reached": False, "reason": "daemon not running"}
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/reload", method="POST",
            headers={"Content-Type": "application/json"},
            data=b"{}",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return {"reached": True, **json.loads(resp.read().decode("utf-8"))}
    except Exception as e:
        return {"reached": True, "ok": False, "error": f"{type(e).__name__}: {e}"}


def _coerce(value, current):
    """Coerce JS-incoming value to match the type of the current dataclass field."""
    if value is None or value == "":
        return None if current is None else current
    if isinstance(current, bool):
        return bool(value)
    if isinstance(current, int) and not isinstance(current, bool):
        return int(value)
    if isinstance(current, float):
        return float(value)
    return str(value)


class Api:
    def load_config(self):
        path = _config_path()
        cfg = load_config(path)
        data = _config_to_dict(cfg)
        data["__path__"] = str(path)
        return data

    def save_config(self, payload):
        try:
            import tomlkit
        except ImportError:
            return {"ok": False, "error": "tomlkit not installed (pip install aureka[ui])"}

        path = _config_path()
        try:
            current = load_config(path)
            doc = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()

            for section_name in ("llm", "vlm", "asr", "tts", "daemon", "hotkey"):
                section = payload.get(section_name) or {}
                if not section:
                    continue
                if section_name not in doc:
                    doc[section_name] = tomlkit.table()
                current_section = getattr(current, section_name)
                for key, raw in section.items():
                    if not hasattr(current_section, key):
                        continue
                    coerced = _coerce(raw, getattr(current_section, key))
                    if coerced is None:
                        if key in doc[section_name]:
                            del doc[section_name][key]
                    else:
                        doc[section_name][key] = coerced

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(tomlkit.dumps(doc))
            return {"ok": True, "path": str(path), "reload": _try_reload_daemon()}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def close(self):
        try:
            import webview
            for w in webview.windows:
                w.destroy()
        except Exception:
            pass


def open_settings():
    try:
        import webview
    except ImportError as e:
        raise SystemExit(
            "pywebview not installed. Install with: pip install 'aureka[ui]'"
        ) from e

    webview.create_window(
        "Aureka Settings",
        html=_HTML,
        js_api=Api(),
        width=640,
        height=560,
    )
    webview.start()


if __name__ == "__main__":
    open_settings()
