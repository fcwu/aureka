## ADDED Requirements

### Requirement: Resemblyzer 權重納入 registry
`aureka.models.model_registry()` SHALL 在 `[diarize]` extra 已安裝時新增一個 `resemblyzer` 條目，指向官方 voice-encoder 權重；`model_status()` 與 `download_all()` 皆能識別並處理此條目。

#### Scenario: registry 新增條目
- **WHEN** `[diarize]` 已安裝、呼叫 `model_registry()`
- **THEN** 回傳字典含 `resemblyzer` key，value 為對應的 HuggingFace repo ID 或本地權重路徑

#### Scenario: 未安裝 [diarize] 時 registry 不變
- **WHEN** `[diarize]` 未安裝
- **THEN** `resemblyzer` 不出現於 registry，避免 UI 顯示誤導使用者「需要下載但實際沒在用」

#### Scenario: model_status 反映下載狀態
- **WHEN** `[diarize]` 已安裝、呼叫 `model_status()`
- **THEN** 回傳 dict 含 `resemblyzer` 條目，`downloaded` / `size_bytes` / `snapshot_path` 由 HuggingFace cache 決定

#### Scenario: download_all 可指定下載
- **WHEN** 呼叫 `download_all(keys=["resemblyzer"])`
- **THEN** 只下載 resemblyzer 權重，不影響其他模型
