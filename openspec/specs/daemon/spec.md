## Purpose

定義 aureka 背景 daemon 的 HTTP/WebSocket 介面、生命週期與模型預載行為。
## Requirements
### Requirement: HTTP 健康檢查端點
系統 SHALL 提供 `GET /health` 端點，回傳 daemon 狀態。

#### Scenario: Daemon 正常運行
- **WHEN** Daemon 啟動完成且模型已載入
- **THEN** `GET /health` 回傳 HTTP 200 及 `{"status": "ok"}` 或包含模型狀態的 JSON

#### Scenario: Daemon 未啟動
- **WHEN** Daemon 未啟動時呼叫 `GET /health`
- **THEN** 連線被拒絕（Connection refused），client 應顯示「Daemon 未啟動」提示

### Requirement: WebSocket 語音輸入介面
系統 SHALL 在 `ws://127.0.0.1:7777/ws` 提供 WebSocket 端點，接收音訊串流並回傳轉錄/修飾結果。支援兩種運作模式：buffer（向下相容）與 streaming（VAD-segmented）。

#### Scenario: 完整語音輸入工作階段（buffer 模式，向下相容）
- **WHEN** Client 送出 `start` 訊息（不含 `streaming` 欄位或 `streaming: false`），接著送多個 `chunk` → `end` 訊息
- **THEN** Server 累積所有 chunks 後一次性轉錄，依序回傳 `transcript` → （可選）`refined` → `done` 事件

#### Scenario: 完整語音輸入工作階段（streaming 模式）
- **WHEN** Client 送出 `start` 訊息含 `streaming: true`，接著邊錄邊送 `chunk`，最後送 `end`
- **THEN** Server 每偵測到一個語句邊界（VAD silence threshold）就立刻轉錄該段並推 `transcript` partial 事件，收到 `end` 後 flush 剩餘 buffer + 對完整累積 transcript 跑 LLM refine（若 mode 為 refine/translate），最後送 `done`

#### Scenario: base64 PCM chunk 格式
- **WHEN** Client 送出 `{"type": "chunk", "data": "<base64>"}`
- **THEN** Server 解碼為 int16 PCM（16kHz mono），累積供 ASR 使用

#### Scenario: refine 模式串流輸出（streaming 與 buffer 共用）
- **WHEN** `start` 訊息中 `mode` 為 `"refine"`
- **THEN** ASR 階段（buffer：完整轉錄；streaming：所有 partial 累積）完成後，Server 對完整 transcript 以 streaming 方式逐 token 送出 `refined` 事件，最後送 `final: true`

#### Scenario: streaming 模式 partial transcript 推送
- **WHEN** Daemon 在 streaming 模式下偵測到 VAD segment-close
- **THEN** Server 對該 segment 跑 ASR，立刻推 `{"type": "transcript", "text": "<段落文字>", "final": false, "is_partial": true}` 事件，使 client 能即時 inject

#### Scenario: streaming 模式 fallback
- **WHEN** Client 送 `streaming: true` 但 daemon 端 silero-vad 載入失敗
- **THEN** Server silently 走 buffer 模式（功能不變但失去 partial 推送），daemon log 寫一筆 warning

#### Scenario: WebSocket 連線異常中斷
- **WHEN** Client 在工作階段中途斷線
- **THEN** Server 清理資源，不影響其他連線

### Requirement: HTTP 批次處理端點
系統 SHALL 提供 `POST /process` 端點，接受音訊/影片檔案路徑，執行批次流水線。

#### Scenario: 提交批次任務
- **WHEN** Client 送出 `POST /process` 含檔案路徑
- **THEN** Server 回傳任務 ID，並在背景非同步執行批次流水線

### Requirement: 模型預載
系統 SHALL 在 daemon 啟動時預載 ASR 模型（和可選的 TTS 模型），避免每次語音輸入重載。

#### Scenario: 啟動時載入 ASR 模型
- **WHEN** `aureka daemon start` 執行
- **THEN** Daemon 在接受第一個 WebSocket 連線前完成 ASR 模型載入

#### Scenario: 載入失敗
- **WHEN** ASR 模型載入失敗（例如記憶體不足）
- **THEN** Daemon 輸出錯誤訊息並以非零退出碼結束

### Requirement: Daemon 程序管理
系統 SHALL 支援 `aureka daemon start/stop/status` 管理 daemon 程序，log 輸出至 `/tmp/aureka-daemon.log`。

#### Scenario: start 啟動 daemon
- **WHEN** 執行 `aureka daemon start`
- **THEN** Daemon 在背景執行，PID 記錄，log 寫入 `/tmp/aureka-daemon.log`

#### Scenario: stop 停止 daemon
- **WHEN** 執行 `aureka daemon stop`
- **THEN** Daemon 程序終止，資源釋放

#### Scenario: 重複啟動
- **WHEN** Daemon 已在執行時再次執行 `aureka daemon start`
- **THEN** 系統提示 daemon 已在執行，不建立新程序

### Requirement: VAD-Segmented Streaming ASR
系統 SHALL 在 daemon 端整合 silero-vad 作為 streaming 模式的語句邊界偵測器。Daemon 啟動時嘗試載入 silero-vad；載入成功則 streaming 路徑可用，失敗則 fail-soft 回退到 buffer 路徑。

#### Scenario: silero-vad 啟動載入成功
- **WHEN** Daemon 啟動並成功 import silero-vad
- **THEN** WS handler 在收到 `streaming: true` 時走 VAD 路徑

#### Scenario: silero-vad 啟動載入失敗
- **WHEN** Daemon 啟動但 silero-vad 載入失敗（套件缺失、onnx download 失敗等）
- **THEN** Daemon log 一筆 warning（一次性）；後續 WS 即使收到 `streaming: true` 也 silently 走 buffer 路徑

#### Scenario: VAD 偵測語句邊界
- **WHEN** Daemon 在 streaming 模式累積 audio buffer，silero-vad 偵測到連續 600ms 靜音（語句結束）
- **THEN** Daemon 把當前 utterance（從上次 segment-close 到偵測點）丟給 ASR，並開始累積下一段

#### Scenario: end 訊息 flush 剩餘 buffer
- **WHEN** Streaming 模式下 daemon 收到 client `{"type": "end"}` 訊息但仍有未轉錄的 audio buffer
- **THEN** Daemon 把剩餘 buffer 當成最後一個 segment 跑 ASR，推最後一個 partial transcript（`final: false, is_partial: true`），然後進入 LLM refine 階段

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

