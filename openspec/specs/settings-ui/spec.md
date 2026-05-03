# settings-ui Specification

## Purpose
TBD - created by archiving change add-topic-aware-llm. Update Purpose after archive.
## Requirements
### Requirement: Hotkey 分頁 Topic 欄位
設定視窗的 Hotkey 分頁 SHALL 提供「Topic / context」單行文字欄位，綁定 `cfg.hotkey.topic`，搭配 helper text 說明用途（例如 `"ZFS storage administration"` 之類的領域字串能讓 LLM refine / translate 用對術語）。空值不影響 prompt。

#### Scenario: 欄位顯示與儲存
- **WHEN** 使用者於 Hotkey 分頁編輯 Topic 欄位並 commit
- **THEN** auto-save 流程把新值寫入 `config.toml [hotkey].topic`，daemon 在線時 `/reload` 套用

#### Scenario: Helper text 引導
- **WHEN** 使用者第一次看到該欄位
- **THEN** helper 文字提示「短句（≤200 字）描述當前的工作領域，refine / translate 模式會帶入 LLM prompt」

### Requirement: 設定視窗框架
系統 SHALL 透過 `aureka.ui.open_settings()` 啟動一個 pywebview 原生視窗，並在 `aureka ui` 子命令觸發時呼叫。視窗 HTML 由模組內嵌字串提供，使用 Tailwind（Play CDN）負責主要樣式，並內嵌一份手寫 CSS 作為離線 fallback；視窗預設大小為 760×600，支援系統深淺色。

#### Scenario: CLI 觸發
- **WHEN** 使用者在 shell 執行 `aureka ui`
- **THEN** 系統建立 pywebview 視窗、載入內嵌 HTML、註冊 `Api` 為 JS bridge

#### Scenario: 缺少 pywebview
- **WHEN** 系統匯入 `webview` 失敗
- **THEN** `open_settings()` 拋出 `SystemExit`，訊息提示 `pip install 'aureka[ui]'`

#### Scenario: 離線可用
- **WHEN** Tailwind Play CDN 無法連線
- **THEN** 視窗仍可顯示與操作，所有欄位、按鈕透過 fallback CSS 維持可點擊與可讀

### Requirement: 自動儲存（auto-save）與 Daemon Reload
設定視窗 SHALL **不**提供 Save 按鈕；任何欄位 commit 事件（`<select>` 的 `change`、`<input>` 的 blur 或 Enter）後，UI MUST 在短延遲（≤500 ms debounce）內把整份表單寫回 `config.toml` 並保留原檔註解。儲存成功且 daemon 在線時系統 SHALL POST `/reload`，狀態列顯示「daemon 熱套用」、「需重啟欄位列表」或「daemon 未運行」。

#### Scenario: 保留註解儲存
- **WHEN** 使用者在 UI 編輯任意欄位並 commit（離開焦點 / 按 Enter / 改變 select）
- **THEN** 系統用 `tomlkit` parse 既有 `config.toml`，覆寫被改的 key，回寫後原註解仍存在

#### Scenario: Daemon 在線且改動可熱套用
- **WHEN** auto-save 完成、daemon 健康，被改的欄位都屬 LLM/VLM 範圍
- **THEN** UI 狀態列顯示 `Saved · daemon reloaded`

#### Scenario: Daemon 在線但有 restart-required 欄位
- **WHEN** auto-save 完成、daemon 健康，改動包含 `asr.model` / `tts.voice` / `daemon.port` 等
- **THEN** UI 狀態列以警告色列出需要重啟的欄位名稱

#### Scenario: Daemon 不在線
- **WHEN** auto-save 完成、無法連到 daemon 端口
- **THEN** UI 顯示 `Saved · daemon not running`，不視為錯誤

#### Scenario: 視窗開啟初始載入不觸發儲存
- **WHEN** 視窗第一次開啟、`Api.load_config()` 把現有值灌入欄位
- **THEN** 系統 MUST NOT 因為這些程式化的填入觸發任何寫回 `config.toml` 的動作

#### Scenario: 程式化欄位寫入也觸發 auto-save
- **WHEN** UI 透過 port Auto 按鈕 / hotkey 捕捉 / benchmark Recommendation Apply 把值塞到欄位
- **THEN** 系統 SHALL 觸發與使用者手動 commit 等價的 auto-save 流程

