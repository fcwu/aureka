## Overview

This delta pins the `aureka ui`, `aureka tray`, and `aureka autostart` subcommand contracts so login launches **tray** (which auto-starts the daemon), and `Settings…` from the tray opens the same pywebview window. One entry point, one mental model: open the Aureka tray, click Settings, edit, done. No more "did I start the daemon?" / "where's the config file?" friction for new users.

## ADDED Requirements

### Requirement: ui 子命令
系統 SHALL 提供 `aureka ui` 子命令，啟動 pywebview 設定視窗。視窗詳細行為定義於 `settings-ui` capability。

#### Scenario: 啟動視窗
- **WHEN** 使用者在 shell 執行 `aureka ui`
- **THEN** 系統建立 pywebview 原生視窗，載入 `aureka.ui` 內嵌 HTML 並啟動 JS bridge

#### Scenario: 缺少相依套件
- **WHEN** pywebview 未安裝
- **THEN** 命令以非零 exit code 結束，stderr 顯示 `pip install 'aureka[ui]'` 提示

### Requirement: tray 子命令
系統 SHALL 提供 `aureka tray` 子命令，啟動系統 tray icon 與選單。Tray 啟動時若 daemon 未在監聽 SHALL 自動 spawn daemon（詳見 `voice-input` capability）。

#### Scenario: 啟動 tray
- **WHEN** 使用者在 shell 執行 `aureka tray`
- **THEN** 系統建立 menu bar / system tray icon，提供 Settings、Start daemon、Stop daemon、Quit 等選單項

#### Scenario: 自動啟 daemon
- **WHEN** 執行 `aureka tray` 但 daemon 未運行
- **THEN** Tray 在 icon 顯示前 spawn `aureka daemon start`，使用者下次按下熱鍵立刻可用

### Requirement: autostart 子命令
系統 SHALL 提供 `aureka autostart {install,uninstall,status}` 子命令，跨平台管理登入時自動啟動的 launch agent / scheduled task。**install** 安裝的命令 MUST 為 `aureka tray`（不直接啟動 `_daemon_serve`），讓登入後使用者同時取得 daemon + tray icon。

#### Scenario: macOS install
- **WHEN** 在 macOS 執行 `aureka autostart install`
- **THEN** 系統寫入 `~/Library/LaunchAgents/com.aureka.daemon.plist`，`ProgramArguments` 指向 `python -m aureka tray`，`ProcessType` 為 `Adaptive`，`KeepAlive.SuccessfulExit=False`、`KeepAlive.Crashed=True`，並 `launchctl bootstrap` 成功

#### Scenario: Windows install
- **WHEN** 在 Windows 執行 `aureka autostart install`
- **THEN** 系統建立 schtasks at-logon task，命令為 `cmd /c "set AUREKA_CONFIG=… && python -m aureka tray"`

#### Scenario: 反向卸載
- **WHEN** 執行 `aureka autostart uninstall`
- **THEN** 對應平台的 launch agent / task 被移除，後續登入不再自動啟動

#### Scenario: 查詢狀態
- **WHEN** 執行 `aureka autostart status`
- **THEN** 系統印出「installed / not installed」與相關詳情（plist 路徑、上次執行結果等），exit code 0 表示已安裝、1 表示未安裝
