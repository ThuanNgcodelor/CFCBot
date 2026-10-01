#!/usr/bin/env python3
"""Safe CLI for AMIS configuration status, audit, and public snapshot sync."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.client import AmisError  # noqa: E402
from domains.amis.config import load_amis_config  # noqa: E402
from domains.amis.service import AmisSyncSafetyError, sync_public_snapshots  # noqa: E402


async def run(command: str) -> int:
    config = load_amis_config()
    if command == "status":
        print(json.dumps(config.safe_status(), ensure_ascii=False, indent=2))
        return 0 if config.credentials_configured else 2

    try:
        result = await sync_public_snapshots(dry_run=command == "audit", config=config)
    except (AmisError, AmisSyncSafetyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 3


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AMIS CRM public data sync")
    parser.add_argument("command", choices=("status", "audit", "sync"))
    args = parser.parse_args()
    return asyncio.run(run(args.command))


if __name__ == "__main__":
    raise SystemExit(main())
