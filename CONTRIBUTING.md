# Contributing to Aureka

開發、測試、debug 相關資訊。User-facing 的「裝完就用」流程在 [README.md](README.md)。

## 快速測試（不需真實 GPU 或模型）

`AUREKA_TEST_MODE=1` 跳過 ASR/TTS 模型載入，配上 mock LLM server 可以在 CPU-only 機器（或 WSL2 / CI）上跑完整流程驗證。

### Step 1：生成測試音訊

```bash
python tests/scripts/gen-test-audio.py
# → tests/fixtures/silence-1s.wav
# → tests/fixtures/speech-zh.wav
```

### Step 2：啟動 mock LLM server

```bash
python tests/scripts/mock-llm-server.py --port 11434 &
# 模擬 /v1/chat/completions（含 vision）和 /v1/models
```

### Step 3：啟動 daemon（測試模式，跳過模型載入）

```bash
AUREKA_TEST_MODE=1 AUREKA_CONFIG=tests/config.test.toml aureka daemon start
curl http://127.0.0.1:7777/health
# → {"status":"ok","version":"0.2.0"}
```

### Step 4：測試 WebSocket 語音輸入

```bash
python tests/scripts/ws-client-test.py \
  --audio tests/fixtures/speech-zh.wav \
  --mode transcribe

# 預期輸出：
# [←] {"type": "transcript", "text": "[mock transcript]", "final": true}
# [←] {"type": "done"}
```

```bash
python tests/scripts/ws-client-test.py \
  --audio tests/fixtures/speech-zh.wav \
  --mode refine

# 預期輸出：
# [←] {"type": "transcript", ...}
# [←] {"type": "refined", "text": "這是一段經過整理的文字。", "final": true}
# [←] {"type": "done"}
```

### Step 5：測試批次處理

```bash
AUREKA_TEST_MODE=1 AUREKA_CONFIG=tests/config.test.toml \
  aureka process tests/fixtures/silence-1s.wav --output-dir /tmp/aureka-out
# → /tmp/aureka-out/YYYYMMDD-silence-1s.md
```

## 執行測試

```bash
# 全部測試（unit + integration + e2e）
pytest tests/ -v

# 只跑 unit（快，無外部相依）
pytest tests/ -v -m unit

# 只跑 integration（需 mock LLM server，由 conftest 自動啟動）
pytest tests/ -v -m integration

# 只跑 e2e（啟動真實 daemon 子程序）
pytest tests/ -v -m e2e
```

CI matrix 跑 ubuntu / macOS / Windows × Python 3.11 / 3.13。

## 開發環境備註

- **WSL2** GPU 不可用，所有測試以 CPU + mock 模式執行
- **CI** 不裝 `[asr]` / `[tts]` extra 以省 torch / kokoro 安裝時間，改在 `.github/workflows/ci.yml` 直接裝測試會 import / patch 到的小型 deps（`huggingface_hub`、`silero-vad`、`tomlkit`、`pywebview`）

## 計畫中的 doctor target

`aureka doctor audio` 已實作，未來可能擴充：

- `aureka doctor llm` — 確認 `cfg.llm.base_url` 端點存活、列 `/v1/models` 結果、量 TTFT 給快速 sanity check
- `aureka doctor models` — 對 `model_registry()` 每個 entry 跑 `huggingface_hub.scan_cache_dir`，回報哪些已下載 / 缺哪些 / 各佔多大

兩個都是「`listen` / `type` 不會動時，第一手診斷」的延伸；歡迎 PR。

## OpenSpec 流程

新功能走 OpenSpec change：

```bash
openspec new change "<kebab-case-name>"
# 寫 proposal.md / design.md / specs/**/*.md / tasks.md
openspec validate <name> --strict
# 實作 + 跑測試
openspec archive <name> --yes   # sync delta 到 openspec/specs/
```

archived changes 在 `openspec/changes/archive/<YYYY-MM-DD>-<name>/`，spec 真相在 `openspec/specs/<capability>/spec.md`。

## Release 流程

```bash
# bump pyproject.toml + aureka/__init__.py 到新版本
git commit -m "chore: bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z

<release notes...>"
git push origin main
git push origin vX.Y.Z
```

`publish.yml` 收到 `v*` tag 會：build → publish PyPI → 自動建立 GitHub Release（annotation 多於 3 行就用 annotation；否則 `--generate-notes`）。
