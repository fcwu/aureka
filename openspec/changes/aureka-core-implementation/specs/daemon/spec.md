## ADDED Requirements

### Requirement: HTTP 健康檢查端點
系統 SHALL 提供 `GET /health` 端點，回傳 daemon 狀態。

#### Scenario: Daemon 正常運行
- **WHEN** Daemon 啟動完成且模型已載入
- **THEN** `GET /health` 回傳 HTTP 200 及 `{"status": "ok"}` 或包含模型狀態的 JSON

#### Scenario: Daemon 未啟動
- **WHEN** Daemon 未啟動時呼叫 `GET /health`
- **THEN** 連線被拒絕（Connection refused），client 應顯示「Daemon 未啟動」提示

### Requirement: WebSocket 語音輸入介面
系統 SHALL 在 `ws://127.0.0.1:7777/ws` 提供 WebSocket 端點，接收音訊串流並回傳轉錄/修飾結果。

#### Scenario: 完整語音輸入工作階段
- **WHEN** Client 依序送出 `start` → 多個 `chunk` → `end` 訊息
- **THEN** Server 依序回傳 `transcript` → （可選）`refined` → `done` 事件

#### Scenario: base64 PCM chunk 格式
- **WHEN** Client 送出 `{"type": "chunk", "data": "<base64>"}`
- **THEN** Server 解碼為 int16 PCM（16kHz mono），累積供 ASR 使用

#### Scenario: refine 模式串流輸出
- **WHEN** `start` 訊息中 `mode` 為 `"refine"`
- **THEN** ASR 完成後，Server 以 streaming 方式逐 token 送出 `refined` 事件，最後送 `final: true`

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
