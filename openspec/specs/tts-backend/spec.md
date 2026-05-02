## ADDED Requirements

### Requirement: Kokoro TTS 封裝
系統 SHALL 使用 Kokoro（82M 參數）作為 TTS 引擎，支援中英雙語，自動選擇 CUDA/MPS/CPU 裝置。

#### Scenario: 初始化 TTS
- **WHEN** `load_tts()` 被呼叫
- **THEN** 回傳已初始化的 Kokoro KPipeline，使用 `resolve_device()` 決定裝置

#### Scenario: 中文語音合成
- **WHEN** 呼叫 `speak("今天天氣很好")` 且語言為中文
- **THEN** 使用 `zf_xiaobei` 預設語音合成音訊

### Requirement: 直接播放
系統 SHALL 支援將 TTS 合成結果直接透過 sounddevice 播放。

#### Scenario: 即時播放
- **WHEN** 呼叫 `speak(text)` 未指定 output_path
- **THEN** 系統透過預設音訊輸出裝置播放合成語音，播放完畢後回傳

### Requirement: 儲存為 WAV 檔案
系統 SHALL 支援將 TTS 合成結果儲存為 24kHz WAV 檔案。

#### Scenario: 儲存音訊
- **WHEN** 呼叫 `speak(text, output_path="output.wav")`
- **THEN** 系統在指定路徑儲存 24kHz mono WAV 檔案，不播放

### Requirement: 從檔案讀取文字朗讀
系統 SHALL 支援讀取 Markdown 或純文字檔案並朗讀其內容（略過 frontmatter 和 Markdown 語法）。

#### Scenario: 朗讀 Markdown 檔案
- **WHEN** 執行 `aureka speak --file note.md`
- **THEN** 系統略過 frontmatter（`---` 包圍區塊）和 Markdown 標記符號，朗讀純文字內容
