# Aureka

> aural + eureka — 聽到，即發現知識

本機 AI 語音處理平台。**所有 ASR / TTS / LLM 都跑在自己機器**（接 LM Studio / Ollama / vLLM），原始音訊不離開。

四個核心能力：

| 指令 | 場景 | 特色 |
|------|------|------|
| `aureka type` | 講話 → 直接打到任何 app 游標 | Streaming 邊講邊出字；LLM 修標點 / 刪贅字 / 翻譯 |
| `aureka listen` | 即時轉錄系統音訊（會議、影片、Podcast） | 跨平台 loopback；輸出檔 / 即時視窗 / mic + system 雙軌 |
| `aureka speak` | TTS 朗讀文字或 Markdown 檔 | Kokoro 中英雙語；daemon 共用 pipeline 低延遲 |
| `aureka process` | 影片／音訊批次 → 結構化 Markdown / SRT / VTT / 互動式 HTML | ASR + VLM 截圖描述 + LLM 摘要；`--diarize` 標記說話人；HTML 內建波形 + 點擊跳段 |

附帶：`aureka ui` 設定視窗 · `aureka tray` 系統托盤 · `aureka autostart` 登入自啟 · `aureka benchmark` 速度評測 · `aureka download` 一次抓所有模型。

<!-- @import "[TOC]" {cmd="toc" depthFrom=2 depthTo=3 orderedList=false} -->

<!-- code_chunk_output -->

