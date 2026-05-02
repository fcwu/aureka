## Context

Aureka 主要會吃硬體資源的工作有三類：
1. **ASR**（`aureka/asr.py`）：Whisper 推論，受 GPU/CPU、記憶體頻寬、模型 backend 影響
2. **TTS**（`aureka/tts.py`）：Kokoro 推論，受 GPU/CPU、模型載入路徑影響
3. **LLM**（`aureka/llm.py`）：透過 OpenAI-compatible 端點打 LM Studio / Ollama，受 LLM server 端硬體 + 模型 quantization 影響（aureka 端只負責 streaming I/O）

過去文件（README、daemon spec）有寫「TTFT 目標 ≤ 12ms/segment」之類的數字，但沒有可重現的量測腳本。使用者裝完 aureka 後缺乏快速 self-check 的方法，也不易跟其他使用者比較。

`aureka download` 已經把 Kokoro / Whisper 模型備好；benchmark 會假設這些模型已存在。

## Goals / Non-Goals

**Goals:**
- 一條 `aureka benchmark` 指令量出 ASR / TTS / LLM 三類的客觀速度數字
- 跑時即時印進度（warm-up、第幾輪、單輪秒數），讓 2-4 分鐘的等待不會讓使用者懷疑當機
- 同時產生 stdout 表格（馬上看）與 Markdown 報告（拿去分享）
- 個別任務失敗不打斷整體：別人 LLM 沒設定也能跑出 ASR/TTS 結果

**Non-Goals:**
- 不做端到端 `aureka process` benchmark（YAGNI；個別工作 + LLM 已經涵蓋使用者實際關心的延遲來源）
- 不做 leaderboard 或 JSON 輸出（YAGNI；Markdown 已足夠）
- 不偵測或自動產出 LLM server 端硬體資訊（aureka 看不到對方機器，由使用者自行從 `base_url` 與 model ID 判讀）
- 不重新發明計時 lib（不用 pytest-benchmark / asv，自己用 `time.perf_counter()` 就夠用）

## Decisions

### Decision 1：單檔 `aureka/benchmark.py`，不切 submodule

**Why:** 整個 benchmark 邏輯估計 200-300 行：3 個 task closure + 計時 harness + 樣本管理 + 報告。切成 `benchmark/` package 會多 4-5 個小檔案、import 路徑變長，但邏輯沒有複雜到需要分隔。單檔更好讀、更好改。

**Alternative considered:** `aureka/benchmark/{runner,tasks,report,samples}.py` package。
- 缺點：對這個規模屬於過度工程
- 結論：等真的超過 400 行再考慮拆

### Decision 2：rigor 預設 5 輪，提供 `--quick` 走 1 輪

**Why:** 5 輪取 median 抑制冷啟、disk cache、其他 process 干擾的抖動，數字適合分享比較。但開發者自己反覆跑時想要快回饋，`--quick` 走 1 輪約 30-60 秒結束。

**Alternative considered:** 預設 3 輪。
- 3 輪 median 抗 outlier 能力差（一個 outlier 就會帶歪）
- 5 輪 median 對 1-2 個 outlier 仍穩定
- 結論：5 輪是嚴謹度與時間的甜蜜點

### Decision 3：ASR 樣本由 Kokoro 動態合成、cache 到 `~/.cache/aureka/benchmark/`

**Why:** 不汙染 repo（不必 ship binary WAV）、跨平台同 Kokoro 版本得到完全一致的音訊（可比對）、剛好把 TTS 當 dependency 試跑一次。第一次跑 benchmark 時多花 ~5s 合成，之後讀 cache。

**Cache 失效策略：** 檔名嵌入 Kokoro 版本與 voice 名稱（例如 `sample-zh-kokoro0.9.4-zf_xiaobei.wav`）。Kokoro 升級或換 voice 自動重生。

**Alternative considered:**
- ship 預錄 WAV：repo +500KB binary、要 ship 多種語言 sample
- 合成正弦波：Whisper 在無語音音訊上的時間波動大、結果不具參考性

### Decision 4：失敗 fail-soft（與 `aureka download` 的 fail-fast 相反）

**Why:** Benchmark 是 informational 工具，不是 critical path。LLM 連不上、Kokoro 在 Windows 不可用、faster-whisper 模型沒載到，都不該讓整個 benchmark 中止。每個 task 用 try/except 包，失敗 row 在報告裡標 `failed: <reason>`，其他繼續跑。`aureka download` 是「請把這件事做好」，所以 fail-fast；`aureka benchmark` 是「告訴我能做什麼、做得多快」，所以 fail-soft。

### Decision 5：LLM 環境資訊只列「aureka 看得到的」

**Why:** Aureka 從 `cfg.llm.base_url` 與 `/v1/models` 能拿到的資訊就那些（URL、model ID、`/v1/models` 回傳的 metadata 欄位）。LLM server 跑在哪台機器、什麼 quantization、ctx size 多大，aureka 無從得知。在報告中老老實實列出能拿到的、不偽裝、不額外加警語、不開「使用者自填」的旗標。讀者自己看 `base_url` 與 model ID 判讀。

### Decision 6：使用 `time.perf_counter()`，不引入 benchmark library

**Why:** 量秒級、亞秒級的單次操作，`time.perf_counter()` 解析度足夠（< 1us）。`pytest-benchmark` / `asv` 是測試框架配套，不適合在 production 程式內呼叫。少一個依賴。

## Risks / Trade-offs

- **Risk:** Kokoro 在 Windows 不可用 → ASR 樣本無法合成
  - **Mitigation:** Windows 上 fallback 到 `tests/fixtures/speech-zh.wav`（短句，數字較不穩但能跑）；都沒有就 skip ASR，標 `skipped: no sample available`
- **Risk:** 系統其他 process 干擾單輪數字
  - **Mitigation:** Median + min/max 三個數字一起呈現，讀者能判斷穩定度；warm-up 也降低首輪冷啟影響
- **Risk:** ASR 量測涵蓋整個 transcribe 過程包含 audio decode/preprocess
  - **Mitigation:** Benchmark 量的是「呼叫 `asr.transcribe()` 的 wall clock」，與實際使用情境一致；不拆細到「純 inference 時間」（那種數字對使用者沒有實用意義）
- **Trade-off:** 5 輪預設讓初次體驗 2-4 分鐘
  - 接受：分享數字的可信度比首次體驗快 1 分鐘重要；想快可用 `--quick`
- **Trade-off:** Markdown 檔預設名 `benchmark-<host>-<YYYY-MM-DD>.md` 寫在 cwd，重跑同一天會覆寫
  - 接受：同天重跑通常就是 iterating，覆寫合理；不同天保留歷史；要保留就 `--output 指定路徑`
