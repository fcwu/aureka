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

### Requirement: Topic 感知 LLM Prompt
`refine` 與 `translate` 模式 SHALL 將使用者設定的 topic 字串注入 LLM system message，作為領域提示。Topic 為空時 prompt 維持與既有版本逐字相同（regression-safe）。

#### Scenario: Topic 不為空時注入 system message
- **WHEN** 使用者送出 transcript，且當前 topic = `"ZFS storage"`，模式 = `refine`
- **THEN** 送至 LLM 的 system message 包含 topic 字串（例如「The user is working on the topic of \"ZFS storage\"...」）

#### Scenario: Topic 為空時 prompt 不變
- **WHEN** 使用者送出 transcript，且 topic = `""`
- **THEN** 送至 LLM 的 messages 與既有版本完全一致

#### Scenario: Translate 模式同樣套用
- **WHEN** 模式為 `translate`、topic 不為空
- **THEN** system message 在語言指令之前先帶 topic 提示

#### Scenario: Transcribe 模式不受影響
- **WHEN** 模式為 `transcribe`
- **THEN** 系統不呼叫 LLM，topic 即使有設值也不影響輸出

### Requirement: Tray icon 平台慣例
系統 SHALL 透過單一輔助函數 `aureka._icon.make_tray_icon() -> PIL.Image.Image` 產生 tray icon，並由所有 tray 入口（`aureka/tray.py` 與 `aureka/client.py:start_tray`）共同呼叫；icon 視覺需依當前平台慣例：

- **macOS**：黑色前景 + 透明背景的 monochrome glyph（最小邊長 ≥ 88px 以涵蓋 Retina），且系統 MUST 透過 pyobjc 把對應的 `NSImage` 設為 `template`，使 menu bar 自動依淺/深色模式反白。
- **Windows / Linux / 其他**：彩色 glyph（推薦圓角方背景 + 白色前景），最小邊長 ≥ 64px。

無論平台，icon 的視覺主體 SHALL 一致：以線條風格的字母「A」加上 2–3 顆小型 4 角星 sparkle 為主視覺；macOS 為黑色 + alpha，Windows 為藍色（accent `#3b82f6`）+ alpha。

#### Scenario: macOS 取得 template image
- **WHEN** 在 macOS 執行任一 tray 入口
- **THEN** 系統呼叫 `make_tray_icon()` 取回 monochrome RGBA 圖；pystray 啟動後系統嘗試對其 NSStatusItem 的 button image 設 `isTemplate=True`

#### Scenario: macOS template shim 失敗 fail-soft
- **WHEN** 設 `isTemplate=True` 因 pystray 內部結構變更而失敗
- **THEN** 系統印出警告，icon 仍以 monochrome 形式顯示，整體應用不中斷

#### Scenario: Windows 彩色 icon
- **WHEN** 在 Windows 執行任一 tray 入口
- **THEN** `make_tray_icon()` 回傳彩色版（背景非透明、有可辨識主視覺色）；不嘗試任何 macOS-only API

#### Scenario: 兩個 tray 視覺一致
- **WHEN** 同一台機器上分別啟動 `aureka tray` 與 `aureka client tray`（或日常的 `start_tray`）
- **THEN** 兩者顯示的 icon 完全相同（共用 helper），不會出現一個藍底白圈、一個藍底白「A」的不一致狀態

#### Scenario: Glyph 為「A + sparkles」
- **WHEN** 任何平台呼叫 `make_tray_icon()`
- **THEN** 回傳影像的主體為線條風格的字母「A」，並在右側帶有 2–3 顆 4 角星 sparkle 裝飾，視覺主體與參考設計一致

### Requirement: Tray 啟動時自動拉起 daemon
任一 tray 入口（`aureka tray` / `aureka.client.start_tray`）啟動時 MUST 檢查 daemon 是否在 `(cfg.daemon.host, cfg.daemon.port)` 上監聽；若否，系統 SHALL 自動 spawn `aureka daemon start` 作為背景子行程並使用 `start_new_session=True` 讓 daemon 獨立於 tray 生命週期。Tray 退出（Quit）SHALL NOT 連帶停止 daemon。

#### Scenario: Daemon 已運行
- **WHEN** 使用者執行 `aureka tray` 且 daemon 已在預設 port 監聽
- **THEN** Tray 不重新拉 daemon，icon 直接出現

#### Scenario: Daemon 未運行
- **WHEN** 使用者執行 `aureka tray` 但 daemon 未啟動
- **THEN** Tray 自動 spawn `aureka daemon start` 後正常啟動 icon；daemon 在背景完成 ASR/TTS 載入

#### Scenario: Tray Quit 不影響 daemon
- **WHEN** 使用者從 tray 選單按下 Quit
- **THEN** Tray 處理程序結束、icon 消失；daemon 繼續運行，後續 `aureka type` / `aureka speak` 仍走 daemon 加速路徑

### Requirement: Pause/Resume 熱鍵
語音輸入流程（`aureka type`、`aureka listen`、tray client）SHALL 支援可設定的 Pause/Resume 熱鍵，預設 `<ctrl>+<alt>+p`，存於 `cfg.hotkey.pause`。按下時切換 `Recorder` / `LoopbackStream` 的 `running` ↔ `paused` 狀態，paused 期間捨棄 audio chunk 但保留 LLM session 狀態。

#### Scenario: 切換暫停
- **WHEN** 錄音中按下 pause hotkey
- **THEN** Recorder 進入 paused 狀態，後續 audio chunk 被捨棄、不送 ASR；stderr 印出 `[paused]`

#### Scenario: 切換繼續
- **WHEN** Recorder 處於 paused 狀態，按下 pause hotkey
- **THEN** Recorder 進入 running 狀態，繼續送 audio；stderr 印出 `[resumed]`

#### Scenario: LLM session 跨越 pause 仍存在
- **WHEN** refine / translate 模式下使用者 pause 後 30 秒再 resume
- **THEN** Daemon 端對應 session 未被釋放，後續 transcript 與 pause 前共用同一個 LLM context

#### Scenario: Tray 同步狀態
- **WHEN** 使用者透過 tray 「Pause capture」勾選項切換
- **THEN** 同樣的 paused 狀態被切換；hotkey 與 tray 兩個入口共享狀態

#### Scenario: stop 跳過 paused 狀態
- **WHEN** Recorder 處於 paused 狀態時被呼叫 stop
- **THEN** Recorder 進入 stopped 狀態（直接結束），不需要先 resume

