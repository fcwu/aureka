## 1. Model Registry 與下載核心

- [x] 1.1 在 `aureka/models.py` 新增模組，定義 `MODEL_REGISTRY: dict[str, str]`，包含 `kokoro`、`faster-whisper`、`thewhisper` 三個 entry
- [x] 1.2 實作 `_select_models(device: str) -> list[str]`：依 `resolve_device()` 與 `thestage_speechkit` 可匯入性決定要下載哪些 model key
- [x] 1.3 實作 `download_all(device: str = "auto") -> list[Path]`：對選定 model key 逐一呼叫 `huggingface_hub.snapshot_download(repo_id)`，回傳本地路徑清單
- [x] 1.4 失敗 fail-fast：捕捉 `huggingface_hub` 的權限例外（GatedRepoError / RepositoryNotFoundError）轉成附帶 `huggingface-cli login` 提示的訊息再 raise

## 2. CLI 整合

- [x] 2.1 在 `aureka/__main__.py` 註冊 `download` subparser（無額外旗標，使用全域 `--device`）
- [x] 2.2 實作 `cmd_download(args)`：呼叫 `models.download_all(args.device)`、捕捉例外印出錯誤後 `sys.exit(1)`
- [x] 2.3 將 `cmd_download` 加入 dispatch dict
- [x] 2.4 下載成功時依序印出每個 model 的「邏輯名稱、repo ID、本地 snapshot 路徑」摘要表

## 3. 測試

- [x] 3.1 在 `tests/` 新增 `test_models_unit.py`：mock `snapshot_download`，驗證 `_select_models` 在不同 (device, thestage_speechkit 可匯入) 組合下回傳預期 key 集合
- [x] 3.2 驗證 `download_all` 在任一 `snapshot_download` 拋例外時不繼續下載剩餘 repo（fail-fast）
- [x] 3.3 驗證 `download_all` 回傳的路徑清單長度與 `_select_models` 結果一致
- [x] 3.4 新增 integration 測試 `test_download_command_integration.py`：以 subprocess 執行 `python -m aureka --device cpu download`，斷言 exit code 為 0、stdout 含 Kokoro 與 faster-whisper repo ID（以 mock LM/HF 環境跳過真實下載）
- [x] 3.5 跑 `pytest tests/ -v -m "unit or integration"` 全綠

## 4. 文件

- [x] 4.1 在 `README.md` 安裝段加入「首次使用建議先執行 `aureka download` 預載模型」段落
- [x] 4.2 在 `CLAUDE.md` 第 1 節（安裝與設定）加入相同提示
- [x] 4.3 `aureka --help` 與 `aureka download --help` 訊息檢查清楚易懂

## 5. Spec 同步

- [x] 5.1 確認 `pytest` 與 `aureka download --help` 都通過後，準備 archive 此 change：執行 `openspec archive add-model-download-command` 將 delta 合入 `openspec/specs/`
