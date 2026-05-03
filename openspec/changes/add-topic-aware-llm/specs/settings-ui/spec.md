## ADDED Requirements

### Requirement: Hotkey 分頁 Topic 欄位
設定視窗的 Hotkey 分頁 SHALL 提供「Topic / context」單行文字欄位，綁定 `cfg.hotkey.topic`，搭配 helper text 說明用途（例如 `"ZFS storage administration"` 之類的領域字串能讓 LLM refine / translate 用對術語）。空值不影響 prompt。

#### Scenario: 欄位顯示與儲存
- **WHEN** 使用者於 Hotkey 分頁編輯 Topic 欄位並 commit
- **THEN** auto-save 流程把新值寫入 `config.toml [hotkey].topic`，daemon 在線時 `/reload` 套用

#### Scenario: Helper text 引導
- **WHEN** 使用者第一次看到該欄位
- **THEN** helper 文字提示「短句（≤200 字）描述當前的工作領域，refine / translate 模式會帶入 LLM prompt」
