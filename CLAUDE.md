# Aureka 開發指南

通用設定與除錯方法。環境特定值（LM Studio URL、模型 ID）記錄在 `tests/.env.local.md`（本機專用，不進 git）。

---

## 1. 安裝與設定

### 安裝相依套件

```bash
# 建議用 venv
python -m venv .venv && source .venv/bin/activate

# 安裝（依平台選 PyTorch，見下方）
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### PyTorch 依平台

```bash
# NVIDIA CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu121

# AMD ROCm（native Linux）
pip install torch --index-url https://download.pytorch.org/whl/rocm6.1

# Apple Silicon / CPU
pip install torch
```

### ffmpeg 系統套件

```bash
sudo apt install ffmpeg          # Ubuntu/Debian
sudo dnf install ffmpeg          # Fedora/RHEL
brew install ffmpeg              # macOS
winget install ffmpeg            # Windows
```

### 設定檔

```bash
cp config.example.toml config.toml
# 編輯 config.toml：設定 LM Studio endpoint、hotkey 等
```

### 預先下載模型（建議）

首次跑 `speak` / `type` / `daemon start` 會在背景從 HuggingFace 抓 Kokoro + Whisper（~2GB），
看起來像卡住。先跑 `aureka download` 把模型一次備齊（idempotent，重跑會跳過已下載項目）。
受 `HF_HOME` 環境變數影響。

---

## 2. 啟動 Daemon

```bash
# 啟動（預載 ASR + TTS 模型）
python -m aureka daemon start

# 確認
curl http://127.0.0.1:7777/health

# 停止
python -m aureka daemon stop
```

Daemon log 位置：`/tmp/aureka-daemon.log`

---

## 3. 執行測試

```bash
# 全部測試
pytest tests/ -v

# 只跑 unit
pytest tests/ -v -m unit

# 只跑 integration（不需啟動 daemon）
pytest tests/ -v -m integration

# 只跑 E2E（需先啟動 daemon）
pytest tests/ -v -m e2e
```

測試報告輸出至 `tests/test-report-<YYYY-MM-DD-HHmm>-<stem>.md`，qa agent 負責維護。

---

## 4. Mock LM Studio（測試用）

不想依賴真實 LM Studio 時，啟動內建 mock server：

```bash
python tests/scripts/mock-llm-server.py --port 11434
# 模擬 /v1/chat/completions（回傳固定文字）
# 模擬 /v1/models（回傳含 vision 支援的假模型）
```

config.toml 指向 mock：

```toml
[llm]
base_url = "http://127.0.0.1:11434/v1"
api_key  = "mock"
model    = "mock-model"
```

---

## 5. 測試用假音訊

unit / integration 測試用的假 WAV（16kHz mono，1 秒靜音）：

```bash
python tests/scripts/gen-test-audio.py
# 輸出 tests/fixtures/silence-1s.wav、tests/fixtures/speech-zh.wav
```

`speech-zh.wav` 為預錄中文句子（「今天天氣很好」），用於 ASR 輸出驗證。

---

## 6. WebSocket 快速診斷

```bash
# 手動測試語音輸入 WS
python tests/scripts/ws-client-test.py --mode transcribe --audio tests/fixtures/speech-zh.wav

# 預期輸出：
# {"type": "transcript", "text": "今天天氣很好", "final": true}
# {"type": "done"}
```

| 現象 | 意義 |
|------|------|
| WS 連線 1006 立刻斷 | Daemon 沒啟動 |
| `transcript` 一直不來 | ASR 模型未載入（看 daemon log） |
| `refined` 超過 5s 才來 | LM Studio 無回應或模型未載 |
| `done` 不出現 | 沒送 `{"type":"end"}` |

---

## 7. 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `AUREKA_CONFIG` | config.toml 路徑 | `./config.toml` |
| `AUREKA_DAEMON_PORT` | Daemon HTTP/WS port | `7777` |
| `AUREKA_LOG_LEVEL` | `debug` / `info` / `warning` | `info` |
| `AUREKA_TEST_MODE` | 設 `1` 跳過模型載入（加速測試） | — |