- [安裝](#安裝)
  - [PyPI（推薦）](#pypi推薦)
  - [從原始碼安裝](#從原始碼安裝)
  - [Python 版本](#python-版本)
  - [PyTorch（依平台）](#pytorch依平台)
  - [ffmpeg（批次處理必要）](#ffmpeg批次處理必要)
  - [設定檔](#設定檔)
  - [即時轉錄（streaming）](#即時轉錄streaming)
  - [選 ASR 模型大小](#選-asr-模型大小)
  - [預先下載模型（建議）](#預先下載模型建議)
  - [Benchmark](#benchmark)
- [批次處理](#批次處理)
  - [用法](#用法)
  - [輸出](#輸出)
- [TTS 回讀](#tts-回讀)
- [語音輸入（Typeless-like）](#語音輸入typeless-like)
  - [啟動 Daemon](#啟動-daemon)
  - [啟動語音輸入 Client](#啟動語音輸入-client)
  - [錄音模式（config.toml）](#錄音模式configtoml)
  - [AI 後處理模式](#ai-後處理模式)
- [設定 UI（`aureka ui`）](#設定-uiaureka-ui)
- [開機自動啟動（`aureka autostart`）](#開機自動啟動aureka-autostart)
- [系統音訊轉錄（`aureka listen`）](#系統音訊轉錄aureka-listen)
- [診斷（`aureka doctor`）](#診斷aureka-doctor)
- [快速測試（不需真實 GPU 或模型）](#快速測試不需真實-gpu-或模型)
  - [Step 1：生成測試音訊](#step-1生成測試音訊)
  - [Step 2：啟動 mock LLM server](#step-2啟動-mock-llm-server)
  - [Step 3：啟動 daemon（測試模式，跳過模型載入）](#step-3啟動-daemon測試模式跳過模型載入)
  - [Step 4：測試 WebSocket 語音輸入](#step-4測試-websocket-語音輸入)
  - [Step 5：測試批次處理](#step-5測試批次處理)
- [執行測試](#執行測試)
- [平台支援](#平台支援)
- [環境變數](#環境變數)
- [License](#license)

<!-- /code_chunk_output -->

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
pip install "aureka[asr,batch,voice,ui]"
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

| 平台                                         | 指令                                                                     |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| NVIDIA GPU（Linux / Windows）                | `pip install torch --index-url https://download.pytorch.org/whl/cu121`   |
| AMD GPU（**僅 Linux**，ROCm 不支援 Windows） | `pip install torch --index-url https://download.pytorch.org/whl/rocm6.1` |
| Apple Silicon / CPU only                     | `pip install torch`                                                      |

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

### 即時轉錄（streaming）

`aureka type` 預設啟用 streaming：daemon 端用 silero-vad 切句，每段 close 立刻轉錄並推回 client。

行為依 mode 而異：

- **`transcribe` 模式**（純轉錄）：partial 文字直接打到游標，邊講邊出現
- **`refine` / `translate` 模式**：partial 文字**不**打到游標（避免你的草稿先被 raw 字污染、再被 LLM 改寫造成 flicker），只在 terminal 印 `[aureka] partial: ...` 當進度回饋；最終 LLM-refined 文字一次寫入草稿

要退回舊行為（錄完才轉）：

```bash
aureka type --no-streaming
```

技術上是 daemon 端用 silero-vad 偵測語句邊界，每段 close 時立刻轉錄並推 partial 回 client。silero-vad 無法載入時自動 fallback 回 buffer 模式。

過程中 daemon 會推 phase 事件回 client，stderr 會看到 `[aureka] transcribing audio... / finalizing last segment... / refining with LLM...`，方便判斷卡在哪一步。

### 選 ASR 模型大小

`config.toml` 的 `[asr] model` 欄位決定 faster-whisper 用哪個 size：

| Model                | 大小        | RTF（M3 MPS 為例） | 中文精度      | 適合                  |
| -------------------- | ----------- | ------------------ | ------------- | --------------------- |
| `tiny` / `base`      | 75 / 145 MB | < 0.1              | 低            | 老機器 / 只測試       |
| `small`              | 460 MB      | ~0.2               | 中            | 入門電腦              |
| **`medium`**（預設） | 1.5 GB      | ~0.4               | 高            | 中等 GPU、中等 Mac    |
| `large-v3`           | 3 GB        | > 1.0              | 最高          | 高階 GPU 或樂意等     |
| `large-v3-turbo`     | ~1.5 GB     | ~0.3               | 接近 large-v3 | 想要 large 精度但更快 |

跑 `aureka benchmark --quick --skip-llm` 看自己機器的 RTF 再決定。改完 config 後重跑 `aureka download` 會抓對應 model；舊 model cache 不會自動刪，要省空間用 `huggingface-cli delete-cache`。

### 預先下載模型（建議）

首次執行 `aureka speak` / `aureka type` / `aureka daemon start` 會在背景從 HuggingFace 下載
ASR 與 TTS 權重（合計約 2GB），下載期間指令會看似 hang 住。建議先執行：

```bash
aureka download
```

這會把 Kokoro TTS 與 Whisper ASR 模型一次下載完，並顯示進度條。已下載的檔案會自動跳過。
HuggingFace cache 路徑可透過 `HF_HOME` 環境變數自訂。

### Benchmark

想知道自己這台機器跑 ASR / TTS / LLM 的速度，或要分享給其他人比較硬體：

```bash
aureka benchmark              # 完整：每個任務 1 輪 warm-up + 5 輪計時
aureka benchmark --quick      # 快速：1 輪計時
aureka benchmark --skip-llm   # 跳過 LLM（沒設或不想測時用）
```

跑完會在當前目錄產生 `benchmark-<host>-<日期>.md`，包含環境資訊（Aureka 端硬體 + LLM 端設定）與
ASR / TTS RTF、LLM tokens/s 等指標，可貼到 issue / discussion 跟其他使用者比較。

#### 指標解讀

| Task / Metric                   | 意思                                                   | 怎麼看                                                                                                          |
| ------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **ASR RTF**                     | Real-Time Factor = 轉錄耗時 ÷ 音訊長度                 | **越小越好**。`< 1.0` = 比即時還快；`0.1` 表示處理 30 秒音訊只要 3 秒；`> 1.0` 代表跟不上即時，現場語音輸入會卡 |
| **ASR chars/s**                 | 每秒可輸出的字元數                                     | 越大越好；給人對「轉錄速度」的直覺感受                                                                          |
| **TTS RTF**                     | 合成耗時 ÷ 輸出音訊長度                                | **越小越好**。`< 1.0` = 比播放還快（可串流邊合成邊播）；`> 1.0` 表示要先合成完才能播，會有延遲                  |
| **TTS chars/s**                 | 每秒能合成的字元數                                     | 越大越好                                                                                                        |
| **LLM tokens/s**                | 串流輸出速度                                           | **越大越好**。30 token/s 大致是「人讀字的速度」；`< 10` 慢、`30-50` 順暢、`> 100` 即時感                        |
| **LLM TTFT (ms)**               | Time To First Token：送出 request 到收到第一個字的延遲 | **越小越好**。`< 200ms` 體感無延遲；`> 1000ms` 互動會明顯卡                                                     |
| **Cold start ASR/TTS load (s)** | 模型首次載入秒數                                       | 影響 daemon 第一次啟動 / 第一次 `aureka speak` 的等待時間，跑起來之後就不再付這個成本                           |

每個 row 都列 `Median / Min / Max`：看 Median 當代表值，Min/Max 之間差距大代表那台機器抖動明顯（背景有其他 process 競爭、或散熱不穩）。

`status` 欄為 `failed` 表示該任務當下跑不起來（如 LLM 連不上）；其他任務不受影響繼續跑。

#### LLM 數字的注意事項

`tokens/s` 與 `TTFT` 反映的是 **「LLM server + 你載入的模型 + LLM server 端硬體」三者組合**，不是跑 aureka 這台機器本身。比較不同人的 LLM 數字時，請看報告中 LLM endpoint 區塊的 `base_url` 與 `resolved_model` 是否相同。

## 批次處理

### 用法

```bash
# 處理影片（提取音訊 + 關鍵畫面 + ASR + VLM + LLM 摘要）
aureka process lecture.mp4

# 處理音訊（只有 ASR + LLM 摘要，無畫面分析）
aureka process podcast.mp3

# 自訂參數
aureka process video.mp4 --frame-interval 60 --device cuda --output-dir ~/notes/inbox

# 多種輸出格式：md（預設）/ srt / vtt / html / all / 逗號清單
aureka process lecture.mp4 --format html
aureka process lecture.mp4 --format md,srt,html

# 多人錄音：標記說話人（需 pip install "aureka[diarize]"）
aureka process interview.mp4 --diarize
aureka process panel.wav --diarize --num-speakers 3   # 已知 N 人時固定下來
aureka process podcast.mp3 --diarize --no-speaker-labels  # md/srt/vtt 不加 [S1] 前綴；html 仍上色
```

### 輸出格式

| 格式 | 用途 |
|------|------|
| `md` | 結構化 Markdown（含摘要、重點、逐段紀錄、視覺、原始轉錄）— 丟知識庫用 |
| `srt` / `vtt` | 標準字幕格式，可丟給影片播放器 |
| `html` | **互動式 transcript player**：自包含單檔，內嵌音訊 + canvas 波形；點任意段或波形位置跳到對應時間，scroll 到該段並 highlight；diarize 時各說話人不同色，波形上對應區段也標色 |

`--diarize` 用 resemblyzer + spectralcluster 做完全離線 voice clustering（不必 HuggingFace token、不像 pyannote 要授權）。第一次跑時自動抓 ~17MB 的 voice encoder weight。

### Markdown 輸出範例

`md` 格式寫入 `output/YYYYMMDD-<slug>.md`，內容結構：

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

## TTS 回讀

```bash
# 直接朗讀文字
aureka speak "今天的工作重點是什麼"

# 朗讀 Markdown 檔案（自動略過 frontmatter 和標記語法）
aureka speak --file path/to/note.md

# 存成 WAV 不播放
aureka speak "測試" --output out.wav

# 調整語速（1.0 = 正常、1.3 = 快、0.8 = 慢；也可在 [tts] speed 設預設）
aureka speak "再快一點" --speed 1.3
```

Daemon 在跑時 `aureka speak` 會打 daemon 的 `POST /speak` 端點共用已暖好的 Kokoro pipeline；daemon 沒在跑會 fallback 到本地冷啟動。

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
aureka type --topic "ZFS storage administration"   # 給 LLM 領域 hint，避免 jargon 被改錯
```

`--topic` 把一段短描述塞進 LLM refine / translate 的 prompt，引導模型用對的詞彙（例如「QNAP firmware」「醫療術語」「程式設計」）。空字串時 prompt 與舊版完全一致。也可以在 `[hotkey] topic = "..."` 設預設、CLI flag override。

或啟動系統托盤 client（有 GUI 圖示，可右鍵切換模式）：

```bash
aureka tray
```

`aureka tray` 啟動時若 daemon 沒在跑會**自動拉起**，所以不必再先 `aureka daemon start`。Quit 只關 tray、daemon 留著。

### 錄音模式（config.toml）

```toml
[hotkey]
trigger    = "<ctrl>+<alt>+space"
pause      = "<ctrl>+<alt>+p"   # 錄音中按一下「暫停」，再按「繼續」
mode       = "hold-to-record"   # hold-to-record / toggle / vad
input_mode = "refine"           # transcribe / refine / translate
lang       = "zh"
topic      = ""                 # 領域 hint（給 LLM refine/translate prompt）
```

| 模式             | 說明                           |
| ---------------- | ------------------------------ |
| `hold-to-record` | 按住熱鍵錄音，放開停止（預設） |
| `toggle`         | 按一下開始，再按停止           |
| `vad`            | 偵測靜音自動停止               |

**Pause 熱鍵**（`pause` 欄位）：錄音中（`aureka type` 或 `aureka listen`）按一下暫停、再按一下繼續——音訊靜悄悄被丟掉，但 LLM session 保留，講話的人短暫離席不必砍掉重來。Tray 選單也有「Pause capture」可勾。

### AI 後處理模式

| 模式         | 說明                 | 額外延遲 |
| ------------ | -------------------- | -------- |
| `transcribe` | 直接注入轉錄文字     | 0        |
| `refine`     | 去除語氣詞、修正語法 | +1–2s    |
| `translate`  | 翻譯成指定語言       | +1–2s    |

## 設定 UI（`aureka ui`）

```bash
aureka ui          # 開設定視窗（pywebview）
```

涵蓋 LLM / VLM / ASR / TTS / Hotkey / Daemon / Models / Tools 八個分頁。

- **自動儲存**：欄位離開焦點 / 按 Enter / select 改變即寫回 `config.toml`（保留註解）；daemon 在線會自動 `/reload`，需要重啟的欄位會在狀態列警告。
- **Models 分頁**：顯示 Kokoro 與 faster-whisper 是否已下載 + 大小，可直接按下載並看進度條。
- **Tools 分頁**：跑 quick benchmark，跑完依結果建議調整 `tts.device` / `asr.model` / `llm.thinking_budget`，按 Apply 就填到對應欄位。
- **Port Auto / Hotkey Press…**：兩個小按鈕分別自動找空 port、捕捉鍵盤組合填到 `daemon.port` / `hotkey.trigger`。
- 沒有 Save / Close 按鈕——靠系統視窗框關閉。

需要先安裝：

```bash
pip install "aureka[ui]"   # pywebview + tomlkit
```

## 開機自動啟動（`aureka autostart`）

跨平台把 `aureka tray` 註冊為登入時自動啟動：

```bash
aureka autostart install     # 安裝
aureka autostart uninstall   # 移除
aureka autostart status      # 查詢狀態
```

| 平台    | 機制               | 寫入位置                                         |
| ------- | ------------------ | ------------------------------------------------ |
| macOS   | launchd user agent | `~/Library/LaunchAgents/com.aureka.daemon.plist` |
| Windows | Task Scheduler     | task name `Aureka`（at-logon）                   |

啟動的命令是 `aureka tray`——tray 自動把 daemon 拉起，所以登入後 menu bar / system tray 出現 icon、daemon 同時在背景就緒、按下熱鍵立即可用。Quit-from-menu 不會被 launchd 重新拉起；crash 才會。

## 系統音訊轉錄（`aureka listen`）

把**電腦正在播的聲音**（不是麥克風）每 5 秒切一段、餵給 ASR、結果印到 stdout。常見用途：邊看 YouTube／開 Zoom／聽 Podcast 邊產出時間戳記字幕，或丟到檔案備查。

```bash
aureka listen                       # 預設 transcribe 模式，stdout 印每段時間戳 + 文字
aureka listen --mode refine         # 過 LLM 修標點刪贅字
aureka listen --mode translate --target en   # 邊聽邊翻成英文
aureka listen --out captions.txt    # 同時 append 到檔案
aureka listen --window              # 開一個 tail-style 視窗即時顯示
aureka listen --mic                 # 連麥克風一起抓（每段標 [system] 或 [mic]）
aureka listen --device "BlackHole 2ch"   # 指定 loopback 裝置（覆蓋自動偵測）
```

預設裝置是平台原生的 loopback：

| 平台    | 預設來源                                | 額外要裝                                                           |
| ------- | --------------------------------------- | ------------------------------------------------------------------ |
| macOS   | BlackHole / Loopback / Aggregate device | [BlackHole](https://github.com/ExistentialAudio/BlackHole)（免費） |
| Windows | WASAPI loopback                         | 內建                                                               |
| Linux   | PulseAudio / PipeWire monitor           | 內建（多數發行版）                                                 |

`config.toml` 的 `[listen]` 段可設預設值（mode / target_lang / window / out_path / device）。Ctrl+C 結束。

## 診斷（`aureka doctor`）

`listen` 跑不起來、loopback 找不到裝置、不知道哪個介面叫什麼名字 → 跑診斷：

```bash
aureka doctor audio
```

輸出當前平台所有偵測到的 loopback candidates 與 backend（pulseaudio / wasapi-loopback / coreaudio）。沒任何 candidate 時印安裝提示（如 macOS 提示裝 BlackHole）。將來可能新增 `aureka doctor llm` / `doctor models` 等其他 target。

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

## 平台支援

| 平台          | 語音輸入 | 批次處理 | ASR 加速              | TTS 加速      |
| ------------- | -------- | -------- | --------------------- | ------------- |
| NVIDIA Linux  | ✅       | ✅       | CUDA (faster-whisper) | CUDA (Kokoro) |
| AMD Linux     | ✅       | ✅       | ROCm (faster-whisper) | ROCm (Kokoro) |
| Apple Silicon | ✅       | ✅       | CPU (faster-whisper)  | MPS (Kokoro)  |
| CPU only      | ✅       | ✅       | CPU (faster-whisper)  | CPU (Kokoro)  |

> WSL2 為開發環境，GPU 不可用，所有測試以 CPU + mock 模式執行。

## 環境變數

| 變數                       | 說明                                           | 預設                   |
| -------------------------- | ---------------------------------------------- | ---------------------- |
| `AUREKA_CONFIG`            | config.toml 路徑                               | `./config.toml`        |
| `AUREKA_TEST_MODE`         | 設 `1` 跳過模型載入（測試加速）                | —                      |
| `AUREKA_LOG_LEVEL`         | `debug` / `info` / `warning`                   | `info`                 |
| `HF_HOME` / `HF_HUB_CACHE` | HuggingFace cache 路徑（aureka download 會吃） | `~/.cache/huggingface` |

## License

MIT
