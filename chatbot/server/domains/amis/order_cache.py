"""Private, freshness-bounded order lookup cache for the CFC chat pipeline.

The AMIS warm job may contain raw customer and sale-order records.  Public
Redis snapshots must never expose those records, so this module publishes only
the allowlisted server-side matching data: order code variants, HMAC'd phones,
approved shop display name, status, delivery status and approved order dates. A chat lookup must provide
both an exact order code and the phone that belongs to that order.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Any

from .config import AmisConfig


def _phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits if len(digits) >= 9 else ""


def _phone_digest(phone: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), phone.encode("utf-8"), hashlib.sha256).hexdigest()


def _account_keys(record: dict[str, Any]) -> set[str]:
    values = (
        record.get("account_name"),
        record.get("account_number"),
        record.get("account_code"),
        record.get("customer_id"),
        record.get("account_id"),
        record.get("id"),
    )
    return {str(value).strip().casefold() for value in values if str(value or "").strip()}


def _order_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _order_keys(order: dict[str, Any]) -> set[str]:
    values = (
        order.get("sale_order_no"),
        order.get("order_no"),
        order.get("order_code"),
        order.get("code"),
        order.get("id"),
    )
    keys: set[str] = set()
    for value in values:
        key = _order_key(value)
        if not key:
            continue
        keys.add(key)
        if key.startswith("DH") and len(key) > 2:
            keys.add(key[2:])
        elif len(key) >= 4:
            keys.add(f"DH{key}")
    return keys


def _display_order_code(order: dict[str, Any]) -> str:
    for field in ("sale_order_no", "order_no", "order_code", "code", "id"):
        value = str(order.get(field) or "").strip()
        if value:
            return value
    return ""


def _safe_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def build_order_lookup_snapshot(
    datasets: dict[str, list[dict[str, Any]]],
    *,
    config: AmisConfig,
    synced_at: str,
) -> dict[str, Any] | None:
    """Create a minimal private cache without raw CRM or order-line values."""
    secret = str(config.order_lookup_hmac_secret or "")
    if not secret:
        return None

    phones_by_account: dict[str, set[str]] = {}
    shop_names_by_account: dict[str, str] = {}
    for customer in datasets.get("customers") or []:
        if not isinstance(customer, dict):
            continue
        phones = {
            _phone(customer.get(field))
            for field in ("office_tel", "phone", "mobile_phone", "tel", "chatbot_public_phone")
        }
        phones.discard("")
        customer_name = _safe_text(
            customer.get("account_name") or customer.get("account_short_name")
        )
        for key in _account_keys(customer):
            if phones:
                phones_by_account.setdefault(key, set()).update(phones)
            if customer_name:
                shop_names_by_account.setdefault(key, customer_name)

    items: list[dict[str, Any]] = []
    for order in datasets.get("sale_orders") or []:
        if not isinstance(order, dict):
            continue
        keys = _order_keys(order)
        display_code = _display_order_code(order)
        if not keys or not display_code:
            continue
        phones = {
            _phone(order.get(field))
            for field in ("customer_phone", "phone", "office_tel", "mobile_phone")
        }
        for account_key in _account_keys(order):
            phones.update(phones_by_account.get(account_key, set()))
        phones.discard("")
        if not phones:
            continue
        status = _safe_text(order.get("status") or order.get("order_status") or "Đang xử lý")
        updated_at = _safe_text(
            order.get("modified_date") or order.get("updated_at") or order.get("created_date"),
            limit=80,
        )
        shop_name = _safe_text(
            order.get("account_name") or order.get("account_short_name")
        )
        if not shop_name:
            for account_key in sorted(_account_keys(order)):
                shop_name = shop_names_by_account.get(account_key, "")
                if shop_name:
                    break
        items.append({
            "order_code": display_code,
            "order_keys": sorted(keys),
            "phone_hmacs": sorted({_phone_digest(phone, secret) for phone in phones}),
            "shop_name": shop_name,
            "status": status,
            # Customer-visible allowlist after ownership verification. Do not
            # add phone numbers, addresses, prices, debts, invoices or notes.
            "delivery_status": _safe_text(order.get("delivery_status")),
            "sale_order_date": _safe_text(order.get("sale_order_date"), limit=80),
            "deadline_date": _safe_text(order.get("deadline_date"), limit=80),
            "updated_at": updated_at,
        })

    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": 2,
        "source": "amis_crm_order_warm",
        "synced_at": synced_at,
        "record_count": len(items),
        "snapshot_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "items": items,
    }


def build_order_lookup_index(snapshot: dict[str, Any]) -> dict[str, str]:
    """Build a Redis Hash payload keyed by normalized order code.

    Duplicate codes are retained as a JSON list; ownership is still checked by
    HMAC after exact-code lookup. Values contain only allowlisted private cache
    fields, never raw AMIS records.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in snapshot.get("items") or []:
        if not isinstance(item, dict):
            continue
        for key in item.get("order_keys") or []:
            normalized = _order_key(key)
            if normalized:
                grouped.setdefault(normalized, []).append(item)
    return {
        key: json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        for key, items in grouped.items()
    }


