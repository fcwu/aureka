## Why

Aureka 是一個本地 AI 語音處理平台，旨在解決兩個核心需求：（1）將影片/音訊自動轉換成結構化知識庫 Markdown，（2）透過全域熱鍵實現無鍵盤語音輸入（Typeless-like）。目前這兩個工作流程都需要手動操作，缺乏整合的本地化方案。

## What Changes

- **新增** 批次處理流水線：影片/音訊 → ffmpeg 提取 → ASR 轉錄 + VLM 畫面描述 → LLM 摘要結構化 → Markdown 輸出
- **新增** 語音輸入 Daemon：FastAPI + WebSocket 常駐服務，預載 ASR 模型，提供串流語音轉文字
- **新增** 全域熱鍵 Client：pynput 捕捉熱鍵 → 錄音 → WebSocket → 文字注入游標位置
- **新增** TTS 回讀：Kokoro 本地 TTS，支援中英雙語
- **新增** 多平台 ASR 後端：TheWhisper（NVIDIA/Apple Silicon）+ faster-whisper（AMD ROCm/CPU fallback）
- **新增** CLI 介面：`aureka process`、`aureka speak`、`aureka type`、`aureka daemon`

## Capabilities

### New Capabilities

- `batch-pipeline`: 影片/音訊批次處理流水線，含 ffmpeg 提取、ASR 轉錄、VLM 畫面描述、LLM 摘要，輸出結構化 Markdown
- `voice-input`: 全域熱鍵觸發的語音輸入模式，支援 transcribe/refine/translate 三種 AI 後處理
- `daemon`: FastAPI WebSocket daemon 服務，預載模型、提供串流 API
- `asr-backend`: 多後端 ASR 封裝（TheWhisper / faster-whisper），依平台自動選擇
- `tts-backend`: Kokoro TTS 封裝，支援 CUDA/MPS/CPU
- `cli`: 命令列介面，整合 process/speak/type/daemon 子命令

### Modified Capabilities

## Impact

- **新增相依套件**：`thestage-speechkit`、`faster-whisper`、`openai`、`kokoro`、`sounddevice`、`fastapi`、`uvicorn`、`websockets`、`pynput`、`pystray`、`pyperclip`、`pyautogui`、`ffmpeg-python`、`torch`
- **系統相依**：需安裝 `ffmpeg`（系統套件）
- **平台支援**：NVIDIA Linux（CUDA）、AMD Linux（ROCm）、Apple Silicon（MPS/CoreML）、CPU fallback
- **外部服務**：需 OpenAI-compatible LLM/VLM 端點（LM Studio、Ollama 等），本地執行無需網路
