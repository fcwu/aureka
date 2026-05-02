## Why

使用者裝完 aureka 後不知道自己這台機器跑得順不順、哪些任務會卡。文件有「TTFT 目標 ≤ 12ms/segment」之類的目標數字，但沒有可重現的量測方式讓使用者驗證、比較。需要一個內建 benchmark，讓任何人都能在自己的硬體上跑一次得到客觀數字，並把結果分享給其他人作為購機/選後端的參考。

## What Changes

- 新增 `aureka benchmark` 子命令，量測 ASR、TTS、LLM 三個工作的速度
- 預設跑 1 輪 warm-up + 5 輪計時，輸出 median + min/max；提供 `--quick` 旗標退回 1 輪
- 跑時即時印進度（`[ASR] run 3/5 → 1.23s`），避免使用者誤以為當機
- 同時輸出至 stdout 對齊表格與 Markdown 報告檔（預設 `benchmark-<host>-<YYYY-MM-DD>.md`，可用 `--output PATH` 指定）
- ASR 樣本第一次跑時用 Kokoro 合成 ~30s 中文段落、cache 到 `~/.cache/aureka/benchmark/sample-zh.wav`，後續沿用
- 個別任務失敗不打斷整體（fail-soft），失敗 row 標 `failed` / `skipped`
- 提供 `--skip-llm` 旗標讓不想或不能測 LLM 的人略過
- Markdown 報告含兩段環境資訊：Aureka 端（OS / GPU / 模型版本）與 LLM 端（base_url / model ID / `/v1/models` metadata）

## Capabilities

### New Capabilities
- `benchmark`：量測本地 ASR/TTS 與遠端 LLM 速度，產出可分享的報告

### Modified Capabilities
- `cli`：新增 `benchmark` 子命令的 CLI 介面要求

## Impact

- 新增 `aureka/benchmark.py`：量測核心 + 樣本管理 + 報告產生
- 修改 `aureka/__main__.py`：註冊 `benchmark` subparser 與 dispatcher
- 新增 `tests/test_benchmark_unit.py`：mock ASR/TTS/LLM 與計時器，驗證計時邏輯、fail-soft、報告格式
- 修改 `README.md` / `CLAUDE.md`：在使用範例段落加入 `aureka benchmark` 介紹
- 不影響現有 daemon、speak、type、process、download 子命令的行為
- 相依套件：`huggingface_hub` / `kokoro` / `faster-whisper` / `openai` 皆已存在，無需新增
