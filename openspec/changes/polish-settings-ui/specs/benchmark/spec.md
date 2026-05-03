## ADDED Requirements

### Requirement: Benchmark 結構化結果回傳
系統 SHALL 修改 `aureka.benchmark.run_benchmark` 使其同時回傳結構化結果與既有 Markdown 報告路徑，回傳形態為 `dict` 至少包含 `report_path: Path`、`tasks: dict[str, dict]`，其中 `tasks[name]` 含 `median: float`、`min: float`、`max: float`、`device: str`、`status: "ok" | "skipped" | "failed"`、以及（若可得）`rtf` 或 `ttft_seconds` 等任務專屬指標。

#### Scenario: 回傳含 report_path
- **WHEN** 呼叫 `run_benchmark()`
- **THEN** 回傳 dict 內 `report_path` 為實際寫出的 Markdown 路徑（與舊行為一致）

#### Scenario: 回傳含 ASR / TTS / LLM 三任務
- **WHEN** 完整跑完 benchmark
- **THEN** `tasks` 至少有 `asr`、`tts`、`llm` 三個 key，每個皆含 `median`、`min`、`max`、`status`

#### Scenario: 跳過 LLM
- **WHEN** 呼叫 `run_benchmark(skip_llm=True)`
- **THEN** `tasks["llm"]["status"] == "skipped"`，`median/min/max` 為 `None` 或缺省

#### Scenario: 任務失敗 fail-soft
- **WHEN** 任一單一任務拋例外但其他任務照跑
- **THEN** 失敗任務 `status="failed"`、含 `error: str` 欄位；其他任務 `status="ok"` 不受影響

### Requirement: Benchmark 進度回呼
系統 SHALL 為 `run_benchmark` 增加可選 `progress: Callable[[str], None] | None` 參數；若提供，系統 MUST 在每行進度訊息（與既有 stdout 行內容一致）寫出時呼叫 callback。

#### Scenario: 不傳 callback 行為不變
- **WHEN** 呼叫 `run_benchmark()` 不傳 `progress`
- **THEN** 進度照舊輸出至 stdout，行為與舊版一致

#### Scenario: callback 收到逐行訊息
- **WHEN** 呼叫 `run_benchmark(progress=cb)` 且 ASR 第 3 輪結束
- **THEN** `cb` 至少被呼叫一次，傳入字串包含 `"[ASR] run 3/5"` 與耗時數字
