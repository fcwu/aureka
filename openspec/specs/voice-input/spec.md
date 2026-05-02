## Purpose

定義語音輸入工作流程：熱鍵觸發 → 錄音 → ASR → 可選 LLM 修飾/翻譯 → 文字注入到游標位置。

## Requirements

### Requirement: 全域熱鍵觸發錄音
系統 SHALL 支援透過可設定的全域熱鍵（預設 `Ctrl+Alt+Space`）觸發語音輸入工作階段。

#### Scenario: 按下熱鍵開始錄音
- **WHEN** 使用者按下設定的熱鍵（hold-to-record 模式）
- **THEN** 系統開始從麥克風錄音，並建立 WebSocket 連線到 daemon

#### Scenario: 放開熱鍵停止錄音
- **WHEN** 使用者放開熱鍵（hold-to-record 模式）
- **THEN** 系統停止錄音並送出 `{"type": "end"}` 訊息

### Requirement: 錄音模式支援
系統 SHALL 支援三種錄音模式：`hold-to-record`（預設）、`toggle`、`VAD`。

#### Scenario: hold-to-record 模式
- **WHEN** 模式設為 `hold-to-record`
- **THEN** 熱鍵按住期間持續錄音，放開即停止

#### Scenario: toggle 模式
- **WHEN** 模式設為 `toggle`
- **THEN** 第一次按熱鍵開始錄音，第二次按熱鍵停止錄音

#### Scenario: VAD 模式
- **WHEN** 模式設為 `vad`
- **THEN** 偵測到靜音超過閾值時自動停止錄音

### Requirement: AI 後處理模式
系統 SHALL 支援 `transcribe`、`refine`、`translate` 三種 AI 後處理模式。

#### Scenario: transcribe 模式注入
- **WHEN** 模式為 `transcribe` 且收到 `transcript final: true`
- **THEN** 系統將轉錄文字注入游標位置

#### Scenario: refine 模式串流替換
- **WHEN** 模式為 `refine` 且收到 `refined` token
- **THEN** 系統先注入草稿，收到後續 token 時替換（退格 + 重新注入）直到 `final: true`

#### Scenario: translate 模式
- **WHEN** 模式為 `translate` 且指定目標語言
- **THEN** 收到 `refined final: true` 後一次性注入翻譯結果

### Requirement: 文字注入
系統 SHALL 將轉錄/修飾後的文字注入目前游標所在位置，支援 macOS、Windows、Linux X11。

#### Scenario: Linux X11 注入
- **WHEN** 平台為 Linux X11
- **THEN** 系統優先使用 `xdotool type` 注入；若失敗則使用剪貼簿注入並還原原始剪貼簿內容

#### Scenario: macOS 注入
- **WHEN** 平台為 macOS
- **THEN** 系統使用剪貼簿 + Cmd+V 注入，注入後還原原始剪貼簿內容

#### Scenario: 替換注入（refine 模式）
- **WHEN** 需要替換前次注入的文字
- **THEN** 系統記錄前次注入字數，先送出對應數量的退格鍵，再注入新文字

### Requirement: 系統托盤圖示
系統 SHALL 在系統托盤顯示圖示，提供右鍵選單（設定模式、退出）。

#### Scenario: 托盤圖示顯示
- **WHEN** `aureka daemon start` 啟動後且 client 執行中
- **THEN** 系統托盤顯示 Aureka 圖示

#### Scenario: 右鍵選單切換模式
- **WHEN** 使用者在托盤圖示點右鍵並選擇模式
- **THEN** 後續語音輸入使用新模式
