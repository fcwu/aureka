## REMOVED Requirements

### Requirement: ASR 後端自動選擇
**Reason**: TheWhisper backend 已完全移除（PyPI 上的 `thestage-speechkit` 是空殼 placeholder，從未真正運作）。系統一律使用 faster-whisper，不再需要 backend 選擇邏輯。
**Migration**: 直接移除 `aureka/device.py:resolve_asr_backend()`；上層程式碼直接呼叫 `aureka.asr.load_asr(device)` 即可。

### Requirement: TheWhisper 後端
**Reason**: TheWhisper SDK 從未在 PyPI 釋出可用版本，相關 code path 永遠走不到。
**Migration**: 移除 `aureka/asr.py:_TheWhisperBackend` class 與 `pyproject.toml` 的 `asr-thewhisper` extra。使用 faster-whisper 取代；想要更高精度可在 `[asr] model = "large-v3"` 設定。

## MODIFIED Requirements

### Requirement: faster-whisper 後端
系統 SHALL 使用 faster-whisper 作為唯一的 ASR backend，所載入的模型由 `cfg.asr.model` 決定（預設 `medium`），支援所有 faster-whisper 接受的模型字串（`tiny`/`base`/`small`/`medium`/`large-v2`/`large-v3`/`large-v3-turbo` 或 HuggingFace repo ID 或本地路徑）。

#### Scenario: 從設定讀取 model
- **WHEN** `cfg.asr.model = "small"` 且 `load_asr()` 被呼叫
- **THEN** `WhisperModel("small", ...)` 被建構，不再寫死 `large-v3`

#### Scenario: 預設 model
- **WHEN** `config.toml` 未提供 `[asr]` 段
- **THEN** 系統使用 `medium` 作為預設模型

#### Scenario: CPU 推論精度設定
- **WHEN** 裝置為 `cpu`
- **THEN** 使用 `int8` compute type 以提升速度

#### Scenario: CUDA/ROCm 推論精度設定
- **WHEN** 裝置為 `cuda`
- **THEN** 使用 `float16` compute type

#### Scenario: 模型字串原樣傳遞
- **WHEN** `cfg.asr.model` 為非標準字串（例如 HuggingFace repo ID 或本地路徑）
- **THEN** 系統將該字串原樣傳給 `WhisperModel(...)`，由 faster-whisper 自行驗證

## ADDED Requirements

### Requirement: ASR 模型可設定
系統 SHALL 提供 `[asr]` config 段，包含 `model: str` 欄位，讓使用者依硬體在不改 source code 的前提下選擇 faster-whisper 模型大小。

#### Scenario: 預設值
- **WHEN** 讀取 `Config()` 的預設值
- **THEN** `cfg.asr.model == "medium"`

#### Scenario: 從 TOML 讀取
- **WHEN** `config.toml` 含 `[asr]\nmodel = "large-v3"`
- **THEN** `cfg.asr.model == "large-v3"`
