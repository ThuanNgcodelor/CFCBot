"""Environment-only configuration for the messaging domain."""

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class MessagingConfig:
    queue_enabled: bool
    queue_shadow: bool
    quiet_ms: int
    max_window_ms: int
    stream_key: str
    consumer_group: str
    consumer_name: str
    sqlite_path: Path
    control_key: str
    sales_enabled: bool
    sales_shadow: bool
    sales_routes_path: Path
    sales_destinations: dict[str, str]
    triage_destination: str
    telegram_bot_token: str
    handoff_enabled: bool
    sla_default_minutes: int
    media_enabled: bool
    ocr_enabled: bool
    media_max_bytes: int
    media_allowed_hosts: tuple[str, ...]
    memory_facts_enabled: bool
    lead_require_phone: bool

    @property
    def queue_mode(self) -> str:
        return "enabled" if self.queue_enabled else "shadow" if self.queue_shadow else "disabled"


def load_config() -> MessagingConfig:
    raw_destinations = os.getenv("TELEGRAM_SALES_DESTINATIONS_JSON", "{}").strip()
    destinations: dict[str, str] = {}
    try:
        raw = json.loads(raw_destinations)
        if isinstance(raw, dict):
            destinations = {str(k): str(v) for k, v in raw.items() if str(k) and str(v)}
    except json.JSONDecodeError:
        # Docker Compose dotenv interpolation can remove inner quotes from a
        # JSON-looking unquoted value: {triage:-100...,sales_can_tho:-100...}.
        # Accept that restricted, non-secret form while keeping JSON preferred.
        if raw_destinations.startswith("{") and raw_destinations.endswith("}"):
            for pair in raw_destinations[1:-1].split(","):
                if ":" not in pair:
                    continue
                key, value = pair.split(":", 1)
                key, value = key.strip().strip("\\\"'"), value.strip().strip("\\\"'")
                if key and value:
                    destinations[key] = value
    return MessagingConfig(
        queue_enabled=_bool("CHAT_QUEUE_ENABLED"),
        queue_shadow=_bool("CHAT_QUEUE_SHADOW"),
        quiet_ms=max(250, _int("CHAT_BUNDLE_QUIET_MS", 4000)),
        max_window_ms=max(1000, _int("CHAT_BUNDLE_MAX_WINDOW_MS", 12000)),
        stream_key=os.getenv("CHAT_INBOUND_STREAM", "cfcbot:inbound:v1"),
        consumer_group=os.getenv("CHAT_QUEUE_CONSUMER_GROUP", "cfcbot-messaging-v1"),
        consumer_name=os.getenv("CHAT_QUEUE_CONSUMER_NAME", f"worker-{os.getpid()}"),
        sqlite_path=Path(os.getenv("CHAT_SQLITE_PATH", "/app/runtime-data/cfcbot.sqlite3")),
        control_key=os.getenv("CHAT_CONVERSATION_CONTROL_KEY", ""),
        sales_enabled=_bool("SALES_HANDOFF_ENABLED"),
        sales_shadow=_bool("SALES_HANDOFF_SHADOW", True),
        sales_routes_path=Path(os.getenv("SALES_ROUTES_PATH", "/app/runtime-data/sales-routes.json")),
        sales_destinations=destinations,
        triage_destination=os.getenv("TELEGRAM_SALES_TRIAGE_DESTINATION", "triage"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        handoff_enabled=_bool("HANDOFF_ENABLED"),
        sla_default_minutes=max(1, _int("HANDOFF_SLA_DEFAULT_MINUTES", 30)),
        media_enabled=_bool("MEDIA_INGEST_ENABLED"),
        ocr_enabled=_bool("OCR_ENABLED"),
        media_max_bytes=max(1024, _int("MEDIA_MAX_BYTES", 10 * 1024 * 1024)),
        media_allowed_hosts=tuple(item.strip().lower() for item in os.getenv("MEDIA_ALLOWED_HOSTS", "").split(",") if item.strip()),
        memory_facts_enabled=_bool("MEMORY_FACTS_ENABLED"),
        lead_require_phone=_bool("LEAD_REQUIRE_PHONE", True),
    )