#### Scenario: 沒有 in-window Save / Close 按鈕
- **WHEN** 視窗開啟
- **THEN** footer 區塊只有狀態文字；視窗關閉走作業系統原生視窗框（紅色關閉鈕 / X）

### Requirement: 欄位皆採選單形式（值域已知時）
系統 SHALL 將任何已知值域的欄位以 `<select>` 或 `<input list="">+<datalist>` 呈現，避免使用者需要記憶字串或 enum：靜態 `<select>` 用於 `tts.lang_code`、`tts.device`、`hotkey.mode`、`hotkey.input_mode`、`daemon.host`；datalist 用於 `asr.model`、`tts.voice`、`hotkey.lang`，以及動態取得的 `llm.model`、`vlm.model`。

#### Scenario: ASR 模型尺寸選單
- **WHEN** 使用者打開 ASR 分頁
- **THEN** `asr.model` 欄位以 datalist 提供 `tiny / base / small / medium / large-v2 / large-v3 / large-v3-turbo`，但仍允許輸入 HuggingFace repo ID

#### Scenario: LLM 模型動態填入
- **WHEN** 設定視窗開啟、`llm.base_url` 已設定
- **THEN** UI 在背景 GET `{base_url}/v1/models`，將回傳 model id 灌入 `llm.model` 對應的 datalist

#### Scenario: VLM 模型過濾 vision
- **WHEN** 取得 `{vlm.base_url}/v1/models` 回應
- **THEN** UI 只把 capabilities 包含 vision 的 model id 加進 `vlm.model` datalist

#### Scenario: 上游不可達
- **WHEN** GET `/v1/models` 失敗（連線或 4xx/5xx）
- **THEN** datalist 退化為僅含 `auto` 一個選項，欄位仍可手動輸入

### Requirement: 模型下載狀態與一鍵下載
系統 SHALL 提供 Models 分頁顯示 `model-management` 註冊的所有模型的下載狀態（已下載 / 缺失）、佔用空間，以及 Download / Re-download 按鈕；下載過程透過進度條顯示百分比並可被取消（取消等同放棄該次調用，不刪除已下載檔）。

#### Scenario: 開啟 Models 分頁顯示狀態
- **WHEN** 使用者切換到 Models 分頁
- **THEN** UI 呼叫 `Api.model_status()` 並對每個 entry 顯示：repo id、是否已下載、若已下載則顯示磁碟大小

#### Scenario: 下載觸發進度條
- **WHEN** 使用者按下某個模型的 Download 按鈕
- **THEN** Api 啟動背景下載，每 500 ms UI 透過 `Api.download_progress()` 取得 `{phase, percent, current_file}` 並更新進度條

#### Scenario: 下載完成
- **WHEN** 下載成功結束
- **THEN** 進度條改為「Downloaded ✓ <size>」，下次重新打開分頁仍顯示已下載

#### Scenario: 下載失敗
- **WHEN** `huggingface_hub.snapshot_download` 拋例外（網路、權限、gated repo）
- **THEN** 進度條改為紅色錯誤訊息，包含例外類型與建議（例如 `huggingface-cli login`）

### Requirement: Port 自動偵測
系統 SHALL 在 `daemon.port` 欄位旁提供「Auto」按鈕，點擊後從目前數值往上探測前 64 個 port，回填第一個 `socket.bind` 成功的 port；不自動 Save。

#### Scenario: 偵測成功
- **WHEN** 目前 `daemon.port = 7777`、7777 已被佔用、7778 空閒
- **THEN** 按下 Auto 後，欄位被填為 `7778`，使用者仍需自己按 Save

#### Scenario: 範圍內全部被佔用
- **WHEN** 從目前值往上 64 個 port 都失敗
- **THEN** UI 在欄位旁顯示「No free port in range」，欄位內容不變

### Requirement: Hotkey 捕捉
系統 SHALL 在 `hotkey.trigger` 欄位旁提供「Press…」按鈕，啟動後攔截下一個 keydown 事件，將修飾鍵與主鍵組合轉成 pynput 字串（例如 `<ctrl>+<alt>+space`）填回欄位；按 ESC 取消。

