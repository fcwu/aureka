# Aureka — 系統設計文件

> 狀態：設計草稿
> 硬體：AMD AI MAX 395+，128GB 統一記憶體，WSL2
> 目標：音訊/影片 → 知識庫自動化，含 TTS 回讀功能

---

## 一、系統定位

將本機已有的 LM Studio 服務與新增的 ASR/TTS 模型串聯，形成一條從多媒體輸入到結構化知識庫輸出的完整流水線，並支援 TTS 將知識庫內容語音化。

---

## 二、硬體與現有資源

| 資源 | 狀態 |
|---|---|
| AMD AI MAX 395+ | 可用，支援 ROCm |
| 128GB 統一記憶體 | 可載入 70B 級模型 |
| LM Studio @ 127.0.0.1:1234 | 已運行，OpenAI-compatible API |
| LM Studio 已載模型 | Qwen3-30B-A3B（需確認 vision 支援） |

---

## 三、技術選型

| 層 | 工具 | 理由 |
|---|---|---|
| ASR | Qwen3-ASR 1.7B | 中文+方言最強，支援時間戳記，ROCm 可用 |
| VLM | LM Studio API | 已在跑，OpenAI-compatible，零配置 |
| LLM | LM Studio API | 同一 endpoint，整合摘要 |
| TTS | Qwen3-TTS 1.7B | 官方 AMD ROCm Docker profile，中英雙語 |

### 3.1 ASR：Qwen3-ASR

- **Repo**：https://github.com/QwenLM/Qwen3-ASR
- **模型**：`Qwen/Qwen3-ASR-1.7B`（輕量）或 `Qwen3-ASR-7B`（精準）
- **優勢**：30 語言 + 22 種中文方言，支援時間戳記，bfloat16 + ROCm

```bash
pip install -U qwen-asr
# GPU 加速版
pip install -U qwen-asr[vllm]
```

```python
from qwen_asr import Qwen3ASRModel
import torch

model = Qwen3ASRModel.from_pretrained(
    "Qwen/Qwen3-ASR-1.7B",
    dtype=torch.bfloat16,
    device_map="cuda:0"  # ROCm 透過 HIP 橋接
)
result = model.transcribe("audio.wav", return_time_stamps=True)
# {"text": "...", "segments": [{"start": 0.0, "end": 3.2, "text": "..."}]}
```

### 3.2 VLM + LLM：LM Studio API

```
Base URL: http://127.0.0.1:1234/v1
```

確認模型是否支援 vision：

```bash
curl http://127.0.0.1:1234/v1/models | jq '.data[].id'
```

若支援，`/v1/chat/completions` 接受 `image_url` 內容：

```python
import openai, base64, pathlib

client = openai.OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

def describe_frame(image_path: str) -> str:
    b64 = base64.b64encode(pathlib.Path(image_path).read_bytes()).decode()
    resp = client.chat.completions.create(
        model="auto",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": "請描述這張影片截圖的內容，包含畫面主題、文字、圖表等資訊。"}
            ]
        }],
        max_tokens=512
    )
    return resp.choices[0].message.content
```

備選（若模型不支援 vision）：

```bash
ollama pull qwen2.5-vl:7b
```

### 3.3 TTS：Qwen3-TTS

- **Repo**：https://github.com/QwenLM/Qwen3-TTS
- **模型**：`Qwen/Qwen3-TTS-1.7B`
- **AMD ROCm**：官方 Docker profile 含 `FLASH_ATTENTION_TRITON_AMD_ENABLE`
- **延遲**：streaming 97ms

```bash
git clone https://github.com/QwenLM/Qwen3-TTS.git
cd Qwen3-TTS && pip install -e .
```

```python
from qwen_tts import Qwen3TTS
import sounddevice as sd
import soundfile as sf

tts = Qwen3TTS.from_pretrained("Qwen/Qwen3-TTS-1.7B")

def speak(text: str, output_path: str = None):
    audio, sr = tts.synthesize(text)
    if output_path:
        sf.write(output_path, audio, sr)
    else:
        sd.play(audio, sr)
        sd.wait()
```

