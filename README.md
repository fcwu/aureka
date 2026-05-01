# Aureka

> aural + eureka — 聽到，即發現知識

本機多媒體 AI 處理流水線：音訊 / 影片 → 結構化知識庫。

## 功能

- **ASR**：語音轉文字，支援中文方言（Qwen3-ASR）
- **VLM**：影片關鍵畫面分析（LM Studio API）
- **LLM**：整合摘要、重點萃取（LM Studio API）
- **TTS**：知識回讀語音合成（Qwen3-TTS，AMD ROCm 支援）

## 硬體需求

- AMD AI MAX 395+ 或同等 GPU（ROCm 6.x）
- 128GB RAM（可載入 70B+ 模型）
- LM Studio 執行於 `127.0.0.1:1234`

## 快速開始

```bash
# 安裝相依
pip install -r requirements.txt
sudo apt install ffmpeg libsndfile1

# 處理影片
python -m aureka process video.mp4

# 處理音訊
python -m aureka process podcast.mp3

# TTS 回讀
python -m aureka speak "今天的工作重點是什麼"
```

## 文件

- [設計文件](docs/design.md)

## 專案結構

```
aureka/
├── aureka/
│   ├── __main__.py       # CLI 入口
│   ├── pipeline.py       # 主流程
│   ├── asr.py            # Qwen3-ASR 封裝
│   ├── vlm.py            # LM Studio VLM
│   ├── llm.py            # LM Studio LLM
│   ├── tts.py            # Qwen3-TTS 封裝
│   ├── ffmpeg_utils.py   # 音訊/畫面提取
│   └── formatter.py      # Markdown 輸出格式化
├── docs/
│   └── design.md
├── requirements.txt
└── README.md
```

## License

MIT
