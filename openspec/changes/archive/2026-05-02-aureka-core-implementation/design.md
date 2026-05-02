## Context

Aureka 是全新專案，無既有程式碼。目標是本地 AI 語音處理平台，支援批次影片/音訊轉知識庫，以及全域熱鍵語音輸入兩個主要使用情境。

核心約束：
- 本地執行，不依賴雲端 API（ASR/TTS 本地模型；LLM/VLM 透過 OpenAI-compatible 本地端點）
- 跨平台：NVIDIA Linux、AMD Linux、Apple Silicon、CPU fallback
- 模型冷啟動 5-15 秒，語音輸入需 daemon 架構避免每次重載

## Goals / Non-Goals

**Goals:**
- 批次流水線：video/audio → Markdown（含 ASR、VLM 畫面描述、LLM 摘要）
- 語音輸入：熱鍵觸發 → 錄音 → ASR → 可選 LLM 後處理 → 注入游標
- Daemon：FastAPI + WebSocket，預載模型，提供串流介面
- 多平台 ASR：TheWhisper（NVIDIA/Apple Silicon）自動 fallback 到 faster-whisper
- TTS 回讀：Kokoro 本地 TTS
- CLI：`aureka process / speak / type / daemon` 子命令

**Non-Goals:**
- Windows native 支援（未來另立專案）
- WSL2 作為部署目標（僅開發環境）
- 雲端 ASR/TTS 服務整合
- GUI 應用程式（僅 CLI + 系統托盤）

## Decisions

### D1：Daemon 架構（FastAPI + WebSocket）

**決策**：使用 FastAPI + uvicorn 作為 daemon，WebSocket 提供串流語音介面，HTTP POST 提供批次介面。

**理由**：
- 模型冷啟動 5-15 秒，必須 daemon 預載；WebSocket 支援串流輸出，使用者可即時看到轉錄文字（TTFT 優先）
- FastAPI 原生支援 async/WebSocket，適合串流場景
- 替代方案（Unix socket + 自訂協定）維護成本高，放棄

### D2：ASR 後端策略（TheWhisper 優先，faster-whisper fallback）

**決策**：`resolve_asr_backend()` 在 cuda/mps 裝置上嘗試 import TheWhisper，失敗則 fallback 到 faster-whisper；AMD ROCm/CPU 直接用 faster-whisper。

**理由**：
- TheWhisper 在 NVIDIA/Apple Silicon 有顯著優勢（WER -25%，TTFT 12ms），但非所有環境都能安裝
- faster-whisper 支援 ROCm 且在 CPU 比原版快 4x，是可靠的通用 fallback
- 統一介面（`asr.transcribe(audio)`）讓上層程式碼不感知後端差異

### D3：文字注入策略（平台差異）

**決策**：macOS 用 pyautogui Cmd+V（剪貼簿注入），Windows 用 Ctrl+V，Linux X11 優先用 `xdotool type`，失敗則剪貼簿。

**理由**：
- `xdotool type` 對 CJK 字元支援有風險，剪貼簿作為備援
- pyautogui 跨平台但剪貼簿會覆蓋使用者內容，須謹慎
- 替換注入（refine 模式）：記錄上次注入字數，先退格再注入新文字

### D4：串流協定設計

**決策**：Client → Server 送 JSON 控制訊息 + base64 PCM chunks；Server → Client 串流 `transcript`/`refined`/`done` 事件。

**理由**：
- JSON over WebSocket 比二進位協定更易除錯與擴充
- base64 PCM（16kHz mono int16）統一格式，避免音訊編解碼複雜度
- `final` 旗標讓 client 知道何時可以替換前次注入

### D5：模組邊界

```
aureka/
  config.py     → 載入 config.toml，全域單例
  device.py     → 平台偵測（cuda/mps/cpu）+ ASR backend 選擇
  asr.py        → 統一 ASR 介面（隱藏 TheWhisper/faster-whisper 差異）
  llm.py        → OpenAI client 封裝（LLM + VLM）
  tts.py        → Kokoro 封裝
  daemon.py     → FastAPI app（WebSocket /ws + POST /process + GET /health）
  pipeline.py   → 批次流程編排（呼叫 ffmpeg_utils → asr → llm → formatter）
  recorder.py   → 麥克風錄音（hold/toggle/VAD 三種模式）
  hotkey.py     → pynput 全域熱鍵
  client.py     → 語音輸入 client（pystray + hotkey + recorder + websockets）
  injector.py   → 文字注入（pyautogui / xdotool，依平台）
  ffmpeg_utils.py → 音訊軌提取 + 關鍵畫面截取
  formatter.py  → 批次輸出 Markdown 格式化
```

## Risks / Trade-offs

- **[Risk] TheWhisper 中文 WER 未實測** → 優先跑 faster-whisper 中文基準，如不達標則 fallback 策略不變但 TheWhisper 非必要
- **[Risk] xdotool CJK 注入** → 備援剪貼簿路徑已設計，測試時需驗證 Unicode 注入
- **[Risk] pynput Linux X11 權限** → 需確認 display server 存取；Wayland 不支援（明確排除）
- **[Risk] LM Studio 模型未載入時 VLM fatal** → `check_vlm_supports_vision()` 在 daemon 啟動時執行，提早失敗比執行到一半再崩潰好
- **[Trade-off] 剪貼簿注入會覆蓋使用者剪貼簿** → 注入後即時恢復原始剪貼簿內容（pyperclip read → inject → restore）

## Open Questions

- TheWhisper 中文 WER 實際數字（需實測）
- faster-whisper CPU 模式處理 45 分鐘音訊的實際耗時
- VAD 靜音閾值最佳預設值
- LM Studio Qwen3 refine 延遲（目標 < 1.5s）
