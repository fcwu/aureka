## ADDED Requirements

### Requirement: Tray icon 平台慣例
系統 SHALL 透過單一輔助函數 `aureka._icon.make_tray_icon() -> PIL.Image.Image` 產生 tray icon，並由所有 tray 入口（`aureka/tray.py` 與 `aureka/client.py:start_tray`）共同呼叫；icon 視覺需依當前平台慣例：

- **macOS**：黑色前景 + 透明背景的 monochrome glyph（最小邊長 ≥ 88px 以涵蓋 Retina），且系統 MUST 透過 pyobjc 把對應的 `NSImage` 設為 `template`，使 menu bar 自動依淺/深色模式反白。
- **Windows / Linux / 其他**：彩色 glyph（推薦圓角方背景 + 白色前景），最小邊長 ≥ 64px。

無論平台，icon 的視覺主體 SHALL 一致：以線條風格的字母「A」加上 2–3 顆小型 4 角星 sparkle 為主視覺；macOS 為黑色 + alpha，Windows 為藍色（accent `#3b82f6`）+ alpha。

#### Scenario: macOS 取得 template image
- **WHEN** 在 macOS 執行任一 tray 入口
- **THEN** 系統呼叫 `make_tray_icon()` 取回 monochrome RGBA 圖；pystray 啟動後系統嘗試對其 NSStatusItem 的 button image 設 `isTemplate=True`

#### Scenario: macOS template shim 失敗 fail-soft
- **WHEN** 設 `isTemplate=True` 因 pystray 內部結構變更而失敗
- **THEN** 系統印出警告，icon 仍以 monochrome 形式顯示，整體應用不中斷

#### Scenario: Windows 彩色 icon
- **WHEN** 在 Windows 執行任一 tray 入口
- **THEN** `make_tray_icon()` 回傳彩色版（背景非透明、有可辨識主視覺色）；不嘗試任何 macOS-only API

#### Scenario: 兩個 tray 視覺一致
- **WHEN** 同一台機器上分別啟動 `aureka tray` 與 `aureka client tray`（或日常的 `start_tray`）
- **THEN** 兩者顯示的 icon 完全相同（共用 helper），不會出現一個藍底白圈、一個藍底白「A」的不一致狀態

#### Scenario: Glyph 為「A + sparkles」
- **WHEN** 任何平台呼叫 `make_tray_icon()`
- **THEN** 回傳影像的主體為線條風格的字母「A」，並在右側帶有 2–3 顆 4 角星 sparkle 裝飾，視覺主體與參考設計一致
