## Overview

This delta adds two subcommands so users can transcribe system audio from the terminal: `aureka listen` is the day-to-day "transcribe what I'm hearing" tool, and `aureka doctor audio` is the routing diagnostic users run when their setup isn't working (e.g. macOS Multi-Output device misconfigured). The pair targets first-time users who hit BlackHole / WASAPI quirks and need a clear "is my plumbing OK?" answer before opening the main listen mode.

## ADDED Requirements

### Requirement: listen 子命令
系統 SHALL 提供 `aureka listen` 子命令，啟動系統音訊 loopback 擷取與串流轉錄。

#### Scenario: 啟動 listen
- **WHEN** 使用者執行 `aureka listen`
- **THEN** 系統偵測平台 loopback 裝置，開始持續擷取並 VAD 切段，每段送 ASR、依模式可選擇送 LLM refine / translate

#### Scenario: 模式 / 語言 / target 等旗標
- **WHEN** 執行 `aureka listen --mode translate --target zh`
- **THEN** transcript 經 ASR 後送 LLM 翻譯為中文輸出

#### Scenario: 輸出 sink
- **WHEN** 執行 `aureka listen --out meeting.txt`
- **THEN** 每段 transcript 即時 append 到 `meeting.txt`，行格式 `[YYYY-MM-DD HH:MM:SS] [system] <text>`

#### Scenario: 視窗模式
- **WHEN** 執行 `aureka listen --window`
- **THEN** 系統以 pywebview 開啟 tail-style transcript 視窗，每段 transcript 即時追加；視窗不搶焦點

#### Scenario: 同時擷取麥克風
- **WHEN** 執行 `aureka listen --mic`
- **THEN** 系統開兩路擷取（loopback + mic），輸出 transcript 帶 label `[system]` / `[mic]`

#### Scenario: 顯式裝置覆寫
- **WHEN** 執行 `aureka listen --device "BlackHole 2ch"`
- **THEN** 系統略過 auto-detect，直接使用指定裝置；找不到時報錯離開

### Requirement: doctor audio 子命令
系統 SHALL 提供 `aureka doctor audio` 子命令印出當前平台音訊裝置診斷資訊，協助排查 loopback 設定問題。

#### Scenario: 診斷輸出
- **WHEN** 執行 `aureka doctor audio`
- **THEN** stdout 列出（1）所有音訊輸入裝置與 sample rate；（2）標記哪些是 loopback；（3）若為 macOS，提示是否在 Multi-Output Device 中正確路由
