# CFCBot

Standalone runtime and source-of-truth workspace for the ZeO/CFC customer
chatbots. Production is intentionally disabled after migration scaffolding.

Current state: the isolated API/Redis stack has passed unit, schema and smoke
tests, then was stopped. The legacy production runtime is still active.

## What is included

- Existing chatbot backend, dashboard, tests, plans and knowledge.
- Seven local n8n-as-code workflow sources.
- Original DOCX/XLSX under `docs/source`.
- Docker Compose for Redis, n8n, API and optional Cloudflare.
- One root `.env` as the secret/config inventory.
- One command: `CFCbot` (also available as lowercase `cfcbot`).

## First-time preparation

```bash
cd /home/kali/Works/David-nguyen/CFCBot
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

## Production — intentionally locked

`CFCbot start` refuses to run until these migration decisions are complete:

1. Fill and audit `.env`.
2. Configure n8n API access and compare local workflow source with live.
3. Reconnect/test Meta, Google Sheets, Telegram and AMIS credentials.
4. Approve whether to adopt the legacy Redis volume and n8n data directory.
5. Complete isolated and canary tests.
6. Set `CFCBOT_PRODUCTION_ENABLED=true`.

For a one-time adoption of current Redis/n8n runtime, also set
`CFCBOT_ADOPT_LEGACY_RUNTIME=true`. The start command then stops only the old
`zeo-n8n` and `zeo-redis` containers before starting CFCBot containers with
the configured persistent data. It does not delete volumes.

Cloudflare stays disabled unless `CLOUDFLARE_ENABLED=true` and a tunnel token
is provided.

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

See [the migration plan](PLAN_DI_CHUYEN_CHATBOT_TU_JAVIS_OS_2026-09-30.md)
before any production cutover.

Test evidence is recorded in
[`docs/operations/TEST_REPORT_2026-09-30.md`](docs/operations/TEST_REPORT_2026-09-30.md).
