# speaker-diarization Specification

## Purpose
TBD - created by archiving change add-speaker-diarization-and-html-player. Update Purpose after archive.
## Requirements
### Requirement: 離線講者辨識管線
系統 SHALL 在 `aureka/diarize.py` 提供 `diarize(audio_path, segments, num_speakers=None) -> list[str]` 函數，使用 resemblyzer voice encoder 提取每段 segment 的語音 embedding、再以 spectralcluster 分群得出講者標籤；全程不依賴 HuggingFace token、不上傳資料。

#### Scenario: 預設 auto 偵測講者數
- **WHEN** 呼叫 `diarize(path, segments)` 不帶 `num_speakers`
- **THEN** 系統在 `[2, 8]` 範圍內自動選擇講者數，回傳長度等於 `len(segments)` 的標籤序列

#### Scenario: 指定講者數
- **WHEN** 呼叫 `diarize(path, segments, num_speakers=3)`
- **THEN** spectralcluster 強制以 3 群輸出標籤；標籤值在 `{0, 1, 2}` 範圍

#### Scenario: 標籤格式化為 S1 / S2
- **WHEN** 系統把 raw cluster 標籤輸出給 pipeline
- **THEN** 標籤依「在 segment 序列中第一次出現的順序」對應為 `S1`、`S2`、...，順序穩定（同樣輸入產生同樣標籤）

#### Scenario: 過短 segment 不參與分群
- **WHEN** segment 持續時間 < 0.6s
- **THEN** 系統不對該 segment 取 embedding，改以前後最近相鄰 segment 的標籤填入，避免噪聲影響 cluster 中心

#### Scenario: 不依賴外部 API
- **WHEN** 在離線環境執行 `diarize`
- **THEN** 整個流程僅讀取本機 audio + 本機已下載的 resemblyzer 權重，不發任何網路請求

