# Phase 00 baseline — 2026-10-06

- Repo runtime: `/home/kali/Works/CFC/CFCBot`
- Command: `/home/kali/.local/bin/CFCbot` trỏ về repo mới.
- API local/public: healthy (`127.0.0.1:7777`, `api.dinhduongcantho.io.vn`).
- n8n local/public: healthy (`127.0.0.1:5678`, `n8n.dinhduongcantho.io.vn`).
- Redis: persistent legacy volume được adopt dạng external; container healthy.
- Ollama và Cloudflare: systemd active; Javis legacy inactive/disabled.
- Baseline unit suite: 252 tests passed.
- Test stack: API 7778, Redis 6380; chat smoke trả `cfc_purchase_request`.
- Production reply path vẫn là `/api/chat-pipeline`; queue mới mặc định tắt.

## Constraint còn mở

`n8nac env status --json` trả `configured=false`. Vì chưa có workspace/API key,
không workflow live nào được pull, sửa hoặc push trong Phase 00–03.
