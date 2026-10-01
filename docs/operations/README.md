# Operations

## Ports

| Service | Production | Isolated test |
|---|---:|---:|
| CFCBot API | 7777 | 7778 |
| Redis | 6379 | 6380 |
| n8n | 5678 | not started |
| Ollama | 11434 (host service) | 11434 (host service) |

## Configuration flow

```text
.env (ignored)
  -> scripts/render-settings.py
    -> runtime/settings.json (ignored)
      -> mounted into /app/chatbot/server/settings.json
```

The old backend still reads `settings.json`; the renderer preserves that
contract while keeping the root `.env` as the only hand-maintained config.

## Data ownership

- Redis production data: named volume selected by `REDIS_VOLUME_NAME`.
- n8n production data: bind path selected by `N8N_DATA_DIR`.
- Test Redis data: `cfcbot-test-redis-data`.
- Secrets and rendered settings: never committed.
- n8n backup/SQLite: kept outside this repository.
