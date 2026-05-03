## Purpose

定義 `aureka` CLI 的子命令介面、全域旗標與設定檔載入規則。
## Requirements
### Requirement: process 子命令
系統 SHALL 提供 `aureka process <file>` 子命令，執行批次流水線。

#### Scenario: 基本批次處理
- **WHEN** 執行 `aureka process video.mp4`
- **THEN** 系統執行完整批次流水線並輸出 Markdown 結果路徑

#### Scenario: 自訂參數
- **WHEN** 執行 `aureka process podcast.mp3 --frame-interval 60 --device cuda`
- **THEN** 系統使用指定的畫面擷取間隔和計算裝置

### Requirement: speak 子命令
系統 SHALL 提供 `aureka speak` 子命令，執行 TTS 回讀。

#### Scenario: 直接文字朗讀
- **WHEN** 執行 `aureka speak "今天的工作重點是什麼"`
- **THEN** 系統合成並播放語音

#### Scenario: 檔案朗讀
- **WHEN** 執行 `aureka speak --file path/to/note.md`
- **THEN** 系統讀取並朗讀檔案內容（略過 frontmatter 和 Markdown 標記）

### Requirement: type 子命令
系統 SHALL 提供 `aureka type` 子命令，觸發單次語音輸入（daemon 未啟動時有冷啟動延遲）。

#### Scenario: 基本語音輸入
- **WHEN** 執行 `aureka type`
- **THEN** 系統錄音後轉錄並注入文字到游標位置

#### Scenario: refine 模式
- **WHEN** 執行 `aureka type --mode refine`
- **THEN** 系統轉錄後以 LLM 修飾並注入

#### Scenario: translate 模式
- **WHEN** 執行 `aureka type --mode translate --lang en`
- **THEN** 系統轉錄後翻譯成英文並注入

### Requirement: daemon 子命令
系統 SHALL 提供 `aureka daemon start/stop/status` 子命令管理 daemon 程序。

#### Scenario: 啟動 daemon
- **WHEN** 執行 `aureka daemon start`
- **THEN** Daemon 在背景啟動，輸出確認訊息含監聽位址

#### Scenario: 停止 daemon
- **WHEN** 執行 `aureka daemon stop`
- **THEN** Daemon 程序終止，輸出確認訊息

#### Scenario: 查詢 daemon 狀態
- **WHEN** 執行 `aureka daemon status`
- **THEN** 輸出 daemon 是否執行中，若執行中顯示 PID 和 uptime

### Requirement: 全域 --device 旗標
系統 SHALL 支援全域 `--device` 旗標（`auto`、`cuda`、`mps`、`cpu`），覆蓋自動裝置偵測。

#### Scenario: 強制 CPU 裝置
- **WHEN** 執行 `aureka process video.mp4 --device cpu`
- **THEN** 系統強制使用 CPU 進行 ASR 和 TTS，忽略 GPU 可用性

### Requirement: 設定檔路徑
系統 SHALL 支援 `AUREKA_CONFIG` 環境變數指定 `config.toml` 路徑，預設為 `./config.toml`。

#### Scenario: 自訂設定檔
- **WHEN** 設定 `AUREKA_CONFIG=/path/to/my-config.toml` 並執行任何子命令
- **THEN** 系統從指定路徑載入設定

#### Scenario: 設定檔不存在
- **WHEN** 指定的設定檔路徑不存在
- **THEN** 系統輸出錯誤訊息提示如何產生設定檔（`cp config.example.toml config.toml`）

### Requirement: download 子命令
系統 SHALL 提供 `aureka download` 子命令，預先下載執行時會用到的所有模型，避免首次使用 `speak` / `type` / `daemon start` 時的長時間靜默等待。

#### Scenario: 基本下載
- **WHEN** 執行 `aureka download`
- **THEN** 系統呼叫 `aureka.models.download_all()`，依當前裝置環境下載 Kokoro、faster-whisper（必下載）以及在 CUDA/MPS + TheWhisper 可用時加碼下載 TheWhisper

#### Scenario: 下載過程顯示進度
- **WHEN** 執行 `aureka download` 且模型尚未存在於本地 cache
- **THEN** 終端顯示 `huggingface_hub` 內建的 tqdm 進度條，使用者可看到下載進度與速度

#### Scenario: 下載完成輸出摘要
- **WHEN** `aureka download` 全部模型下載成功
- **THEN** 終端依序列出每個模型的邏輯名稱、HuggingFace repo ID 與本地 snapshot 路徑

#### Scenario: 已下載則跳過
- **WHEN** 模型已存在於本地 cache 後再次執行 `aureka download`
- **THEN** 系統快速驗證 cache 並列印「已存在」摘要，不重新下載

#### Scenario: 下載失敗以 non-zero exit code 結束
- **WHEN** 任一模型下載失敗（網路、權限或磁碟錯誤）
- **THEN** `aureka download` 印出錯誤訊息並以 non-zero exit code 結束，不靜默忽略

#### Scenario: 接受 --device 旗標
- **WHEN** 執行 `aureka --device cpu download`
- **THEN** 系統把 `device` 視為 `cpu`，跳過 TheWhisper 的下載

### Requirement: benchmark 子命令
系統 SHALL 提供 `aureka benchmark` 子命令，量測本機 ASR/TTS 與遠端 LLM 速度，輸出 stdout 表格與 Markdown 報告。

#### Scenario: 基本執行
- **WHEN** 執行 `aureka benchmark`
- **THEN** 系統呼叫 `aureka.benchmark.run_benchmark()`，跑完 ASR、TTS、LLM 三個任務，stdout 顯示對齊表格，當前目錄產生 `benchmark-<hostname>-<YYYY-MM-DD>.md`

