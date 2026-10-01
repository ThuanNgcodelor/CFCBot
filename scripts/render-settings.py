#!/usr/bin/env python3
"""Render chatbot/server/settings.json from the single root .env file."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "chatbot" / "server" / "settings.example.json"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SystemExit(f"Missing env file: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    values.update({key: value for key, value in os.environ.items() if key in values})
    return values


def as_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def as_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render(values: dict[str, str]) -> dict[str, Any]:
    cfg = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    cfg["redis"].update(
        host=values.get("REDIS_HOST", "127.0.0.1"),
        port=as_int(values.get("REDIS_PORT", ""), 6379),
        password=values.get("REDIS_PASSWORD", ""),
        db=as_int(values.get("REDIS_DB", ""), 0),
    )
    cfg["ollama"].update(
        base_url=values.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        embed_model=values.get("OLLAMA_EMBED_MODEL", "bge-m3"),
        embed_dim=as_int(values.get("OLLAMA_EMBED_DIM", ""), 1024),
        chat_model=values.get("OLLAMA_CHAT_MODEL", "qwen2.5:7b-instruct"),
        fallback_embed_model=values.get("OLLAMA_FALLBACK_EMBED_MODEL", "qwen2.5:7b-instruct"),
    )
    cfg["server"].update(
        host=values.get("CFCBOT_API_HOST", "127.0.0.1"),
        port=as_int(values.get("CFCBOT_API_PORT", ""), 7777),
        reload=False,
    )
    cfg["n8n"].update(
        url=values.get("N8N_EDITOR_BASE_URL", "https://n8n.dinhduongcantho.io.vn"),
        api_key=values.get("N8N_API_KEY", ""),
    )
    cfg["llm_nlu"].update(
        mode=values.get("LLM_NLU_MODE", "off"),
        timeout_seconds=as_float(values.get("LLM_NLU_TIMEOUT", ""), 1.6),
        min_confidence=as_float(values.get("LLM_NLU_CONFIDENCE", ""), 0.72),
    )
    cfg["conversation"].update(
        orchestrator_mode=values.get("CHAT_CONVERSATION_MODE", "assist"),
        orchestrator_min_confidence=as_float(
            values.get("CHAT_CONVERSATION_MIN_CONFIDENCE", ""), 0.85
        ),
        orchestrator_history_limit=as_int(
            values.get("CHAT_CONVERSATION_HISTORY_LIMIT", ""), 6
        ),
        orchestrator_timeout_seconds=as_float(
            values.get("CHAT_CONVERSATION_TIMEOUT_SECONDS", ""), 6.0
        ),
    )
    cfg["ai_providers"].update(
        execution_mode=values.get("AI_EXECUTION_MODE", "local"),
        preferred_provider=values.get("AI_PREFERRED_PROVIDER", "groq"),
    )
    cfg["ai_providers"]["gemini"].update(
        api_key=values.get("GEMINI_API_KEY", ""),
        model=values.get("GEMINI_MODEL", "gemini-2.0-flash"),
    )
    cfg["ai_providers"]["openrouter"].update(
        api_key=values.get("OPENROUTER_API_KEY", ""),
        model=values.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free"),
    )
    cfg["ai_providers"]["groq"].update(
        api_key=values.get("GROQ_API_KEY", ""),
        model=values.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )
    cfg["telegram"].update(
        enabled=as_bool(values.get("TELEGRAM_ENABLED", ""), False),
        bot_token=values.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=values.get("TELEGRAM_CHAT_ID", ""),
    )
    cfg["shopee"].update(sheet_url=values.get("SHOPEE_SHEET_URL", ""))
    cfg["amis"].update(
        base_url=values.get("AMIS_BASE_URL", "https://crmconnect.misa.vn/api/v2"),
        client_id=values.get("AMIS_CLIENT_ID", "JavisCFCChatbot"),
    )
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--output", default=str(ROOT / "runtime" / "settings.json"))
    parser.add_argument("--redis-port", type=int)
    parser.add_argument("--redis-password")
    parser.add_argument("--server-port", type=int)
    args = parser.parse_args()

    values = parse_env(Path(args.env))
    if args.redis_port is not None:
        values["REDIS_PORT"] = str(args.redis_port)
    if args.redis_password is not None:
        values["REDIS_PASSWORD"] = args.redis_password
    if args.server_port is not None:
        values["CFCBOT_API_PORT"] = str(args.server_port)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(render(values), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(output)
    print(output)


if __name__ == "__main__":
    main()
