"""Protected, freshness-bounded loyalty lookup for the CFC chatbot.

The hourly AMIS warm may contain raw customer and sale-order records.  This
module projects them to a Redis Hash keyed only by an HMAC of the normalized
phone number.  Values contain direct CRM loyalty fields plus match flags; raw
phones, addresses, order values and customer records are never persisted.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Any

from .config import AmisConfig


PHONE_FIELDS = (
    "office_tel",
    "phone",
    "mobile",
    "mobile_phone",
    "tel",
    "chatbot_public_phone",
)
POINT_FIELDS = ("total_score", "points", "loyalty_points")
TIER_FIELDS = ("membership_tier", "tier")
BENEFIT_FIELDS = (
    "loyalty_benefits",
    "membership_benefits",
    "benefits",
    "customer_policy",
    "discount_policy",
)


def _phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits if 9 <= len(digits) <= 12 else ""


def _phone_digest(phone: str, secret: str) -> str:
    # Domain separation prevents the same phone from sharing a digest with the
    # order cache even when both caches intentionally reuse one server secret.
    payload = f"loyalty:{phone}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


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


def _first_value(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = record.get(field)
        if value not in (None, ""):
            return value
    return None


def _points(record: dict[str, Any]) -> int | None:
    value = _first_value(record, POINT_FIELDS)
    if value in (None, ""):
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def build_loyalty_lookup_snapshot(
    datasets: dict[str, list[dict[str, Any]]],
    *,
    config: AmisConfig,
    synced_at: str,
) -> dict[str, Any] | None:
    """Project direct CRM loyalty facts into a minimal phone-HMAC snapshot."""
    secret = str(config.loyalty_lookup_hmac_secret or "")
    if not secret:
        return None

    customers = [item for item in datasets.get("customers") or [] if isinstance(item, dict)]
    orders = [item for item in datasets.get("sale_orders") or [] if isinstance(item, dict)]

    profiles: list[dict[str, Any]] = []
    alias_to_profiles: dict[str, set[int]] = {}
    for customer in customers:
        account_keys = _account_keys(customer)
        phones = {_phone(customer.get(field)) for field in PHONE_FIELDS}
        phones.discard("")
        profile = {
            "account_keys": account_keys,
            "phones": phones,
            "points": _points(customer),
            "tier": _safe_text(_first_value(customer, TIER_FIELDS), limit=120),
            "benefits": _safe_text(_first_value(customer, BENEFIT_FIELDS), limit=400),
            "customer_profile_matched": True,
            "order_phone_matched": False,
        }
        profile_index = len(profiles)
        profiles.append(profile)
        for key in account_keys:
            alias_to_profiles.setdefault(key, set()).add(profile_index)

    # A phone is often present only on SaleOrders.  Join it to the customer by
    # exact account aliases when unique.  If no customer can be joined, retain
    # only a minimal order-backed match so the chatbot does not falsely claim
    # that the phone has no customer history.
    order_only: dict[str, dict[str, Any]] = {}
    for order in orders:
        phones = {_phone(order.get(field)) for field in PHONE_FIELDS}
        phones.discard("")
        if not phones:
            continue
        matched_profiles: set[int] = set()
        for key in _account_keys(order):
            matched_profiles.update(alias_to_profiles.get(key, set()))
        if len(matched_profiles) == 1:
            profile = profiles[next(iter(matched_profiles))]
            profile["phones"].update(phones)
            profile["order_phone_matched"] = True
            continue

        order_account_keys = _account_keys(order)
        order_signature = "|".join(sorted(order_account_keys)) or "order-only"
        for phone in phones:
            candidate_key = f"{phone}:{order_signature}"
            order_only[candidate_key] = {
                # Keep only transient account aliases for ambiguity detection.
                # They are removed by the final projection and never persisted.
                "account_keys": order_account_keys,
                "phones": {phone},
                "points": None,
                "tier": "",
                "benefits": "",
                "customer_profile_matched": False,
                "order_phone_matched": True,
            }

    candidates_by_phone: dict[str, list[dict[str, Any]]] = {}
    for profile in [*profiles, *order_only.values()]:
        for phone in profile["phones"]:
            candidates_by_phone.setdefault(phone, []).append(profile)

    items: list[dict[str, Any]] = []
    ambiguous_count = 0
    direct_loyalty_count = 0
    for phone, candidates in sorted(candidates_by_phone.items()):
        # Multiple unrelated AMIS accounts sharing one phone require a human
        # identity check; never pick one arbitrarily.
        unique_accounts = {
            "|".join(sorted(candidate.get("account_keys") or set())) or "order-only"
            for candidate in candidates
        }
        ambiguous = len(unique_accounts) > 1
        if ambiguous:
            ambiguous_count += 1
            item = {
                "phone_hmac": _phone_digest(phone, secret),
                "ambiguous": True,
                "customer_profile_matched": any(
                    bool(candidate.get("customer_profile_matched")) for candidate in candidates
                ),
                "order_phone_matched": any(
                    bool(candidate.get("order_phone_matched")) for candidate in candidates
                ),
            }
        else:
            candidate = candidates[0]
            points = candidate.get("points")
            tier = _safe_text(candidate.get("tier"), limit=120)
            benefits = _safe_text(candidate.get("benefits"), limit=400)
            if points is not None or tier or benefits:
                direct_loyalty_count += 1
            item = {
                "phone_hmac": _phone_digest(phone, secret),
                "ambiguous": False,
                "points": points,
                "tier": tier,
                "benefits": benefits,
                "customer_profile_matched": bool(candidate.get("customer_profile_matched")),
                "order_phone_matched": bool(candidate.get("order_phone_matched")),
            }
        items.append(item)

    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": 1,
        "source": "amis_crm_loyalty_warm",
        "synced_at": synced_at,
        "record_count": len(items),
        "direct_loyalty_count": direct_loyalty_count,
        "ambiguous_count": ambiguous_count,
        "snapshot_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "items": items,
    }


def build_loyalty_lookup_index(snapshot: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in snapshot.get("items") or []:
        if not isinstance(item, dict):
            continue
        digest = str(item.get("phone_hmac") or "").strip()
        if digest:
            index[digest] = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    return index


def _parse_synced_at(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


async def lookup_cached_loyalty_info(
    redis_client: Any,
    *,
    config: AmisConfig,
    phone: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    canonical_phone = _phone(phone)
    if not canonical_phone:
        return {"outcome": "missing_input"}
    secret = str(config.loyalty_lookup_hmac_secret or "")
    if not secret:
        return {"outcome": "unavailable", "reason": "LOYALTY_LOOKUP_SECRET_MISSING"}

    try:
        raw_metadata = await redis_client.get(config.redis_loyalty_lookup_metadata_key)
    except Exception:
        return {"outcome": "unavailable", "reason": "LOYALTY_CACHE_READ_FAILED"}
    if not raw_metadata:
        return {"outcome": "unavailable", "reason": "LOYALTY_CACHE_MISSING"}
    try:
        if isinstance(raw_metadata, bytes):
            raw_metadata = raw_metadata.decode("utf-8")
        metadata = json.loads(raw_metadata)
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {"outcome": "unavailable", "reason": "LOYALTY_CACHE_INVALID"}

    synced_at_raw = str(metadata.get("synced_at") or "")
    synced_at = _parse_synced_at(synced_at_raw)
    current = now or datetime.now(timezone.utc)
    if synced_at is None or (
        current - synced_at
    ).total_seconds() > config.loyalty_lookup_max_age_seconds:
        return {
            "outcome": "unavailable",
            "reason": "LOYALTY_CACHE_STALE",
            "synced_at": synced_at_raw,
        }

    digest = _phone_digest(canonical_phone, secret)
    try:
        raw_item = await redis_client.hget(config.redis_loyalty_lookup_index_key, digest)
    except Exception:
        return {"outcome": "unavailable", "reason": "LOYALTY_CACHE_READ_FAILED"}
    if not raw_item:
        return {
            "outcome": "not_found",
            "synced_at": synced_at_raw,
            "source_id": "amis:internal:loyalty-warm",
        }
    try:
        if isinstance(raw_item, bytes):
            raw_item = raw_item.decode("utf-8")
        item = json.loads(raw_item)
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {"outcome": "unavailable", "reason": "LOYALTY_CACHE_INVALID"}

    if item.get("ambiguous"):
        return {
            "outcome": "ambiguous",
            "synced_at": synced_at_raw,
            "source_id": "amis:internal:loyalty-warm",
        }
    points = item.get("points")
    tier = _safe_text(item.get("tier"), limit=120)
    benefits = _safe_text(item.get("benefits"), limit=400)
    outcome = "found" if points is not None or tier or benefits else "profile_found_no_loyalty"
    return {
        "outcome": outcome,
        "points": points,
        "tier": tier,
        "benefits": benefits,
        "customer_profile_matched": bool(item.get("customer_profile_matched")),
        "order_phone_matched": bool(item.get("order_phone_matched")),
        "synced_at": synced_at_raw,
        "source_id": "amis:internal:loyalty-warm",
        "data_mode": "protected_warm_cache",
        "ownership_check": "phone_hmac_match",
        "freshness_checked": True,
    }
