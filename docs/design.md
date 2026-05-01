# Aureka — 系統設計文件

> 狀態：設計草稿
> 目標：音訊/影片 → 知識庫自動化，含 TTS 回讀；全域語音輸入（Typeless-like）
> 平台目標：NVIDIA Linux、AMD Linux、Apple Silicon、CPU fallback

---

## 一、系統定位

Aureka 是一個本地 AI 語音處理平台，包含兩個主要使用模式：

| 模式 | 描述 | 觸發方式 |
|------|------|----------|
| **批次處理（Batch）** | 影片/音訊 → 知識庫 markdown；知識庫 TTS 回讀 | CLI `aureka process` |
| **語音輸入（Voice Input）** | 全域熱鍵 → 錄音 → STT + AI 修飾/翻譯 → 注入文字 | 全域熱鍵，常駐 daemon |

兩個模式共用相同的 ASR、LLM、裝置偵測元件，差別在延遲需求與執行方式。

---

## 二、平台支援矩陣

| 平台 | Voice Input | Batch | ASR 加速 | TTS 加速 |
|------|-------------|-------|----------|----------|
| NVIDIA Linux | ✅ | ✅ | CUDA (TheWhisper) | CUDA (Kokoro) |
| AMD Linux | ✅ | ✅ | ROCm (faster-whisper) | ROCm (Kokoro) |
| Apple Silicon | ✅ | ✅ | CoreML (TheWhisper) | MPS (Kokoro) |
| CPU only | ✅ | ✅ | CPU (faster-whisper) | CPU (Kokoro) |

> WSL2 是開發環境，不是部署目標。Windows native 未來另立專案，屆時再討論。

---

## 三、技術選型

| 層 | 工具 | 平台 | 理由 |
|---|------|------|------|
| ASR | **TheWhisper** | NVIDIA / Apple Silicon | WER -25%，TTFT 12ms，本地模型 |
| ASR | **faster-whisper** | AMD ROCm / CPU | ROCm 支援，CPU 比原版快 4x |
| VLM / LLM | **OpenAI-compatible API** | 全部 | 可接 LM Studio、Ollama 或任何相容端點 |
| TTS | **Kokoro** | CUDA / MPS / CPU | 82M 參數，跨平台，中英雙語 |

### 3.1 裝置偵測與 ASR 後端選擇

```python
# aureka/device.py
import torch

def resolve_device(preference: str = "auto") -> str:
    if preference != "auto":
        return preference
    if torch.cuda.is_available():
        return "cuda"   # NVIDIA CUDA 或 AMD ROCm（HIP 橋接）
    if torch.backends.mps.is_available():
        return "mps"    # Apple Silicon Metal
    return "cpu"

def resolve_asr_backend(device: str) -> str:
    """TheWhisper 優先（NVIDIA/Apple Silicon），否則 faster-whisper。"""
    if device in ("cuda", "mps"):
        try:
            import thestage_speechkit  # noqa: F401
            return "thewhisper"
        except ImportError:
            pass
    return "faster-whisper"
```

### 3.2 ASR：TheWhisper（NVIDIA / Apple Silicon）

- **Repo**：https://github.com/TheStageAI/TheWhisper
- **模型**：HuggingFace `thestage-ai/thewhisper-large-v3-turbo`（本地下載，無需 API key）
- **數據**：WER 5.91 vs 原版 7.83（英文；中文需實測），TTFT 12ms，CoreML 支援 Apple Silicon
- **授權**：模型 MIT；`thestage-speechkit` 優化引擎 ≤4 GPU 免費

```bash
pip install thestage-speechkit
# 首次執行時自動從 HuggingFace 下載模型（~3GB）
```

```python
from thestage_speechkit import WhisperPipeline

pipeline = WhisperPipeline.from_pretrained(
    "thestage-ai/thewhisper-large-v3-turbo",
    device="cuda",   # 或 "mps"
)
result = pipeline("audio.wav")
# result.segments: [{start, end, text}, ...]
```

### 3.3 ASR：faster-whisper（AMD ROCm / CPU fallback）

