## ADDED Requirements

### Requirement: SRT 字幕輸出
`aureka.pipeline` SHALL 提供 `aureka.subtitle.write_srt(segments, path)`，將 batch pipeline 既有的 `(t_start, t_end, text)` segment 序列寫入合法的 SubRip Subtitle (SRT) 檔。

#### Scenario: 單段輸出格式
- **WHEN** 寫入單段 segment `(0.0, 2.5, "今天天氣很好")`
- **THEN** 檔案內容為：
  ```
  1
  00:00:00,000 --> 00:00:02,500
  今天天氣很好

  ```
  （含結尾空行）

#### Scenario: 多段連續編號
- **WHEN** 寫入兩段 segment
- **THEN** 第一段 index = 1、第二段 index = 2，兩段間以單一空行分隔

#### Scenario: 毫秒精度
- **WHEN** segment 時間為 `1.234`
- **THEN** SRT 時間戳格式為 `00:00:01,234`（逗號分隔毫秒）

### Requirement: WebVTT 字幕輸出
`aureka.pipeline` SHALL 提供 `aureka.subtitle.write_vtt(segments, path)`，輸出合法的 WebVTT 檔。

#### Scenario: WEBVTT 標頭
- **WHEN** 寫入任意 segments
- **THEN** 檔案第一行為 `WEBVTT`、第二行為空行

#### Scenario: 點分毫秒格式
- **WHEN** segment 時間為 `1.234`
- **THEN** VTT 時間戳格式為 `00:00:01.234`（點分隔毫秒）

### Requirement: --format 旗標選擇輸出格式
`aureka process` SHALL 接受 `--format` 旗標，值為 `md` / `srt` / `vtt` / `all` 或任意逗號組合。預設 `md`，與既有行為一致；可同時要求多種格式。

#### Scenario: 預設行為不變
- **WHEN** 執行 `aureka process video.mp4`（不帶 `--format`）
- **THEN** 只產出 `.md`（與本變更前的行為一致）

#### Scenario: 全格式輸出
- **WHEN** 執行 `aureka process video.mp4 --format all`
- **THEN** 同目錄產出 `.md`、`.srt`、`.vtt` 三個檔案

#### Scenario: 多格式組合
- **WHEN** 執行 `aureka process video.mp4 --format md,srt`
- **THEN** 產出 `.md` 與 `.srt`，不產出 `.vtt`
