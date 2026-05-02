# Aureka TODO

## PyPI 發佈

- [ ] 建立 PyPI 帳號（https://pypi.org/account/register/）
- [ ] 在 PyPI 設定 Trusted Publisher：
      Project → Publishing → Add trusted publisher
      owner: fcwu / repo: aureka / workflow: publish.yml / env: pypi
- [ ] 建立 `.github/workflows/publish.yml`（tag `v*` 觸發，OIDC 推 PyPI）
- [ ] 推第一版：`git tag v0.1.0 && git push origin v0.1.0`

## 測試補強

- [ ] Windows 平台：injector xdotool 路徑不適用，確認 clipboard 注入正常
- [ ] macOS 平台：Cmd+V 注入測試
- [ ] pynput Linux Wayland 支援確認（目前只驗 X11）
- [ ] 補 `speech-zh-source.wav` 真實中文語音 fixture，提升 ASR 輸出驗證準確度
