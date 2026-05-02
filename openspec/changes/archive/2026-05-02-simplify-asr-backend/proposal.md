## Why

Aureka 目前的 ASR 設計同時支援 TheWhisper（thestage-ai 的低延遲 backend）與 faster-whisper，並寫死使用 `large-v3` 模型。實際情況是：

1. **TheWhisper 整條安裝路徑是死的：** `pyproject.toml` 的 `asr-thewhisper` extra 指向 PyPI 上一個只有 1.5KB 的 placeholder package（作者欄位是 "Your Name <your.email@example.com>"），不是 thestage-ai 真正的 SDK。`asr.py` 的 `_TheWhisperBackend` 路徑因此永遠走不到。
2. **Hardcoded `large-v3` 對中等硬體偏重：** Apple Silicon M3 上跑 RTF = 1.23（轉錄比即時還慢 23%），10 秒語音要等 12 秒才出文字，使用體驗很差。但 source code 寫死，使用者沒辦法在不改原始碼的情況下換成 `medium`/`small`。

需要把這條死路清掉，並讓 ASR 模型可以從 `config.toml` 設定。

## What Changes

- **BREAKING（spec 層）**：移除 ASR backend 自動選擇邏輯。系統一律使用 faster-whisper backend，TheWhisper 完全消失（從 code、spec、extras、registry 全部移除）
- 新增 `[asr]` config 段，`model` 欄位預設 `medium`，使用者可改成任何 faster-whisper 接受的字串（`tiny` / `base` / `small` / `medium` / `large-v3` 等）
- `aureka/asr.py:_FasterWhisperBackend.__init__` 從 `cfg.asr.model` 讀模型名，不再 hardcoded
- `aureka/models.py` MODEL_REGISTRY 改成只含 Kokoro + 動態組成的 faster-whisper repo（依 config 決定要下哪個 size）
- `aureka/benchmark.py` 環境收集區塊不再列 `asr_backend`（恆為 faster-whisper），改列 `asr_model`
- 移除 `pyproject.toml` 的 `asr-thewhisper` extra
- 對應的測試（`test_device.py`、`test_models_unit.py`）配合修改

## Capabilities

### New Capabilities
（無新 capability）

### Modified Capabilities
- `asr-backend`：移除 TheWhisper backend 與「ASR 後端自動選擇」要求；新增「ASR 模型可設定」要求
- `model-management`：MODEL_REGISTRY 不再含 `thewhisper`，faster-whisper 的 repo_id 改為依 config 動態決定

## Impact

- 修改 `aureka/asr.py`（移除 `_TheWhisperBackend`、簡化 `load_asr`）
- 修改 `aureka/device.py`（移除 `resolve_asr_backend`）
- 修改 `aureka/config.py`（新增 `AsrConfig`）
- 修改 `aureka/models.py`（registry 簡化 + 動態 repo_id）
- 修改 `aureka/benchmark.py`（env 欄位調整）
- 修改 `pyproject.toml`（移除 `asr-thewhisper` extra）
- 修改 `config.example.toml`（新增 `[asr]` 段）
- 修改 `tests/test_device.py`、`tests/test_models_unit.py`（移除已不存在的 API 測試、新增 config-based 測試）
- 修改 `README.md` / `CLAUDE.md`（不再宣傳 TheWhisper、加入 `[asr]` 設定說明）
- 不影響 daemon / speak / type / process / download / benchmark / hotkey 子命令的對外行為
- 已下載 `Systran/faster-whisper-large-v3` 的 cache 不會自動清掉，但也不會用到；使用者要省空間請手動 `huggingface-cli delete-cache`