def _parse_synced_at(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


async def lookup_cached_order_status(
    redis_client: Any,
    *,
    config: AmisConfig,
    order_code: str,
    phone: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Look up one exact code only when its owner phone also matches."""
    key = _order_key(order_code)
    canonical_phone = _phone(phone)
    if not key or not canonical_phone:
        return {"outcome": "missing_input"}
    if not config.order_lookup_hmac_secret:
        return {"outcome": "unavailable", "reason": "ORDER_LOOKUP_SECRET_MISSING"}

    def _decode_json(raw: Any) -> Any:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    # Schema v2 warms an exact-code Redis Hash. The old snapshot remains a
    # safe compatibility fallback until the next scheduled warm has published
    # the index, so deployment never makes an existing cache unreadable.
    metadata: dict[str, Any] = {}
    try:
        raw_metadata = await redis_client.get(config.redis_order_lookup_metadata_key)
        if raw_metadata:
            parsed_metadata = _decode_json(raw_metadata)
            if isinstance(parsed_metadata, dict):
                metadata = parsed_metadata
    except (TypeError, ValueError, UnicodeDecodeError):
        metadata = {}
    except Exception:
        return {"outcome": "unavailable", "reason": "ORDER_CACHE_READ_FAILED"}

    indexed_matches: list[dict[str, Any]] | None = None
    if metadata:
        try:
            raw_matches = await redis_client.hget(config.redis_order_lookup_index_key, key)
            if raw_matches:
                parsed_matches = _decode_json(raw_matches)
                if isinstance(parsed_matches, list) and all(isinstance(item, dict) for item in parsed_matches):
                    indexed_matches = parsed_matches
            elif int(metadata.get("schema_version") or 0) >= 2:
                # A schema-v2 publication writes the Hash and its metadata in
                # one Redis transaction. No field is a safe exact-code miss.
                indexed_matches = []
        except AttributeError:
            # Old test doubles/deployments fall back to the v1 snapshot below.
            indexed_matches = None
        except (TypeError, ValueError, UnicodeDecodeError):
            indexed_matches = None
        except Exception:
            return {"outcome": "unavailable", "reason": "ORDER_CACHE_READ_FAILED"}

    snapshot: dict[str, Any] = {}
    if indexed_matches is None:
        try:
            raw = await redis_client.get(config.redis_order_lookup_key)
        except Exception:
            return {"outcome": "unavailable", "reason": "ORDER_CACHE_READ_FAILED"}
        if not raw:
            return {"outcome": "unavailable", "reason": "ORDER_CACHE_MISSING"}
        try:
            parsed_snapshot = _decode_json(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            return {"outcome": "unavailable", "reason": "ORDER_CACHE_INVALID"}
        if not isinstance(parsed_snapshot, dict) or not isinstance(parsed_snapshot.get("items"), list):
            return {"outcome": "unavailable", "reason": "ORDER_CACHE_INVALID"}
        snapshot = parsed_snapshot
        if not metadata:
            metadata = snapshot
        indexed_matches = [
            item for item in snapshot["items"]
            if isinstance(item, dict) and key in set(item.get("order_keys") or [])
        ]

    synced_at_raw = str(metadata.get("synced_at") or "")
    synced_at = _parse_synced_at(synced_at_raw)
    current = now or datetime.now(timezone.utc)
    if synced_at is None or (current - synced_at).total_seconds() > config.order_lookup_max_age_seconds:
        return {
            "outcome": "unavailable",
            "reason": "ORDER_CACHE_STALE",
            "synced_at": synced_at_raw,
        }

    if not indexed_matches:
        return {
            "outcome": "not_found",
            "synced_at": synced_at_raw,
            "source_id": "amis:internal:order-warm",
        }
    phone_hmac = _phone_digest(canonical_phone, config.order_lookup_hmac_secret)
    matched = next((item for item in indexed_matches if phone_hmac in set(item.get("phone_hmacs") or [])), None)
    if not matched:
        return {
            "outcome": "phone_mismatch",
            "synced_at": synced_at_raw,
            "source_id": "amis:internal:order-warm",
        }
    return {
        "outcome": "found",
        "order_code": str(matched.get("order_code") or order_code),
        "shop_name": str(matched.get("shop_name") or ""),
        "status": str(matched.get("status") or "Đang xử lý"),
        "delivery_status": str(matched.get("delivery_status") or ""),
        "sale_order_date": str(matched.get("sale_order_date") or ""),
        "deadline_date": str(matched.get("deadline_date") or ""),
        "order_updated_at": str(matched.get("updated_at") or ""),
        "synced_at": synced_at_raw,
        "source_id": "amis:internal:order-warm",
        # Do not call this "realtime": it is a protected warm-cache result.
        # The code + phone HMAC match is the minimum ownership check until an
        # approved sender-link/OTP realtime adapter exists.
        "data_mode": "protected_warm_cache",
        "ownership_check": "order_code_and_phone_hmac_match",
        "freshness_checked": True,
    }