#### Scenario: Quick 模式
- **WHEN** 執行 `aureka benchmark --quick`
- **THEN** 每個任務跑 1 輪 warm-up + 1 輪計時，總時間顯著縮短

#### Scenario: 跳過 LLM
- **WHEN** 執行 `aureka benchmark --skip-llm`
- **THEN** 系統不打 LLM 端點，報告中 LLM rows 標記為 `skipped`

#### Scenario: 自訂報告路徑
- **WHEN** 執行 `aureka benchmark --output /tmp/r.md`
- **THEN** 報告寫到 `/tmp/r.md`

#### Scenario: 跑時即時進度
- **WHEN** 執行 `aureka benchmark`
- **THEN** stdout 在每輪結束後立刻印出進度（如 `[ASR] run 3/5 → 1.23s`），不等全部跑完才一次顯示

#### Scenario: 接受 --device 旗標
- **WHEN** 執行 `aureka --device cpu benchmark`
- **THEN** ASR 與 TTS 載入時使用 `cpu` 裝置

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

### Requirement: process 子命令 --format 旗標
`aureka process` SHALL 接受 `--format` 旗標，值為 `md` / `srt` / `vtt` / `all` 或任意逗號組合，控制輸出哪些字幕 / 文件格式。

#### Scenario: 多格式並存
- **WHEN** 執行 `aureka process video.mp4 --format md,vtt`
- **THEN** 系統同時產出 `.md` 與 `.vtt`

#### Scenario: 無效值報錯
- **WHEN** 執行 `aureka process video.mp4 --format pdf`
- **THEN** 系統以 non-zero exit code 結束，stderr 印出有效值清單

### Requirement: type / listen 子命令尊重 [hotkey].pause
`aureka type` 與 `aureka listen` SHALL 在啟動時讀取 `cfg.hotkey.pause`，若不為空則註冊該熱鍵為暫停 / 繼續切換。

#### Scenario: 預設 pause 鍵
- **WHEN** config 沒設 `[hotkey].pause`、執行 `aureka type`
- **THEN** 系統綁定預設 `<ctrl>+<alt>+p` 為暫停鍵

#### Scenario: 自訂 pause 鍵
- **WHEN** config `[hotkey].pause = "<f12>"`、執行 `aureka type`
- **THEN** 系統改綁定 F12 為暫停鍵

#### Scenario: 與 trigger 衝突警告
- **WHEN** `[hotkey].trigger` 與 `[hotkey].pause` 設為同一值
- **THEN** 系統 stderr 印出警告，pause 熱鍵不註冊（trigger 優先）

### Requirement: listen 子命令
系統 SHALL 提供 `aureka listen` 子命令，啟動系統音訊 loopback 擷取與串流轉錄。

#### Scenario: 啟動 listen
- **WHEN** 使用者執行 `aureka listen`
- **THEN** 系統偵測平台 loopback 裝置，開始持續擷取並 VAD 切段，每段送 ASR、依模式可選擇送 LLM refine / translate

#### Scenario: 模式 / 語言 / target 等旗標
- **WHEN** 執行 `aureka listen --mode translate --target zh`
- **THEN** transcript 經 ASR 後送 LLM 翻譯為中文輸出

#### Scenario: 輸出 sink
- **WHEN** 執行 `aureka listen --out meeting.txt`
- **THEN** 每段 transcript 即時 append 到 `meeting.txt`，行格式 `[YYYY-MM-DD HH:MM:SS] [system] <text>`

#### Scenario: 視窗模式
- **WHEN** 執行 `aureka listen --window`
- **THEN** 系統以 pywebview 開啟 tail-style transcript 視窗，每段 transcript 即時追加；視窗不搶焦點

#### Scenario: 同時擷取麥克風
- **WHEN** 執行 `aureka listen --mic`
- **THEN** 系統開兩路擷取（loopback + mic），輸出 transcript 帶 label `[system]` / `[mic]`

#### Scenario: 顯式裝置覆寫
- **WHEN** 執行 `aureka listen --device "BlackHole 2ch"`
- **THEN** 系統略過 auto-detect，直接使用指定裝置；找不到時報錯離開

### Requirement: doctor audio 子命令
系統 SHALL 提供 `aureka doctor audio` 子命令印出當前平台音訊裝置診斷資訊，協助排查 loopback 設定問題。

#### Scenario: 診斷輸出
- **WHEN** 執行 `aureka doctor audio`
- **THEN** stdout 列出（1）所有音訊輸入裝置與 sample rate；（2）標記哪些是 loopback；（3）若為 macOS，提示是否在 Multi-Output Device 中正確路由

### Requirement: process 子命令 --diarize / --num-speakers / --no-speaker-labels
`aureka process` SHALL 接受 `--diarize`、`--num-speakers N`、`--no-speaker-labels` 三個與講者辨識相關的旗標。

#### Scenario: 啟用講者辨識
- **WHEN** 執行 `aureka process meeting.mp4 --diarize`
- **THEN** 系統在 ASR 後額外跑 diarization，所有輸出格式都帶講者標籤

#### Scenario: 指定講者人數
- **WHEN** 執行 `aureka process meeting.mp4 --diarize --num-speakers 3`
- **THEN** spectralcluster 強制以 3 群輸出；忽略自動偵測

#### Scenario: 講者辨識但不顯示文字標籤
- **WHEN** 執行 `aureka process meeting.mp4 --diarize --no-speaker-labels`
- **THEN** Markdown / SRT / VTT 內不顯示 `[S1]` 等前綴；HTML 仍以顏色標記講者

#### Scenario: --diarize 與 --format html 組合
- **WHEN** 執行 `aureka process meeting.mp4 --diarize --format html`
- **THEN** 產出的 HTML 含逐字稿、講者顏色、波形互動播放器

