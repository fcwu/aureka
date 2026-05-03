## Overview

This delta surfaces the resemblyzer voice-encoder weights in the Settings UI Models tab so users pre-download or check status from the GUI — same UX as Kokoro and faster-whisper. Users who have not installed `[diarize]` see no extra row (no false advertising); installing the extra makes the row appear automatically next time the window is opened.

## ADDED Requirements

### Requirement: Models 分頁顯示 resemblyzer
設定視窗 Models 分頁 SHALL 在 `[diarize]` 已安裝時顯示 resemblyzer 權重的下載狀態（同 Kokoro / faster-whisper 的 UX），未安裝時該條目不顯示。

#### Scenario: 已安裝 [diarize] 時顯示
- **WHEN** 使用者於 `[diarize]` 已安裝環境開啟 Models 分頁
- **THEN** 出現第三條 row 顯示 `resemblyzer` repo id、是否已下載、磁碟大小，附 Download / Re-download 按鈕

#### Scenario: 未安裝 [diarize] 時不顯示
- **WHEN** 使用者於未安裝 `[diarize]` 環境開啟 Models 分頁
- **THEN** UI 僅顯示 Kokoro 與 faster-whisper 兩條，不渲染 resemblyzer

#### Scenario: 下載觸發進度條
- **WHEN** 使用者按下 resemblyzer 的 Download
- **THEN** UI 走與既有模型一致的 polling 進度條流程，下載完成後狀態更新為 Downloaded
