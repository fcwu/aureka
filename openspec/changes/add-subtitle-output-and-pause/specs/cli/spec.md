## ADDED Requirements

### Requirement: process 子命令 --format 旗標
`aureka process` SHALL 接受 `--format` 旗標，值為 `md` / `srt` / `vtt` / `all` 或任意逗號組合，控制輸出哪些字幕 / 文件格式。

#### Scenario: 多格式並存
- **WHEN** 執行 `aureka process video.mp4 --format md,vtt`
- **THEN** 系統同時產出 `.md` 與 `.vtt`

#### Scenario: 無效值報錯
- **WHEN** 執行 `aureka process video.mp4 --format pdf`
- **THEN** 系統以 non-zero exit code 結束，stderr 印出有效值清單

### Requirement: type / listen 子命令尊重 [hotkey].pause
`aureka type` 與 `aureka listen` SHALL 在啟動時讀取 `cfg.hotkey.pause`，若不為空則註冊該熱鍵為暫停 / 繼續切換。

#### Scenario: 預設 pause 鍵
- **WHEN** config 沒設 `[hotkey].pause`、執行 `aureka type`
- **THEN** 系統綁定預設 `<ctrl>+<alt>+p` 為暫停鍵

#### Scenario: 自訂 pause 鍵
- **WHEN** config `[hotkey].pause = "<f12>"`、執行 `aureka type`
- **THEN** 系統改綁定 F12 為暫停鍵

#### Scenario: 與 trigger 衝突警告
- **WHEN** `[hotkey].trigger` 與 `[hotkey].pause` 設為同一值
- **THEN** 系統 stderr 印出警告，pause 熱鍵不註冊（trigger 優先）
