## Overview

This delta extends voice-input refine / translate so users can pin a **domain hint** that nudges the LLM toward correct jargon. Set `[hotkey].topic = "ZFS storage"` once and refined transcripts in that workflow stop garbling "ZFS pool", "vdev", and "RAIDZ"; switch to a financial workflow with `--topic "M&A due diligence"` and the same engine respects deal-room vocabulary instead. The change is opt-in: empty topic preserves today's prompt verbatim.

## ADDED Requirements

### Requirement: Topic 感知 LLM Prompt
`refine` 與 `translate` 模式 SHALL 將使用者設定的 topic 字串注入 LLM system message，作為領域提示。Topic 為空時 prompt 維持與既有版本逐字相同（regression-safe）。

#### Scenario: Topic 不為空時注入 system message
- **WHEN** 使用者送出 transcript，且當前 topic = `"ZFS storage"`，模式 = `refine`
- **THEN** 送至 LLM 的 system message 包含 topic 字串（例如「The user is working on the topic of \"ZFS storage\"...」）

#### Scenario: Topic 為空時 prompt 不變
- **WHEN** 使用者送出 transcript，且 topic = `""`
- **THEN** 送至 LLM 的 messages 與既有版本完全一致

#### Scenario: Translate 模式同樣套用
- **WHEN** 模式為 `translate`、topic 不為空
- **THEN** system message 在語言指令之前先帶 topic 提示

#### Scenario: Transcribe 模式不受影響
- **WHEN** 模式為 `transcribe`
- **THEN** 系統不呼叫 LLM，topic 即使有設值也不影響輸出
