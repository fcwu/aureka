## ADDED Requirements

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