- **Repo**：https://github.com/SYSTRAN/faster-whisper
- **模型**：`large-v3`（精準）或 `medium`（速度/品質平衡）

```bash
pip install faster-whisper
```

```python
from faster_whisper import WhisperModel

def load_asr_fallback(device: str = "cpu"):
    compute = "float16" if device == "cuda" else "int8"
    return WhisperModel("large-v3", device=device, compute_type=compute)
```

### 3.4 VLM + LLM：OpenAI-compatible API

端點與模型透過 `config.toml` 設定，可對接 LM Studio、Ollama 或任何 OpenAI-compatible 服務：

```toml
# config.toml
[llm]
base_url = "http://127.0.0.1:1234/v1"   # LM Studio 預設；Ollama 用 11434
api_key  = "lm-studio"                   # LM Studio 任意值；Ollama 用 "ollama"
model    = "auto"                        # 或指定模型 ID

[vlm]
base_url = "http://127.0.0.1:1234/v1"
api_key  = "lm-studio"
model    = "auto"
# 必須載入支援 vision 的模型，否則啟動時 fatal error
```

```python
# aureka/llm.py
import openai
from aureka.config import cfg

client = openai.OpenAI(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key)
vlm_client = openai.OpenAI(base_url=cfg.vlm.base_url, api_key=cfg.vlm.api_key)

def describe_frame(image_path: str) -> str:
    import base64, pathlib
    b64 = base64.b64encode(pathlib.Path(image_path).read_bytes()).decode()
    resp = vlm_client.chat.completions.create(
        model=cfg.vlm.model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": "請描述這張影片截圖的內容，包含畫面主題、文字、圖表等資訊。"},
        ]}],
        max_tokens=512,
    )
    return resp.choices[0].message.content
```

VLM 啟動時檢查：

```python
def check_vlm_supports_vision():
    try:
        describe_frame("test.jpg")
    except Exception as e:
        raise SystemExit(f"[fatal] VLM 不支援 vision，請在 {cfg.vlm.base_url} 載入支援視覺的模型。\n{e}")
```

### 3.5 TTS：Kokoro

- **Repo**：https://github.com/hexgrad/kokoro
- **模型**：82M 參數，CUDA/MPS/CPU 全支援，中英雙語

```bash
pip install kokoro sounddevice soundfile
```

```python
from kokoro import KPipeline
from aureka.device import resolve_device

def load_tts(device: str = "auto"):
    return KPipeline(lang_code="z", device=resolve_device(device))

pipeline = load_tts()

def speak(text: str, output_path: str = None):
    import sounddevice as sd
    import soundfile as sf
    for _, _, audio in pipeline(text, voice="zf_xiaobei"):
        if output_path:
            sf.write(output_path, audio, 24000)
        else:
            sd.play(audio, 24000); sd.wait()
```

---

## 四、批次流水線架構

```
輸入：video.mp4 / audio.mp3 / audio.wav
          │
          ▼
    ┌─────────────┐
    │   ffmpeg    │  提取音訊軌 + 關鍵畫面（每 N 秒一張）
    └─────┬───────┘
          │
    ┌─────┴──────────────────────┐
    │                            │
    ▼                            ▼
┌──────────┐            ┌──────────────────┐
│   ASR    │            │    VLM API       │
│ 語音轉文字│            │ 畫面描述（批次）  │
└────┬─────┘            └────────┬─────────┘
     │                           │
     └──────────┬────────────────┘
                ▼
        ┌───────────────┐
        │   LLM API     │  整合摘要、重點萃取、知識結構化
        └───────┬───────┘
                │
                ▼
        output/YYYYMMDD-<slug>.md
                │
                ▼
          (丟入 mykb inbox → triage → ingest → wiki)

TTS 回讀路徑：
    query → LLM API → text → Kokoro TTS → 播放/存 wav
```

---

## 五、輸出格式

