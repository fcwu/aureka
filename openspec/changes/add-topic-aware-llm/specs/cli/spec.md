## Overview

This delta gives `aureka type` a one-shot `--topic STRING` flag so users can pin a domain hint for a single voice-input session without editing `config.toml`. Useful for the "I just need this one meeting transcribed in compliance jargon" cases — the flag wins over the config value, and nothing is persisted.

## ADDED Requirements

### Requirement: type 子命令 --topic 旗標
系統 SHALL 為 `aureka type` 子命令提供可選 `--topic STRING` 旗標，覆寫該次調用的 topic（不寫回 config.toml）。優先順序：CLI 旗標 > config.toml 設定 > 空字串。

#### Scenario: CLI 旗標覆寫 config
- **WHEN** config.toml 有 `[hotkey] topic = "general"`、執行 `aureka type --topic "ZFS storage"`
- **THEN** 該次 LLM session 使用 `"ZFS storage"`，config 檔不被修改

#### Scenario: 沒給 --topic 時 fallback config
- **WHEN** config.toml 有 `[hotkey] topic = "QTS firmware"`、執行 `aureka type` 不帶 `--topic`
- **THEN** 該次 LLM session 使用 `"QTS firmware"`

#### Scenario: 都沒設定時為空
- **WHEN** config.toml 沒 `[hotkey] topic`、執行 `aureka type`
- **THEN** topic 為 `""`，prompt 與既有版本一致
