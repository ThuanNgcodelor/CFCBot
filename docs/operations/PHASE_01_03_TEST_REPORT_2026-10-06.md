# Phase 01–03 test report — 2026-10-06

## Automated regression

- `python -m unittest discover -s chatbot/server/tests -p 'test_*.py' -q`
- Kết quả: **258 tests passed**, 0 failure.
- Test mới: contract validation, SQLite WAL idempotency, lead merge không cần phone,
  route khu vực/triage và 4-message ordered bundle.

## Isolated integration (7778/6380)

- Mode: queue `shadow`, Sales `shadow`, Telegram/Meta side effect blocked.
- 4 inbound events cùng sender trong quiet window: accepted = 4.
- Gửi lại `idempotency_key` cuối: `duplicate=true`.
- Kết quả: bundles = 1, response outbox shadow = 1, LeadDraft = 1,
  sales outbox shadow = 1, pipeline errors = 0, sales sent = 0.
- Compatibility endpoint `/api/chat-pipeline`: HTTP 200, `ok=true`.
- Test stack đã dừng sau kiểm thử.

## Production deployment

- Chỉ recreate `cfcbot-api`; Redis và n8n giữ nguyên.
- Queue: `disabled`; Sales: `shadow`; accepted/bundles/sales sent = 0.
- API/n8n local và public health: pass.
- Compatibility chat synthetic: HTTP 200, `ok=true`, intent `greeting`.
- Trace response headers hiện diện; startup/runtime log không có error.

## Gates còn mở

- n8n-as-code chưa có workspace/API key nên chưa pull/live drift/adapter.
- Chưa có Telegram bot token, group chat ID, mapping owner/PII/SLA được duyệt.
- Vì hai gate trên, không bật queue production hoặc Telegram delivery thật.