```markdown
---
source: video
original_file: lecture-2026-05-01.mp4
duration: 45:32
processed_at: 2026-05-01T14:30:00
---

# <自動萃取的標題>

## 摘要

<LLM 生成的 3-5 行摘要>

## 重點

- ...

## 逐段紀錄

| 時間 | 內容 |
|------|------|
| 00:00 | ... |

## 視覺內容

| 畫面時間點 | 描述 |
|----------|------|
| 00:30 | ... |

## 原始轉錄

<完整逐字稿，含時間戳記>
```

---

## 六、CLI 介面

```bash
# 批次處理影片或音訊
aureka process video.mp4
aureka process podcast.mp3 --frame-interval 60 --device cuda

# TTS 回讀
aureka speak "今天的工作重點是什麼"
aureka speak --file path/to/note.md

# 語音輸入 daemon
aureka daemon start          # 啟動常駐服務（預載模型）
aureka daemon stop
aureka daemon status

# 單次語音輸入（daemon 未啟動時有冷啟動延遲）
aureka type                          # 轉錄 → 注入
aureka type --mode refine            # 轉錄 → LLM 修飾 → 注入
aureka type --mode translate --lang en
```

---

## 七、語音輸入模式（Typeless-like）

### 設計目標

按下熱鍵 → 說話 → 放開熱鍵 → 文字出現在目前游標位置，延遲目標 < 3 秒（GPU）/ < 8 秒（CPU）。

### 架構：Daemon + WebSocket（串流）

模型冷啟動需要 5-15 秒，不能每次觸發都重載。常駐 daemon 預載模型，以 **WebSocket** 對外提供串流介面，讓使用者在說話時即可看到文字逐步出現：

```
┌──────────────────────────────────────────┐
│  aureka daemon（FastAPI + uvicorn）        │
│                                          │
│  已載入：ASR model                        │
│         LLM client（OpenAI-compatible）   │
│         Kokoro TTS（可選）                │
│                                          │
│  ws://127.0.0.1:7777/ws    ← 語音輸入    │
│  POST   /process           ← 批次音訊    │
│  GET    /health                          │
└──────────────────┬───────────────────────┘
                   │ WebSocket
    ┌──────────────┴──────────────┐
    │                             │
    ▼                             ▼
aureka CLI                 hotkey client
(aureka type)              (pynput + pystray)
```

**串流協定（WebSocket）：**

Client → Server：
```json
{"type": "start", "mode": "refine", "lang": "zh"}
{"type": "chunk", "data": "<base64 PCM 16kHz mono>"}
{"type": "chunk", "data": "..."}
{"type": "end"}
```

Server → Client：
```json
{"type": "transcript", "text": "今天天氣", "final": false}
{"type": "transcript", "text": "今天天氣很好", "final": true}
{"type": "refined",    "text": "今天天",     "final": false}
{"type": "refined",    "text": "今天天氣非常好，適合出門。", "final": true}
{"type": "done"}
```

**串流注入策略：**

| 模式 | 注入時機 | 說明 |
|------|----------|------|
| `transcribe` | 每段 `transcript final` → append 注入 | 邊說邊出字 |
| `refine` | 收到 `refined` token → 替換前次注入 | 先顯示草稿，LLM 修飾完再定稿 |
| `translate` | `refined final` 後一次注入 | 翻譯完整句才有意義 |

替換注入：在注入前先模擬選取前次文字（Shift+Home 或記住字數）再覆蓋，或使用浮動 overlay 顯示，關閉時一次注入。

**Daemon 實作（FastAPI）：**

```python
# aureka/daemon.py
from fastapi import FastAPI, WebSocket
import asyncio, base64, json, numpy as np

app = FastAPI()

@app.websocket("/ws")
async def voice_input(ws: WebSocket):
    await ws.accept()
    config = await ws.receive_json()          # {"type":"start", "mode":..., "lang":...}
    audio_chunks: list[np.ndarray] = []

    async for msg in ws.iter_json():
        if msg["type"] == "chunk":
            pcm = np.frombuffer(base64.b64decode(msg["data"]), dtype=np.int16)
            audio_chunks.append(pcm)
        elif msg["type"] == "end":
            break

    audio = np.concatenate(audio_chunks).astype(np.float32) / 32768.0

    # ASR — segments 為 generator，逐段送出
    for seg in asr_model.transcribe_stream(audio):
        await ws.send_json({"type": "transcript", "text": seg.text, "final": seg.is_last})

    # LLM refine — streaming=True
    if config["mode"] == "refine":
        async for token in llm_refine_stream(transcript):
            await ws.send_json({"type": "refined", "text": token, "final": False})
        await ws.send_json({"type": "refined", "text": "", "final": True})

    await ws.send_json({"type": "done"})
```

