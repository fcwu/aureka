# benchmark Specification

## Purpose

量測 Aureka 在當前硬體上的 ASR / TTS / LLM 端到端速度，產出可分享的 Markdown 報告與供 UI 消費的結構化結果，協助使用者在升級模型前先估算 cold-start 時間、單次推論延遲、tokens/s 與 RTF。設定 UI Tools 分頁依據結果產出具體的調整建議（例：device、ASR model size、thinking_budget），讓使用者一鍵套用而不必自行解讀數字。

## Requirements
### Requirement: Benchmark Entry 函數
系統 SHALL 在 `aureka/benchmark.py` 提供 `run_benchmark(device: str = "auto", quick: bool = False, output_path: str | None = None, skip_llm: bool = False) -> Path` 函數，作為 benchmark 的程式介面，回傳寫出的 Markdown 報告路徑。

#### Scenario: 預設執行
- **WHEN** 呼叫 `run_benchmark()`
- **THEN** 系統依序量測 ASR、TTS、LLM 三個任務，每個任務跑 1 輪 warm-up + 5 輪計時，並把結果同時印到 stdout 與寫入 Markdown 報告

#### Scenario: Quick 模式
- **WHEN** 呼叫 `run_benchmark(quick=True)`
- **THEN** 每個任務改為 1 輪 warm-up + 1 輪計時，總時間顯著縮短

#### Scenario: Skip LLM
- **WHEN** 呼叫 `run_benchmark(skip_llm=True)`
- **THEN** 系統跳過 LLM 量測，報告中 LLM rows 標記為 `skipped`

### Requirement: 多輪計時與統計
系統 SHALL 對每個任務執行 N 輪計時（預設 5，`quick` 模式 1），用 `time.perf_counter()` 量單輪 wall clock，回傳 median、min、max 三個值。

#### Scenario: Warm-up 不計入統計
- **WHEN** 系統執行任意 task 的計時迴圈
- **THEN** 第 1 輪屬於 warm-up，不納入 median/min/max 計算

#### Scenario: Median 計算
- **WHEN** 5 輪計時結果為 `[1.0, 1.1, 1.0, 1.2, 1.05]`
- **THEN** 統計回傳 `median=1.05, min=1.0, max=1.2`

### Requirement: 即時進度輸出
系統 SHALL 在 benchmark 跑的過程中即時印出進度訊息至 stdout，至少包含「目前 task 名稱」、「目前是 warm-up 或第幾輪」、「該輪秒數」。

#### Scenario: 進度訊息格式
- **WHEN** ASR benchmark 第 3 輪結束、耗時 1.23 秒
- **THEN** stdout 出現類似 `[ASR] run 3/5 → 1.23s` 的單行訊息

#### Scenario: Warm-up 訊息
- **WHEN** ASR benchmark 開始 warm-up
- **THEN** stdout 出現類似 `[ASR] warm-up...` 的訊息

### Requirement: ASR 量測
系統 SHALL 量測 ASR 任務的 RTF（real-time factor）與字元/秒兩個指標，使用固定的 ~30 秒中文音訊樣本。

#### Scenario: RTF 計算
- **WHEN** ASR 對 30 秒樣本耗時 2.4 秒完成
- **THEN** 系統回報 `RTF = 0.08`（transcription_time / audio_duration）

#### Scenario: 字元/秒計算
- **WHEN** ASR 在 2.4 秒內輸出 600 個字元
- **THEN** 系統回報 `chars/s = 250`

#### Scenario: ASR 模型未可用
- **WHEN** 載入 ASR backend 失敗
- **THEN** ASR rows 在報告中標記為 `failed: <reason>`，benchmark 繼續跑剩餘 tasks

### Requirement: TTS 量測
系統 SHALL 量測 TTS 任務的 RTF 與字元/秒，使用固定的 ~150 字中文段落。

#### Scenario: RTF 計算
- **WHEN** TTS 在 1.5 秒內合成 5 秒長音訊
- **THEN** 系統回報 `RTF = 0.30`（synthesis_time / audio_duration）

#### Scenario: TTS 不可用
- **WHEN** Kokoro 在當前平台（如 Windows）不可用
- **THEN** TTS rows 標記為 `skipped: kokoro unavailable on platform`

### Requirement: LLM 量測
系統 SHALL 量測 LLM 任務的 tokens/s（streaming throughput）與 TTFT（time-to-first-token），使用固定 prompt 對 `cfg.llm.base_url` 端點。

