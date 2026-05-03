## Overview

This delta adds three opt-in flags to `aureka process` so users dial in diarization without breaking existing scripts: `--diarize` enables it, `--num-speakers N` overrides auto-detection (useful when the user knows there are exactly 3 panelists), and `--no-speaker-labels` keeps the colored HTML view but strips text-format prefixes for users producing clean translation tracks.

## ADDED Requirements

### Requirement: process 子命令 --diarize / --num-speakers / --no-speaker-labels
`aureka process` SHALL 接受 `--diarize`、`--num-speakers N`、`--no-speaker-labels` 三個與講者辨識相關的旗標。

#### Scenario: 啟用講者辨識
- **WHEN** 執行 `aureka process meeting.mp4 --diarize`
- **THEN** 系統在 ASR 後額外跑 diarization，所有輸出格式都帶講者標籤

#### Scenario: 指定講者人數
- **WHEN** 執行 `aureka process meeting.mp4 --diarize --num-speakers 3`
- **THEN** spectralcluster 強制以 3 群輸出；忽略自動偵測

#### Scenario: 講者辨識但不顯示文字標籤
- **WHEN** 執行 `aureka process meeting.mp4 --diarize --no-speaker-labels`
- **THEN** Markdown / SRT / VTT 內不顯示 `[S1]` 等前綴；HTML 仍以顏色標記講者

#### Scenario: --diarize 與 --format html 組合
- **WHEN** 執行 `aureka process meeting.mp4 --diarize --format html`
- **THEN** 產出的 HTML 含逐字稿、講者顏色、波形互動播放器
