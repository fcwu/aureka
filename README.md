# Aureka

> aural + eureka — 聽到，即發現知識

本機 AI 語音處理平台，兩個核心使用模式：

| 模式 | 說明 | 觸發方式 |
|------|------|----------|
| **批次處理** | 影片／音訊 → 結構化 Markdown，可丟入知識庫 | `aureka process` |
| **語音輸入** | 全域熱鍵 → 說話 → 文字出現在游標位置 | 常駐 daemon + 熱鍵 |

---

## 安裝

### PyPI（推薦）

```bash
# 基本安裝（daemon + LLM client）
pip install aureka

# 按需加裝功能模組
pip install "aureka[asr]"           # ASR（faster-whisper）
pip install "aureka[tts]"           # TTS（Kokoro）— 僅 Linux / macOS
pip install "aureka[batch]"         # 批次流水線（需另裝 ffmpeg，見下方）
pip install "aureka[voice]"         # 語音輸入 client（pynput/pystray）
pip install "aureka[all]"           # 以上全部（Windows 請用下方指令）
```

> **注意**：PyTorch 需依平台單獨安裝（見下方），不包含在 extras 中。

**Windows 用戶**：Kokoro TTS 目前無 Windows wheel，請跳過 `[tts]`：

```powershell
pip install "aureka[asr,batch,voice]"
```

### 從原始碼安裝

```bash
git clone https://github.com/fcwu/aureka
cd aureka
pip install -e ".[all]"
pip install -r requirements-dev.txt   # 測試用
```

### Python 版本

需要 Python **3.11 或 3.13**（推薦）。Python 3.14+ 目前許多 ML 套件尚未支援，請勿使用。

### PyTorch（依平台）

| 平台 | 指令 |
|------|------|
| NVIDIA GPU（Linux / Windows） | `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| AMD GPU（**僅 Linux**，ROCm 不支援 Windows） | `pip install torch --index-url https://download.pytorch.org/whl/rocm6.1` |
| Apple Silicon / CPU only | `pip install torch` |

> **Windows 用戶**：只支援 NVIDIA CUDA 或 CPU。若不確定，直接 `pip install torch` 即可（CPU 模式）。

### ffmpeg（批次處理必要）

```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# Fedora / RHEL
sudo dnf install ffmpeg

# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
# 或：choco install ffmpeg
```

### 設定檔

```bash
cp config.example.toml config.toml
# 編輯 config.toml：填入 LM Studio / Ollama 端點
```

最少需要設定 `[llm]` 和 `[vlm]` 的 `base_url`，其他欄位有預設值。

### 預先下載模型（建議）

首次執行 `aureka speak` / `aureka type` / `aureka daemon start` 會在背景從 HuggingFace 下載
ASR 與 TTS 權重（合計約 2GB），下載期間指令會看似 hang 住。建議先執行：

```bash
aureka download
```

這會把 Kokoro TTS 與 Whisper ASR 模型一次下載完，並顯示進度條。已下載的檔案會自動跳過。
HuggingFace cache 路徑可透過 `HF_HOME` 環境變數自訂。

---

## 批次處理

### 用法

```bash
# 處理影片（提取音訊 + 關鍵畫面 + ASR + VLM + LLM 摘要）
aureka process lecture.mp4

# 處理音訊（只有 ASR + LLM 摘要，無畫面分析）
aureka process podcast.mp3

# 自訂參數
aureka process video.mp4 --frame-interval 60 --device cuda --output-dir ~/notes/inbox
```

### 輸出

結果寫入 `output/YYYYMMDD-<slug>.md`，格式如下：

```markdown
---
source: video
original_file: lecture.mp4
duration: 45:32
processed_at: 2026-05-01T14:30:00
---

# <自動萃取的標題>

## 摘要
## 重點
## 逐段紀錄
## 視覺內容
## 原始轉錄
```

完成後可直接丟入 mykb `inbox/` 走 triage → ingest 流程。

---

## TTS 回讀

```bash
# 直接朗讀文字
aureka speak "今天的工作重點是什麼"

# 朗讀 Markdown 檔案（自動略過 frontmatter 和標記語法）
aureka speak --file path/to/note.md

# 存成 WAV 不播放
aureka speak "測試" --output out.wav
```

---

## 語音輸入（Typeless-like）

### 啟動 Daemon

```bash
# 啟動常駐 daemon（預載 ASR 模型，避免每次冷啟動）
aureka daemon start

# 確認狀態
aureka daemon status
# → Daemon: running (PID 12345) → http://127.0.0.1:7777

# 停止
aureka daemon stop
```

Daemon log：`/tmp/aureka-daemon.log`

