## Purpose

定義 `aureka` CLI 的子命令介面、全域旗標與設定檔載入規則。
## Requirements
### Requirement: process 子命令
系統 SHALL 提供 `aureka process <file>` 子命令，執行批次流水線。

#### Scenario: 基本批次處理
- **WHEN** 執行 `aureka process video.mp4`
- **THEN** 系統執行完整批次流水線並輸出 Markdown 結果路徑

#### Scenario: 自訂參數
- **WHEN** 執行 `aureka process podcast.mp3 --frame-interval 60 --device cuda`
- **THEN** 系統使用指定的畫面擷取間隔和計算裝置

### Requirement: speak 子命令
系統 SHALL 提供 `aureka speak` 子命令，執行 TTS 回讀。

#### Scenario: 直接文字朗讀
- **WHEN** 執行 `aureka speak "今天的工作重點是什麼"`
- **THEN** 系統合成並播放語音

#### Scenario: 檔案朗讀
- **WHEN** 執行 `aureka speak --file path/to/note.md`
- **THEN** 系統讀取並朗讀檔案內容（略過 frontmatter 和 Markdown 標記）

### Requirement: type 子命令
系統 SHALL 提供 `aureka type` 子命令，觸發單次語音輸入（daemon 未啟動時有冷啟動延遲）。

#### Scenario: 基本語音輸入
- **WHEN** 執行 `aureka type`
- **THEN** 系統錄音後轉錄並注入文字到游標位置

#### Scenario: refine 模式
- **WHEN** 執行 `aureka type --mode refine`
- **THEN** 系統轉錄後以 LLM 修飾並注入

#### Scenario: translate 模式
- **WHEN** 執行 `aureka type --mode translate --lang en`
- **THEN** 系統轉錄後翻譯成英文並注入

### Requirement: daemon 子命令
系統 SHALL 提供 `aureka daemon start/stop/status` 子命令管理 daemon 程序。

#### Scenario: 啟動 daemon
- **WHEN** 執行 `aureka daemon start`
- **THEN** Daemon 在背景啟動，輸出確認訊息含監聽位址

#### Scenario: 停止 daemon
- **WHEN** 執行 `aureka daemon stop`
- **THEN** Daemon 程序終止，輸出確認訊息

#### Scenario: 查詢 daemon 狀態
- **WHEN** 執行 `aureka daemon status`
- **THEN** 輸出 daemon 是否執行中，若執行中顯示 PID 和 uptime

### Requirement: 全域 --device 旗標
系統 SHALL 支援全域 `--device` 旗標（`auto`、`cuda`、`mps`、`cpu`），覆蓋自動裝置偵測。

#### Scenario: 強制 CPU 裝置
- **WHEN** 執行 `aureka process video.mp4 --device cpu`
- **THEN** 系統強制使用 CPU 進行 ASR 和 TTS，忽略 GPU 可用性

### Requirement: 設定檔路徑
系統 SHALL 支援 `AUREKA_CONFIG` 環境變數指定 `config.toml` 路徑，預設為 `./config.toml`。

#### Scenario: 自訂設定檔
- **WHEN** 設定 `AUREKA_CONFIG=/path/to/my-config.toml` 並執行任何子命令
- **THEN** 系統從指定路徑載入設定

#### Scenario: 設定檔不存在
- **WHEN** 指定的設定檔路徑不存在
- **THEN** 系統輸出錯誤訊息提示如何產生設定檔（`cp config.example.toml config.toml`）

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

