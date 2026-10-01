# CFCBot agent instructions

This repository owns the ZeO/CFC customer chatbot, its n8n workflow source,
runtime templates, documentation and tests.

## Safety

- Production is locked unless `CFCBOT_PRODUCTION_ENABLED=true` in the ignored root `.env`.
- Never commit `.env`, rendered `runtime/settings*.json`, n8n data, Redis data,
  AMIS caches, Shopee auth, tokens, cookies or customer PII.
- Do not start Cloudflare in tests.
- Use port 7778 and Redis port 6380 for isolated tests.
- Do not edit or publish live n8n workflows without first configuring n8n-as-code,
  listing the environment, and pulling the workflow.
- Treat a push to an already published n8n 2.x workflow as a production deploy.
- Keep Javis compatibility active until CFC and ZeO both pass canary and rollback gates.

## Source layout

- `chatbot/server`: FastAPI runtime and business logic.
- `workflows/local-n8n`: n8n-as-code workflow source.
- `infra`: runtime/system templates.
- `scripts/cfcbot`: lifecycle CLI.
- `.env.example`: central configuration inventory without secrets.
- `runtime`: rendered ignored configuration.

## Required checks

```bash
CFCbot doctor
CFCbot test-start
curl http://127.0.0.1:7778/health
CFCbot test-stop
```

Never remove the source chatbot from Javis OS during migration. Retire it only
after an explicitly approved 7–14 day production observation window.

