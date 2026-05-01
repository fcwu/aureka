---
name: test-writer
description: 根據 docs/design.md 或使用者描述，產出結構化 test cases 並寫入 tests/test*.md。Use when you need to generate test cases for a feature, module, or API.
---

根據設計文件或使用者描述，產出結構化 test cases 並寫入 `tests/test*.md`。

## 測試層級

| 層級 | 說明 | 外部相依 |
|------|------|----------|
| **Unit** | pytest，mock ASR/LLM/TTS 所有外部呼叫 | 無 |
| **Integration** | FastAPI `TestClient`，mock LM Studio（`mock-llm-server.py`） | 無（mock） |
| **E2E-ws** | 啟動真實 daemon，WebSocket 客戶端驗證串流協定 | Daemon 已啟動 |
| **E2E-cli** | 啟動真實 daemon，CLI 指令（`aureka process / speak / type`） | Daemon 已啟動 |
| **Device** | 需要真實 GPU 或麥克風 | GPU / 音訊硬體 |

## 輸入來源

- `docs/design.md` 中的模組或章節（e.g. `七、語音輸入模式`）
- 描述文字
- 具體功能名稱（e.g. `asr`, `daemon`, `injector`）

## 步驟

### 1. 判斷來源

- 有指定 design.md 章節 → 讀取對應章節
- 描述文字 → 直接產出
- 未指定 → 詢問使用者

### 2. 讀取目標測試檔

```bash
ls tests/test*.md
```

- 只有一個檔案 → 寫入該檔
- 多個檔案 → 詢問要加到哪個，或建新檔 `tests/test-<module>.md`
- 建新檔 → 加上 header：

```markdown
# Aureka Test Cases — <模組名稱>
```

### 3. 取得現有編號

掃描目標檔，找最後的 `## T<N>`，從 `T<N+1>` 開始編號。

### 4. 產出 test cases（BDD 格式）

````markdown
## T<N> — <功能描述>

**層級**：Unit | Integration | E2E-ws | E2E-cli | Device

> **自動化**（若有對應 pytest）：`pytest tests/test_<module>.py::test_<name> -v`

**Given** <前置條件與環境狀態>
**When** <執行的操作>
**Then** <可觀察的結果>

**When** <另一操作（同情境變體）>
**Then** <對應結果>

**反向驗證**（若適用）：
```bash
# 驗證錯誤情況的指令
```
````

**BDD 原則：**
- **Given**：描述環境（daemon 是否啟動、config 內容、測試音訊）
- **When**：單一操作（WebSocket 訊息、CLI 指令、HTTP 請求）
- **Then**：可觀察輸出（WS 訊息類型、HTTP 狀態碼、檔案內容、stdout）
- 同一 case 可有多組 When/Then 涵蓋不同分支
- **不寫詳細 setup 步驟**：前置用一句描述意圖，test-verifier 自行執行

**用戶導向原則（最重要）：**
- 測試描述的是**使用者能觀察到的行為**，不是程式內部狀態
- 禁止：函式回傳值（`asr.transcribe() 回傳 list`）、變數名稱、記憶體狀態
- 正例：`When 客戶端送 {"type":"end"}` / `Then 收到 {"type":"done"}`
- 反例：`When 呼叫 pipeline.run()` / `Then segments 不為空`

**層級選擇原則：**
- 能在 Unit / Integration 驗證的邏輯，不要標 E2E
- 只有真正需要 WebSocket 串流行為才用 E2E-ws
- Device 只用於必須有真實硬體的測試

**涵蓋範圍：**
- Happy path
- Edge cases（空音訊、零長度輸入、超長文字）
- Error cases（daemon 未啟動、LM Studio 無回應、模型載入失敗）

### 5. 每個 case 之間加 `---` 分隔線

### 6. 排序：依相依條件分組，減少 daemon 重啟

排序優先序：
1. **Unit**（無需 daemon）
2. **Integration**（TestClient，無需 daemon）
3. **E2E-ws / E2E-cli — 預設設定**（daemon 以預設 config 啟動）
4. **E2E-ws / E2E-cli — 需特殊 config**（按 config 分組）
5. **Device**（需 GPU / 麥克風）

### 7. 回報結果

```
新增了 T<N> ~ T<M>，共 <X> 個 test cases 到 tests/<file>.md
涵蓋：<功能列表>
```

## 注意事項

- 使用**繁體中文**撰寫 test case 說明
- 指令、路徑、JSON 保持英文
- 若需要環境資訊使用 placeholder（e.g. `<DAEMON_URL>`、`<LLM_BASE_URL>`）
- 不重複已存在的 test case（先掃描現有內容）
- 假音訊使用 `tests/fixtures/silence-1s.wav`（靜音）或 `tests/fixtures/speech-zh.wav`（中文語音）
