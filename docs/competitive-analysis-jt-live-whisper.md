# 競品分析：jt-live-whisper

> 對標：[`jasoncheng7115/jt-live-whisper`](https://github.com/jasoncheng7115/jt-live-whisper) v2.16.1
> 日期：2026-05-03
> 目的：盤點他們有但 Aureka 沒有的功能，篩出值得借用的方向。

## 兩者定位差異

| 維度 | jt-live-whisper | Aureka |
|------|----------------|--------|
| 主要使用情境 | 即時轉錄 / 翻譯**會議與影片**，地端 AI 字幕工具集 | 全域**語音輸入到游標** + TTS 回讀 + 批次媒體 → 知識庫 |
| 核心 I/O | 系統音訊（loopback）+ 麥克風 → 字幕視窗 / 終端機 | 麥克風 → 文字注入到游標 / 朗讀文字 |
| 輸出端 | 字幕、HTML 逐字稿、會議摘要、轉發到 Slack/Telegram 等 | 任何前景 app 的文字框、TTS 音訊 |
| 對地端 LLM 的依賴 | 翻譯與摘要會用，但有 NLLB / Argos 完全離線備援 | 必要（refine / translate 模式） |

兩者都是「100% 地端」、都用 OpenAI-compatible / Ollama 後端 LLM，但**核心 workflow 不同**——他們做「字幕」，我們做「輸入」。借用時要篩過，不能整套照搬。

## 他們有、我們沒有的

| 項目 | 說明 |
|------|------|
| 系統音訊擷取 | macOS BlackHole、Windows WASAPI Loopback。能擷取 Zoom/Teams/YouTube 任何 app 的聲音 |
| 雙向字幕模式 | `en_zh` / `ja_zh`：同時擷取系統音訊（對方）+ 麥克風（自己），各翻譯一邊 |
| Speaker diarization | resemblyzer + spectralcluster，多人錄音以顏色區分講者，避開 pyannote 的 HF token 限制 |
| 會議 LLM 摘要 | 對轉錄產出做重點 + 校正逐字稿 |
| 主題感知翻譯 | `--topic "ZFS storage"` 提升 LLM 翻譯/摘要專業術語準確度 |
| 多 ASR 引擎 | whisper.cpp / faster-whisper / mlx-whisper / Moonshine（300ms 超低延遲，英文）四選一 |
| 自動偵測 LLM 伺服器 | 探 Ollama 11434 / LM Studio 1234 / vLLM 8000 / Jan 1337 / LiteLLM 4000 等 port |
| WebUI（瀏覽器） | FastAPI + WebSocket，手機/平板可用，聊天/字幕兩種顯示模式 |
| 懸浮字幕（PyQt6） | 半透明覆蓋視窗、可拖曳、滑鼠穿透 |
| 關鍵字警報 | 設關鍵字 → 即時辨識命中時全螢幕閃 + 音效 + 推播 |
| 字幕轉發 | Telegram / Slack / Discord / Teams / LINE / Nextcloud / 通用 API |
| 多種輸出格式 | SRT / VTT / HTML（含波形音訊播放器，點時間戳跳到對應位置）/ TXT |
| 音訊場景 preset | meeting / training / presentation / subtitle 四組 VAD/buffer 預設 |
| Pause / Resume 熱鍵 | 即時模式 Ctrl+P 暫停 |
| 互動式選單啟動 | 不帶參數啟動會走 wizard，最後印出對應 CLI 指令 |
| GPU 伺服器分離模式 | 本機收音 → 區網 GPU 伺服器辨識 |
| 一鍵安裝腳本 | `install.sh` / `install.ps1` 連 ffmpeg / BlackHole / 模型一起裝 |

## 我們有、他們沒有的

- **TTS（Kokoro）**：他們完全不做朗讀，我們是核心
- **文字注入到游標**：他們是字幕導向，我們的 `aureka type` 才是日常 power-user 流
- **pywebview 設定 UI（Tailwind + 自動存）**：他們是 CLI menu / browser webui
- **Cross-platform autostart**：launchd plist / Task Scheduler 一鍵
- **`aureka benchmark` + UI 推薦**：他們沒量測機制
- **POST `/reload` 熱套用**：他們 config 改了得重啟

## 建議借用清單（已排序）

> 排序依「對 Aureka 核心使用者價值 ÷ 實作成本」。每項對應一個 OpenSpec proposal。

### P0 — 高價值低成本

1. **`--topic` 主題感知 LLM**（`add-topic-aware-llm`）
   - 加一個字串塞進 LLM prompt 就能大幅提升專業術語準確度
   - Refine / translate 兩個模式都受惠
   - 估時：半天

2. **系統音訊擷取 + `aureka listen`**（`add-system-audio-capture`）
   - 解鎖整個「轉錄會議/影片」場景
   - macOS 用 BlackHole（需引導使用者裝），Windows 用 WASAPI Loopback（內建）
   - 不取代 `aureka type`，是平行子命令
   - 估時：2-3 天

### P1 — 中價值低成本

3. **SRT / VTT 輸出 + Pause/Resume 熱鍵**（`add-subtitle-output-and-pause`）
   - SRT/VTT：batch pipeline 多兩個 writer，影片字幕用
   - Pause/Resume：錄音中按熱鍵暫停，多輪錄音實用
   - 兩者獨立但都是低成本，合併一個 proposal 推進
   - 估時：合計半天

### P1 — 中價值中成本

4. **Speaker diarization + HTML 播放器**（`add-speaker-diarization-and-html-player`）
   - 多人錄音以顏色區分講者
   - HTML 逐字稿：點時間戳跳到對應音訊位置（waveform.js 風格）
   - 兩者搭配價值最大化
   - 用 resemblyzer + spectralcluster（避開 pyannote 的 HF token 麻煩）
   - 估時：一週

## 不建議追的

- **WebUI（瀏覽器版）**：和我們 pywebview 重疊，多一份維護
- **懸浮字幕（PyQt6）**：依賴重，跟 Aureka「注入到游標」核心情境正交
- **多 ASR 引擎切換**：faster-whisper 已經涵蓋我們的需求；plug-in framework 維護成本不值
- **GPU 伺服器分離模式**：使用者群極窄、大重構
- **轉發到 Slack/Telegram/Teams**：偏離核心
- **關鍵字警報 + 全螢幕閃爍**：場景跟 Aureka 不貼

## 跟 Aureka 既有 capability 的對應

借用項目會落到這些 spec：

| 借用項目 | 影響的 capability |
|---------|------------------|
| Topic-aware | `voice-input`（refine prompts）、`cli`（`--topic`）、`settings-ui`（topic 欄位） |
| System audio capture | 新 `system-audio` capability、`cli`（`aureka listen`）、`daemon`（streaming endpoint） |
| SRT / VTT | `batch-pipeline`（output writers） |
| Pause / Resume hotkey | `voice-input`（hotkey behavior） |
| Speaker diarization | 新 `speaker-diarization` capability、`batch-pipeline`、`model-management` |
| HTML player | `batch-pipeline`（HTML writer） |
