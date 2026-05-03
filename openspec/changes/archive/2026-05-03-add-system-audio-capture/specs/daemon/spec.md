## Overview

This delta gives the daemon a long-lived `/listen` WebSocket endpoint so the listen client can stream system audio for as long as the user keeps it open — different lifetime semantics than the short-lived `/voice` sessions. Users get the same daemon speed-up they enjoy for `aureka type` (no per-session ASR/LLM cold start) but for hour-long meetings or lectures.

## ADDED Requirements

### Requirement: WebSocket /listen 端點
Daemon SHALL 提供 `/listen` WebSocket 端點，接受持續性的 PCM 串流並回傳逐段 transcript / refined 文字。Frame 格式與 `/voice` 類似但設計為長連線：

| 方向 | type | 欄位 | 說明 |
|------|------|------|------|
| client → server | `start` | `mode`, `lang`, `topic`, `label` | 開始一條 stream，`label` 為 `system` 或 `mic` |
| client → server | `audio` | `data` (base64 PCM) | 持續送 audio chunk |
| client → server | `end` | — | 主動結束（Ctrl+C 等） |
| server → client | `transcript` | `text`, `label`, `ts_start`, `ts_end`, `is_final` | 每段 ASR 結果 |
| server → client | `refined` | `text`, `label`, `is_final` | LLM refined / translated（refine / translate 模式） |

#### Scenario: 長連線維持
- **WHEN** client 開啟 `/listen`、持續送 `audio` 但無 `end`
- **THEN** Server 不主動關閉連線，每段 VAD 切完即推 transcript / refined 回 client

#### Scenario: 雙路 label
- **WHEN** client 同時開兩條 `/listen` 連線（label 分別為 `system` 和 `mic`）
- **THEN** Server 各自處理，回傳的 transcript / refined 都帶對應 label，client 可依 label 顯示或 forward

#### Scenario: idle timeout
- **WHEN** client 連線後超過 30 分鐘（可由 config 覆寫）沒有任何 audio frame
- **THEN** Server 主動關閉該 stream 並釋放 LLM session 狀態
