## ADDED Requirements

### Requirement: download 子命令
系統 SHALL 提供 `aureka download` 子命令，預先下載執行時會用到的所有模型，避免首次使用 `speak` / `type` / `daemon start` 時的長時間靜默等待。

#### Scenario: 基本下載
- **WHEN** 執行 `aureka download`
- **THEN** 系統呼叫 `aureka.models.download_all()`，依當前裝置環境下載 Kokoro、faster-whisper（必下載）以及在 CUDA/MPS + TheWhisper 可用時加碼下載 TheWhisper

#### Scenario: 下載過程顯示進度
- **WHEN** 執行 `aureka download` 且模型尚未存在於本地 cache
- **THEN** 終端顯示 `huggingface_hub` 內建的 tqdm 進度條，使用者可看到下載進度與速度

#### Scenario: 下載完成輸出摘要
- **WHEN** `aureka download` 全部模型下載成功
- **THEN** 終端依序列出每個模型的邏輯名稱、HuggingFace repo ID 與本地 snapshot 路徑

#### Scenario: 已下載則跳過
- **WHEN** 模型已存在於本地 cache 後再次執行 `aureka download`
- **THEN** 系統快速驗證 cache 並列印「已存在」摘要，不重新下載

#### Scenario: 下載失敗以 non-zero exit code 結束
- **WHEN** 任一模型下載失敗（網路、權限或磁碟錯誤）
- **THEN** `aureka download` 印出錯誤訊息並以 non-zero exit code 結束，不靜默忽略

#### Scenario: 接受 --device 旗標
- **WHEN** 執行 `aureka --device cpu download`
- **THEN** 系統把 `device` 視為 `cpu`，跳過 TheWhisper 的下載
