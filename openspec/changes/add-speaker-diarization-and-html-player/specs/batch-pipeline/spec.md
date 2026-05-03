## Overview

This delta plumbs speaker labels through every existing writer (Markdown / SRT / VTT) and adds a **self-contained interactive HTML transcript** with embedded audio, canvas waveform, and click-to-seek navigation. The HTML output turns a flat batch transcript into a usable review tool: the user clicks any segment to play it back, clicks the waveform to jump to a moment, and watches the active segment auto-highlight as audio plays — all without an internet connection or external player.

## ADDED Requirements

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
