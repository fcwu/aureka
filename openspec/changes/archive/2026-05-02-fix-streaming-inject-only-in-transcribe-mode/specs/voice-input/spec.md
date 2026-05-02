## MODIFIED Requirements

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
