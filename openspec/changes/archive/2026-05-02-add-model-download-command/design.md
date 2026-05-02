## Context

Aureka 目前有三個會觸發模型下載的進入點：

1. `aureka speak` → `aureka/tts.py:load_tts()` 初始化 `KPipeline`，背後從 HuggingFace 下載 Kokoro 權重 + voice 檔
2. `aureka type`（無 daemon）→ `aureka/asr.py:load_asr()` 視 backend 與裝置不同，下載 TheWhisper 或 faster-whisper 權重
3. `aureka daemon start` → 同時觸發上述兩者

下載過程由 `huggingface_hub` 處理，預設會印 tqdm 進度，但因為呼叫端是 GUI/TTY 子行程，使用者體感是「卡住」。
此外，daemon 模式啟動時模型下載是「順便」做的，沒有獨立的「準備環境」階段。

ASR backend 的選擇邏輯（`aureka/device.py:resolve_asr_backend()`）：
- `cuda`/`mps` 且 `thestage_speechkit` 可匯入 → TheWhisper
- 其他情形 → faster-whisper

`aureka/device.py:resolve_device()` 自動偵測：CUDA > MPS > CPU。

## Goals / Non-Goals

**Goals:**
- 提供一條獨立指令 `aureka download`，把所有「執行時實際會用到」的模型一次下載完
- 純下載：不載入模型到 GPU/CPU 記憶體，不建立 KPipeline / WhisperModel 物件
- 下載過程顯示進度（直接利用 huggingface_hub 內建 tqdm 即可）
- Idempotent：重複執行只會驗證 cache、不會重抓
- 終端輸出列出每個模型的 repo ID 與本地路徑，讓使用者知道存放位置

**Non-Goals:**
- 不負責下載 LLM/VLM 模型（這些走 LM Studio/Ollama 的 API，由使用者自行管理）
- 不提供「移除 / 清理 cache」子命令（HuggingFace CLI 已有 `huggingface-cli delete-cache`）
- 不提供下載特定 voice 子集的選項（snapshot_download 預設抓整個 repo，剛好把所有 voice 一次備齊；未來有需要再加 `--voice` 旗標）
- 不修改現有 `load_tts` / `load_asr` 的 lazy-load 行為（download 指令是補充，不是取代）

## Decisions

### Decision 1：用 `huggingface_hub.snapshot_download` 而非呼叫 backend 載入函數

**Why:** 純下載不應啟動 GPU runtime，也不該佔用記憶體。`snapshot_download` 是 huggingface_hub 的低階 API，只搬檔案。

**Alternative considered:** 呼叫 `load_tts()` / `load_asr()` 觸發 backend 自帶的下載邏輯。
- 優點：完全不用維護 repo ID 清單
- 缺點：會 spin up CUDA/MPS context、佔幾百 MB 記憶體；呼叫端立刻退出時 backend 解構流程可能不乾淨
- 結論：放棄，違反「純下載」目標

### Decision 2：把 model registry 集中到 `aureka/models.py`

**Why:** 目前 repo ID 散在 `asr.py`（`thestage-ai/thewhisper-large-v3-turbo`）、`tts.py`（透過 `KPipeline` 隱式）和 `device.py`。新增 `MODEL_REGISTRY` 字典作為 single source of truth：

```python
MODEL_REGISTRY = {
    "kokoro": "hexgrad/Kokoro-82M",
    "faster-whisper": "Systran/faster-whisper-large-v3",
    "thewhisper": "thestage-ai/thewhisper-large-v3-turbo",
}
```

**Alternative considered:** 寫死在 `__main__.py` 的 `cmd_download`。
- 缺點：未來 backend 升級時要改兩個地方（backend 的硬編碼 + download 指令）
- 結論：集中化更可維護；未來甚至可重構讓 `asr.py` 也從 registry 讀

### Decision 3：依當前環境決定下載哪個 ASR backend

**Why:** 在 CPU-only 機器上下載 TheWhisper 沒有意義（`resolve_asr_backend` 永遠不會選它）；反之在 Apple Silicon 上 faster-whisper 仍是 fallback、值得一併下載。

**規則：**
- 一律下載 Kokoro TTS
- 一律下載 faster-whisper（所有平台都會 fallback 到它）
- 若 `resolve_device()` 回傳 `cuda` 或 `mps` 且 `thestage_speechkit` 可匯入 → 額外下載 TheWhisper

**Alternative considered:** 不論裝置一律下載 TheWhisper（多 1.5GB）。
- 缺點：CPU-only 使用者多花頻寬與磁碟空間在永遠不會用到的模型
- 結論：環境感知下載，省資源

### Decision 4：尊重 HuggingFace 標準環境變數

**Why:** `huggingface_hub` 已有 `HF_HOME`、`HF_HUB_CACHE` 等變數控制 cache 路徑。download 指令直接呼叫 `snapshot_download` 自然就會吃到這些變數，不重新發明。

### Decision 5：失敗處理採 fail-fast

**Why:** 一個模型下載失敗（網路斷、disk full、權限問題）就 raise 例外、印錯誤訊息並以 non-zero exit code 結束。不要靜默繼續下載其他模型，避免使用者以為都成功了。

## Risks / Trade-offs

- **Risk:** Kokoro repo 上的 voice 檔列表未來可能變動（新增/移除 voice） → snapshot_download 預設抓整個 repo，會自動同步；不需處理
- **Risk:** TheWhisper repo 為 thestage-ai 私人/受限 repo（需要授權） → 若使用者沒有 HF token 會在下載階段就 fail，比執行 `type` 時才發現好。錯誤訊息應引導使用者 `huggingface-cli login`
- **Risk:** repo ID 在 backend 升級時與 registry 脫鉤 → 用集中 registry + 後續可加單元測試比對 `asr.py` 內字串與 registry 一致性
- **Trade-off:** 不下載 LLM/VLM → 使用者仍需手動在 LM Studio 拉模型；接受，因為 LLM 端點是 user-configurable 的，aureka 無從預判要哪個