#### Scenario: 捕捉組合鍵
- **WHEN** 使用者點 Press…，按下 Ctrl+Alt+Space
- **THEN** 欄位被填為 `<ctrl>+<alt>+space`，捕捉狀態結束

#### Scenario: 取消捕捉
- **WHEN** 使用者在 Press… 模式下按 ESC
- **THEN** 欄位內容不變，捕捉狀態結束

### Requirement: Benchmark 與設定建議整合
系統 SHALL 提供 Tools 分頁，內含「Run benchmark」按鈕觸發 `aureka.benchmark.run_benchmark(quick=True)`；執行期間將 stdout 行流式渲染到 UI，完成後依 benchmark 結構化結果產生具體建議（例如 device、ASR 模型大小、thinking_budget），每條建議旁附 Apply 按鈕直接寫入相應欄位（仍需 Save）。

#### Scenario: 串流 stdout
- **WHEN** Tools 分頁按下 Run benchmark
- **THEN** UI 顯示一個 log 區塊，benchmark 每印出一行（例如 `[ASR] run 3/5 → 1.23s`）UI 即時追加

#### Scenario: 推薦 device
- **WHEN** benchmark 結果顯示 mps median 顯著快於 cpu median（< 0.7×）
- **THEN** UI 出現一張 Recommendation 卡片：「Set tts.device = mps」與 Apply 按鈕

#### Scenario: 推薦 ASR 降級
- **WHEN** ASR median RTF > 0.5 且目前 `asr.model` 為 medium 或更大
- **THEN** UI 出現建議「Drop ASR model size to <next-smaller>」與 Apply 按鈕

#### Scenario: 推薦關閉 thinking
- **WHEN** LLM TTFT > 3 秒且 `llm.thinking_budget` > 0
- **THEN** UI 出現建議「Disable thinking_budget」與 Apply 按鈕

#### Scenario: Apply 寫入欄位
- **WHEN** 使用者按下任一 Recommendation 的 Apply
- **THEN** 對應欄位被填為建議值，分頁切換到該欄位所在頁面，仍需手動 Save 才會持久化

### Requirement: Listen 分頁
設定視窗 SHALL 新增 Listen 分頁，顯示偵測到的 loopback 裝置清單、目前選用的裝置、輸出 sink 設定（是否 `--window`、是否寫檔）、以及一個 Test capture 按鈕能即時量 5 秒 RMS / 顯示波形以驗證路由。

#### Scenario: 顯示偵測結果
- **WHEN** 使用者開啟 Listen 分頁
- **THEN** UI 列出當前平台所有 loopback 候選裝置，並標記哪一個是預設

#### Scenario: 切換裝置
- **WHEN** 使用者改選裝置並 commit
- **THEN** auto-save 把新值寫入 `[listen].device` 並 `/reload` daemon

#### Scenario: Test capture
- **WHEN** 使用者按下 Test capture 按鈕
- **THEN** UI 啟動 5 秒擷取，顯示即時 RMS 數值與小型波形；若 RMS 始終為 0 則紅字提示 routing 可能未設好

#### Scenario: macOS 提示
- **WHEN** macOS 上沒有偵測到任何 BlackHole 類裝置
- **THEN** Listen 分頁顯示一張卡片，內含安裝指令與 README 設定章節連結

### Requirement: Models 分頁顯示 resemblyzer
設定視窗 Models 分頁 SHALL 在 `[diarize]` 已安裝時顯示 resemblyzer 權重的下載狀態（同 Kokoro / faster-whisper 的 UX），未安裝時該條目不顯示。

#### Scenario: 已安裝 [diarize] 時顯示
- **WHEN** 使用者於 `[diarize]` 已安裝環境開啟 Models 分頁
- **THEN** 出現第三條 row 顯示 `resemblyzer` repo id、是否已下載、磁碟大小，附 Download / Re-download 按鈕

#### Scenario: 未安裝 [diarize] 時不顯示
- **WHEN** 使用者於未安裝 `[diarize]` 環境開啟 Models 分頁
- **THEN** UI 僅顯示 Kokoro 與 faster-whisper 兩條，不渲染 resemblyzer

#### Scenario: 下載觸發進度條
- **WHEN** 使用者按下 resemblyzer 的 Download
- **THEN** UI 走與既有模型一致的 polling 進度條流程，下載完成後狀態更新為 Downloaded

