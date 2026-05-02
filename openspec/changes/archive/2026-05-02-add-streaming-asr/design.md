## Context

`aureka type` 的當前資料流（已知 from `aureka/client.py:_voice_session` + `aureka/daemon.py:voice_input`）：

```
recorder.start() → 錄完整段 → recorder.stop() 拿到 numpy 陣列
  → client.py 切成 0.5s chunks 經 WS 連送 → daemon 收到全部 chunks 後 concatenate
  → 一次性 asr.transcribe(audio) → 推 transcript segments 回 client
  → 對全文跑 llm_refine_stream → 推 refined tokens → client 用 replace_text 蓋
```

存在的便利條件：
- `recorder.py` 已有 `on_chunk: Callable` hook（line 17, 81），目前 client.py 沒用
- WS 協定已有 `transcript`（含 `final` bool）與 `refined` 兩種 server-to-client 事件，client 端 `replace_text` 邏輯已能處理「partial → final」覆寫

Whisper 系列模型不是 streaming 模型；要做「邊講邊顯示」必須在外面套 VAD（voice activity detection）切句，每一段切出來才有完整的 utterance 讓 Whisper 跑。silero-vad 是業界標準（onnx-runtime, ~2MB, 16kHz, low-latency）。

## Goals / Non-Goals

**Goals:**
- 講話過程中，每停頓 600ms 就把那一段轉錄完、立刻 inject 到游標，給使用者「系統有在聽」的回饋
- 講完那一刻只剩最後 1 個 segment 沒轉完（總 ASR wait time 約 1s 以內）
- LLM refine 拿完整累積 transcript 跑（不切段）→ 收到後 client `replace_text` 蓋寫所有 partial
- 跟現有 daemon 路徑共存：舊 client（沒送 `streaming` flag）仍走 buffer-then-transcribe 流程

**Non-Goals:**
- 不做 sliding-window streaming（會 flicker、需更小 model、總精度反而更差；user 已 reject）
- 不做 LLM streaming refine 分段（每段都 refine 會切斷上下文、品質下降）
- 不做真的 token-by-token streaming（Whisper 不是這種架構，需換 model 家族 — 範圍太大）
- 不在 `aureka process` 批次流水線啟用 streaming（沒有對應的「使用者等待」UX 問題）
- 不做端到端 streaming benchmark（latency 量測由 user 主觀感受評估，不在自動化測試 scope）

## Decisions

### Decision 1：VAD 在 daemon 端、不在 client 端

**Why:** Daemon 是中央決策點，client 只負責灌音訊。把 VAD 放 daemon 的好處：
- Client 不必載 silero-vad（client 可能跑在 macOS GUI / 其他 client，不應該每個都載 ML 套件）
- VAD 跟 ASR 在同一 process，segment close 直接餵給 ASR pipeline，沒有額外網路往返
- 將來若 daemon 換更聰明的 segmenter（neural endpoint detector 等），client 不必改

**Alternative considered:** Client 端 VAD，client 直接送「完整 segment」訊息給 daemon。
- 缺點：每個 client 都要載 silero-vad；client 與 daemon 之間多一層解耦但 daemon 失去主導權
- 結論：daemon 端統籌

### Decision 2：silero-vad 而非 webrtcvad / 自製 RMS

**Why:** silero-vad 是 onnx-runtime 跑的小型 neural VAD，~2MB onnx model，CPU 也跑得很快（10ms latency）；準度遠高於 RMS-based 或 webrtcvad（後者是 2010s 老技術，誤判率高）。對中文等 tonal language 表現較好。

**Alternative considered:** 自己用 RMS threshold（recorder.py 已有類似邏輯）。
- 缺點：誤判嚴重（呼吸、雜音算進語音；輕聲尾音被切掉）；門檻調參敏感
- 結論：silero-vad 加 ~2MB 依賴換可靠的 endpoint detection，划算

### Decision 3：Backward compat — 舊 buffer 路徑保留，由 `streaming` 旗標切換

**Why:** Daemon WS 協定是公開介面；舊 client（沒送 `streaming` field）一律走 buffer 路徑。新 client 送 `streaming: true` 才走 VAD 路徑。這樣：
- 不會 break 任何既存 client（包含 tests/scripts/ws-client-test.py）
- 使用者可用 `aureka type --no-streaming` 退回舊路徑做對照（debug 用）
- 未來移除舊路徑前可先 deprecation warning

