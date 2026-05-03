## ADDED Requirements

### Requirement: 模型下載狀態查詢
系統 SHALL 在 `aureka.models` 提供 `model_status() -> dict[str, dict]` 函數，對 `model_registry()` 中每個 entry 回報下載狀態，且本身不觸發任何下載；rendered shape 至少包含 `downloaded: bool`、`size_bytes: int`、`snapshot_path: str | None`。

#### Scenario: 全未下載
- **WHEN** 呼叫 `model_status()` 且本機尚未抓過任何模型
- **THEN** 回傳每個 key 對應 `{"downloaded": False, "size_bytes": 0, "snapshot_path": None}`

#### Scenario: 已下載 Kokoro、未下載 faster-whisper
- **WHEN** 本機 HuggingFace cache 已有 Kokoro 但無對應 faster-whisper
- **THEN** Kokoro 條目 `downloaded=True` 且 `size_bytes>0`、`snapshot_path` 指向實體目錄；faster-whisper 條目 `downloaded=False`

#### Scenario: 不觸發下載
- **WHEN** 系統呼叫 `model_status()`
- **THEN** 不執行 `snapshot_download`，僅讀取 cache（`huggingface_hub.scan_cache_dir` 或等效）

### Requirement: 下載進度回呼
系統 SHALL 為 `aureka.models.download_all` 增加可選 `progress: Callable[[dict], None] | None` 參數；若提供，系統 MUST 在每個模型開始下載、檔案進度更新、結束時呼叫該 callback，傳入至少包含 `phase`（`"start" | "progress" | "done" | "error"`）、`repo_key`、以及進度數值（如 `percent` 或 `bytes_done / bytes_total`）的 dict。

#### Scenario: 不傳 callback 行為不變
- **WHEN** 呼叫 `download_all()` 不傳 `progress`
- **THEN** 行為與 callback 不存在時完全一致（向後相容）

#### Scenario: callback 收到 start / done
- **WHEN** 呼叫 `download_all(progress=cb)` 並順利下載完 Kokoro
- **THEN** `cb` 至少被呼叫兩次，phase 分別為 `start`（含 `repo_key="kokoro"`）與 `done`（含 `repo_key="kokoro"`）

#### Scenario: callback 收到 error
- **WHEN** 任一 repo 下載失敗
- **THEN** `cb` 收到 `phase="error"`、`repo_key=<失敗的 key>`、`error=<message>`，且 `download_all` 仍按原行為向上拋出例外
