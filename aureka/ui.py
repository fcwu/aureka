"""Settings UI: pywebview window backed by config.toml.

Launched via `aureka ui`. Reads/writes the same config.toml that daemon and
CLI use; integrates model download status, benchmark recommendations, and
hotkey capture so non-experts can configure Aureka end-to-end without
reading the docs.
"""
from __future__ import annotations

import json
import os
import socket
import threading
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from queue import Queue, Empty

from aureka.config import Config, load_config


# ── Static dropdown options ──────────────────────────────────────────────────

# Kokoro voices (subset; project-relevant zh + en — datalist allows custom)
TTS_VOICES = [
    "zf_xiaobei", "zm_yunxi", "zf_xiaoxiao", "zm_yunxia",
    "af_heart", "af_alloy", "am_michael", "am_eric",
]

# faster-whisper sizes — datalist (also accepts HF repo IDs)
ASR_MODELS = [
    "tiny", "base", "small", "medium",
    "large-v2", "large-v3", "large-v3-turbo",
]

# Common ISO codes — datalist
HOTKEY_LANGS = ["zh", "en", "ja", "ko", "es", "fr", "de"]

# Hostnames that pywebview can show as a select
DAEMON_HOSTS = ["127.0.0.1", "0.0.0.0"]


# ── HTML ─────────────────────────────────────────────────────────────────────

_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aureka Settings</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  if (window.tailwind) {
    tailwind.config = {
      darkMode: 'media',
      theme: {
        extend: {
          colors: { accent: { DEFAULT: '#3b82f6', soft: '#dbeafe', dark: '#1e3a8a' } },
        },
      },
    };
  }
