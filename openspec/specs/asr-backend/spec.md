## ADDED Requirements

### Requirement: 統一 ASR 介面
系統 SHALL 提供統一的 `transcribe(audio: np.ndarray, sample_rate: int) -> list[Segment]` 介面，隱藏底層後端差異。

#### Scenario: 呼叫統一介面
- **WHEN** 上層程式碼呼叫 `asr.transcribe(audio, 16000)`
- **THEN** 回傳 `[Segment(start, end, text), ...]` 清單，不論底層使用哪個後端

### Requirement: 平台自動裝置偵測
系統 SHALL 透過 `resolve_device()` 自動偵測最佳計算裝置：CUDA（NVIDIA/AMD ROCm HIP 橋接）> MPS（Apple Silicon）> CPU。

#### Scenario: NVIDIA CUDA 環境
- **WHEN** `torch.cuda.is_available()` 回傳 True
- **THEN** `resolve_device()` 回傳 `"cuda"`

#### Scenario: Apple Silicon 環境
- **WHEN** `torch.backends.mps.is_available()` 回傳 True 且 CUDA 不可用
- **THEN** `resolve_device()` 回傳 `"mps"`

#### Scenario: CPU fallback
- **WHEN** CUDA 和 MPS 均不可用
- **THEN** `resolve_device()` 回傳 `"cpu"`

### Requirement: ASR 後端自動選擇
系統 SHALL 在 `cuda` 或 `mps` 裝置上優先嘗試 TheWhisper，匯入失敗則 fallback 到 faster-whisper；AMD ROCm 和 CPU 直接使用 faster-whisper。

#### Scenario: TheWhisper 可用
- **WHEN** 裝置為 `cuda` 或 `mps` 且 `thestage_speechkit` 可匯入
- **THEN** `resolve_asr_backend()` 回傳 `"thewhisper"`

#### Scenario: TheWhisper 不可用，fallback
- **WHEN** 裝置為 `cuda` 或 `mps` 但 `thestage_speechkit` 匯入失敗
- **THEN** `resolve_asr_backend()` 回傳 `"faster-whisper"`

#### Scenario: CPU 裝置
- **WHEN** 裝置為 `cpu`
- **THEN** `resolve_asr_backend()` 直接回傳 `"faster-whisper"`，不嘗試 TheWhisper

### Requirement: TheWhisper 後端
系統 SHALL 使用 `thestage-ai/thewhisper-large-v3-turbo` 模型（本地 HuggingFace 快取），在 NVIDIA/Apple Silicon 提供低延遲 ASR。

#### Scenario: 首次執行自動下載模型
- **WHEN** 本地不存在 HuggingFace 快取
- **THEN** 系統自動從 HuggingFace 下載模型（約 3GB），期間顯示進度

#### Scenario: CUDA 裝置推論
- **WHEN** 後端為 `thewhisper` 且裝置為 `cuda`
- **THEN** 使用 GPU 推論，TTFT 目標 ≤ 12ms/segment

### Requirement: faster-whisper 後端
系統 SHALL 使用 faster-whisper `large-v3` 模型（精準）或 `medium`（速度平衡），支援 AMD ROCm 和 CPU。

#### Scenario: CPU 推論精度設定
- **WHEN** 裝置為 `cpu`
- **THEN** 使用 `int8` compute type 以提升速度

#### Scenario: CUDA/ROCm 推論精度設定
- **WHEN** 裝置為 `cuda`
- **THEN** 使用 `float16` compute type

### Requirement: 支援音訊格式
系統 SHALL 接受 `float32` numpy array（值域 -1.0 至 1.0，16kHz mono）作為 ASR 輸入標準格式。

#### Scenario: int16 PCM 轉換
- **WHEN** 輸入為 int16 PCM（來自麥克風錄音）
- **THEN** 系統自動轉換：`audio.astype(np.float32) / 32768.0`
