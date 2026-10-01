"""Audit and atomically publish AMIS public snapshots to Redis."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Optional

from domains.common.db import get_redis_client

from .client import AmisClient
from .config import AmisConfig, load_amis_config
from .loyalty_cache import build_loyalty_lookup_index, build_loyalty_lookup_snapshot
from .order_cache import build_order_lookup_index, build_order_lookup_snapshot
from .projection import (
    assert_public_projection_safe,
    build_public_products,
    build_public_sales_locations,
)


class AmisSyncSafetyError(RuntimeError):
    """Raised when a new snapshot fails minimum safety gates."""


def _snapshot(items: list[dict[str, Any]], *, synced_at: str) -> dict[str, Any]:
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    envelope = {
        "schema_version": 1,
        "source": "amis_crm",
        "synced_at": synced_at,
        "record_count": len(items),
        "snapshot_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "items": items,
    }
    assert_public_projection_safe(envelope)
    return envelope


async def build_public_bundle(
    *,
    config: Optional[AmisConfig] = None,
    client: Optional[AmisClient] = None,
    now: Optional[datetime] = None,
    raw_datasets: Optional[dict[str, list]] = None,
    order_synced_at: str = "",
    include_private_order_snapshot: bool = False,
    include_private_loyalty_snapshot: bool = False,
) -> dict[str, Any]:
    cfg = config or load_amis_config()
    if raw_datasets is not None:
        # Pre-fetched path: n8n (or tests) supply data directly — no network call.
        datasets = raw_datasets
    elif client is None:
        async with AmisClient(cfg) as owned_client:
            datasets = await owned_client.fetch_public_source_datasets()
    else:
        datasets = await client.fetch_public_source_datasets()

    products, product_metrics = build_public_products(datasets["products"])
    locations, location_metrics = build_public_sales_locations(
        datasets["customers"],
        datasets["sale_orders"],
        datasets["products"],
        cfg,
        now=now,
    )
    gate_reasons = []
    if len(products) < cfg.min_public_products:
        gate_reasons.append(
            f"public products {len(products)} < minimum {cfg.min_public_products}"
        )
    if len(locations) < cfg.min_public_locations:
        gate_reasons.append(
            f"public locations {len(locations)} < minimum {cfg.min_public_locations}"
        )

    bundle = {
        "products": products,
        "locations": locations,
        "metrics": {
            "source": {
                "products": len(datasets["products"]),
                "customers": len(datasets["customers"]),
                "sale_orders": len(datasets["sale_orders"]),
            },
            "products": product_metrics,
            "locations": location_metrics,
        },
        "gate": {
            "ready": not gate_reasons,
            "reasons": gate_reasons,
        },
    }
    if include_private_order_snapshot:
        # This is consumed only inside sync_public_snapshots.  The default
        # public-bundle contract remains products/locations only.
        bundle["_private_order_snapshot"] = build_order_lookup_snapshot(
            datasets,
            config=cfg,
            synced_at=order_synced_at or (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        )
    if include_private_loyalty_snapshot:
        # Keep the wider AMIS customer feed isolated from the public dealer
        # projection. Only the minimal HMAC-keyed loyalty projection survives.
        loyalty_customers = datasets.get("loyalty_customers", datasets["customers"])
        bundle["_private_loyalty_snapshot"] = build_loyalty_lookup_snapshot(
            {
                "customers": loyalty_customers,
                "sale_orders": datasets["sale_orders"],
            },
            config=cfg,
            synced_at=order_synced_at
            or (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        )
    return bundle


async def _write_bundle_to_redis(
    redis_client: Any,
    *,
    config: AmisConfig,
    products_snapshot: dict[str, Any],
    locations_snapshot: dict[str, Any],
    metadata: dict[str, Any],
    order_snapshot: Optional[dict[str, Any]] = None,
    loyalty_snapshot: Optional[dict[str, Any]] = None,
) -> None:
    pipeline = redis_client.pipeline(transaction=True)
    pipeline.set(
        config.redis_products_key,
        json.dumps(products_snapshot, ensure_ascii=False, separators=(",", ":")),
    )
    pipeline.set(
        config.redis_locations_key,
        json.dumps(locations_snapshot, ensure_ascii=False, separators=(",", ":")),
    )
    pipeline.delete(config.redis_locations_geo_key)

    geo_values: list[Any] = []
    for location in locations_snapshot["items"]:
        longitude = location.get("longitude")
        latitude = location.get("latitude")
        if longitude is None or latitude is None:
            continue
        geo_values.extend([longitude, latitude, location["location_id"]])
    if geo_values:
        pipeline.geoadd(config.redis_locations_geo_key, geo_values)

    pipeline.set(
        config.redis_metadata_key,
        json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    )
    if order_snapshot is not None:
        order_index = build_order_lookup_index(order_snapshot)
        pipeline.set(
            config.redis_order_lookup_key,
            json.dumps(order_snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        pipeline.delete(config.redis_order_lookup_index_key)
        if order_index:
            pipeline.hset(config.redis_order_lookup_index_key, mapping=order_index)
        pipeline.set(
            config.redis_order_lookup_metadata_key,
            json.dumps({
                "schema_version": order_snapshot.get("schema_version", 1),
                "source": order_snapshot.get("source", "amis_crm_order_warm"),
                "synced_at": order_snapshot.get("synced_at", ""),
                "record_count": order_snapshot.get("record_count", 0),
                "snapshot_hash": order_snapshot.get("snapshot_hash", ""),
            }, ensure_ascii=False, separators=(",", ":")),
        )
    if loyalty_snapshot is not None:
        loyalty_index = build_loyalty_lookup_index(loyalty_snapshot)
        pipeline.delete(config.redis_loyalty_lookup_index_key)
        if loyalty_index:
            pipeline.hset(config.redis_loyalty_lookup_index_key, mapping=loyalty_index)
        pipeline.set(
            config.redis_loyalty_lookup_metadata_key,
            json.dumps({
                "schema_version": loyalty_snapshot.get("schema_version", 1),
                "source": loyalty_snapshot.get("source", "amis_crm_loyalty_warm"),
                "synced_at": loyalty_snapshot.get("synced_at", ""),
                "record_count": loyalty_snapshot.get("record_count", 0),
                "direct_loyalty_count": loyalty_snapshot.get("direct_loyalty_count", 0),
                "ambiguous_count": loyalty_snapshot.get("ambiguous_count", 0),
                "snapshot_hash": loyalty_snapshot.get("snapshot_hash", ""),
            }, ensure_ascii=False, separators=(",", ":")),
        )
    await pipeline.execute()


async def sync_public_snapshots(
    *,
    dry_run: bool = False,
    config: Optional[AmisConfig] = None,
    client: Optional[AmisClient] = None,
    redis_client: Any = None,
    now: Optional[datetime] = None,
    raw_datasets: Optional[dict[str, list]] = None,
) -> dict[str, Any]:
    cfg = config or load_amis_config()
    synced_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    bundle = await build_public_bundle(
        config=cfg,
        client=client,
        now=now,
        raw_datasets=raw_datasets,
        order_synced_at=synced_at,
        include_private_order_snapshot=True,
        include_private_loyalty_snapshot=True,
    )
    order_snapshot = bundle.pop("_private_order_snapshot", None)
    loyalty_snapshot = bundle.pop("_private_loyalty_snapshot", None)
    order_lookup_skip_reason = ""
    candidate_order_count = int((order_snapshot or {}).get("record_count") or 0)
    if order_snapshot is not None and candidate_order_count < cfg.min_order_lookup_records:
        # Do not replace the last known-good private cache with a partial AMIS
        # page/filter result. Products and public dealer snapshots can still
        # refresh; the old private order cache remains atomically intact.
        order_snapshot = None
        order_lookup_skip_reason = "ORDER_LOOKUP_RECORD_COUNT_BELOW_MINIMUM"
    loyalty_lookup_skip_reason = ""
    candidate_loyalty_count = int((loyalty_snapshot or {}).get("record_count") or 0)
    candidate_direct_loyalty_count = int(
        (loyalty_snapshot or {}).get("direct_loyalty_count") or 0
    )
    if (
        loyalty_snapshot is not None
        and candidate_loyalty_count < cfg.min_loyalty_lookup_records
    ):
        loyalty_snapshot = None
        loyalty_lookup_skip_reason = "LOYALTY_LOOKUP_RECORD_COUNT_BELOW_MINIMUM"
    products_snapshot = _snapshot(bundle["products"], synced_at=synced_at)
    locations_snapshot = _snapshot(bundle["locations"], synced_at=synced_at)

    report = {
        "status": "ok" if bundle["gate"]["ready"] else "blocked",
        "dry_run": dry_run,
        "written": False,
        "synced_at": synced_at,
        "gate": bundle["gate"],
        "metrics": bundle["metrics"],
        "snapshots": {
            "products": {
                "key": cfg.redis_products_key,
                "record_count": products_snapshot["record_count"],
                "snapshot_hash": products_snapshot["snapshot_hash"],
            },
            "locations": {
                "key": cfg.redis_locations_key,
                "geo_key": cfg.redis_locations_geo_key,
                "record_count": locations_snapshot["record_count"],
                "snapshot_hash": locations_snapshot["snapshot_hash"],
            },
            "order_lookup": {
                "key": cfg.redis_order_lookup_key,
                "record_count": int((order_snapshot or {}).get("record_count") or 0),
                "candidate_record_count": candidate_order_count,
                "snapshot_hash": str((order_snapshot or {}).get("snapshot_hash") or ""),
                "enabled": bool(order_snapshot),
                "retained_previous": bool(order_lookup_skip_reason),
                "reason": order_lookup_skip_reason,
            },
            "loyalty_lookup": {
                "key": cfg.redis_loyalty_lookup_index_key,
                "record_count": int((loyalty_snapshot or {}).get("record_count") or 0),
                "candidate_record_count": candidate_loyalty_count,
                "direct_loyalty_count": candidate_direct_loyalty_count,
                "snapshot_hash": str((loyalty_snapshot or {}).get("snapshot_hash") or ""),
                "enabled": bool(loyalty_snapshot),
                "retained_previous": bool(loyalty_lookup_skip_reason),
                "reason": loyalty_lookup_skip_reason,
            },
        },
    }
    if dry_run:
        return report
    if not bundle["gate"]["ready"]:
        raise AmisSyncSafetyError("; ".join(bundle["gate"]["reasons"]))

    metadata = {
        "schema_version": 1,
        "source": "amis_crm",
        "synced_at": synced_at,
        "product_count": products_snapshot["record_count"],
        "location_count": locations_snapshot["record_count"],
        "location_with_coordinates_count": bundle["metrics"]["locations"]["with_coordinates_count"],
        "products_snapshot_hash": products_snapshot["snapshot_hash"],
        "locations_snapshot_hash": locations_snapshot["snapshot_hash"],
    }

    owns_redis = redis_client is None
    target_redis = redis_client or get_redis_client(decode=True)
    try:
        await _write_bundle_to_redis(
            target_redis,
            config=cfg,
            products_snapshot=products_snapshot,
            locations_snapshot=locations_snapshot,
            metadata=metadata,
            order_snapshot=order_snapshot,
            loyalty_snapshot=loyalty_snapshot,
        )
    finally:
        if owns_redis:
            await target_redis.aclose()

    report["written"] = True
    return report
