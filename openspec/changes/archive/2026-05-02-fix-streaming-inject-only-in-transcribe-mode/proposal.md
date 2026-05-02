## Why

剛上線的 streaming ASR 在 `refine` / `translate` 模式下會把 raw partial transcript 直接 inject 到使用者游標位置。等 LLM refine 完成後再 `replace_text` 用 backspace + retype 蓋掉。實際使用情境（在草稿視窗打字）會看到：

1. 講話過程中，草稿視窗陸續冒出 raw 字（含同音錯字、無標點、語氣詞）
2. 講完後，那串 raw 字被 backspace 刪掉
3. 換成 LLM refined 後的乾淨文字

對使用者：草稿被 raw 字「污染」過一輪、然後又被改寫，視覺上是噪音。使用者明確只想看到最終的 refined 文字。

`transcribe` 模式（沒 LLM 修飾）邊講邊 inject 是合理的——沒有 refine 來覆寫。

## What Changes

- Client `_voice_session` 收到 partial transcript（`is_partial: true`）時：
  - `mode == "transcribe"`：append inject 到游標（同現在）
  - `mode in ("refine", "translate")`：**不** inject，只在 stderr 印「[aureka] partial: ...」當作命令列回饋
- 等收到 final `refined` 才一次 inject 整段（保持現有 `replace_text(injected_len, refined)` 的 anchor，因 `injected_len = 0` 時等同於純 inject）
- 不改變 daemon 端 streaming 路徑、不動 `--no-streaming` 旗標、不變 protocol

## Capabilities

### New Capabilities
（無新 capability）

### Modified Capabilities
- `voice-input`：`refine` / `translate` 模式下 streaming partial 不 inject 到游標、改為 stderr-only 進度顯示

## Impact

- 修改 `aureka/client.py`：partial transcript handler 加 mode 判斷
- 不需修改 daemon、protocol、CLI 或 config
- 既有 `tests/test_daemon_streaming.py` 不受影響（測 daemon 推送行為，不測 client inject）
- 新增 client-side unit test 驗證 mode-based inject behavior（refine 模式不 inject、transcribe 模式 inject）