</script>
<style>
  /* Fallback styles — used when Tailwind CDN can't load. Keep the form usable. */
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    font: 13px -apple-system, "Segoe UI", system-ui, sans-serif;
    margin: 0; height: 100vh; display: flex; flex-direction: column;
    background: #fafafa; color: #1a1a1a;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #0f0f10; color: #e5e5e5; }
  }
  .layout { display: flex; flex: 1; min-height: 0; }
  aside.nav { width: 168px; border-right: 1px solid #8884; padding: 12px 8px; flex-shrink: 0; }
  aside.nav button {
    display: block; width: 100%; text-align: left; padding: 7px 10px;
    border: 0; background: transparent; color: inherit; font: inherit;
    border-radius: 6px; cursor: pointer; margin-bottom: 2px;
  }
  aside.nav button.active { background: #3b82f622; color: #3b82f6; font-weight: 600; }
  main.body { flex: 1; overflow-y: auto; padding: 20px 24px; min-width: 0; }
  header.bar { padding: 14px 24px; border-bottom: 1px solid #8884; display: flex; align-items: baseline; justify-content: space-between; }
  header.bar h1 { margin: 0; font-size: 15px; font-weight: 600; }
  header.bar .path { font-size: 11px; color: #888; font-family: ui-monospace, Menlo, monospace; }
  .panel { display: none; }
  .panel.active { display: block; }
  .field { display: grid; grid-template-columns: 1fr 1.5fr; gap: 16px; padding: 12px 0; border-bottom: 1px solid #8881; align-items: start; }
  .field:last-child { border-bottom: 0; }
  .field .label { font-weight: 500; }
  .field .help { color: #888; font-size: 11px; margin-top: 2px; }
  .field input, .field select {
    width: 100%; padding: 7px 9px; border-radius: 6px;
    border: 1px solid #8886; background: transparent; color: inherit; font: inherit;
  }
  .field input:focus, .field select:focus { outline: 2px solid #3b82f6; outline-offset: -1px; border-color: transparent; }
  .row { display: flex; gap: 6px; }
  .row input { flex: 1; }
  .btn {
    padding: 7px 12px; border-radius: 6px; border: 1px solid #8886;
    background: transparent; color: inherit; font: inherit; cursor: pointer; white-space: nowrap;
  }
  .btn:hover { background: #8881; }
  .btn.primary { background: #3b82f6; border-color: #3b82f6; color: white; }
  .btn.primary:hover { background: #2563eb; }
  .btn.ghost { padding: 4px 9px; font-size: 11px; }
  footer.bar {
    padding: 10px 24px; border-top: 1px solid #8884;
    display: flex; align-items: center; gap: 10px;
  }
  footer.bar .status { flex: 1; font-size: 12px; color: #888; }
  footer.bar .status.ok { color: #16a34a; }
  footer.bar .status.err { color: #dc2626; }
  footer.bar .status.warn { color: #d97706; }
  .section-title { font-size: 13px; font-weight: 600; margin: 0 0 4px 0; }
  .section-desc { color: #888; font-size: 12px; margin: 0 0 12px 0; }
  .model-row {
    display: grid; grid-template-columns: 1fr auto; gap: 12px;
    padding: 14px; border: 1px solid #8884; border-radius: 8px; margin-bottom: 10px;
  }
  .model-row .repo { font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
  .model-row .meta { color: #888; font-size: 11px; margin-top: 4px; }
  .badge {
    display: inline-block; padding: 1px 6px; font-size: 10px; border-radius: 4px;
    background: #8882; vertical-align: middle; margin-left: 6px;
  }
  .badge.ok { background: #16a34a22; color: #16a34a; }
  .badge.miss { background: #d9770622; color: #d97706; }
  .badge.err { background: #dc262622; color: #dc2626; }
  .progress {
    height: 6px; background: #8882; border-radius: 3px; overflow: hidden; margin-top: 8px;
    grid-column: 1 / -1; display: none;
  }
  .progress > div { height: 100%; background: #3b82f6; width: 0%; transition: width .3s; }
  .progress.active { display: block; }
  .recommendations { display: grid; gap: 10px; margin-top: 14px; }
  .rec {
    border: 1px solid #3b82f655; border-radius: 8px; padding: 12px;
    background: #3b82f608; display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: start;
  }
  .rec .rec-title { font-weight: 600; }
  .rec .rec-reason { color: #888; font-size: 11px; margin-top: 4px; }
  pre.log {
    background: #00000010; border: 1px solid #8884; border-radius: 8px;
    padding: 10px 12px; height: 220px; overflow-y: auto; font-size: 11px;
    font-family: ui-monospace, Menlo, monospace; margin: 12px 0; white-space: pre-wrap;
  }
  @media (prefers-color-scheme: dark) {
    pre.log { background: #ffffff08; }
    .rec { background: #3b82f612; }
  }
</style>
</head>
<body class="bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-sans">
  <header class="bar">
    <h1 class="font-semibold text-[15px]">Aureka Settings</h1>
    <span class="path text-xs text-slate-500 font-mono" id="config-path"></span>
  </header>

  <div class="layout">
    <aside class="nav">
      <button data-tab="llm" class="active">LLM</button>
      <button data-tab="vlm">VLM</button>
      <button data-tab="asr">ASR</button>
      <button data-tab="tts">TTS</button>
      <button data-tab="hotkey">Hotkey</button>
      <button data-tab="daemon">Daemon</button>
      <button data-tab="models">Models</button>
      <button data-tab="tools">Tools</button>
    </aside>

    <main class="body">
      <!-- LLM -->
      <section class="panel active" id="llm">
        <h2 class="section-title">LLM endpoint</h2>
        <p class="section-desc">OpenAI-compatible chat completion server (LM Studio, Ollama, vLLM…).</p>
        <div class="field">
          <div><div class="label">Base URL</div><div class="help">e.g. <code>http://127.0.0.1:1234/v1</code> for LM Studio, <code>http://127.0.0.1:11434/v1</code> for Ollama.</div></div>
          <input data-k="llm.base_url">
        </div>
        <div class="field">
          <div><div class="label">API key</div><div class="help">Any string for LM Studio. Use <code>"ollama"</code> for Ollama.</div></div>
          <input data-k="llm.api_key">
        </div>
        <div class="field">
          <div><div class="label">Model</div><div class="help"><code>auto</code> picks the first model from the server. Type or pick from the list (fetched on open).</div></div>
          <input data-k="llm.model" list="llm-models">
        </div>
        <div class="field">
          <div><div class="label">Max tokens</div><div class="help">Total response budget incl. CoT. Reasoning models need ≥4K to leave room for the answer.</div></div>
          <input type="number" data-k="llm.max_tokens" min="64" max="32768">
        </div>
        <div class="field">
          <div><div class="label">Thinking budget</div><div class="help">qwen3 thinking-mode CoT cap. <code>0</code> disables; small int = brief CoT.</div></div>
          <input type="number" data-k="llm.thinking_budget" min="0" max="8192">
        </div>
        <datalist id="llm-models"><option value="auto"></option></datalist>
      </section>

      <!-- VLM -->
      <section class="panel" id="vlm">
        <h2 class="section-title">Vision LM endpoint</h2>
        <p class="section-desc">Used by the batch pipeline to caption video frames. Must be vision-capable.</p>
        <div class="field"><div><div class="label">Base URL</div><div class="help">Often the same endpoint as LLM if you load both there.</div></div><input data-k="vlm.base_url"></div>
        <div class="field"><div><div class="label">API key</div><div class="help"></div></div><input data-k="vlm.api_key"></div>
        <div class="field">
          <div><div class="label">Model</div><div class="help">Suggestions filtered to vision-capable IDs from the endpoint.</div></div>
          <input data-k="vlm.model" list="vlm-models">
        </div>
        <datalist id="vlm-models"><option value="auto"></option></datalist>
      </section>

      <!-- ASR -->
      <section class="panel" id="asr">
        <h2 class="section-title">Speech recognition</h2>
        <p class="section-desc">faster-whisper backend. Smaller models = faster but less accurate.</p>
        <div class="field">
          <div><div class="label">Model</div><div class="help">Standard sizes or any faster-whisper-compatible HF repo ID.</div></div>
          <input data-k="asr.model" list="asr-models">
        </div>
        <datalist id="asr-models">
          __ASR_OPTIONS__
        </datalist>
      </section>

      <!-- TTS -->
      <section class="panel" id="tts">
        <h2 class="section-title">Text-to-speech</h2>
        <p class="section-desc">Kokoro voice synthesis. Voice IDs ship with Kokoro; lang_code follows misaki tokenizer.</p>
        <div class="field">
          <div><div class="label">Voice</div><div class="help">Prefix: <code>zf_</code>/<code>zm_</code> = Chinese F/M, <code>af_</code>/<code>am_</code> = English F/M.</div></div>
          <input data-k="tts.voice" list="tts-voices">
        </div>
        <div class="field">
          <div><div class="label">Lang code</div><div class="help"><code>z</code> = Chinese, <code>a</code> = English (American).</div></div>
          <select data-k="tts.lang_code"><option>z</option><option>a</option></select>
        </div>
        <div class="field">
          <div><div class="label">Device</div><div class="help"><code>auto</code> picks the best available accelerator.</div></div>
          <select data-k="tts.device">
            <option>auto</option><option>cuda</option><option>mps</option><option>cpu</option>
          </select>
        </div>
        <div class="field">
          <div><div class="label">Speed</div><div class="help">1.0 = normal · 1.3 = faster · 0.8 = slower.</div></div>
          <input type="number" data-k="tts.speed" step="0.1" min="0.5" max="2.0">
        </div>
        <datalist id="tts-voices">
          __VOICE_OPTIONS__
        </datalist>
      </section>

      <!-- Hotkey -->
      <section class="panel" id="hotkey">
        <h2 class="section-title">Voice input hotkey</h2>
        <p class="section-desc">Global shortcut for the tray voice-input client.</p>
        <div class="field">
          <div><div class="label">Trigger</div><div class="help">pynput format. Click "Press…" to capture; ESC cancels.</div></div>
          <div class="row">
            <input data-k="hotkey.trigger">
            <button class="btn ghost" type="button" id="hk-capture">Press…</button>
          </div>
        </div>
        <div class="field">
          <div><div class="label">Pause hotkey</div><div class="help">Toggles capture pause/resume during voice input. Empty = no binding. Must differ from Trigger.</div></div>
          <div class="row">
            <input data-k="hotkey.pause">
            <button class="btn ghost" type="button" id="hk-capture-pause">Press…</button>
          </div>
        </div>
        <div class="field">
          <div><div class="label">Mode</div><div class="help"><code>hold-to-record</code> while pressed; <code>toggle</code> press to start/stop; <code>vad</code> auto-stops on silence.</div></div>
          <select data-k="hotkey.mode">
            <option>hold-to-record</option><option>toggle</option><option>vad</option>
          </select>
        </div>
        <div class="field">
          <div><div class="label">Input mode</div><div class="help"><code>transcribe</code> = raw text; <code>refine</code> = LLM cleanup; <code>translate</code> = LLM translate.</div></div>
          <select data-k="hotkey.input_mode">
            <option>transcribe</option><option>refine</option><option>translate</option>
          </select>
        </div>
        <div class="field">
          <div><div class="label">Lang</div><div class="help">ISO 639-1 hint passed to ASR.</div></div>
          <input data-k="hotkey.lang" list="hotkey-langs">
        </div>
        <div class="field">
          <div><div class="label">Topic / context</div><div class="help">Short phrase (≤200 chars) describing the domain — e.g. <code>"ZFS storage"</code>. Refine / translate add this as an LLM hint so jargon survives the rewrite. Empty = no hint.</div></div>
          <input data-k="hotkey.topic" maxlength="200" placeholder="e.g. ZFS storage administration">
        </div>
        <datalist id="hotkey-langs">
          __HKLANG_OPTIONS__
        </datalist>
      </section>

      <!-- Daemon -->
      <section class="panel" id="daemon">
        <h2 class="section-title">Daemon process</h2>
        <p class="section-desc">Background HTTP/WebSocket server that pre-loads ASR/TTS.</p>
        <div class="field">
          <div><div class="label">Host</div><div class="help"><code>127.0.0.1</code> = local only; <code>0.0.0.0</code> = LAN.</div></div>
          <select data-k="daemon.host">
            <option>127.0.0.1</option><option>0.0.0.0</option>
          </select>
        </div>
        <div class="field">
          <div><div class="label">Port</div><div class="help">Default 7777. "Auto" probes the next free port.</div></div>
          <div class="row">
            <input type="number" data-k="daemon.port" min="1" max="65535">
            <button class="btn ghost" type="button" id="port-auto">Auto</button>
          </div>
        </div>
        <div class="field"><div><div class="label">PID file</div><div class="help"></div></div><input data-k="daemon.pid_file"></div>
        <div class="field"><div><div class="label">Log file</div><div class="help"></div></div><input data-k="daemon.log_file"></div>
      </section>

      <!-- Models -->
      <section class="panel" id="models">
        <h2 class="section-title">Model downloads</h2>
        <p class="section-desc">Pre-fetch HuggingFace snapshots so the first <code>type</code> / <code>speak</code> doesn't stall.</p>
        <div id="model-list"><div class="text-xs text-slate-500">Loading…</div></div>
      </section>

      <!-- Tools -->
      <section class="panel" id="tools">
        <h2 class="section-title">Benchmark</h2>
        <p class="section-desc">Measure ASR / TTS / LLM speed and apply concrete configuration suggestions.</p>
        <div class="row" style="align-items:center">
          <button class="btn primary" type="button" id="bench-run">Run benchmark</button>
          <label style="font-size:12px; display:flex; align-items:center; gap:4px;">
            <input type="checkbox" id="bench-quick" checked> Quick (1 run/task)
          </label>
          <label style="font-size:12px; display:flex; align-items:center; gap:4px;">
            <input type="checkbox" id="bench-skip-llm"> Skip LLM
          </label>
          <span style="flex:1"></span>
        </div>
        <pre class="log" id="bench-log"></pre>
        <div class="recommendations" id="bench-recs"></div>
      </section>
    </main>
  </div>

  <footer class="bar">
    <span class="status" id="status">Edits save automatically.</span>
  </footer>

<script>
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ── Tab navigation ─────────────────────────────────────────────────────
  $$('aside.nav button').forEach(b => {
    b.onclick = () => activateTab(b.dataset.tab);
  });
  function activateTab(name) {
    $$('aside.nav button').forEach(x => x.classList.remove('active'));
    $$('section.panel').forEach(x => x.classList.remove('active'));
    $(`aside.nav button[data-tab="${name}"]`).classList.add('active');
    $(`section.panel#${name}`).classList.add('active');
    if (name === 'models') refreshModels();
  }

  // ── Status helper ──────────────────────────────────────────────────────
  function setStatus(msg, kind) {
    const el = $('#status');
    el.textContent = msg || '';
    el.className = 'status' + (kind ? ' ' + kind : '');
  }

  // ── Config load/save ───────────────────────────────────────────────────
  function applyConfig(cfg) {
    $$('[data-k]').forEach(el => {
      const [section, key] = el.dataset.k.split('.');
      const v = cfg?.[section]?.[key];
      el.value = (v === undefined || v === null) ? '' : String(v);
    });
    $('#config-path').textContent = cfg.__path__ || '';
  }
  function collect() {
    const data = {};
    $$('[data-k]').forEach(el => {
      const [section, key] = el.dataset.k.split('.');
      data[section] = data[section] || {};
      let v = el.value;
      if (el.type === 'number') v = (v === '' ? null : Number(v));
      data[section][key] = v;
    });
    return data;
  }
  // Auto-save: debounce per-field commits so quick edits coalesce into one
  // POST /reload but the user gets immediate feedback in the status bar.
  let _saveTimer = null;
  let _initialLoadDone = false;
  function scheduleSave() {
    if (!_initialLoadDone) return;  // suppress saves during applyConfig()
    setStatus('Saving…');
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(doSave, 350);
  }
  async function doSave() {
    const r = await window.pywebview.api.save_config(collect());
    if (!r || !r.ok) { setStatus('Error: ' + (r && r.error || 'unknown'), 'err'); return; }
    let msg = 'Saved';
    const rl = r.reload;
    if (rl && rl.reached) {
      if (rl.ok && (rl.needs_restart || []).length === 0) msg += ' · daemon reloaded';
      else if (rl.needs_restart && rl.needs_restart.length) {
        msg += ' · restart daemon for: ' + rl.needs_restart.join(', ');
        setStatus(msg, 'warn'); return;
      } else if (!rl.ok) msg += ' · reload failed: ' + (rl.error || 'unknown');
    } else { msg += ' · daemon not running'; }
    setStatus(msg, 'ok');
  }
  function bindAutoSave() {
    $$('[data-k]').forEach(el => {
      el.addEventListener('change', scheduleSave);  // SELECT: instant; INPUT: blur/Enter
    });
  }
  // Helper: programmatic value set that triggers the auto-save listener.
  function setFieldValue(el, value) {
    el.value = value;
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // ── LLM/VLM model dropdowns ────────────────────────────────────────────
  async function fillEndpointModels() {
    const llm = await window.pywebview.api.list_llm_models();
    const dl = $('#llm-models');
    dl.innerHTML = '';
    ['auto', ...(llm?.models || [])].forEach(id => {
      const o = document.createElement('option'); o.value = id; dl.appendChild(o);
    });
    const vlm = await window.pywebview.api.list_vlm_models();
    const dl2 = $('#vlm-models');
    dl2.innerHTML = '';
    ['auto', ...(vlm?.models || [])].forEach(id => {
      const o = document.createElement('option'); o.value = id; dl2.appendChild(o);
    });
  }

  // ── Models tab ─────────────────────────────────────────────────────────
  let _dl_polling = null;
  function fmtSize(n) {
    if (!n) return '0';
    if (n > 1e9) return (n/1e9).toFixed(2) + ' GB';
    if (n > 1e6) return (n/1e6).toFixed(1) + ' MB';
    if (n > 1e3) return (n/1e3).toFixed(0) + ' KB';
    return n + ' B';
  }
  async function refreshModels() {
    const status = await window.pywebview.api.model_status();
    const root = $('#model-list');
    root.innerHTML = '';
    Object.entries(status.models || {}).forEach(([key, m]) => {
      const row = document.createElement('div');
      row.className = 'model-row';
      row.dataset.key = key;
      const left = document.createElement('div');
      const badge = m.downloaded ? '<span class="badge ok">Downloaded</span>'
                                  : '<span class="badge miss">Not downloaded</span>';
      left.innerHTML =
        `<div class="repo"><strong>${key}</strong> · ${m.repo_id} ${badge}</div>` +
        `<div class="meta">${m.downloaded ? fmtSize(m.size_bytes) + ' on disk' : 'Run download to fetch ~' + (key === 'kokoro' ? '350 MB' : '1.5 GB')}</div>`;
      const btn = document.createElement('button');
      btn.className = 'btn'; btn.type = 'button';
      btn.textContent = m.downloaded ? 'Re-download' : 'Download';
      btn.onclick = () => triggerDownload(key);
      const prog = document.createElement('div');
      prog.className = 'progress'; prog.innerHTML = '<div></div>';
      row.appendChild(left); row.appendChild(btn); row.appendChild(prog);
      root.appendChild(row);
    });
  }
  async function triggerDownload(key) {
    await window.pywebview.api.start_download([key]);
    if (_dl_polling) clearInterval(_dl_polling);
    _dl_polling = setInterval(pollDownload, 500);
  }
  async function pollDownload() {
    const s = await window.pywebview.api.download_progress();
    if (!s) return;
    Object.entries(s.repos || {}).forEach(([key, info]) => {
      const row = document.querySelector(`.model-row[data-key="${key}"]`);
      if (!row) return;
      const prog = row.querySelector('.progress');
      const bar = prog.querySelector('div');
      const btn = row.querySelector('button');
      if (info.phase === 'start' || info.phase === 'progress') {
        prog.classList.add('active');
        bar.style.width = (info.percent || 8) + '%';
        btn.disabled = true;
      } else if (info.phase === 'done') {
        bar.style.width = '100%';
        setTimeout(() => prog.classList.remove('active'), 600);
        btn.disabled = false;
        const left = row.querySelector('.repo');
        if (left && !left.innerHTML.includes('Downloaded')) refreshModels();
      } else if (info.phase === 'error') {
        prog.classList.remove('active');
        btn.disabled = false;
        const meta = row.querySelector('.meta');
        meta.innerHTML = `<span class="badge err">Error</span> ${info.error || ''}`;
      }
    });
    if (s.done) { clearInterval(_dl_polling); _dl_polling = null; }
  }

  // ── Port auto-detect ───────────────────────────────────────────────────
  $('#port-auto').onclick = async () => {
    const cur = Number($('[data-k="daemon.port"]').value) || 7777;
    const r = await window.pywebview.api.find_free_port(cur);
    if (r && r.port) {
      setFieldValue($('[data-k="daemon.port"]'), r.port);
    } else {
      setStatus('No free port in range', 'err');
    }
  };

  // ── Hotkey capture ─────────────────────────────────────────────────────
  function bindCapture(btnId, fieldKey) {
    const btn = $(btnId);
    if (!btn) return;
    btn.onclick = function() {
      const input = document.querySelector(`[data-k="${fieldKey}"]`);
      btn.textContent = 'Press a key…';
      btn.disabled = true;
      function done(text) {
        btn.textContent = 'Press…'; btn.disabled = false;
        window.removeEventListener('keydown', onKey, true);
        if (text) setFieldValue(input, text);
      }
      function onKey(e) {
        e.preventDefault(); e.stopPropagation();
        if (e.key === 'Escape') { done(null); return; }
        const mods = [];
        if (e.ctrlKey)  mods.push('<ctrl>');
        if (e.altKey)   mods.push('<alt>');
        if (e.shiftKey) mods.push('<shift>');
        if (e.metaKey)  mods.push('<cmd>');
        if (['Control','Alt','Shift','Meta'].includes(e.key)) return;
        const main = e.key.length === 1 ? e.key.toLowerCase() : `<${e.key.toLowerCase()}>`;
        done([...mods, main].join('+'));
      }
      window.addEventListener('keydown', onKey, true);
    };
  }
  bindCapture('#hk-capture', 'hotkey.trigger');
  bindCapture('#hk-capture-pause', 'hotkey.pause');

  // Legacy single-binding (kept disabled to avoid double-bind)
  if (false) $('#hk-capture').onclick = function() {
    const btn = this;
    const input = $('[data-k="hotkey.trigger"]');
    btn.textContent = 'Press a key…';
    btn.disabled = true;
    function done(text) {
      btn.textContent = 'Press…'; btn.disabled = false;
      window.removeEventListener('keydown', onKey, true);
      if (text) setFieldValue(input, text);
    }
    function onKey(e) {
      e.preventDefault(); e.stopPropagation();
      if (e.key === 'Escape') { done(null); return; }
      const mods = [];
      if (e.ctrlKey)  mods.push('<ctrl>');
      if (e.altKey)   mods.push('<alt>');
      if (e.shiftKey) mods.push('<shift>');
      if (e.metaKey)  mods.push('<cmd>');
      // Skip if user only pressed a modifier
      if (['Control','Alt','Shift','Meta'].includes(e.key)) return;
      const main = e.key.length === 1 ? e.key.toLowerCase() : `<${e.key.toLowerCase()}>`;
      done([...mods, main].join('+'));
    }
    window.addEventListener('keydown', onKey, true);
  };

  // ── Benchmark ──────────────────────────────────────────────────────────
  let _bench_polling = null;
  $('#bench-run').onclick = async () => {
    const quick = $('#bench-quick').checked;
    const skipLlm = $('#bench-skip-llm').checked;
    $('#bench-log').textContent = '';
    $('#bench-recs').innerHTML = '';
    $('#bench-run').disabled = true;
    const r = await window.pywebview.api.start_benchmark(quick, skipLlm);
    if (!r || !r.ok) {
      setStatus('Benchmark error: ' + (r && r.error || 'unknown'), 'err');
      $('#bench-run').disabled = false;
      return;
    }
    if (_bench_polling) clearInterval(_bench_polling);
    _bench_polling = setInterval(pollBenchmark, 500);
  };
  async function pollBenchmark() {
    const s = await window.pywebview.api.benchmark_progress();
    if (!s) return;
    if (s.lines && s.lines.length) {
      const log = $('#bench-log');
      s.lines.forEach(l => log.textContent += l + '\n');
      log.scrollTop = log.scrollHeight;
    }
    if (s.done) {
      clearInterval(_bench_polling); _bench_polling = null;
      $('#bench-run').disabled = false;
      if (s.result && s.result.recommendations) renderRecommendations(s.result.recommendations);
    }
  }
  function renderRecommendations(recs) {
    const root = $('#bench-recs');
    root.innerHTML = '';
    if (!recs.length) {
      root.innerHTML = '<div class="text-xs text-slate-500">No specific recommendations — current settings look reasonable.</div>';
      return;
    }
    recs.forEach(r => {
      const card = document.createElement('div');
      card.className = 'rec';
      card.innerHTML =
        `<div><div class="rec-title">${r.title}</div><div class="rec-reason">${r.reason}</div></div>`;
      const btn = document.createElement('button');
      btn.className = 'btn primary'; btn.type = 'button'; btn.textContent = 'Apply';
      btn.onclick = () => {
        const k = `${r.section}.${r.key}`;
        const el = document.querySelector(`[data-k="${k}"]`);
        if (!el) return;
        setFieldValue(el, r.value);
        activateTab(r.section);
      };
      card.appendChild(btn);
      root.appendChild(card);
    });
  }

  // ── Init ───────────────────────────────────────────────────────────────
  window.addEventListener('pywebviewready', async () => {
    const cfg = await window.pywebview.api.load_config();
    applyConfig(cfg);
    setStatus('Edits save automatically.');
    fillEndpointModels().catch(() => {});  // best-effort
    bindAutoSave();
    _initialLoadDone = true;
  });
</script>
</body>
</html>
"""


def _options_html(values: list[str]) -> str:
    return "\n".join(f'<option value="{v}">' for v in values)


def _render_html() -> str:
    return (
        _HTML
        .replace("__ASR_OPTIONS__", _options_html(ASR_MODELS))
        .replace("__VOICE_OPTIONS__", _options_html(TTS_VOICES))
        .replace("__HKLANG_OPTIONS__", _options_html(HOTKEY_LANGS))
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _config_path() -> Path:
    return Path(os.environ.get("AUREKA_CONFIG", "config.toml")).resolve()


def _config_to_dict(cfg: Config) -> dict:
    out = {}
    for f in fields(cfg):
        v = getattr(cfg, f.name)
        out[f.name] = asdict(v) if is_dataclass(v) else v
    return out


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


def _try_reload_daemon() -> dict:
    """POST /reload to a running daemon. Returns a small status dict;
    'reached: False' if daemon isn't reachable (not an error)."""
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


def _fetch_models(base_url: str, api_key: str) -> list[dict]:
    """GET {base_url}/models. Returns a list of `{id, ...}` dicts. Empty on failure."""
    import urllib.request
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("data", [])
    except Exception:
        return []


def _is_vision_capable(model: dict) -> bool:
    """Heuristic: LM Studio exposes `compatibility_type` / `architectures`; many
    multimodal model IDs include `vision` / `vl` / `mm`. Be permissive — the user
    can always type a custom value."""
    blob = json.dumps(model).lower()
    return any(tok in blob for tok in ("vision", "image", "multimodal", "-vl", "_vl", "llava", "mm-"))


# ── Long-running task state (download + benchmark) ───────────────────────────

_dl_lock = threading.Lock()
_dl_state: dict = {"repos": {}, "done": True}

_bench_lock = threading.Lock()
_bench_state: dict = {"lines": [], "done": True, "result": None, "consumed": 0}


def _benchmark_recommendations(result: dict) -> list[dict]:
    """Inspect benchmark dict, return UI-renderable recommendations."""
    recs: list[dict] = []
    tasks = result.get("tasks", {})
    cfg = load_config(_config_path())

    # 1. ASR RTF too high → drop one size
    asr = tasks.get("asr") or {}
    if asr.get("status") == "ok" and (asr.get("median") or 0) > 0.5:
        cur = cfg.asr.model
        order = ["large-v3", "large-v3-turbo", "large-v2", "medium", "small", "base", "tiny"]
        if cur in order:
            i = order.index(cur)
            if i + 1 < len(order):
                recs.append({
                    "section": "asr", "key": "model",
                    "value": order[i + 1],
                    "title": f"ASR is slow — drop to {order[i + 1]}",
                    "reason": f"RTF median {asr['median']:.2f} > 0.5 with {cur}; smaller model trades accuracy for latency.",
                })

    # 2. LLM TTFT high with thinking on → disable thinking
    llm = tasks.get("llm") or {}
    if llm.get("status") == "ok":
        ttft = llm.get("median")
        if ttft and ttft > 3000 and (cfg.llm.thinking_budget or 0) > 0:
            recs.append({
                "section": "llm", "key": "thinking_budget",
                "value": 0,
                "title": "LLM TTFT > 3s — try disabling thinking",
                "reason": f"First-token latency median {ttft:.0f} ms; reasoning CoT often dominates this. Set thinking_budget=0 to compare.",
            })

    # 3. Device == cpu but TTS slow → suggest mps if Apple Silicon
    tts = tasks.get("tts") or {}
    if tts.get("status") == "ok" and (tts.get("median") or 0) > 0.4 and cfg.tts.device == "cpu":
        recs.append({
            "section": "tts", "key": "device",
            "value": "auto",
            "title": "TTS RTF > 0.4 on CPU — try device=auto",
            "reason": f"RTF {tts['median']:.2f} on CPU. `auto` will pick MPS/CUDA if available and re-measuring.",
        })

    return recs


# ── Api class (JS bridge) ────────────────────────────────────────────────────

class Api:
    # — Config —
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
            doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()

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
            path.write_text(tomlkit.dumps(doc), encoding="utf-8")
            return {"ok": True, "path": str(path), "reload": _try_reload_daemon()}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # — Endpoint model discovery —
    def list_llm_models(self):
        cfg = load_config(_config_path())
        items = _fetch_models(cfg.llm.base_url, cfg.llm.api_key)
        return {"models": [m["id"] for m in items if "id" in m]}

    def list_vlm_models(self):
        cfg = load_config(_config_path())
        items = _fetch_models(cfg.vlm.base_url, cfg.vlm.api_key)
        return {"models": [m["id"] for m in items if "id" in m and _is_vision_capable(m)]}

    # — Models tab —
    def model_status(self):
        try:
            from aureka.models import model_status
            return {"models": model_status()}
        except Exception as e:
            return {"models": {}, "error": f"{type(e).__name__}: {e}"}

    def start_download(self, keys):
        with _dl_lock:
            if not _dl_state.get("done", True):
                return {"ok": False, "error": "Download already in progress"}
            _dl_state.clear()
            _dl_state.update({"repos": {}, "done": False})

        def _run():
            from aureka.models import download_all

            def cb(event):
                with _dl_lock:
                    _dl_state["repos"][event["repo_key"]] = event
            try:
                download_all(progress=cb, keys=list(keys))
            except Exception:
                pass  # cb already recorded the error event
            finally:
                with _dl_lock:
                    _dl_state["done"] = True

        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True}

    def download_progress(self):
        with _dl_lock:
            return json.loads(json.dumps(_dl_state))  # cheap deep copy via JSON

    # — Port helper —
    def find_free_port(self, start):
        try:
            start = int(start)
        except (TypeError, ValueError):
            start = 7777
        for p in range(start, start + 64):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", p))
                s.close()
                return {"port": p}
            except OSError:
                continue
        return {"port": None}

    # — Benchmark —
    def start_benchmark(self, quick: bool, skip_llm: bool):
        with _bench_lock:
            if not _bench_state.get("done", True):
                return {"ok": False, "error": "Benchmark already running"}
            _bench_state.clear()
            _bench_state.update({"lines": [], "done": False, "result": None, "consumed": 0})

        def _run():
            from aureka.benchmark import run_benchmark

            def push(line):
                with _bench_lock:
                    _bench_state["lines"].append(line)

            try:
                result = run_benchmark(quick=bool(quick), skip_llm=bool(skip_llm), progress=push)
                # Flatten Path → str for JSON
                result["report_path"] = str(result.get("report_path", ""))
                result["recommendations"] = _benchmark_recommendations(result)
                with _bench_lock:
                    _bench_state["result"] = result
            except Exception as e:
                with _bench_lock:
                    _bench_state["lines"].append(f"[error] {type(e).__name__}: {e}")
            finally:
                with _bench_lock:
                    _bench_state["done"] = True

        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True}

    def benchmark_progress(self):
        with _bench_lock:
            consumed = _bench_state.get("consumed", 0)
            new_lines = _bench_state["lines"][consumed:]
            _bench_state["consumed"] = len(_bench_state["lines"])
            return {
                "lines": list(new_lines),
                "done": _bench_state["done"],
                "result": _bench_state.get("result"),
            }

    # — Window —
    def close(self):
        # Destroy on a short delay so the JS bridge RPC has a chance to return
        # before the window goes away — calling destroy() inside the bridge
        # worker thread can hang on macOS WKWebView.
        def _later():
            try:
                import webview
                for w in list(webview.windows):
                    try:
                        w.destroy()
                    except Exception:
                        pass
            except Exception:
                pass
        threading.Timer(0.05, _later).start()
        return {"ok": True}


def open_settings():
    try:
        import webview
    except ImportError as e:
        raise SystemExit(
            "pywebview not installed. Install with: pip install 'aureka[ui]'"
        ) from e

    webview.create_window(
        "Aureka Settings",
        html=_render_html(),
        js_api=Api(),
        width=760,
        height=600,
    )
    webview.start()


if __name__ == "__main__":
    open_settings()
