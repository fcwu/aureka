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
系統 SHALL 支援 `transcribe`、`refine`、`translate` 三種 AI 後處理模式。Streaming 模式下，partial transcripts 是否 inject 到游標由 mode 決定：`transcribe` 模式 inject、`refine`/`translate` 模式不 inject（避免 raw 文字污染使用者草稿、再被 LLM-refined 文字覆寫造成 flicker）。最終的 LLM-refined 文字（refine/translate 模式）一次性 inject 到游標。

#### Scenario: transcribe 模式注入（buffer 模式，向下相容）
- **WHEN** 模式為 `transcribe` 且收到 `transcript final: true`
- **THEN** 系統將完整轉錄文字注入游標位置

#### Scenario: transcribe 模式注入（streaming 模式）
- **WHEN** 模式為 `transcribe` 且 streaming 啟用
- **THEN** 每收到一個 partial transcript（`is_partial: true`）就 append inject 到游標；收到 `done` 即結束

#### Scenario: refine 模式串流替換（streaming 與 buffer 共用）
- **WHEN** 模式為 `refine` 且收到 `refined` token
- **THEN** 系統注入 refined 文字（首個 token 為純 inject，後續以 backspace+retype 替換）直到 `final: true`

#### Scenario: refine / translate 模式 streaming partial 不 inject
- **WHEN** 模式為 `refine` 或 `translate` 且 streaming 啟用，收到 partial transcript（`is_partial: true`）
- **THEN** 系統 **不** inject partial 文字到游標，只在 stderr 印出 `[aureka] partial: <text>` 作為命令列進度回饋；待收到 `refined final: true` 才一次性 inject 最終文字

#### Scenario: translate 模式
- **WHEN** 模式為 `translate` 且指定目標語言
- **THEN** 收到 `refined final: true` 後一次性注入翻譯結果（streaming 模式下不 inject partial）

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

### Requirement: aureka type 預設啟用 streaming
系統 SHALL 在 `aureka type` 預設啟用 streaming 模式（送出 `start` message 含 `streaming: true`），並提供 `--no-streaming` 旗標讓使用者退回 buffer 模式（debug 或 daemon streaming 不可用時的對照）。

#### Scenario: 預設啟用
- **WHEN** 使用者執行 `aureka type`（無 `--no-streaming` 旗標）
- **THEN** Client 送出 `start` message 含 `streaming: true`

#### Scenario: 顯式停用
- **WHEN** 使用者執行 `aureka type --no-streaming`
- **THEN** Client 送出 `start` message 含 `streaming: false`，daemon 走原本的 buffer-then-transcribe 流程

#### Scenario: Streaming 啟用時邊錄邊送
- **WHEN** Client 在 streaming 模式下開始錄音
- **THEN** Recorder 透過 `on_chunk` callback 把每個 chunk 立刻 base64 編碼送到 daemon WS（不再等錄完才一次送）