### 啟動語音輸入 Client

```bash
aureka type            # 預設 refine 模式
aureka type --mode transcribe   # 直接轉錄，不過 LLM
aureka type --mode translate --lang en   # 說中文，輸出英文
```

或啟動系統托盤 client（有 GUI 圖示，可右鍵切換模式）：

```bash
python -m aureka._daemon_serve --host 127.0.0.1 --port 7777 &
python -c "from aureka.client import start_tray; start_tray()"
```

### 錄音模式（config.toml）

```toml
[hotkey]
trigger    = "<ctrl>+<alt>+space"
mode       = "hold-to-record"   # hold-to-record / toggle / vad
input_mode = "refine"           # transcribe / refine / translate
lang       = "zh"
```

| 模式 | 說明 |
|------|------|
| `hold-to-record` | 按住熱鍵錄音，放開停止（預設） |
| `toggle` | 按一下開始，再按停止 |
| `vad` | 偵測靜音自動停止 |

### AI 後處理模式

| 模式 | 說明 | 額外延遲 |
|------|------|----------|
| `transcribe` | 直接注入轉錄文字 | 0 |
| `refine` | 去除語氣詞、修正語法 | +1–2s |
| `translate` | 翻譯成指定語言 | +1–2s |

---

## 快速測試（不需真實 GPU 或模型）

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
# → {"status":"ok","version":"0.1.0"}
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

---

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

---

## 專案結構

```
aureka/
├── aureka/
│   ├── __main__.py       # CLI 入口（process / speak / type / daemon）
│   ├── config.py         # config.toml 載入（AUREKA_CONFIG env var）
│   ├── device.py         # 裝置偵測（cuda / mps / cpu）+ ASR 後端選擇
│   ├── asr.py            # ASR 統一介面（TheWhisper / faster-whisper）
│   ├── llm.py            # LLM / VLM 呼叫（OpenAI-compatible）
│   ├── tts.py            # Kokoro TTS 封裝 + Markdown 前處理
│   ├── pipeline.py       # 批次流程編排
│   ├── daemon.py         # FastAPI daemon（WebSocket /ws + HTTP）
│   ├── recorder.py       # 麥克風錄音（hold / toggle / VAD）
│   ├── hotkey.py         # 全域熱鍵（pynput）
│   ├── client.py         # 語音輸入 client（pystray + WebSocket）
│   ├── injector.py       # 文字注入（xdotool / 剪貼簿）
│   ├── ffmpeg_utils.py   # 音訊提取 + 關鍵畫面截取
│   └── formatter.py      # Markdown 輸出格式化
├── tests/
│   ├── conftest.py               # 共用 fixtures（mock server、config）
│   ├── test_device.py            # unit: 裝置偵測、ASR 後端選擇
│   ├── test_tts.py               # unit: Markdown 前處理
│   ├── test_injector.py          # unit: 文字注入邏輯
│   ├── test_llm.py               # integration: LLM/VLM client
│   ├── test_pipeline.py          # integration: 批次流水線
│   ├── test_daemon.py            # integration: HTTP + WebSocket
│   ├── test_e2e.py               # e2e: daemon 程序管理
│   ├── fixtures/                 # 測試音訊（gen-test-audio.py 生成）
│   └── scripts/
│       ├── gen-test-audio.py     # 生成測試 WAV fixtures
│       ├── mock-llm-server.py    # mock OpenAI-compatible server
│       └── ws-client-test.py     # WebSocket 手動測試工具
├── docs/
│   └── design.md
├── config.example.toml   # 設定範本
├── requirements.txt
└── requirements-dev.txt
```

---

## 平台支援

| 平台 | 語音輸入 | 批次處理 | ASR 加速 | TTS 加速 |
|------|---------|---------|---------|---------|
| NVIDIA Linux | ✅ | ✅ | CUDA (TheWhisper) | CUDA (Kokoro) |
| AMD Linux | ✅ | ✅ | ROCm (faster-whisper) | ROCm (Kokoro) |
| Apple Silicon | ✅ | ✅ | CoreML (TheWhisper) | MPS (Kokoro) |
| CPU only | ✅ | ✅ | CPU (faster-whisper) | CPU (Kokoro) |

> WSL2 為開發環境，GPU 不可用，所有測試以 CPU + mock 模式執行。

---

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `AUREKA_CONFIG` | config.toml 路徑 | `./config.toml` |
| `AUREKA_TEST_MODE` | 設 `1` 跳過模型載入（測試加速） | — |
| `AUREKA_LOG_LEVEL` | `debug` / `info` / `warning` | `info` |

---

## License

MIT
