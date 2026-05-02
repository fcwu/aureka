## 1. 依賴與 VAD 封裝

- [x] 1.1 在 `pyproject.toml` 的 `[asr]` extra 加入 `silero-vad>=6.0.0`；`requirements.txt` 同步加入
- [x] 1.2 新增 `aureka/vad.py`：封裝 silero-vad 載入 + `VadSegmenter` class（吃 PCM chunk，回傳 segment-close 事件）
- [x] 1.3 `VadSegmenter.__init__` 用 try/except 包 silero-vad 載入；失敗時 raise 自訂 `VadUnavailable` 例外
- [x] 1.4 `VadSegmenter.feed(pcm_int16)`: 把 chunk 餵給 silero-vad，回傳 `list[np.ndarray]`（已 close 的 segments），沒 close 則回空 list
- [x] 1.5 `VadSegmenter.flush()`: 呼叫者送 `end` 後用，回傳剩餘 buffer 作為最後一個 segment

## 2. Daemon 端 Streaming WS 路徑

- [x] 2.1 在 `aureka/daemon.py` 啟動時嘗試 import `aureka.vad`；失敗時設 `_vad_available = False` 並 log warning
- [x] 2.2 修改 `voice_input` WS handler：讀取 `start` message 的 `streaming` 欄位（預設 false）
- [x] 2.3 `streaming=true` 且 `_vad_available=True`：走新 streaming 路徑（VadSegmenter loop）；其他狀況走既有 buffer 路徑
- [x] 2.4 Streaming loop：每收到 `chunk` 餵給 `VadSegmenter.feed`，每個 close 的 segment 跑 `asr.transcribe` 並推 `{"type": "transcript", "text": ..., "final": false, "is_partial": true}`
- [x] 2.5 收到 `end`：呼叫 `flush()` 拿剩餘 buffer 跑 ASR 推最後 partial；接著對所有 partial 拼成的完整 transcript 跑 LLM refine（若 mode 為 refine/translate）；最後送 `done`
- [x] 2.6 ASR 改用 `run_in_executor` 跑（不阻塞 event loop），確保 partial 推送不被卡住

## 3. Client 端 Streaming 整合

- [x] 3.1 `aureka/client.py`：`_voice_session` 加新 parameter `streaming: bool = True`
- [x] 3.2 `start` message 包含 `streaming` 欄位
- [x] 3.3 Streaming 模式下：改造 audio 送出邏輯，使用 recorder 的 `on_chunk` callback 邊錄邊送（而非等 stop 後一次送）
- [x] 3.4 收到 `transcript` 含 `is_partial: true`：append inject 到游標，並更新累計的 `injected_len`
- [x] 3.5 確認既有 `replace_text(injected_len, refined)` 邏輯能正確覆寫整段累積長度（不論 streaming 或 buffer）

## 4. CLI 整合

- [x] 4.1 `aureka/__main__.py` 的 `cmd_type` parser 加入 `--no-streaming` action="store_true"
- [x] 4.2 `cmd_type` 把 `not args.no_streaming` 傳給 `_voice_session(streaming=...)`
- [x] 4.3 daemon 不在的 fallback 路徑（直接本地跑 ASR）保持原樣（不做 streaming，因沒 daemon 端 VAD pipeline）

## 5. 測試

- [x] 5.1 新增 `tests/test_vad_unit.py`：mock silero-vad，驗證 `VadSegmenter.feed` 在收到 silence 後回傳 segment、`flush` 回傳剩餘 buffer
- [x] 5.2 新增 `tests/test_daemon_streaming.py`：用 mock VAD + mock ASR 啟動 daemon，發 streaming WS 訊息序列，斷言 partial transcripts 即時送出（在 `end` 之前）
- [x] 5.3 驗證 `streaming=true` 但 daemon 端 `_vad_available=False` → silently 走 buffer 路徑（沒 partial 事件，但有最終 transcript）
- [x] 5.4 驗證 buffer 模式（streaming=false）行為與既有測試一致（向下相容性 regression test）
- [x] 5.5 跑 `pytest tests/ -m "unit or integration"` 全綠

## 6. 文件

- [x] 6.1 `README.md` 加入 streaming 說明：「`aureka type` 預設邊講邊顯示，`--no-streaming` 可退回」
- [x] 6.2 `CLAUDE.md` 在「6. WebSocket 快速診斷」加入 streaming protocol 訊息範例
- [x] 6.3 確認 `aureka type --help` 顯示 `--no-streaming` 旗標說明清楚

## 7. Spec 同步

- [x] 7.1 全綠後 archive：`openspec archive add-streaming-asr`