**Trade-off:** Daemon 需維護兩條路徑一段時間，多 ~50 行 code。可接受 — VAD 路徑成熟後可在後續 change 移除舊路徑。

### Decision 4：Fail-soft — silero-vad 不可用時自動 fallback 到舊路徑

**Why:** silero-vad 載入失敗（onnx 下載失敗、torch hub network error、權限問題）不應該讓使用者完全無法用 voice input。daemon 啟動時嘗試載 silero-vad，失敗時：
- log warning 一次「streaming ASR unavailable, falling back to buffer mode」
- WS handler 看到 `streaming=true` 但 VAD 不在時，silently 跑 buffer 路徑（同等於 `streaming=false`）

**Alternative considered:** 啟動時 hard-fail。
- 缺點：使用者就被擋在門外，連 `aureka type --no-streaming` 也沒用
- 結論：silently degrade

### Decision 5：Partial transcript 不過 LLM，但累積給最終 refine

**Why:** Daemon 在 streaming 模式下：
- 每個 VAD segment close → 跑 ASR → 直接推 `transcript` partial（`final: false`）
- 收到 `end` → flush 任何剩餘 buffer → 推最後一段 partial（`final: true` for ASR phase）
- 把所有 partial 拼成完整 transcript → 跑 LLM `llm_refine_stream` → 推 `refined` events
- Client 端 `replace_text(injected_len, refined)` 蓋寫整段累積長度

這樣 LLM 拿到的是完整上下文（refine 品質有保障），中間 partial 只是 UX 層的「動」。

**Alternative considered:** 每個 VAD segment 都跑 LLM refine。
- 缺點：每段失去跨段語境（標點、代名詞、重複字偵測都會差）；LLM call 次數爆增
- 結論：LLM 等到最後

### Decision 6：Inject 用「累計長度」做 anchor，不依賴 segment_idx

**Why:** Client 已有 `injected_len: int` 追蹤目前 inject 的總字元數。streaming 模式下：
- 每個 partial transcript 用 `inject_text(text)` append，並把 `len(text)` 累加到 `injected_len`
- 最終 `refined` 來時 `replace_text(injected_len, refined_text)` 蓋掉所有累積長度

不必引入 segment_idx 追蹤——以「目前游標前已 inject 多少字元」作 anchor 比較符合既有 `replace_text` 的 backspace+inject 模型。

### Decision 7：silero-vad 放 `[asr]` extra 而非新 extra

**Why:** Streaming 是 ASR 的核心 UX 特性，不是可選的「進階功能」。把 silero-vad 跟 faster-whisper 一起放 `[asr]` 讓所有用 voice input 的人都自動有它。多 ~2MB 依賴 + 一次性 ~2MB onnx download 可接受。

**Alternative considered:** 新增 `[asr-streaming]` extra。
- 缺點：使用者得知道要裝這個 extra 才有 streaming，又一個 footgun
- 結論：直接吃進 `[asr]`，預設啟用

## Risks / Trade-offs

- **Risk:** silero-vad onnx 第一次載入時要從 torch hub 下載，可能因網路問題卡住
  - **Mitigation:** Daemon 啟動時 lazy load + try/except，下載失敗就 fallback 到 buffer 路徑（fail-soft）
- **Risk:** VAD 切句太敏感（背景雜音被當成語音）→ segment 過多、ASR 被洗版
  - **Mitigation:** silero-vad 預設 threshold 0.5 已經保守；若仍噪 → 後續調整 threshold 與 min-silence-ms 參數
- **Risk:** 短促語音（< 600ms）可能被 VAD 判為 noise 整段丟掉
  - **Mitigation:** silero-vad 對短語音（單字、短回應）也能偵測；若實測有問題可調 min-speech-ms
- **Risk:** Partial transcript inject 出現後，使用者看到不準的字會分心
  - **Mitigation:** 既有 design 已接受 — 反正 LLM 會 refine 替換；UX 的核心是「有東西在動」而非「一字不差」
- **Risk:** Daemon 多開一條 streaming code path → 維護面積增加
  - **Mitigation:** 接受 — backward compat 必要；待 streaming 路徑成熟（幾個版本後）可在後續 change 移除舊路徑
- **Trade-off:** 為了 backward compat，舊 client 得不到 streaming 體驗
  - 接受 — `aureka type` 就是預設啟用，使用者不需做任何事
