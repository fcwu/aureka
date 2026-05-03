## ADDED Requirements

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
