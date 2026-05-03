## ADDED Requirements

### Requirement: 跨平台 Loopback 擷取介面
系統 SHALL 在 `aureka/audio_loopback.py` 提供 `LoopbackStream` 類別封裝平台差異：macOS 透過虛擬音訊裝置（如 BlackHole）、Windows 透過 WASAPI Loopback、Linux 透過 PulseAudio monitor source；統一以 16 kHz mono int16 PCM 對外輸出。

#### Scenario: macOS 偵測 BlackHole
- **WHEN** macOS 上有任一名稱符合 `^BlackHole.*$` 或 `^Loopback.*$` 的音訊輸入裝置
- **THEN** `LoopbackStream.detect()` 回傳該裝置；否則回傳 `None`，搭配清晰的 install 提示

#### Scenario: Windows WASAPI Loopback
- **WHEN** Windows 上呼叫 `LoopbackStream.detect()`
- **THEN** 系統取得當前預設輸出裝置的 loopback 輸入 handle，不需安裝任何驅動

#### Scenario: Linux Monitor Source
- **WHEN** Linux 上有任一 `.monitor` PulseAudio source
- **THEN** `LoopbackStream.detect()` 回傳第一個 monitor source

#### Scenario: 統一輸出格式
- **WHEN** 任一平台的 `LoopbackStream.read()` 被呼叫
- **THEN** 回傳 16 kHz、單聲道、int16 PCM frame，與 `aureka.recorder.Recorder` 的麥克風輸出格式一致

### Requirement: 串流 ASR 整合
`aureka listen` 子命令 SHALL 把 `LoopbackStream` 的輸出餵進現有 VAD 切段 + ASR 流水線，每個完整 utterance 對應一條 transcript 記錄；refine / translate 模式繼續走 daemon 的 LLM 路徑。

#### Scenario: VAD 切段
- **WHEN** loopback 持續輸入，使用者連續說話 5 秒後停頓
- **THEN** 系統在停頓處切段，完整 5 秒 utterance 被送入 ASR 並產出一條 transcript

#### Scenario: refine 模式走 daemon
- **WHEN** `aureka listen --mode refine` 且 daemon 運行中
- **THEN** transcript 透過 WebSocket `/listen` 送至 daemon，daemon 回傳 LLM refined 結果

#### Scenario: 雙路擷取（--mic）
- **WHEN** `aureka listen --mic` 啟動
- **THEN** 系統同時開兩條 stream（loopback + mic），各自 VAD 切段，輸出 transcript 帶 label `[system]` 或 `[mic]`

### Requirement: 失敗模式與診斷
系統 SHALL 在 loopback 不可用時提供具操作性的錯誤訊息，包含安裝指引或設定步驟。

#### Scenario: macOS 無 BlackHole
- **WHEN** macOS 執行 `aureka listen`、`detect_loopback()` 回傳 `None`
- **THEN** 印出含 `brew install --cask blackhole-2ch` 與 README 章節連結的訊息，exit code 非 0

#### Scenario: aureka doctor audio
- **WHEN** 執行 `aureka doctor audio`
- **THEN** 系統列出當前平台所有音訊輸入裝置、標記哪些是 loopback、印出當前路由是否正確
