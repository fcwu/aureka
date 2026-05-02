# model-management Specification

## Purpose
TBD - created by archiving change add-model-download-command. Update Purpose after archive.
## Requirements
### Requirement: 模型 Registry
系統 SHALL 在 `aureka/models.py` 提供 `MODEL_REGISTRY` 字典作為所有可下載模型的 single source of truth，key 為邏輯名稱、value 為 HuggingFace repo ID。

#### Scenario: Registry 涵蓋所有執行時模型
- **WHEN** 開發者讀取 `aureka.models.MODEL_REGISTRY`
- **THEN** 字典至少包含 `kokoro`、`faster-whisper`、`thewhisper` 三個 key，對應正確的 HuggingFace repo ID

### Requirement: 預先下載介面
系統 SHALL 提供 `aureka.models.download_all(device: str = "auto") -> list[Path]` 函數，依當前環境決定要下載哪些模型，並回傳所有已下載 snapshot 的本地路徑清單。

#### Scenario: 純下載不載入模型
- **WHEN** 呼叫 `download_all()`
- **THEN** 系統使用 `huggingface_hub.snapshot_download` 下載檔案，**不**建立 KPipeline 或 WhisperModel 物件，**不**佔用 GPU/MPS 記憶體

#### Scenario: 環境感知選擇 ASR 後端
- **WHEN** `resolve_device()` 回傳 `cuda` 或 `mps` 且 `thestage_speechkit` 可匯入
- **THEN** `download_all()` 額外下載 TheWhisper repo，否則只下載 faster-whisper

#### Scenario: 一律下載 Kokoro 與 faster-whisper
- **WHEN** 呼叫 `download_all()`，不論裝置為何
- **THEN** Kokoro 與 faster-whisper 兩者皆會被下載（後者在所有平台都是 ASR fallback）

#### Scenario: 重複執行 idempotent
- **WHEN** 已下載完成後再次呼叫 `download_all()`
- **THEN** `snapshot_download` 比對本地 cache 後不重新下載，僅快速驗證並回傳路徑

### Requirement: 失敗 Fail-Fast
系統 SHALL 在任一模型下載失敗時立即拋出例外、印出錯誤訊息並停止後續下載，避免靜默忽略錯誤。

#### Scenario: 網路錯誤
- **WHEN** `snapshot_download` 因網路問題拋出例外
- **THEN** `download_all()` 不繼續下載剩餘模型，向上拋出例外

#### Scenario: 受限 repo 無權限
- **WHEN** TheWhisper repo 因 HuggingFace token 缺失或權限不足而下載失敗
- **THEN** 系統印出錯誤訊息並建議執行 `huggingface-cli login`，以 non-zero exit code 結束

### Requirement: 尊重 HuggingFace Cache 環境變數
系統 SHALL 透過呼叫 `huggingface_hub.snapshot_download` 自動繼承 `HF_HOME`、`HF_HUB_CACHE` 等環境變數的設定，不另外定義 cache 路徑。

#### Scenario: 自訂 cache 位置
- **WHEN** 使用者設定 `HF_HOME=/data/hf-cache` 並執行 `download_all()`
- **THEN** 模型下載至 `/data/hf-cache` 之下，不使用預設 `~/.cache/huggingface`

