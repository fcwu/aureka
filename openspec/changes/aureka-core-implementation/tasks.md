## 1. 專案基礎架構

- [x] 1.1 建立 `aureka/` Python package 結構（`__init__.py` + 所有模組骨架）
- [x] 1.2 撰寫 `aureka/config.py`：載入 `config.toml`（含 llm/vlm/tts/daemon/hotkey section）
- [x] 1.3 建立 `config.example.toml` 範本（包含所有可設定欄位與說明注釋）
- [x] 1.4 更新 `requirements.txt` 加入所有相依套件
- [x] 1.5 建立 `aureka/__main__.py` CLI 入口（使用 `argparse` 或 `click`，含 process/speak/type/daemon 子命令）

## 2. 裝置偵測與 ASR 後端

- [x] 2.1 實作 `aureka/device.py`：`resolve_device()` + `resolve_asr_backend()`
- [x] 2.2 實作 `aureka/asr.py`：統一 `Segment` dataclass 和 `transcribe()` 介面
- [x] 2.3 實作 TheWhisper 後端（`WhisperPipeline.from_pretrained`，CUDA/MPS）
- [x] 2.4 實作 faster-whisper 後端（`WhisperModel`，float16/int8 按裝置選擇）
- [x] 2.5 撰寫 unit tests：`resolve_device()` 和 `resolve_asr_backend()` 的各平台邏輯（mock torch）

## 3. LLM / VLM 客戶端

- [x] 3.1 實作 `aureka/llm.py`：`openai.OpenAI` client 封裝（llm + vlm 雙 client）
- [x] 3.2 實作 `describe_frame(image_path)` 使用 base64 image 呼叫 VLM
- [x] 3.3 實作 `check_vlm_supports_vision()`（啟動時驗證，失敗則 fatal error）
- [x] 3.4 實作 `llm_refine_stream(transcript)` async generator（streaming LLM 呼叫）
- [x] 3.5 撰寫 integration tests：使用 mock LLM server 驗證 `describe_frame` 和 `llm_refine_stream`

## 4. TTS 後端

- [x] 4.1 實作 `aureka/tts.py`：`load_tts()` + `speak(text, output_path=None)`
- [x] 4.2 實作 `speak --file` 的 Markdown 前處理（略過 frontmatter 和 Markdown 標記）
- [x] 4.3 撰寫 unit tests：Markdown 前處理邏輯（不需真實 Kokoro 模型）

## 5. 批次流水線

- [x] 5.1 實作 `aureka/ffmpeg_utils.py`：`extract_audio()` + `extract_keyframes(frame_interval)`
- [x] 5.2 實作 `aureka/formatter.py`：`format_output(segments, frame_descriptions, summary)` → Markdown
- [x] 5.3 實作 `aureka/pipeline.py`：編排 ffmpeg → ASR → VLM → LLM → formatter 流程
- [x] 5.4 實作 `output/` 目錄自動建立和輸出檔案命名（`YYYYMMDD-<slug>.md`）
- [x] 5.5 撰寫 integration tests：使用 `tests/fixtures/silence-1s.wav` + mock LLM 驗證完整流水線

## 6. Daemon

- [x] 6.1 實作 `aureka/daemon.py`：FastAPI app 骨架（`GET /health`、`POST /process`、`WebSocket /ws`）
- [x] 6.2 實作 daemon 啟動時預載 ASR 模型（全域單例）
- [x] 6.3 實作 WebSocket `/ws` handler：解碼 base64 PCM → ASR → LLM refine（串流）→ `done`
- [x] 6.4 實作 daemon 程序管理：start（背景啟動 + PID 記錄）、stop、status
- [x] 6.5 撰寫 integration tests：`GET /health`、WebSocket transcribe 模式、WebSocket refine 模式（使用 mock ASR + mock LLM）

## 7. 語音輸入 Client

- [x] 7.1 實作 `aureka/recorder.py`：hold-to-record、toggle、VAD 三種錄音模式
- [x] 7.2 實作 `aureka/hotkey.py`：pynput 全域熱鍵綁定（可設定）
- [x] 7.3 實作 `aureka/injector.py`：Linux xdotool + 剪貼簿 fallback；macOS/Windows 剪貼簿注入
- [x] 7.4 實作替換注入邏輯（記錄前次注入字數，退格 + 重新注入）
- [x] 7.5 實作 `aureka/client.py`：pystray 托盤圖示 + websockets 連線 + 錄音 → 注入完整流程
- [x] 7.6 撰寫 unit tests：injector 文字替換邏輯（mock 鍵盤 API）

## 8. CLI 整合

- [x] 8.1 實作 `aureka process` 子命令（呼叫 pipeline，含 --frame-interval、--device 參數）
- [x] 8.2 實作 `aureka speak` 子命令（直接文字 + --file 兩種輸入）
- [x] 8.3 實作 `aureka type` 子命令（--mode、--lang 參數；優先連 daemon，fallback 本地載入）
- [x] 8.4 實作 `aureka daemon start/stop/status` 子命令
- [x] 8.5 實作 `AUREKA_CONFIG` 環境變數支援和設定檔不存在的錯誤訊息
- [x] 8.6 撰寫 E2E tests：`aureka daemon start` → `curl /health` → `aureka daemon stop` 流程

## 9. 測試工具與 fixtures

- [x] 9.1 確認 `tests/scripts/gen-test-audio.py` 能產生 `silence-1s.wav` 和 `speech-zh.wav`
- [x] 9.2 確認 `tests/scripts/mock-llm-server.py` 支援 `/v1/chat/completions`（含 vision）和 `/v1/models`
- [x] 9.3 確認 `tests/scripts/ws-client-test.py` 支援 `--mode transcribe` 和 `--mode refine`
- [x] 9.4 建立 `tests/.env.local.md`（本機環境設定範本，不進 git）
