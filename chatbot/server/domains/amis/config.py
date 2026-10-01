"""Configuration for the read-only AMIS CRM integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

from domains.common.config import get_cfg


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: Any, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(value))
    except (TypeError, ValueError):
        return default


def _csv(value: Any, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(part.strip() for part in str(value).split(",") if part.strip())


@dataclass(frozen=True)
class AmisConfig:
    base_url: str = "https://crmconnect.misa.vn/api/v2"
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    timeout_seconds: float = 20.0
    page_size: int = 100
    max_pages: int = 1000
    max_retries: int = 3

    public_approval_field: str = "chatbot_public"
    public_phone_field: str = "chatbot_public_phone"
    public_address_field: str = "chatbot_public_address"
    public_account_allowlist: tuple[str, ...] = ()
    public_recency_days: int = 200
    allowed_revenue_statuses: tuple[str, ...] = ("Đã ghi",)
    blocked_order_status_fragments: tuple[str, ...] = ("Hủy", "Từ chối")
    allow_billing_address_fallback: bool = False
    allow_office_phone_fallback: bool = True
    min_public_products: int = 1
    min_public_locations: int = 1

    # Pilot mode: approve all KH001/KH002 eligible customers when no
    # chatbot_public field and no allowlist are configured.
    pilot_approve_all: bool = False
    # Only include locations that have valid GPS coordinates.
    require_coordinates: bool = True
    # Default GEO search radius (km) used by the chatbot tool.
    geo_radius_km: float = 30.0

    redis_products_key: str = "amis:public:products:active"
    redis_locations_key: str = "amis:public:sales-locations:active"
    redis_locations_geo_key: str = "amis:public:sales-locations:geo"
    redis_metadata_key: str = "amis:public:sync:last-success"
    # Private, server-only cache for a customer to check a specific order using
    # both its code and the phone number on the order. This is deliberately
    # separate from the public product/location snapshots above.
    redis_order_lookup_key: str = "amis:internal:orders:active"
    # Exact-code index for the private order cache. This contains only the
    # same allowlisted, HMAC-protected values as redis_order_lookup_key.
    redis_order_lookup_index_key: str = "amis:internal:orders:index:active"
    redis_order_lookup_metadata_key: str = "amis:internal:orders:last-success"
    # Short-lived internal staging area used when n8n transfers a full AMIS
    # dataset in chunks.  It is never read by the chatbot and is deleted after
    # a successful commit (or expires if a run is interrupted).
    redis_warm_staging_prefix: str = "amis:internal:warm:stage"
    warm_staging_ttl_seconds: int = 7200
    warm_staging_chunk_max_records: int = 100
    # Keep the last complete, ownership-protected order snapshot usable through
    # intermittent AMIS/n8n failures.  The warm pipeline publishes atomically,
    # so a failed run never overwrites this snapshot.  After 12 hours we fail
    # closed rather than risk presenting an excessively old order status.
    order_lookup_max_age_seconds: int = 43200
    # Refuse a suspiciously small warm result so a partial AMIS response cannot
    # replace a healthy private order cache.
    min_order_lookup_records: int = 100
    order_lookup_hmac_secret: str = field(default="", repr=False)
    # Protected customer-loyalty projection. The Redis Hash key is an HMAC of
    # the normalized phone; raw customer rows and raw phone numbers are not
    # published to the active cache.
    redis_loyalty_lookup_index_key: str = "amis:internal:loyalty:index:active"
    redis_loyalty_lookup_metadata_key: str = "amis:internal:loyalty:last-success"
    loyalty_lookup_max_age_seconds: int = 5400
    min_loyalty_lookup_records: int = 100
    loyalty_lookup_hmac_secret: str = field(default="", repr=False)
    internal_token: str = field(default="", repr=False)
    warehouse_location: str = "Tổng kho Nhà máy Cần Thơ (KCN Trà Nóc)"

    @property
    def credentials_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def safe_status(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
            "credentials_configured": self.credentials_configured,
            "public_approval_field": self.public_approval_field,
            "public_phone_field": self.public_phone_field,
            "public_address_field": self.public_address_field,
            "public_allowlist_count": len(self.public_account_allowlist),
            "public_recency_days": self.public_recency_days,
            "allowed_revenue_statuses": list(self.allowed_revenue_statuses),
            "allow_billing_address_fallback": self.allow_billing_address_fallback,
            "allow_office_phone_fallback": self.allow_office_phone_fallback,
            "pilot_approve_all": self.pilot_approve_all,
            "require_coordinates": self.require_coordinates,
            "geo_radius_km": self.geo_radius_km,
            "internal_token_configured": bool(self.internal_token),
            "order_lookup_enabled": bool(self.order_lookup_hmac_secret),
            "order_lookup_max_age_seconds": self.order_lookup_max_age_seconds,
            "loyalty_lookup_enabled": bool(self.loyalty_lookup_hmac_secret),
            "loyalty_lookup_max_age_seconds": self.loyalty_lookup_max_age_seconds,
            "warm_staging_ttl_seconds": self.warm_staging_ttl_seconds,
            "warm_staging_chunk_max_records": self.warm_staging_chunk_max_records,
            "warehouse_location": self.warehouse_location,
        }

def load_amis_config() -> AmisConfig:
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[4]
        load_dotenv(repo_root / ".env", override=True)
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
    except Exception:
        pass
    settings = get_cfg().get("amis", {})

    def value(env_name: str, setting_name: str, default: Any) -> Any:
        env_value = os.getenv(env_name)
        return env_value if env_value is not None else settings.get(setting_name, default)

    # The client secret and internal token intentionally never fall back to settings.json.
    client_secret = os.getenv("AMIS_CLIENT_SECRET", "").strip()
    internal_token = os.getenv("AMIS_SYNC_INTERNAL_TOKEN", "").strip()
    # Prefer a dedicated secret. Falling back to the existing AMIS credential
    # keeps the private cache usable during migration without storing a phone
    # number in Redis; the value is never exposed through status responses.
    order_lookup_hmac_secret = os.getenv("AMIS_ORDER_LOOKUP_HMAC_SECRET", "").strip() or client_secret
    loyalty_lookup_hmac_secret = (
        os.getenv("AMIS_LOYALTY_LOOKUP_HMAC_SECRET", "").strip()
        or order_lookup_hmac_secret
    )

    return AmisConfig(
        base_url=str(value("AMIS_BASE_URL", "base_url", AmisConfig.base_url)).rstrip("/"),
        client_id=str(value("AMIS_CLIENT_ID", "client_id", "JavisCFCChatbot")).strip(),
        client_secret=client_secret,
        timeout_seconds=_as_float(value("AMIS_TIMEOUT_SECONDS", "timeout_seconds", 20.0), 20.0, 1.0),
        page_size=min(100, _as_int(value("AMIS_PAGE_SIZE", "page_size", 100), 100, 1)),
        max_pages=_as_int(value("AMIS_MAX_PAGES", "max_pages", 1000), 1000, 1),
        max_retries=_as_int(value("AMIS_MAX_RETRIES", "max_retries", 3), 3, 1),
        public_approval_field=str(
            value("AMIS_PUBLIC_APPROVAL_FIELD", "public_approval_field", "chatbot_public")
        ).strip(),
        public_phone_field=str(
            value("AMIS_PUBLIC_PHONE_FIELD", "public_phone_field", "chatbot_public_phone")
        ).strip(),
        public_address_field=str(
            value("AMIS_PUBLIC_ADDRESS_FIELD", "public_address_field", "chatbot_public_address")
        ).strip(),
        public_account_allowlist=_csv(
            value("AMIS_PUBLIC_ACCOUNT_ALLOWLIST", "public_account_allowlist", ())
        ),
        public_recency_days=_as_int(
            value("AMIS_PUBLIC_RECENCY_DAYS", "public_recency_days", 365), 365, 0
        ),
        allowed_revenue_statuses=_csv(
            value("AMIS_ALLOWED_REVENUE_STATUSES", "allowed_revenue_statuses", ("Đã ghi",)),
            ("Đã ghi",),
        ),
        blocked_order_status_fragments=_csv(
            value(
                "AMIS_BLOCKED_ORDER_STATUS_FRAGMENTS",
                "blocked_order_status_fragments",
                ("Hủy", "Từ chối"),
            ),
            ("Hủy", "Từ chối"),
        ),
        allow_billing_address_fallback=_as_bool(
            value("AMIS_ALLOW_BILLING_ADDRESS_FALLBACK", "allow_billing_address_fallback", False)
        ),
        allow_office_phone_fallback=_as_bool(
            value("AMIS_ALLOW_OFFICE_PHONE_FALLBACK", "allow_office_phone_fallback", True)
        ),
        min_public_products=_as_int(
            value("AMIS_MIN_PUBLIC_PRODUCTS", "min_public_products", 1), 1, 0
        ),
        min_public_locations=_as_int(
            value("AMIS_MIN_PUBLIC_LOCATIONS", "min_public_locations", 1), 1, 0
        ),
        pilot_approve_all=_as_bool(
            value("AMIS_PILOT_APPROVE_ALL", "pilot_approve_all", False)
        ),
        require_coordinates=_as_bool(
            value("AMIS_REQUIRE_COORDINATES", "require_coordinates", True)
        ),
        geo_radius_km=_as_float(
            value("AMIS_GEO_RADIUS_KM", "geo_radius_km", 30.0), 30.0, 1.0
        ),
        redis_products_key=str(
            value("AMIS_REDIS_PRODUCTS_KEY", "redis_products_key", AmisConfig.redis_products_key)
        ).strip(),
        redis_locations_key=str(
            value("AMIS_REDIS_LOCATIONS_KEY", "redis_locations_key", AmisConfig.redis_locations_key)
        ).strip(),
        redis_locations_geo_key=str(
            value(
                "AMIS_REDIS_LOCATIONS_GEO_KEY",
                "redis_locations_geo_key",
                AmisConfig.redis_locations_geo_key,
            )
        ).strip(),
        redis_metadata_key=str(
            value("AMIS_REDIS_METADATA_KEY", "redis_metadata_key", AmisConfig.redis_metadata_key)
        ).strip(),
        redis_order_lookup_key=str(
            value("AMIS_REDIS_ORDER_LOOKUP_KEY", "redis_order_lookup_key", AmisConfig.redis_order_lookup_key)
        ).strip(),
        redis_order_lookup_index_key=str(
            value(
                "AMIS_REDIS_ORDER_LOOKUP_INDEX_KEY",
                "redis_order_lookup_index_key",
                AmisConfig.redis_order_lookup_index_key,
            )
        ).strip(),
        redis_order_lookup_metadata_key=str(
            value(
                "AMIS_REDIS_ORDER_LOOKUP_METADATA_KEY",
                "redis_order_lookup_metadata_key",
                AmisConfig.redis_order_lookup_metadata_key,
            )
        ).strip(),
        redis_warm_staging_prefix=str(
            value(
                "AMIS_REDIS_WARM_STAGING_PREFIX",
                "redis_warm_staging_prefix",
                AmisConfig.redis_warm_staging_prefix,
            )
        ).strip(),
        warm_staging_ttl_seconds=_as_int(
            value("AMIS_WARM_STAGING_TTL_SECONDS", "warm_staging_ttl_seconds", 7200),
            7200,
            300,
        ),
        warm_staging_chunk_max_records=_as_int(
            value("AMIS_WARM_STAGING_CHUNK_MAX_RECORDS", "warm_staging_chunk_max_records", 100),
            100,
            1,
        ),
        order_lookup_max_age_seconds=_as_int(
            value("AMIS_ORDER_LOOKUP_MAX_AGE_SECONDS", "order_lookup_max_age_seconds", 43200),
            43200,
            60,
        ),
        min_order_lookup_records=_as_int(
            value("AMIS_MIN_ORDER_LOOKUP_RECORDS", "min_order_lookup_records", 100),
            100,
            1,
        ),
        order_lookup_hmac_secret=order_lookup_hmac_secret,
        redis_loyalty_lookup_index_key=str(
            value(
                "AMIS_REDIS_LOYALTY_LOOKUP_INDEX_KEY",
                "redis_loyalty_lookup_index_key",
                AmisConfig.redis_loyalty_lookup_index_key,
            )
        ).strip(),
        redis_loyalty_lookup_metadata_key=str(
            value(
                "AMIS_REDIS_LOYALTY_LOOKUP_METADATA_KEY",
                "redis_loyalty_lookup_metadata_key",
                AmisConfig.redis_loyalty_lookup_metadata_key,
            )
        ).strip(),
        loyalty_lookup_max_age_seconds=_as_int(
            value(
                "AMIS_LOYALTY_LOOKUP_MAX_AGE_SECONDS",
                "loyalty_lookup_max_age_seconds",
                5400,
            ),
            5400,
            60,
        ),
        min_loyalty_lookup_records=_as_int(
            value(
                "AMIS_MIN_LOYALTY_LOOKUP_RECORDS",
                "min_loyalty_lookup_records",
                100,
            ),
            100,
            1,
        ),
        loyalty_lookup_hmac_secret=loyalty_lookup_hmac_secret,
        internal_token=internal_token,
        warehouse_location=str(
            value("AMIS_WAREHOUSE_DEFAULT", "warehouse_location", AmisConfig.warehouse_location)
        ).strip(),
    )
