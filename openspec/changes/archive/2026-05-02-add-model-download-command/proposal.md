## Why

第一次執行 `aureka speak` 或 `aureka type` 時，Kokoro TTS 與 Whisper ASR 會在背景從 HuggingFace 下載權重（合計約 2GB），下載期間沒有任何進度提示，使用者只看到指令長時間 hang 住，誤以為當機。需要一條「先把模型備齊」的明確指令來改善首次使用體驗。

## What Changes

- 新增 `aureka download` 子命令，預先抓取所有執行時會用到的模型權重
- 使用 `huggingface_hub.snapshot_download` 直接下載 repo，**不**載入模型到記憶體、不佔 GPU/MPS
- 下載目標固定為當前支援的後端：
  - Kokoro TTS：`hexgrad/Kokoro-82M`
  - faster-whisper：`Systran/faster-whisper-large-v3`
  - TheWhisper（若 CUDA/MPS 可用）：`thestage-ai/thewhisper-large-v3-turbo`
- 利用 HuggingFace Hub 內建 tqdm 進度條，使用者看得到下載進度
- 已下載的檔案 snapshot_download 會自動跳過，重複執行 idempotent

## Capabilities

### New Capabilities
- `model-management`：管理本地 model cache 的預先下載與檢查

### Modified Capabilities
- `cli`：新增 `download` 子命令的 CLI 介面要求

## Impact

- 新增 `aureka/models.py`：定義 model registry 與 `download_all()` 函數
- 修改 `aureka/__main__.py`：註冊 `download` subparser 與 dispatcher
- 修改 `README.md` / `CLAUDE.md`：在「安裝與設定」段落加入建議的首次下載步驟
- 不影響現有 daemon、speak、type、process 子命令的行為
- 相依套件：`huggingface_hub` 已透過 `transformers` / `kokoro` 間接安裝，無需新增
