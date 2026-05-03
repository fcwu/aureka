## Overview

This delta adds a Listen tab to the Settings UI so users pick the loopback device, verify routing visually with a Test capture button (5-second RMS + waveform), and configure default modes / sinks for `aureka listen`. The waveform check is the user-facing answer to "did I plug things together correctly?" — a no-CLI alternative to `aureka doctor audio`.

## ADDED Requirements

### Requirement: Listen 分頁
設定視窗 SHALL 新增 Listen 分頁，顯示偵測到的 loopback 裝置清單、目前選用的裝置、輸出 sink 設定（是否 `--window`、是否寫檔）、以及一個 Test capture 按鈕能即時量 5 秒 RMS / 顯示波形以驗證路由。

#### Scenario: 顯示偵測結果
- **WHEN** 使用者開啟 Listen 分頁
- **THEN** UI 列出當前平台所有 loopback 候選裝置，並標記哪一個是預設

#### Scenario: 切換裝置
- **WHEN** 使用者改選裝置並 commit
- **THEN** auto-save 把新值寫入 `[listen].device` 並 `/reload` daemon

#### Scenario: Test capture
- **WHEN** 使用者按下 Test capture 按鈕
- **THEN** UI 啟動 5 秒擷取，顯示即時 RMS 數值與小型波形；若 RMS 始終為 0 則紅字提示 routing 可能未設好

#### Scenario: macOS 提示
- **WHEN** macOS 上沒有偵測到任何 BlackHole 類裝置
- **THEN** Listen 分頁顯示一張卡片，內含安裝指令與 README 設定章節連結
