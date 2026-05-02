## MODIFIED Requirements

### Requirement: AI 後處理模式
系統 SHALL 支援 `transcribe`、`refine`、`translate` 三種 AI 後處理模式。在 streaming 模式下，partial transcripts（每個 VAD segment 的 ASR 結果）會即時 inject 到游標，最終的 LLM-refined 文字（refine/translate 模式）會 replace 整段累積長度。

#### Scenario: transcribe 模式注入（buffer 模式，向下相容）
- **WHEN** 模式為 `transcribe` 且收到 `transcript final: true`
- **THEN** 系統將完整轉錄文字注入游標位置

#### Scenario: transcribe 模式注入（streaming 模式）
- **WHEN** 模式為 `transcribe` 且 streaming 啟用
- **THEN** 每收到一個 partial transcript（`is_partial: true`）就 append inject 到游標；收到 `done` 即結束

#### Scenario: refine 模式串流替換（streaming 與 buffer 共用）
- **WHEN** 模式為 `refine` 且收到 `refined` token
- **THEN** 系統先注入草稿，收到後續 token 時替換（退格 + 重新注入）直到 `final: true`

#### Scenario: refine 模式 streaming partial inject
- **WHEN** 模式為 `refine` 且 streaming 啟用，收到 partial transcript（`is_partial: true`）
- **THEN** 系統 append inject partial 文字到游標（給使用者「系統有在聽」的回饋），追蹤 `injected_len` 累計；後續收到 `refined` 事件時用 `replace_text(injected_len, refined_text)` 蓋寫整段

#### Scenario: translate 模式
- **WHEN** 模式為 `translate` 且指定目標語言
- **THEN** 收到 `refined final: true` 後一次性注入翻譯結果（streaming 模式下若先有 partial transcript inject，則最終 refined 來時 replace 整段）

## ADDED Requirements

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
