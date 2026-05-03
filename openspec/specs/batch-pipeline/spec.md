## Purpose

定義批次流水線（影片/音訊 → ASR + 關鍵畫面 + LLM 摘要 → Markdown）的輸入、處理階段與輸出規則。
## Requirements
### Requirement: 接受影片或音訊輸入
系統 SHALL 接受 `.mp4`、`.mkv`、`.mov`、`.mp3`、`.wav`、`.m4a` 格式的輸入檔案。

#### Scenario: 有效影片輸入
- **WHEN** 使用者執行 `aureka process video.mp4`
- **THEN** 系統開始處理並輸出進度訊息

#### Scenario: 無效格式輸入
- **WHEN** 使用者傳入不支援格式的檔案（如 `.txt`）
- **THEN** 系統輸出明確錯誤訊息並以非零退出碼結束

### Requirement: 音訊軌提取
系統 SHALL 使用 ffmpeg 從影片提取 16kHz mono WAV 音訊軌，供 ASR 使用。

#### Scenario: 成功提取音訊
- **WHEN** 輸入為合法影片檔案
- **THEN** 系統在暫存目錄產生 16kHz mono WAV 檔案，並繼續 ASR 步驟

#### Scenario: ffmpeg 不存在
- **WHEN** 系統路徑找不到 `ffmpeg` 執行檔
- **THEN** 系統輸出安裝說明並終止

### Requirement: 關鍵畫面提取
系統 SHALL 以可設定的間隔（預設每 30 秒）從影片擷取關鍵畫面（JPEG），供 VLM 描述使用。

#### Scenario: 影片關鍵畫面提取
- **WHEN** 輸入為影片檔案且 VLM 已設定
- **THEN** 系統產生若干 JPEG 截圖，數量約等於 `duration / frame_interval`

#### Scenario: 純音訊輸入略過畫面提取
- **WHEN** 輸入為純音訊檔案（`.mp3`、`.wav` 等）
- **THEN** 系統略過畫面提取步驟，Markdown 輸出中「視覺內容」區塊留空或省略

### Requirement: ASR 轉錄
系統 SHALL 對提取的音訊執行 ASR，產生含時間戳記的逐字稿（segments）。

#### Scenario: 成功轉錄
- **WHEN** 音訊提取完成
- **THEN** 系統回傳 `[{start, end, text}, ...]` 格式的 segments

### Requirement: VLM 畫面描述
系統 SHALL 對每張關鍵畫面呼叫 VLM，取得畫面內容描述（文字、圖表、主題等）。

#### Scenario: VLM 成功描述畫面
- **WHEN** 關鍵畫面提取完成且 VLM 支援 vision
- **THEN** 每張截圖產生對應的文字描述，含畫面時間點

#### Scenario: VLM 不支援 vision
- **WHEN** 設定的 VLM 端點回應不含 vision 能力
- **THEN** 系統在啟動時輸出 fatal error 並終止

### Requirement: LLM 摘要結構化
系統 SHALL 將 ASR 逐字稿與 VLM 畫面描述交給 LLM，產生結構化摘要（標題、摘要、重點、逐段紀錄）。

#### Scenario: LLM 摘要成功
- **WHEN** ASR 與 VLM 結果均已取得
- **THEN** LLM 輸出符合輸出格式規範的 Markdown 內容

### Requirement: Markdown 輸出
系統 SHALL 將處理結果輸出為標準格式的 Markdown 檔案，路徑為 `output/YYYYMMDD-<slug>.md`。

#### Scenario: 輸出檔案產生
- **WHEN** LLM 摘要完成
- **THEN** 系統在 `output/` 目錄建立 Markdown 檔案，包含 frontmatter、摘要、重點、逐段紀錄、視覺內容、原始轉錄六個區塊

#### Scenario: 輸出目錄不存在
- **WHEN** `output/` 目錄不存在
- **THEN** 系統自動建立目錄再寫入檔案

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

### Requirement: 講者標籤帶入輸出
`aureka.pipeline` SHALL 在啟用 `--diarize` 時呼叫 `aureka.diarize.diarize` 並把得到的 `speaker` 欄位附加到每段 segment 的資料結構，後續所有 writers（Markdown / SRT / VTT / HTML）能取得該欄位。

#### Scenario: Markdown 帶講者標籤
- **WHEN** `--diarize` 啟用、Markdown 寫出
- **THEN** 每段標題包含講者，例如 `**[00:01:23] S1:** ...`

#### Scenario: SRT / VTT 帶講者前綴
- **WHEN** `--diarize` 啟用、SRT/VTT 寫出
- **THEN** 每段 cue 文字前綴為 `[S1] ` / `[S2] `

#### Scenario: --no-speaker-labels 移除前綴
- **WHEN** `--diarize --no-speaker-labels` 同時啟用
- **THEN** Markdown / SRT / VTT 內仍跑 diarization 但輸出文字不帶講者前綴；HTML 仍以顏色顯示講者

### Requirement: HTML 互動逐字稿
`aureka.pipeline` SHALL 提供 HTML 輸出格式（`--format html`），產生單一自包含 `.html` 檔，內含：
- `<audio>` 元素與本地擷取或連結的音訊檔
- `<canvas>` 渲染的波形（peaks 直接 inline 進頁面）
- 可點擊的逐字稿段落，每段顯示時間戳 + 講者顏色（若 `--diarize`）

#### Scenario: 點擊段落跳到對應音訊位置
- **WHEN** 使用者在 HTML 中點擊一段逐字稿
- **THEN** `<audio>` 元素 seek 到該段 `t_start`，該段以高亮樣式顯示

#### Scenario: 點擊波形跳到對應段落
- **WHEN** 使用者點擊波形 `<canvas>` 任意位置
- **THEN** 音訊 seek 到對應時間，該時間落點所在的逐字稿段落滾動到視窗中央並高亮

#### Scenario: 播放時自動高亮當前段落
- **WHEN** 使用者按 play、播放至某段時間範圍
- **THEN** 對應段落自動加上高亮樣式，逐字稿區塊自動滾動跟隨（除非使用者按下「鎖定捲動」按鈕）

#### Scenario: 講者顏色一致
- **WHEN** 同一份檔案中同一個講者的多段被渲染
- **THEN** 所有屬於該講者的段落使用同一顏色，且波形上的對應區段以相同顏色淡色 stripe 標記

#### Scenario: 自包含可離線
- **WHEN** 把 `.html` 檔與相鄰的音訊檔複製到無網路環境
- **THEN** 在任意現代瀏覽器仍可正常播放、互動，不依賴 CDN