### 錄音模式

| 模式 | 行為 | 適用場景 |
|------|------|----------|
| **hold-to-record** | 按住熱鍵錄音，放開停止 | 短句、精確控制（預設） |
| **toggle** | 按一下開始，再按停止 | 長段落 |
| **VAD** | 自動偵測靜音停止 | 免動手，偶爾誤停 |

### AI 後處理模式

| 模式 | 說明 | 額外延遲 |
|------|------|----------|
| `transcribe` | 原始轉錄，不過 LLM | 0 |
| `refine` | 移除語氣詞、修正語法、保持語意 | +1-2s |
| `translate` | 轉錄後翻譯成指定語言 | +1-2s |
| `context` | 依剪貼簿內容推斷語境再修飾（進階） | +2-3s |

LLM prompt（refine mode）：

```
你是專業文字編輯。將以下語音轉錄文字整理成自然流暢的書面文字：
- 移除重複、語氣詞（嗯、那個、就是說）
- 修正明顯語音辨識錯誤
- 保持原意，不要添加內容
- 直接輸出結果，不要解釋

原文：{transcript}
```

### Client 實作：純 Python

跨平台最易維護的方案：同一份 Python 程式碼，不引入額外框架。

```
pynput     → 全域熱鍵捕捉（Linux X11 / macOS / Windows）
pystray    → 系統托盤圖示與右鍵選單
pyperclip  → 跨平台剪貼簿操作
```

```python
# aureka/client.py
from pynput import keyboard
import pystray, pyperclip, websockets, asyncio, sounddevice, base64, numpy as np

WS_URL = "ws://127.0.0.1:7777/ws"
MODE   = "refine"

async def voice_session():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "start", "mode": MODE, "lang": "zh"}))

        # 錄音同時透過 WebSocket 送 chunks
        with sounddevice.InputStream(samplerate=16000, channels=1, dtype="int16") as mic:
            while recording:
                chunk, _ = mic.read(1600)   # 100ms @ 16kHz
                await ws.send(json.dumps({
                    "type": "chunk",
                    "data": base64.b64encode(chunk.tobytes()).decode()
                }))

        await ws.send(json.dumps({"type": "end"}))

        injected_len = 0
        async for msg_str in ws:
            msg = json.loads(msg_str)
            if msg["type"] == "transcript" and msg["final"]:
                inject_text(msg["text"])          # transcribe 模式：直接注入
                injected_len = len(msg["text"])
            elif msg["type"] == "refined":
                # 替換前次注入：先退格再打新字
                replace_injected(injected_len, msg["text"])
                injected_len = len(msg["text"])
```

### 文字注入

| 平台 | 方法 |
|------|------|
| macOS | `pyautogui` Cmd+V（剪貼簿注入，最相容） |
| Windows | `pyautogui` Ctrl+V |
| Linux X11 | `xdotool type` 直接注入；失敗則剪貼簿 |

### 延遲預算（串流模式）

串流下「首字延遲（TTFT）」比「總時間」更重要，使用者感知更好：

```
按下熱鍵（開始錄音 + 同步送 chunks）
  │
  ├─ [說話中] ASR 對每個語音段即時產出 transcript
  │    TheWhisper NVIDIA    TTFT ~12ms／段
  │    TheWhisper CoreML    TTFT ~50ms／段
  │    faster-whisper ROCm  TTFT ~200-500ms／段
  │    faster-whisper CPU   TTFT ~1-3s／段
  │
放開熱鍵（送 end）
  │
  ├─ [transcribe mode] 最後一段 transcript 注入 → 完成
  │    NVIDIA: 放開後 ~50ms  ✅
  │
  └─ [refine mode] LLM streaming token 替換注入
       LLM 首 token ~300-500ms，邊收邊更新
       NVIDIA: 放開後 ~500ms-1.5s 完成  ✅
       CPU:    放開後 ~3-6s 完成         ⚠️
```

