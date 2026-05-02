## Why

`aureka type` 的當前流程是「錄音 → 停止 → 一次性轉錄整段 → LLM refine → inject」。對長語音（例如 30 秒以上）使用者體驗很差：

1. **視覺死寂期**：講話過程中游標完全沒動，使用者不確定系統有沒有在聽
2. **講完還要等很久**：30s 音訊在 medium 模型上需 ~12s 才轉錄完，這 12s 都是純等待

換成 streaming ASR（VAD 分段）能同時解決這兩個問題：講話過程中段落會一段一段顯示出來（心理回饋）、講完那一刻只剩最後一個 segment 沒轉錄（總等待時間從 12s 降到 ~1s）。

partial transcript 不必精準——後續 LLM refine 都會替換成最終版，使用者最終看到的還是 refined 文字。

## What Changes

- 在 daemon WebSocket `/ws` 路徑新增 streaming 模式（VAD-segmented）
  - 用 silero-vad 偵測語句邊界（停頓 600ms）
  - 每段 close 時立刻丟給 ASR、推 `transcript` partial event 回 client
  - 收到 client `end` 訊息時 flush 剩餘 buffer，跑 LLM refine on 完整累積的 transcript
- `start` message 新增 `streaming: bool` 欄位（預設 false 維持向下相容）
- `aureka type` client 預設啟用 streaming（送 `streaming: true`），加 `--no-streaming` 旗標可退回舊行為
- `aureka.client._voice_session` 改用 recorder 的 `on_chunk` callback 邊錄邊送，不再 batch 在錄完後一次送
- 收到 streaming partial transcript 立刻 inject（append cursor）；收到 LLM refined final 時 `replace_text` 蓋寫累積長度
- 加新依賴 `silero-vad>=6.0.0`（~2MB pip + ~2MB onnx model 第一次跑時下載）放到 `[asr]` extra
- 若 silero-vad import 失敗或 daemon 端模型載入失敗 → fallback 回舊 buffer 模式 + log warning
- 不影響 `aureka process` 批次流水線（仍走非-streaming 路徑）

## Capabilities

### New Capabilities
（無新 capability）

### Modified Capabilities
- `daemon`：新增 streaming ASR WS path（與現有 buffer path 共存）
- `voice-input`：`aureka type` 預設啟用 streaming + 新增 `--no-streaming` 旗標 + UX 改成邊講邊顯示

## Impact

- 修改 `aureka/daemon.py`：擴充 `/ws` handler 處理 `streaming` 旗標、引入 VAD 切句邏輯、新增 partial transcript 推送
- 修改 `aureka/client.py`：`_voice_session` 改用 callback streaming + 處理多段 partial transcript inject
- 修改 `aureka/__main__.py`：`aureka type` 加 `--no-streaming` 旗標
- 新增 `aureka/streaming.py`（或併入 daemon.py）：封裝 VAD 切句邏輯
- 修改 `pyproject.toml` / `requirements.txt`：新增 `silero-vad`
- 新增 `tests/test_streaming_unit.py`：mock VAD + ASR 驗證 segment-close → partial transcript 流程
- 不改變既有 daemon `/health` / `/process` / `/speak` HTTP 端點
- 不改變既有 `[asr]` config（streaming 沿用 `cfg.asr.model`）
- 不改變 `aureka process` 批次流水線
