# CFCBot isolated migration test report — 2026-09-30

Production cutover was not performed. The legacy Javis, n8n and Redis runtime
remained online during all checks.

## Results

- Shell and Python configuration syntax: passed.
- Production and test Docker Compose rendering: passed.
- `CFCbot doctor`: passed.
- n8n-as-code schema validation: 7/7 workflows passed.
- Python unit suite: 252/252 tests passed.
- Docker image build: passed.
- Docker build context excluded `.env`; `/app/.env` was absent from the image.
- Runtime manifest: 39 tracked files, zero missing.
- Isolated Redis: healthy on `127.0.0.1:6380`.
- Isolated API: healthy on `127.0.0.1:7778`.
- Ollama connection: healthy; `bge-m3` available.
- Chat smoke test: HTTP 200, `cfc_purchase_request`.
- Duplicate-message smoke test: idempotency cache hit.
- Test teardown: passed; ports 7778 and 6380 closed afterward.
- Production safety lock: passed; `CFCbot start` refused to start.
- Legacy runtime after test: n8n 5678 and Javis 7777 remained healthy.

## Not tested yet

- Live Meta webhooks.
- Live Cloudflare route to the production CFCBot port 7777.
- Production n8n credential decryption and reconnect checks.
- Google Sheets, Telegram and AMIS live credentials.
- Adoption of the existing n8n data directory and Redis volume.

Those checks belong to the separately approved cutover/canary phase.