---

## 八、專案結構

```
aureka/
├── aureka/
│   ├── __main__.py       # CLI 入口
│   ├── config.py         # config.toml 載入
│   ├── device.py         # 裝置偵測（cuda / mps / cpu）
│   ├── asr.py            # ASR 封裝（TheWhisper / faster-whisper 統一介面）
│   ├── llm.py            # LLM / VLM 呼叫（OpenAI-compatible）
│   ├── tts.py            # Kokoro 封裝
│   ├── pipeline.py       # 批次流程編排
│   ├── daemon.py         # HTTP daemon（預載模型）
│   ├── recorder.py       # 麥克風錄音（hold/toggle/VAD）
│   ├── hotkey.py         # 全域熱鍵（pynput）
│   ├── client.py         # Voice input client（pystray + pyperclip）
│   ├── injector.py       # 文字注入（pyautogui / xdotool）
│   ├── ffmpeg_utils.py   # 音訊/畫面提取
│   └── formatter.py      # Markdown 輸出格式化
├── docs/
│   └── design.md
├── config.toml           # 使用者設定（端點、hotkey、模式、語言等）
├── requirements.txt
└── README.md
```

---

## 九、相依套件

```
# ASR
thestage-speechkit>=0.1.0   # TheWhisper（NVIDIA / Apple Silicon）
faster-whisper>=1.0.0        # AMD ROCm / CPU fallback

# LLM / VLM
openai>=1.0.0

# TTS
kokoro>=0.9.0
sounddevice>=0.4.6
soundfile>=0.12.1

# Daemon（HTTP + WebSocket）
fastapi>=0.111.0
uvicorn>=0.30.0
websockets>=12.0

# Voice Input client
pynput>=1.7.0
pystray>=0.19.0
pyperclip>=1.8.0
pyautogui>=0.9.0

# Batch pipeline
ffmpeg-python>=0.2.0
Pillow>=10.0.0
torch>=2.1.0
```

### PyTorch 安裝（依平台）

```bash
# NVIDIA CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu121

# AMD ROCm（native Linux）
pip install torch --index-url https://download.pytorch.org/whl/rocm6.1

# Apple Silicon / CPU
pip install torch
```

### ffmpeg 安裝（依平台）

```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# Fedora / RHEL
sudo dnf install ffmpeg

# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
# 或 choco install ffmpeg
```

---

## 十、待確認

**批次流水線**
- [ ] VLM 啟動時驗證 vision 支援（`check_vlm_supports_vision()`），不支援則 fatal error
- [ ] TheWhisper 中文 WER 實測（Open ASR Leaderboard 數字為英文）
- [ ] faster-whisper CPU 速度實測（45 分鐘音訊預估處理時間）
- [ ] Kokoro 中文語音品質評估（voice 選項：`zf_xiaobei` 等）

**語音輸入模式**
- [ ] pynput Linux X11 熱鍵測試（需確認 display server 存取權限）
- [ ] xdotool Unicode 注入測試（CJK 字元）
- [ ] LM Studio Qwen3 refine 延遲實測（目標 < 1.5s）
- [ ] VAD 靈敏度調整（靜音閾值 config 化）

---

## 十一、參考

- [TheWhisper](https://github.com/TheStageAI/TheWhisper)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Kokoro TTS](https://github.com/hexgrad/kokoro)
- [pynput](https://pynput.readthedocs.io/)
- [pystray](https://github.com/moses-palmer/pystray)
- [AMD ROCm + PyTorch](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/how-to/3rd-party/pytorch-install.html)
- [PyTorch MPS (Apple Silicon)](https://developer.apple.com/metal/pytorch/)
- [LM Studio](https://lmstudio.ai)
- [Ollama](https://ollama.ai)
