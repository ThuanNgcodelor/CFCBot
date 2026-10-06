"""SQLite WAL repository for durable response/sales outboxes and LeadDraft."""

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import LeadDraftV1, ResponseOutboxEventV1, SalesOutboxEventV1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MessagingRepository:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS response_outbox (
                  event_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, brand TEXT NOT NULL,
                  sender_id TEXT NOT NULL, bundle_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL UNIQUE, payload_json TEXT NOT NULL,
                  status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                  external_message_id TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lead_drafts (
                  lead_id TEXT PRIMARY KEY, conversation_key TEXT NOT NULL UNIQUE,
                  version INTEGER NOT NULL, trace_id TEXT NOT NULL, brand TEXT NOT NULL,
                  sender_id TEXT NOT NULL, payload_json TEXT NOT NULL, state TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sales_outbox (
                  event_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
                  lead_version INTEGER NOT NULL, destination_key TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL UNIQUE, payload_json TEXT NOT NULL,
                  status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                  external_message_id TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_response_status ON response_outbox(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_sales_status ON sales_outbox(status, created_at);
            """)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _insert_response_sync(self, event: ResponseOutboxEventV1) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("""INSERT OR IGNORE INTO response_outbox
                (event_id, trace_id, brand, sender_id, bundle_id, idempotency_key,
                 payload_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.trace_id, event.brand, event.sender_id, event.bundle_id,
                 event.idempotency_key, json.dumps(event.payload, ensure_ascii=False), event.status,
                 event.created_at.isoformat(), _now()))
            return cursor.rowcount == 1

    async def insert_response(self, event: ResponseOutboxEventV1) -> bool:
        return await asyncio.to_thread(self._insert_response_sync, event)

    def _upsert_lead_sync(self, lead: LeadDraftV1) -> LeadDraftV1:
        with self._lock, self._connect() as conn:
            current = conn.execute("SELECT * FROM lead_drafts WHERE conversation_key = ?", (lead.conversation_key,)).fetchone()
            now = _now()
            if current:
                old = json.loads(current["payload_json"])
                merged = lead.model_dump(mode="json")
                for key in ("fb_name", "phone", "area", "need", "intent"):
                    if not merged.get(key):
                        merged[key] = old.get(key, "")
                merged["lead_id"] = current["lead_id"]
                merged["version"] = int(current["version"]) + 1
                lead = LeadDraftV1.model_validate(merged)
                conn.execute("""UPDATE lead_drafts SET version=?, trace_id=?, payload_json=?, state=?, updated_at=?
                    WHERE lead_id=?""", (lead.version, lead.trace_id,
                    json.dumps(lead.model_dump(mode="json"), ensure_ascii=False), lead.state, now, lead.lead_id))
            else:
                conn.execute("""INSERT INTO lead_drafts
                    (lead_id, conversation_key, version, trace_id, brand, sender_id,
                     payload_json, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lead.lead_id, lead.conversation_key, lead.version, lead.trace_id, lead.brand,
                     lead.sender_id, json.dumps(lead.model_dump(mode="json"), ensure_ascii=False), lead.state, now, now))
            return lead

    async def upsert_lead(self, lead: LeadDraftV1) -> LeadDraftV1:
        return await asyncio.to_thread(self._upsert_lead_sync, lead)

    def _insert_sales_sync(self, event: SalesOutboxEventV1) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("""INSERT OR IGNORE INTO sales_outbox
                (event_id, trace_id, lead_id, lead_version, destination_key, idempotency_key,
                 payload_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.trace_id, event.lead_id, event.lead_version, event.destination_key,
                 event.idempotency_key, json.dumps(event.payload, ensure_ascii=False), event.status,
                 event.created_at.isoformat(), _now()))
            return cursor.rowcount == 1

    async def insert_sales(self, event: SalesOutboxEventV1) -> bool:
        return await asyncio.to_thread(self._insert_sales_sync, event)

    def _list_sync(self, table: str, limit: int) -> list[dict[str, Any]]:
        if table not in {"response_outbox", "lead_drafts", "sales_outbox"}:
            raise ValueError("unsupported table")
        with self._lock, self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                if "payload_json" in item:
                    item["payload"] = json.loads(item.pop("payload_json"))
                result.append(item)
            return result

    async def list_rows(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_sync, table, limit)

    def _counts_sync(self) -> dict[str, dict[str, int]]:
        result = {}
        with self._lock, self._connect() as conn:
            for table, field in (("response_outbox", "status"), ("lead_drafts", "state"), ("sales_outbox", "status")):
                rows = conn.execute(f"SELECT {field} AS status, COUNT(*) AS count FROM {table} GROUP BY {field}").fetchall()
                result[table] = {str(row["status"]): int(row["count"]) for row in rows}
        return result

    async def counts(self) -> dict[str, dict[str, int]]:
        return await asyncio.to_thread(self._counts_sync)

    def _pending_sales_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM sales_outbox WHERE status IN ('pending','retry') ORDER BY created_at LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]

    async def pending_sales(self, limit: int = 20) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._pending_sales_sync, limit)

    def _mark_sync(self, table: str, event_id: str, status: str, external_id: str, error: str) -> None:
        if table not in {"response_outbox", "sales_outbox"}:
            raise ValueError("unsupported table")
        with self._lock, self._connect() as conn:
            conn.execute(f"""UPDATE {table} SET status=?, attempts=attempts+1,
                external_message_id=?, last_error=?, updated_at=? WHERE event_id=?""",
                (status, external_id, error[:1000], _now(), event_id))

    async def mark_delivery(self, table: str, event_id: str, status: str, external_id: str = "", error: str = "") -> None:
        await asyncio.to_thread(self._mark_sync, table, event_id, status, external_id, error)
