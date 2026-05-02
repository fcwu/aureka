## 1. Code 修改

- [x] 1.1 在 `aureka/client.py` 的 `_voice_session` 修改 partial transcript handler：`mode == "transcribe"` 時 append inject、`mode in ("refine", "translate")` 時改成只 print 到 stderr，不 inject 也不更新 `injected_len`
- [x] 1.2 確認既有 `replace_text(injected_len, refined)` 在 `injected_len = 0` 時等同於純 inject，refine 模式仍正確顯示

## 2. 測試

- [x] 2.1 新增 `tests/test_client_streaming_inject_unit.py`：mock injector，模擬 daemon 推 partial transcript，驗證
  - `transcribe` 模式：injector.inject_text 被呼叫
  - `refine` 模式：injector.inject_text 在 partial 階段未被呼叫；只有最終 refined 時被呼叫（透過 replace_text）
- [x] 2.2 跑 `pytest tests/ -m "unit or integration"` 全綠

## 3. 文件

- [x] 3.1 在 `README.md` 把 streaming 段落補一句：「`refine` 模式下 streaming 不會在草稿即時顯示 raw 文字，只在 terminal 印 partial 進度；最終 refined 才一次寫入草稿」

## 4. Spec 同步

- [x] 4.1 全綠後 archive：`openspec archive fix-streaming-inject-only-in-transcribe-mode`
