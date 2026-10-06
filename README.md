# CFCBot

Standalone runtime and source-of-truth workspace for the ZeO/CFC customer
chatbots.

Current state: CFCBot is the active production runtime. The API, Redis and n8n
containers run under the CFCBot Compose project; the legacy Javis service is
disabled but its rollback artifacts remain during the observation window.

## What is included

- Existing chatbot backend, dashboard, tests, plans and knowledge.
- Seven local n8n-as-code workflow sources.
- Original DOCX/XLSX under `docs/source`.
- Docker Compose for Redis, n8n, API and optional Cloudflare.
- One root `.env` as the secret/config inventory.
- One command: `CFCbot` (also available as lowercase `cfcbot`).

## First-time preparation

```bash
cd /home/kali/Works/CFC/CFCBot
cp .env.example .env
chmod 600 .env
./scripts/bootstrap-command.sh
CFCbot doctor
```

Do not put real secrets in `.env.example`. Put them only in the ignored `.env`.

## Safe isolated test

```bash
CFCbot test-start
curl http://127.0.0.1:7778/health
CFCbot test-stop
```

This starts only:

- `cfcbot-test-redis` on `127.0.0.1:6380`;
- `cfcbot-test-api` on `127.0.0.1:7778`.

It does not start n8n or Cloudflare and does not modify the live workflows.

The test stack enables the new messaging queue in `shadow` mode with a short
bundle window. Production keeps `CHAT_QUEUE_ENABLED=false` and
`SALES_HANDOFF_ENABLED=false` until n8n live source and Telegram routes are approved.

## Messaging queue and Telegram Sales

- Ingress: `POST /api/messaging/enqueue`
- Observe-only status: `GET /api/messaging/status`
- Protected outbox/lead views: `/api/messaging/operations/*`
- Durable state: `runtime/data/cfcbot.sqlite3` (SQLite WAL, ignored by Git)
- Region mapping: `runtime/data/sales-routes.json` (copy from `config/sales_routes.example.json`)

Telegram group setup and safe pilot steps are in
[`docs/operations/TELEGRAM_SALES_SETUP.md`](docs/operations/TELEGRAM_SALES_SETUP.md).

## Production lifecycle

Production has completed the one-time adoption of the existing Redis volume
and n8n data directory. `CFCbot start` now starts the CFCBot API, Redis and n8n
stack; the existing systemd Cloudflare tunnel remains the public ingress.

Do not delete the stopped legacy containers, source or volumes until the
7–14 day observation and rollback window has passed.

## Commands

```text
CFCbot doctor
CFCbot test-start
CFCbot test-stop
CFCbot start
CFCbot stop
CFCbot restart
CFCbot status
CFCbot logs
```

Planning documents:

- [Phase execution pack](plans/feature-upgrade/README.md)
  — thứ tự triển khai và file riêng cho Phase 00–09, gồm dependency, test, gate và rollback.
- [Feature improvement roadmap](PLAN_NANG_CAP_TINH_NANG_CFCBOT_2026-10-01.md)
  — product priorities, user journeys, phases, KPI and acceptance gates.
- [Current technical direction](chatbot/plan/PLAN_DINH_HUONG_CAP_NHAT_CFCBOT_QUEUE_OCR_TELEGRAM_2026-10-01.md)
  — queue, OCR, Telegram routing, rollout and rollback architecture.
- [Migration plan](PLAN_DI_CHUYEN_CHATBOT_TU_JAVIS_OS_2026-09-30.md)
  — historical cutover plan from Javis OS to CFCBot.

Test evidence is recorded in
[`docs/operations/TEST_REPORT_2026-09-30.md`](docs/operations/TEST_REPORT_2026-09-30.md).
Phase 0–3 evidence is recorded under [`docs/operations`](docs/operations/).
