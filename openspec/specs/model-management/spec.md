# model-management Specification

## Purpose

集中管理 Aureka 執行所需的本機 AI 模型（Kokoro TTS、faster-whisper ASR，未來可擴充 resemblyzer 等），提供下載 / 狀態查詢 / 進度回呼介面，讓使用者透過 `aureka download` CLI 或設定 UI Models 分頁預先抓齊權重，避免首次 `aureka type` / `aureka speak` 在背景下載大檔案造成「卡住」的錯覺。

## Requirements
### Requirement: 模型 Registry
系統 SHALL 在 `aureka/models.py` 提供 `model_registry() -> dict[str, str]` 函數作為所有可下載模型的 single source of truth，key 為邏輯名稱、value 為 HuggingFace repo ID；faster-whisper 的 repo_id 依當前 `cfg.asr.model` 動態決定。

#### Scenario: Registry 涵蓋所有執行時模型
- **WHEN** 開發者呼叫 `aureka.models.model_registry()`
- **THEN** 字典包含 `kokoro` 與 `faster-whisper` 兩個 key，對應正確的 HuggingFace repo ID

#### Scenario: faster-whisper repo 跟隨 config
- **WHEN** `cfg.asr.model = "medium"` 且呼叫 `model_registry()`
- **THEN** `model_registry()["faster-whisper"] == "Systran/faster-whisper-medium"`

#### Scenario: faster-whisper repo 切換 model
- **WHEN** `cfg.asr.model = "large-v3"` 且呼叫 `model_registry()`
- **THEN** `model_registry()["faster-whisper"] == "Systran/faster-whisper-large-v3"`

### Requirement: 預先下載介面
系統 SHALL 提供 `aureka.models.download_all(device: str = "auto") -> list[Path]` 函數，下載 `model_registry()` 中所有 entry，回傳所有已下載 snapshot 的本地路徑清單。

#### Scenario: 純下載不載入模型
- **WHEN** 呼叫 `download_all()`
- **THEN** 系統使用 `huggingface_hub.snapshot_download` 下載檔案，**不**建立 KPipeline 或 WhisperModel 物件，**不**佔用 GPU/MPS 記憶體

#### Scenario: 下載 Kokoro 與 faster-whisper
- **WHEN** 呼叫 `download_all()`
- **THEN** Kokoro 與 faster-whisper（model 由 config 決定）兩者皆會被下載

#### Scenario: 重複執行 idempotent
- **WHEN** 已下載完成後再次呼叫 `download_all()`
- **THEN** `snapshot_download` 比對本地 cache 後不重新下載，僅快速驗證並回傳路徑

#### Scenario: 切換 model 後下載新 model
- **WHEN** 使用者把 `cfg.asr.model` 從 `medium` 改成 `large-v3` 後重新執行 `aureka download`
- **THEN** 系統下載 `Systran/faster-whisper-large-v3`（舊的 `medium` cache 不會自動刪除）

### Requirement: 失敗 Fail-Fast
系統 SHALL 在任一模型下載失敗時立即拋出例外、印出錯誤訊息並停止後續下載，避免靜默忽略錯誤。

#### Scenario: 網路錯誤
- **WHEN** `snapshot_download` 因網路問題拋出例外
- **THEN** `download_all()` 不繼續下載剩餘模型，向上拋出例外

#### Scenario: 受限 repo 無權限
- **WHEN** 任一目標 repo 因 HuggingFace token 缺失或權限不足而下載失敗
- **THEN** 系統印出錯誤訊息並建議執行 `huggingface-cli login`，以 non-zero exit code 結束

### Requirement: 尊重 HuggingFace Cache 環境變數
系統 SHALL 透過呼叫 `huggingface_hub.snapshot_download` 自動繼承 `HF_HOME`、`HF_HUB_CACHE` 等環境變數的設定，不另外定義 cache 路徑。

#### Scenario: 自訂 cache 位置
- **WHEN** 使用者設定 `HF_HOME=/data/hf-cache` 並執行 `download_all()`
- **THEN** 模型下載至 `/data/hf-cache` 之下，不使用預設 `~/.cache/huggingface`

