"""Safe, short-lived staging for chunked AMIS warm runs.

The final snapshots are deliberately untouched until every expected chunk is
present and has passed the existing projection/safety gates.  A failed or
interrupted n8n execution therefore only leaves expiring internal staging keys.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from domains.common.db import get_redis_client

from .config import AmisConfig, load_amis_config
from .service import AmisSyncSafetyError, sync_public_snapshots


REQUIRED_DATASET_NAMES = ("customers", "products", "sale_orders")
OPTIONAL_DATASET_NAMES = ("loyalty_customers",)
ALLOWED_DATASET_NAMES = (*REQUIRED_DATASET_NAMES, *OPTIONAL_DATASET_NAMES)
_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{8,100}$")


def _validate_run_id(run_id: str) -> str:
    value = str(run_id or "").strip()
    if not _RUN_ID.fullmatch(value):
        raise AmisSyncSafetyError("Invalid AMIS warm run id")
    return value


def _normalise_plan(
    expected_counts: dict[str, Any],
    expected_chunks: dict[str, Any],
    *,
    max_records: int,
) -> tuple[dict[str, int], dict[str, int]]:
    count_names = set(expected_counts)
    chunk_names = set(expected_chunks)
    if count_names != chunk_names:
        raise AmisSyncSafetyError("AMIS warm plan counts and chunks must contain the same datasets")
    if not set(REQUIRED_DATASET_NAMES).issubset(count_names):
        raise AmisSyncSafetyError("AMIS warm plan must include customers, products and sale_orders")
    if not count_names.issubset(set(ALLOWED_DATASET_NAMES)):
        raise AmisSyncSafetyError("AMIS warm plan contains an unsupported dataset")

    counts: dict[str, int] = {}
    chunks: dict[str, int] = {}
    for dataset in ALLOWED_DATASET_NAMES:
        if dataset not in count_names:
            continue
        try:
            count = int(expected_counts[dataset])
            chunk_count = int(expected_chunks[dataset])
        except (TypeError, ValueError) as exc:
            raise AmisSyncSafetyError("AMIS warm plan contains a non-numeric count") from exc
        if count < 0 or chunk_count < 0:
            raise AmisSyncSafetyError("AMIS warm plan contains a negative count")
        if chunk_count != math.ceil(count / max_records):
            raise AmisSyncSafetyError("AMIS warm plan does not match the configured chunk size")
        counts[dataset] = count
        chunks[dataset] = chunk_count
    return counts, chunks


def _manifest_key(config: AmisConfig, run_id: str) -> str:
    return f"{config.redis_warm_staging_prefix}:{run_id}:manifest"


def _chunk_key(config: AmisConfig, run_id: str, dataset: str, chunk_index: int) -> str:
    return f"{config.redis_warm_staging_prefix}:{run_id}:{dataset}:{chunk_index}"


async def stage_warm_chunk(
    *,
    run_id: str,
    dataset: str,
    chunk_index: int,
    records: list[dict[str, Any]],
    expected_counts: dict[str, Any],
    expected_chunks: dict[str, Any],
    config: AmisConfig | None = None,
    redis_client: Any = None,
) -> dict[str, Any]:
    """Store one bounded raw-data chunk without changing any active snapshot."""
    cfg = config or load_amis_config()
    run_id = _validate_run_id(run_id)
    if dataset not in ALLOWED_DATASET_NAMES:
        raise AmisSyncSafetyError("Unsupported AMIS warm dataset")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise AmisSyncSafetyError("AMIS warm chunk must contain object records")
    if len(records) > cfg.warm_staging_chunk_max_records:
        raise AmisSyncSafetyError("AMIS warm chunk exceeds the configured record limit")

    counts, chunks = _normalise_plan(
        expected_counts,
        expected_chunks,
        max_records=cfg.warm_staging_chunk_max_records,
    )
    try:
        index = int(chunk_index)
    except (TypeError, ValueError) as exc:
        raise AmisSyncSafetyError("AMIS warm chunk index is invalid") from exc
    if index < 0 or index >= chunks[dataset]:
        raise AmisSyncSafetyError("AMIS warm chunk index is outside the expected plan")

    expected_size = min(
        cfg.warm_staging_chunk_max_records,
        counts[dataset] - index * cfg.warm_staging_chunk_max_records,
    )
    if len(records) != expected_size:
        raise AmisSyncSafetyError("AMIS warm chunk record count does not match the expected plan")

    owns_redis = redis_client is None
    redis = redis_client or get_redis_client(decode=True)
    manifest_key = _manifest_key(cfg, run_id)
    plan = json.dumps({"counts": counts, "chunks": chunks}, sort_keys=True, separators=(",", ":"))
    try:
        existing_plan = await redis.hget(manifest_key, "plan")
        if existing_plan and str(existing_plan) != plan:
            raise AmisSyncSafetyError("AMIS warm run id already exists with another plan")
        await redis.set(
            _chunk_key(cfg, run_id, dataset, index),
            json.dumps(records, ensure_ascii=False, separators=(",", ":")),
            ex=cfg.warm_staging_ttl_seconds,
        )
        await redis.hset(manifest_key, mapping={"plan": plan})
        await redis.expire(manifest_key, cfg.warm_staging_ttl_seconds)
    finally:
        if owns_redis:
            await redis.aclose()

    return {
        "status": "staged",
        "run_id": run_id,
        "dataset": dataset,
        "chunk_index": index,
        "record_count": len(records),
        "expected_chunks": chunks,
    }


async def commit_warm_run(
    *,
    run_id: str,
    config: AmisConfig | None = None,
    redis_client: Any = None,
) -> dict[str, Any]:
    """Reassemble a complete staged run and atomically publish safe snapshots."""
    cfg = config or load_amis_config()
    run_id = _validate_run_id(run_id)
    owns_redis = redis_client is None
    redis = redis_client or get_redis_client(decode=True)
    manifest_key = _manifest_key(cfg, run_id)
    staging_keys: list[str] = []
    try:
        manifest = await redis.hgetall(manifest_key)
        plan_raw = manifest.get("plan") if isinstance(manifest, dict) else None
        if not plan_raw:
            raise AmisSyncSafetyError("AMIS warm run was not found or has expired")
        try:
            plan = json.loads(plan_raw)
            counts, chunks = _normalise_plan(
                plan["counts"], plan["chunks"], max_records=cfg.warm_staging_chunk_max_records
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AmisSyncSafetyError("AMIS warm run manifest is invalid") from exc

        raw_datasets: dict[str, list[dict[str, Any]]] = {}
        for dataset in counts:
            collected: list[dict[str, Any]] = []
            for index in range(chunks[dataset]):
                key = _chunk_key(cfg, run_id, dataset, index)
                staging_keys.append(key)
                payload = await redis.get(key)
                if not payload:
                    raise AmisSyncSafetyError(
                        f"AMIS warm run is incomplete: missing {dataset} chunk {index}"
                    )
                try:
                    records = json.loads(payload)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise AmisSyncSafetyError("AMIS warm chunk is invalid") from exc
                if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
                    raise AmisSyncSafetyError("AMIS warm chunk has an unsafe shape")
                collected.extend(records)
            if len(collected) != counts[dataset]:
                raise AmisSyncSafetyError(
                    f"AMIS warm run is incomplete: {dataset} count does not match the plan"
                )
            raw_datasets[dataset] = collected

        result = await sync_public_snapshots(raw_datasets=raw_datasets, redis_client=redis)
        # Cleanup is intentionally after the final snapshot write.  If projection
        # rejects the run, active data stays intact and the staged input remains
        # available until its TTL for diagnosis/retry.
        await redis.delete(manifest_key, *staging_keys)
        return result
    finally:
        if owns_redis:
            await redis.aclose()