#### Scenario: tokens/s 計算
- **WHEN** LLM 串流回傳共 240 個 tokens、總耗時 5.0 秒
- **THEN** 系統回報 `tokens/s = 48.0`

#### Scenario: TTFT 計算
- **WHEN** LLM 從送出 request 到收到第一個 token 經過 180ms
- **THEN** 系統回報 `TTFT = 180 ms`

#### Scenario: LLM 連線失敗
- **WHEN** `cfg.llm.base_url` 連不上
- **THEN** LLM rows 標記為 `failed: <reason>`，benchmark 繼續跑剩餘 tasks

### Requirement: Cold-Start 量測
系統 SHALL 在所有計時之前量測一次 ASR 與 TTS 的模型載入時間（從呼叫 `load_asr` / `load_tts` 到回傳）。

#### Scenario: 載入時間計入報告
- **WHEN** ASR 模型首次載入耗時 3.2 秒
- **THEN** 報告 cold-start rows 顯示 `ASR load = 3.2s`，min/max 為 `—`（只跑一次）

### Requirement: 樣本管理
系統 SHALL 在第一次需要 ASR 樣本時用 Kokoro 合成 ~30 秒中文段落，cache 到 `~/.cache/aureka/benchmark/sample-zh-kokoro<version>-<voice>.wav`，後續執行直接讀檔。

#### Scenario: 首次合成
- **WHEN** cache 目錄不含 sample 檔
- **THEN** 系統呼叫 Kokoro 合成並寫檔，stdout 印出「Generating sample audio...」

#### Scenario: Cache 命中
- **WHEN** cache 目錄已含對應 Kokoro 版本與 voice 的 sample 檔
- **THEN** 系統直接讀檔，不重新合成

#### Scenario: Kokoro 不可用 fallback
- **WHEN** Kokoro 不可用且 cache 也不存在
- **THEN** 系統嘗試 fallback 到 `tests/fixtures/speech-zh.wav`；若仍不存在，ASR rows 標記為 `skipped: no sample available`

### Requirement: 環境資訊收集
系統 SHALL 收集兩段環境資訊寫入 Markdown 報告：「Aureka 端」與「LLM 端」。

#### Scenario: Aureka 端欄位
- **WHEN** 產生報告
- **THEN** 報告包含至少 hostname、OS 名稱與版本、Python 版本、torch 版本與 CUDA/MPS 狀態、GPU model（若可取得）、aureka 版本、ASR backend 與模型 ID、TTS 模型 ID 與 voice、Kokoro 版本

#### Scenario: LLM 端欄位
- **WHEN** 產生報告
- **THEN** 報告包含 `cfg.llm.base_url`、設定的 model 字串、解析後實際 model ID、`/v1/models` 回傳的相關 metadata（owned_by、object 等可取得欄位）

### Requirement: 雙輸出格式
系統 SHALL 同時把 benchmark 結果輸出到 stdout（對齊 ASCII 表格）與 Markdown 報告檔。

#### Scenario: stdout 表格
- **WHEN** benchmark 完成
- **THEN** stdout 出現包含 task / metric / median / min / max 欄位的對齊表格，並在最後印出 `Report saved: <path>`

#### Scenario: 預設 Markdown 路徑
- **WHEN** 未指定 `output_path`
- **THEN** 報告寫到 `./benchmark-<hostname>-<YYYY-MM-DD>.md`（同日重跑覆寫）

#### Scenario: 自訂 Markdown 路徑
- **WHEN** 呼叫 `run_benchmark(output_path="/tmp/x.md")`
- **THEN** 報告寫到 `/tmp/x.md`

### Requirement: Fail-Soft 策略
系統 SHALL 在任一 task 拋例外時補捉、標記為 failed、繼續跑剩餘 task，不讓單一失敗中斷整個 benchmark。

#### Scenario: ASR 失敗不影響 TTS
- **WHEN** ASR 在計時時拋例外
- **THEN** 系統印出錯誤、ASR rows 標記為 `failed`、繼續跑 TTS 與 LLM

### Requirement: Markdown Report 結構
系統 SHALL 讓寫出的 Markdown 報告至少包含三個 ## 區塊：「Environment」（含 Aureka 端與 LLM 端兩個 ### 子區塊）、「Results」（含結果表格）、「Notes」（含 quick 模式或 skip 標記等執行條件）。

#### Scenario: 報告章節
- **WHEN** 開啟產出的 Markdown 報告
- **THEN** 檔案依序包含 `## Environment`、`### Aureka host`、`### LLM endpoint`、`## Results`、`## Notes` 區塊

