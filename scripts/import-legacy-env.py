#!/usr/bin/env python3
"""Import reusable legacy runtime settings into CFCBot .env without printing values."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEGACY_ROOT = Path("/home/kali/Works/David-nguyen/javis-os")


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        try:
            parsed = shlex.split(f"x={raw_value.strip()}", comments=False, posix=True)
            value = parsed[0].split("=", 1)[1] if parsed else ""
        except (ValueError, IndexError):
            value = raw_value.strip().strip("\"'")
        values[key] = value
    return values


def quote_env(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@%+,=-]*", value):
        return value
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def configured(value: str | None) -> bool:
    return bool(str(value or "").strip()) and not str(value).startswith("CHANGE_ME")


def legacy_redis_password(legacy_root: Path, legacy_settings: dict) -> str:
    try:
        inspect = json.loads(
            subprocess.check_output(["docker", "inspect", "zeo-redis"], text=True)
        )[0]
        container_env = {}
        for item in inspect.get("Config", {}).get("Env", []):
            if "=" in item:
                key, value = item.split("=", 1)
                container_env[key] = value
        args = shlex.split(container_env.get("REDIS_ARGS", ""))
        if "--requirepass" in args:
            return args[args.index("--requirepass") + 1]
    except Exception:
        pass

    infra_env = parse_env(legacy_root / "infra" / "redis" / ".env")
    return str(
        infra_env.get("REDIS_PASSWORD")
        or legacy_settings.get("redis", {}).get("password", "")
        or ""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=str(ROOT / ".env"))
    parser.add_argument("--legacy-root", default=str(DEFAULT_LEGACY_ROOT))
    args = parser.parse_args()

    target = Path(args.target).resolve()
    legacy_root = Path(args.legacy_root).resolve()
    if not target.exists():
        raise SystemExit(f"Missing target env: {target}")

    target_values = parse_env(target)
    legacy_env = parse_env(legacy_root / ".env")
    legacy_env.update(parse_env(legacy_root / "chatbot" / "server" / ".env"))

    settings_path = legacy_root / "chatbot" / "server" / "settings.json"
    legacy_settings = (
        json.loads(settings_path.read_text(encoding="utf-8"))
        if settings_path.exists()
        else {}
    )

    updates: dict[str, str] = {}
    for key in target_values:
        if key in legacy_env and configured(legacy_env[key]):
            updates[key] = legacy_env[key]

    settings_map = {
        "N8N_API_KEY": legacy_settings.get("n8n", {}).get("api_key", ""),
        "GEMINI_API_KEY": legacy_settings.get("ai_providers", {}).get("gemini", {}).get("api_key", ""),
        "OPENROUTER_API_KEY": legacy_settings.get("ai_providers", {}).get("openrouter", {}).get("api_key", ""),
        "GROQ_API_KEY": legacy_settings.get("ai_providers", {}).get("groq", {}).get("api_key", ""),
        "TELEGRAM_BOT_TOKEN": legacy_settings.get("telegram", {}).get("bot_token", ""),
        "TELEGRAM_CHAT_ID": legacy_settings.get("telegram", {}).get("chat_id", ""),
        "SHOPEE_SHEET_URL": legacy_settings.get("shopee", {}).get("sheet_url", ""),
    }
    for key, value in settings_map.items():
        if configured(str(value or "")):
            updates[key] = str(value)

    redis_password = legacy_redis_password(legacy_root, legacy_settings)
    if not configured(redis_password):
        raise SystemExit("Legacy Redis password could not be resolved; refusing cutover.")
    updates["REDIS_PASSWORD"] = redis_password

    updates.update(
        {
            "CFCBOT_PRODUCTION_ENABLED": "true",
            "CFCBOT_ADOPT_LEGACY_RUNTIME": "true",
            "CFCBOT_API_PORT": "7777",
            "CFCBOT_API_BASE_URL": "http://127.0.0.1:7777",
            "CLOUDFLARE_MODE": "systemd",
            "CLOUDFLARE_ENABLED": "false",
        }
    )
    for key in ("CHAT_CONVERSATION_CONTROL_KEY", "CHAT_CANARY_SALT"):
        if not configured(target_values.get(key)):
            updates[key] = secrets.token_urlsafe(32)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f".env.pre-cutover-{stamp}")
    shutil.copy2(target, backup)
    os.chmod(backup, 0o600)

    lines = target.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in updates:
                output.append(f"{key}={quote_env(updates[key])}")
                seen.add(key)
                continue
        output.append(line)
    for key in sorted(set(updates) - seen):
        output.append(f"{key}={quote_env(updates[key])}")

    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(target)

    print(f"Backup: {backup}")
    print("Imported keys (values hidden):")
    for key in sorted(updates):
        print(f"  {key}")


if __name__ == "__main__":
    main()

