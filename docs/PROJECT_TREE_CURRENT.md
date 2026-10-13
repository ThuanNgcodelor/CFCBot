# CFCBot — cây thư mục hiện hành

Cập nhật: 13/10/2026

Tài liệu này là bản đồ nhanh của repository đang vận hành. Không dùng nó làm
nguồn cấu hình; cấu hình thực tế nằm ở `.env` (không commit) và Docker/systemd.

## 1. Repository chính

```text
/home/kali/Works/CFC/CFCBot/
├── chatbot/                 Backend FastAPI, business logic, knowledge và tests
├── workflows/local-n8n/     Source workflow n8n dạng .workflow.ts
├── runtime/                 Runtime data/settings; dữ liệu thật bị ignore
├── config/                  Template cấu hình không chứa secret
├── compose.yaml              Production: API + Redis + n8n + Cloudflare profile
├── compose.test.yaml         Test cô lập: API :7778, Redis :6380
├── scripts/cfcbot            CLI chính: doctor/start/stop/restart/status/logs
├── infra/                    Template systemd, Cloudflare, Redis, n8n
├── plans/feature-upgrade/    Phase 00–09 hiện hành
├── docs/operations/          Runbook, setup, test report và policy
├── docs/source/              Tài liệu gốc DOCX/XLSX dùng làm knowledge/source
├── docs/legacy/              Tài liệu lịch sử, chỉ đọc để tra cứu/rollback
├── .env.example              Danh mục biến môi trường, không chứa secret
├── .env                      Cấu hình máy thật, không commit
├── Dockerfile                Image API CFCBot
└── README.md                 Hướng dẫn vận hành cấp repository
```

## 2. Cách chạy hiện hành

```text
CFCbot start
  ├─ cfcbot-api       FastAPI :7777
  ├─ cfcbot-redis     Redis :6379
  ├─ cfcbot-n8n       n8n :5678
  ├─ cloudflared      systemd tunnel/public ingress (nếu được bật)
  └─ ollama           systemd service, model runtime bên ngoài Compose
```

Lệnh kiểm tra:

```bash
cd /home/kali/Works/CFC/CFCBot
CFCbot status
curl -sS http://127.0.0.1:7777/health
curl -sS http://127.0.0.1:5678/healthz
```

## 3. Luồng tin nhắn hiện tại

```text
Meta/n8n hiện tại
  → POST /api/chat-pipeline (đường tương thích cũ, đồng bộ)
  → trả answer ngay
  → n8n gọi Meta Graph API

CFCBot queue đã triển khai nội bộ
  → POST /api/messaging/enqueue
  → Redis bundle/worker
  → response_outbox + LeadDraft + sales_outbox
  → Telegram sales đã test thật
```

Hai workflow Meta test đã được pull về và validate:

```text
workflows/local-n8n/[TEST] CFC Co Bay Chatbot.workflow.ts
workflows/local-n8n/[TEST] Zeo Chatbot.workflow.ts
```

Chưa chuyển Meta production sang queue vì còn thiếu adapter đọc
`response_outbox` và gửi trả lời về Meta Graph API.

## 4. Nguồn workflow n8n

| File | Vai trò |
|---|---|
| `cfc_cobay_chatbot.workflow.ts` | Workflow CFC production hiện hữu |
| `zeo_chatbot.workflow.ts` | Workflow ZeO production hiện hữu |
| `[TEST] CFC Co Bay Chatbot.workflow.ts` | Bản test đã pull từ n8n |
| `[TEST] Zeo Chatbot.workflow.ts` | Bản test đã pull từ n8n |
| `cfc_knowledge_sync_basic.workflow.ts` | Đồng bộ knowledge CFC |
| `zeo_knowledge_sync_basic.workflow.ts` | Đồng bộ knowledge ZeO |
| `amis_crm_full_warm.workflow.ts` | Warm/sync CRM định kỳ |
| `amis_crm_public_sync.workflow.ts` | Sync CRM public |
| `chatbot_operations_alert.workflow.ts` | Cảnh báo vận hành |

`n8nac list` hiện đã xác nhận: 8 workflow tracked, 0 remote-only, 0 conflict.

## 5. Phase hiện hành

| Phase | Trạng thái hiện tại |
|---|---|
| 00 | DONE — runtime path/baseline |
| 01 | Shadow/code/test hoàn tất; live n8n adapter còn pending |
| 02 | Queue/bundle/response outbox đã validate shadow |
| 03 | Telegram sales routing đã test; production handoff cần gate |
| 03.1 | Phone qualification đã triển khai |
| 04 | Handoff/SLA đã có code; flag đang tắt |
| 05 | Media security gate có; OCR đang tắt |
| 06 | Memory facts API có; governance/evaluation còn pending |
| 07–09 | Chưa triển khai; làm sau khi gateway ổn định |

Chi tiết nằm trong `plans/feature-upgrade/README.md` và các file `PHASE_*.md`.

## 6. Quy tắc tài liệu

- **Giữ nguyên:** `plans/feature-upgrade/` vì đây là phase pack hiện hành.
- **Giữ nguyên:** `docs/source/docx/` và `docs/source/xlsx/` vì đây là nguồn
  knowledge/tài liệu nghiệp vụ, không phải plan thừa.
- **Giữ nguyên:** `docs/operations/` vì là runbook và evidence vận hành.
- **Giữ nguyên:** `docs/legacy/` và `chatbot/plan/archive/` để rollback/tra cứu.
- **Đọc tham khảo:** các plan cũ trực tiếp trong `chatbot/plan/`; chưa được
  xóa vì một số file vẫn được README và tài liệu kỹ thuật tham chiếu.

Không xóa vĩnh viễn plan/DOCX nào chỉ dựa trên tên file. Nếu muốn rút gọn,
hãy chuyển plan cũ vào archive sau khi cập nhật liên kết, thay vì xóa mất lịch
sử thiết kế và căn cứ rollback.

## 7. Các file không phải nguồn vận hành

`.venv/`, `.pytest_cache/`, `__pycache__/`, runtime SQLite/WAL, n8n data và
Redis data là artifact/runtime; không đưa vào Git và không dùng làm source code.
