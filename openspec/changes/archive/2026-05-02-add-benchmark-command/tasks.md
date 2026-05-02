## 1. 計時 Harness 與樣本管理

- [x] 1.1 在 `aureka/benchmark.py` 新增模組，定義 `BenchmarkResult` dataclass（task / metric / median / min_v / max_v / unit / status）
- [x] 1.2 實作 `_time_runs(callable, runs: int, warmup: int = 1) -> tuple[float, float, float]`：用 `time.perf_counter()` 計時，回傳 `(median, min, max)`，warm-up 不計入
- [x] 1.3 實作 `_print_progress(task: str, label: str, secs: float | None = None)` helper：統一輸出 `[ASR] run 3/5 → 1.23s` 格式
- [x] 1.4 實作 `_resolve_sample(voice: str) -> Path`：依 Kokoro 版本與 voice 組 cache 檔名於 `~/.cache/aureka/benchmark/`，不存在時呼叫 `aureka.tts.speak(text, output_path=...)` 合成 ~30s 段落
- [x] 1.5 `_resolve_sample` fallback：Kokoro 不可用且 cache 不存在時嘗試 `tests/fixtures/speech-zh.wav`；都沒有則 raise

## 2. 各 Task 量測函數

- [x] 2.1 實作 `_bench_asr(device, runs) -> list[BenchmarkResult]`：用 `_resolve_sample` 取樣本，量 ASR `transcribe()` 時間，計算 RTF 與 chars/s
- [x] 2.2 實作 `_bench_tts(device, runs) -> list[BenchmarkResult]`：用固定 ~150 字段落，量 TTS 合成時間（不寫檔），計算 RTF 與 chars/s
- [x] 2.3 實作 `_bench_llm(runs) -> list[BenchmarkResult]`：用固定 prompt 打 `cfg.llm.base_url`，量 streaming tokens/s 與 TTFT
- [x] 2.4 實作 `_bench_cold_start(device) -> list[BenchmarkResult]`：在所有 warm task 之前呼叫一次 `load_asr` / `load_tts`，量載入時間，min/max 標 None
- [x] 2.5 每個 `_bench_*` 用 try/except 包，失敗時回傳含 `status="failed: <reason>"` 的 BenchmarkResult、不 propagate 例外

## 3. 環境收集 + 報告產生

- [x] 3.1 實作 `_collect_aureka_env() -> dict`：收 hostname、OS、Python、torch + CUDA/MPS、GPU model、aureka version、ASR backend + 模型、TTS 模型 + voice、Kokoro version
- [x] 3.2 實作 `_collect_llm_env() -> dict`：讀 `cfg.llm.base_url`、`cfg.llm.model`、嘗試 `GET /v1/models` 取實際 model ID 與 metadata；連線失敗時欄位填 `unavailable`
- [x] 3.3 實作 `_render_table(results: list[BenchmarkResult], env_summary: str) -> str`：對齊 ASCII 表格
- [x] 3.4 實作 `_render_markdown(results, aureka_env, llm_env, notes) -> str`：產生 `## Environment` / `### Aureka host` / `### LLM endpoint` / `## Results` / `## Notes` 結構

## 4. Entry 函數與 CLI 整合

- [x] 4.1 實作 `run_benchmark(device="auto", quick=False, output_path=None, skip_llm=False) -> Path`：依序 cold-start → ASR → TTS → (LLM unless skip)，組裝結果，印 stdout、寫 Markdown，回傳路徑
- [x] 4.2 預設 output_path 為 `Path.cwd() / f"benchmark-{hostname}-{YYYY-MM-DD}.md"`
- [x] 4.3 在 `aureka/__main__.py` 註冊 `benchmark` subparser（`--quick`、`--output PATH`、`--skip-llm`）
- [x] 4.4 實作 `cmd_benchmark(args)`：呼叫 `benchmark.run_benchmark(device=args.device, quick=args.quick, output_path=args.output, skip_llm=args.skip_llm)`
- [x] 4.5 加入 dispatch dict

## 5. 測試

- [x] 5.1 在 `tests/test_benchmark_unit.py` 驗證 `_time_runs`：傳入 lambda 模擬不同耗時，斷言 warm-up 不計入、median 計算正確
- [x] 5.2 驗證 `_resolve_sample` 在 cache 已存在時不重新合成（mock `aureka.tts.speak` 計次）
- [x] 5.3 驗證 `_bench_asr` / `_bench_tts` / `_bench_llm` 在底層拋例外時回傳 status `failed`，不 propagate
- [x] 5.4 驗證 `_render_table` 包含所有 result rows、欄位對齊
- [x] 5.5 驗證 `_render_markdown` 產出含 `## Environment`、`### Aureka host`、`### LLM endpoint`、`## Results`、`## Notes` 區塊
- [x] 5.6 驗證 `run_benchmark(skip_llm=True)` 不打 LLM 端點（mock LLM client，斷言未被呼叫）
- [x] 5.7 跑 `pytest tests/ -v -m "unit or integration"` 全綠

## 6. 文件

- [x] 6.1 在 `README.md` 加入 `aureka benchmark` 章節（短，含一個 stdout sample output 與一段說明）
- [x] 6.2 在 `CLAUDE.md` 加入一段「8. Benchmark」介紹
- [x] 6.3 確認 `aureka --help` 與 `aureka benchmark --help` 訊息清楚

## 7. Spec 同步

- [x] 7.1 確認 `pytest` 與 `aureka benchmark --quick --skip-llm` 都通過後，archive 此 change：`openspec archive add-benchmark-command`