---

## 四、流水線架構

```
輸入：video.mp4 / audio.mp3 / audio.wav
          │
          ▼
    ┌─────────────┐
    │   ffmpeg    │  提取音訊軌 + 關鍵畫面（每 N 秒一張）
    └─────┬───────┘
          │
    ┌─────┴──────────────────────┐
    │                            │
    ▼                            ▼
┌──────────┐            ┌──────────────────┐
│Qwen3-ASR │            │ LM Studio VLM    │
│語音轉文字 │            │ 畫面描述（批次）  │
└────┬─────┘            └────────┬─────────┘
     │                           │
     └──────────┬────────────────┘
                ▼
        ┌───────────────┐
        │ LM Studio LLM │  整合摘要、重點萃取、知識結構化
        └───────┬───────┘
                │
                ▼
        output/YYYYMMDD-<slug>.md
                │
                ▼
          (丟入 mykb inbox → triage → ingest → wiki)

TTS 回讀路徑：
    query → LM Studio LLM → text → Qwen3-TTS → 播放/存 wav
```

---

## 五、輸出格式

每次處理輸出一個 markdown 檔案：

```markdown
---
source: video
original_file: lecture-2026-05-01.mp4
duration: 45:32
processed_at: 2026-05-01T14:30:00
---

# <自動萃取的標題>

## 摘要

<LLM 生成的 3-5 行摘要>

## 重點

- ...

## 逐段紀錄

| 時間 | 內容 |
|------|------|
| 00:00 | ... |

## 視覺內容

| 畫面時間點 | 描述 |
|----------|------|
| 00:30 | ... |

## 原始轉錄

<完整逐字稿，含時間戳記>
```

---

## 六、CLI 介面

```bash
# 處理影片或音訊
python -m aureka process video.mp4
python -m aureka process podcast.mp3 --frame-interval 60

# TTS 回讀
python -m aureka speak "今天的工作重點是什麼"
python -m aureka speak --file path/to/note.md
```

---

## 七、專案結構

```
aureka/
├── aureka/
│   ├── __main__.py       # CLI 入口
│   ├── pipeline.py       # 主流程編排
│   ├── asr.py            # Qwen3-ASR 封裝
│   ├── vlm.py            # LM Studio VLM 呼叫
│   ├── llm.py            # LM Studio LLM 呼叫
│   ├── tts.py            # Qwen3-TTS 封裝
│   ├── ffmpeg_utils.py   # 音訊/畫面提取
│   └── formatter.py      # Markdown 輸出格式化
├── docs/
│   └── design.md         # 本文件
├── requirements.txt
└── README.md
```

---

## 八、相依套件

```
qwen-asr>=0.1.0
openai>=1.0.0
sounddevice>=0.4.6
soundfile>=0.12.1
torch>=2.1.0
ffmpeg-python>=0.2.0
Pillow>=10.0.0
```

系統套件：

```bash
sudo apt install ffmpeg libsndfile1
```

---

## 九、待確認

- [ ] 確認 LM Studio 模型是否支援 vision（`/v1/models` + 測試 image payload）
- [ ] 若不支援：改用 Ollama `qwen2.5-vl:7b` 或在 LM Studio 另載 VLM
- [ ] Qwen3-ASR ROCm 測試（`device_map="cuda:0"` 在 ROCm HIP 下行為）
- [ ] Qwen3-TTS：pip 安裝 vs AMD 官方 Docker profile

---

## 十、參考

- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [AMD ROCm + Qwen3](https://rocm.blogs.amd.com/artificial-intelligence/qwen3-day0-amd/README.html)
- [VibeVoice](https://github.com/microsoft/VibeVoice)（備選 ASR+TTS）
- [Omnilingual ASR](https://github.com/facebookresearch/omnilingual-asr)（備選 1600 語言）
- [LM Studio](https://lmstudio.ai)
