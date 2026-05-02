## ADDED Requirements

### Requirement: benchmark 子命令
系統 SHALL 提供 `aureka benchmark` 子命令，量測本機 ASR/TTS 與遠端 LLM 速度，輸出 stdout 表格與 Markdown 報告。

#### Scenario: 基本執行
- **WHEN** 執行 `aureka benchmark`
- **THEN** 系統呼叫 `aureka.benchmark.run_benchmark()`，跑完 ASR、TTS、LLM 三個任務，stdout 顯示對齊表格，當前目錄產生 `benchmark-<hostname>-<YYYY-MM-DD>.md`

#### Scenario: Quick 模式
- **WHEN** 執行 `aureka benchmark --quick`
- **THEN** 每個任務跑 1 輪 warm-up + 1 輪計時，總時間顯著縮短

#### Scenario: 跳過 LLM
- **WHEN** 執行 `aureka benchmark --skip-llm`
- **THEN** 系統不打 LLM 端點，報告中 LLM rows 標記為 `skipped`

#### Scenario: 自訂報告路徑
- **WHEN** 執行 `aureka benchmark --output /tmp/r.md`
- **THEN** 報告寫到 `/tmp/r.md`

#### Scenario: 跑時即時進度
- **WHEN** 執行 `aureka benchmark`
- **THEN** stdout 在每輪結束後立刻印出進度（如 `[ASR] run 3/5 → 1.23s`），不等全部跑完才一次顯示

#### Scenario: 接受 --device 旗標
- **WHEN** 執行 `aureka --device cpu benchmark`
- **THEN** ASR 與 TTS 載入時使用 `cpu` 裝置
