## Context

`add-streaming-asr` change（commit `04ac813`）在 `aureka/client.py:_voice_session` 的 `transcript` handler 加了：

```python
if msg.get("is_partial"):
    injector.inject_text(seg_text)
    injected_len += len(seg_text)
```

這對所有 mode 都觸發，包含 `refine` / `translate`。實際結果是使用者的草稿視窗在錄音過程中被 raw transcript 寫入，等 LLM refine 完成才被 `replace_text` 用 backspace + retype 替換。視覺上是雙重 inject + flicker。

## Goals / Non-Goals

**Goals:**
- 解掉 refine / translate 模式下的草稿 flicker：partial transcript 不 inject 到游標
- 保留命令列使用者的進度回饋：partial 改成印到 stderr
- transcribe 模式（純轉錄、無 LLM）保持邊講邊 inject 的行為

**Non-Goals:**
- 不動 daemon 端 streaming 行為（仍然推 partial event）
- 不動 WS protocol
- 不引入新 config（mode 已決定行為，不需要再加旗標）

## Decisions

### Decision 1：以 mode 區分 partial 處理，不引入新 config

**Why:** 需求純粹是「refine/translate 模式下 final 才 inject」，跟 mode 概念完全對齊。引入新 config（如 `inject_partials: bool`）會多一個使用者要懂的旋鈕，但實際上沒人會想在 refine 模式下啟用 partial inject（那就是現在的 bug）。Mode-based dispatch 是 invariant 不是 preference。

**Alternative considered:** 加 `[ui] inject_partials = false` config。
- 缺點：增加表面積、預設值仍是「refine 模式下 false」、本質還是 mode-based 判斷
- 結論：直接 mode-based，不要 config

### Decision 2：refine / translate 的 partial 改印到 stderr

**Why:** 命令列使用者跑 `aureka type` 時 terminal 是開著的，把 partial 輸出到 stderr 等於「另一個視窗顯示進度」，不污染草稿。Tray icon 模式下使用者看不到 stderr，但 tray 模式本來就是「丟一段話、等結果」的後台流程，partial 進度顯示對 tray 模式幫助有限——這個 trade-off 接受。

**Alternative considered:** 完全不顯示 partial。
- 缺點：失去「ASR 在跑」的回饋
- 結論：stderr-only 是最低成本的回饋方式

## Risks / Trade-offs

- **Trade-off:** Tray icon 模式下使用者看不到 streaming partial（沒 terminal）。但 tray 模式本來 UX 就是「按熱鍵 → 講完 → 結果出現」，使用者預期就是等。可接受
- **Risk:** 若使用者已經習慣現在的 partial-inject 行為，這個改動算 BREAKING UX
  - **Mitigation:** Streaming 是上一個 change 才剛 ship 的（同一天），不太可能有使用者已習慣；release notes 提一下即可
- **No risk** to backward compat at protocol level：daemon 端不改，舊 client（沒 streaming）也不影響
