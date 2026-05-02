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
