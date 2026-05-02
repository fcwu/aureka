## 1. Config 與 Code 變更

- [x] 1.1 在 `aureka/config.py` 新增 `AsrConfig` dataclass（`model: str = "medium"`）；加入 `Config.asr` field 與 `load_config` 的 `[asr]` 處理
- [x] 1.2 在 `aureka/asr.py` 移除 `_TheWhisperBackend` class
- [x] 1.3 在 `aureka/asr.py` 將 `_FasterWhisperBackend.__init__` 從 hardcoded `large-v3` 改為從 `cfg.asr.model` 讀
- [x] 1.4 在 `aureka/asr.py` 簡化 `load_asr`：移除 backend 選擇邏輯，永遠 instantiate `_FasterWhisperBackend`
- [x] 1.5 在 `aureka/device.py` 移除 `resolve_asr_backend` 函數
- [x] 1.6 在 `aureka/models.py` 把 `MODEL_REGISTRY` dict 改成 `model_registry()` function，依 `cfg.asr.model` 動態組 faster-whisper repo_id；移除 `thewhisper` 與 `_thewhisper_available`；簡化 `_select_models`（不再依裝置決定）
- [x] 1.7 在 `aureka/__main__.py` 的 `cmd_download` 與 `aureka/benchmark.py` 中所有 `MODEL_REGISTRY` 與 `_select_models` 引用改用新 API
- [x] 1.8 在 `aureka/benchmark.py` `_collect_aureka_env` 把 `asr_backend` 欄位改為 `asr_model`（值為 `cfg.asr.model`）
- [x] 1.9 在 `pyproject.toml` 移除 `asr-thewhisper` extra
- [x] 1.10 在 `config.example.toml` 新增 `[asr]` 段，註解列出可選 model

## 2. 測試調整

- [x] 2.1 在 `tests/test_device.py` 移除全部 `resolve_asr_backend` 相關 test（4 個），只保留 `resolve_device` test
- [x] 2.2 在 `tests/test_models_unit.py` 移除 `_thewhisper_available` 相關 test 與 cuda+thewhisper combination test；新增 `model_registry()` 隨 config 變動 test
- [x] 2.3 在 `tests/test_models_unit.py` 把 `MODEL_REGISTRY` 直接讀取的 test 改為呼叫 `model_registry()`
- [x] 2.4 在 `tests/` 新增 `test_config.py`（如果尚未存在）或在現有 config-相關 test 內驗證 `[asr]` 段預設值與 TOML 載入
- [x] 2.5 跑 `pytest tests/ -v -m "unit or integration"` 全綠

## 3. 文件

- [x] 3.1 在 `README.md` 移除任何 TheWhisper / thestage-speechkit 相關說明（若有）；新增「ASR 模型可調」段落，說明 `[asr] model = "..."` 與如何選 size
- [x] 3.2 在 `CLAUDE.md` 同步更新（如有提及）
- [x] 3.3 加入 release-note 風格段落在 README 提醒「default ASR model 從 `large-v3` 改為 `medium`，舊 cache 需手動清理」

## 4. Spec 同步

- [x] 4.1 確認 `pytest` 全綠後，archive 此 change：`openspec archive simplify-asr-backend`
