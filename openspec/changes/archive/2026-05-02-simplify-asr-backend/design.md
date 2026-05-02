## Context

ASR 模組目前的設計（`aureka/asr.py` + `aureka/device.py`）來自一個假設：thestage-ai 會在 PyPI 釋出 `thestage-speechkit` 套件，aureka 在 cuda/mps 平台優先用它、否則 fallback 到 faster-whisper。實際上：

- PyPI 上的 `thestage-speechkit==0.1.0` 是 1.5KB 的空殼 placeholder（作者欄 "Your Name <your.email@example.com>"），沒有 `WhisperPipeline` API
- aureka 的 `asr-thewhisper` extra（`pyproject.toml:43`）指向這個空殼，所以 `pip install "aureka[asr-thewhisper]"` 裝完什麼都跑不起來
- 因此 `_TheWhisperBackend` 路徑從未被執行；所有平台實際上都走 faster-whisper

並且 `_FasterWhisperBackend.__init__` 把 `model_size` 寫成 default `"large-v3"`，從未從 config 讀。Apple Silicon M3 上實測 RTF 1.23（30s 音訊轉錄要 28s），對交互式語音輸入體驗很差，但使用者沒有合法管道改它。

## Goals / Non-Goals

**Goals:**
- 移除所有 TheWhisper 相關 code、spec、extra、registry entry，把 ASR 簡化成「只有 faster-whisper」一條路
- 讓使用者透過 `config.toml` 的 `[asr] model = "..."` 改 ASR 模型大小，不必改 source code
- 預設改成 `medium`，給中等硬體一個能用的 starting point
- `aureka download` 與 ASR runtime 永遠下載/使用同一個 model（透過共用 config）

**Non-Goals:**
- 不引入別的 ASR backend（例如 OpenAI Whisper API、whisper.cpp）
- 不做 ASR streaming / 即時轉錄
- 不做模型熱切換（runtime 切 model 仍需 reload daemon）
- 不自動清理已下載但用不到的舊 model cache
- 不做 quality benchmark（使用者自己換 model 跑 `aureka benchmark` 比較 RTF；精度評估留給使用者試聽）

## Decisions

### Decision 1：完全移除 TheWhisper，不留 stub

**Why:** 既然這條路沒人能走通（PyPI 上沒有真的 package），留著只會誤導使用者去裝那個空殼。完全移除才是誠實的做法。如果未來 thestage-ai 真的推出 SDK，到時候再加回來；現在留 dead code 沒有任何好處。

**Alternative considered:** 留 `_TheWhisperBackend` class 並在 `pyproject.toml` 加註解說「未來支援」。
- 缺點：使用者讀 code 會以為這是現在能用的選擇；spec 文件也得繼續維護
- 結論：YAGNI，刪掉

### Decision 2：`MODEL_REGISTRY` 從 dict 改成 function

**Why:** 因為 faster-whisper 的 repo_id 現在依 config 變動（`Systran/faster-whisper-{model}`），靜態 dict 會跟 runtime 行為脫鉤。改成 `model_registry() -> dict[str, str]`，每次呼叫時讀 config 動態組 repo_id。

**Alternative considered:** 保留靜態 dict + 額外 helper function。
- 缺點：兩個 source of truth 容易不同步
- 結論：function-based 單一真相

### Decision 3：Default 模型用 `medium`

**Why:** 在 M3/M2/RTX 中階以上機器，medium RTF 大約 0.3-0.5（比即時快 2-3x），中文精度足以做語音輸入後給 LLM refine 修字。`large-v3` 對 80% 使用者太重；`small`/`base` 中文精度退化明顯。`medium` 是 sweet spot。

**Alternative considered:** Default `large-v3-turbo`（Whisper turbo 變體，比 large-v3 快 ~3x、精度幾乎相同）。
- 優點：精度 vs 速度更平衡
- 缺點：較新，部分版本 faster-whisper 對 turbo 支援可能還不穩；新使用者讀 config 看到 `large-v3-turbo` 也比看到 `medium` 不直觀
- 結論：medium 是更保守、文件化更完整的選擇；想用 turbo 的使用者一行 config 就能切

### Decision 4：不對 `cfg.asr.model` 做 whitelist 驗證

**Why:** faster-whisper 接受的 model 字串包含預設名（`tiny`/`base`/...）、HF repo IDs（`Systran/faster-whisper-medium-en`）、本地路徑。我們做 whitelist 反而限制使用者。把 config 字串原樣傳給 `WhisperModel(...)`，錯了就讓 faster-whisper 自己抱錯（錯誤訊息比我們自製的更精準）。

**Trade-off:** 拼錯 model 名要等到 ASR 載入才發現。可接受：daemon 啟動時就會嘗試 load，第一時間就抱錯。

### Decision 5：Cleanup 與 config 化在同一個 change 裡做

**Why:** 拆兩個 change 沒意義 — cleanup 完了 ASR 還是 hardcoded `large-v3`，使用者體驗沒變化；config 化又得跟 cleanup 綁在一起避免重複改 `asr.py`。一個 change 一次到位、一次測試覆蓋、一次 commit。

## Risks / Trade-offs

- **Risk:** 已有使用者跑 `aureka download` 抓了 `Systran/faster-whisper-large-v3`（~3GB），升級後 default 變 `medium`，那 3GB 變成 dead cache
  - **Mitigation:** Release notes / README 提醒；提供清理命令的 hint：`huggingface-cli delete-cache`。不自動刪除（不該動使用者磁碟內容）
- **Risk:** Default 改 `medium` 後，原本對精度敏感的使用者升級會發現中文轉錄品質降
  - **Mitigation:** Release notes 明寫 default 改了；config.example.toml 註解列出 `large-v3` 的選擇與 trade-off
- **Risk:** 使用者 config 拼錯 model 名（如 `mediumn`）
  - **Mitigation:** faster-whisper 會在 load 時 raise 清楚的 model-not-found 錯誤
- **Trade-off:** Spec 走 MODIFIED Requirements 而非 REMOVED + ADDED
  - 對 `asr-backend/spec.md` 的「ASR backend 自動選擇」/「TheWhisper 後端」是 REMOVED；「faster-whisper 後端」是 MODIFIED（加上 model 從 config 讀）；「ASR 模型可設定」是 ADDED
  - 對 `model-management/spec.md` 的「模型 Registry」與「預先下載介面」都是 MODIFIED（不再含 thewhisper、改為 function-based）
