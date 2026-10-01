"""Customer-safe projection and search for the public AMIS product snapshot.

The AMIS export currently contains a mixture of fertilizer and non-agricultural
items.  This module deliberately applies a conservative allowlist before any
item can be shown to a customer.  It never exposes price, stock, customer, or
raw CRM fields.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


PRODUCT_SNAPSHOT_KEY = "amis:public:products:active"

_FERTILIZER_TERMS = (
    "phan bon",
    "phan npk",
    "npk",
    "huu co",
    "sinh hoc",
    "cobanic",
    "canxi",
    "magie",
    "kali",
    "ure",
    "dap",
    "lan nung chay",
)
_ALLOWED_CATEGORIES = {"phan npk", "phan huu co", "phan bon", "phan sinh hoc"}
_CATEGORY_QUERY_ALIASES = {
    "phan huu co": "phan huu co",
    "huu co": "phan huu co",
    "phan sinh hoc": "phan sinh hoc",
    "sinh hoc": "phan sinh hoc",
    "phan npk": "phan npk",
    "npk": "phan npk",
}
_EXCLUDED_TERMS = (
    "ao mua",
    "ao thun",
    "bot giat",
    "nuoc lau",
    "nuoc rua",
    "combo",
    "hop qua",
    "may rai",
    "thau nhua",
    "truc in",
    "tui vai",
    "bao bi",
    "bao in",
    "tem nhan",
)


def normalize_catalog_text(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "d").lower()
    text = re.sub(r"[^a-z0-9%+\s.-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _item_name(item: dict[str, Any]) -> str:
    return str(item.get("display_name") or item.get("product_name") or item.get("name") or "").strip()


def _category(item: dict[str, Any]) -> str:
    return normalize_catalog_text(item.get("product_category") or item.get("category"))


def _requested_category(query_norm: str) -> str:
    """Return a category constraint only when the customer names one explicitly."""
    for phrase in ("phan huu co", "huu co", "phan sinh hoc", "sinh hoc", "phan npk", "npk"):
        if re.search(rf"\b{re.escape(phrase)}\b", query_norm):
            return _CATEGORY_QUERY_ALIASES[phrase]
    return ""


def _matches_requested_category(item: dict[str, Any], category: str) -> bool:
    if not category:
        return True
    item_category = _category(item)
    name_norm = normalize_catalog_text(_item_name(item))
    if category == "phan npk":
        return item_category == category or "npk" in name_norm
    if category == "phan huu co":
        return item_category == category or bool(re.search(r"\b(huu co|cobanic)\b", name_norm))
    if category == "phan sinh hoc":
        return item_category == category or "sinh hoc" in name_norm
    return item_category == category


def _formula_key(value: Any) -> tuple[str, ...]:
    text = normalize_catalog_text(value)
    match = re.search(r"\bnpk\b(.{0,45})", text)
    segment = match.group(1) if match else text
    numbers = re.findall(r"\d{1,3}", segment)
    # Nutrient formulae are represented by the first three numbers after NPK.
    # A fourth number is retained for forms such as 16-8-16-12S.
    if len(numbers) >= 4 and re.search(r"\d\s*[.-]\s*\d\s*[.-]\s*\d\s*[.-]\s*\d", segment):
        return tuple(numbers[:4])
    if len(numbers) >= 3:
        return tuple(numbers[:3])
    return ()


def is_public_fertilizer_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    name = normalize_catalog_text(_item_name(item))
    category = _category(item)
    if not name or any(term in name for term in _EXCLUDED_TERMS):
        return False
    if category in _ALLOWED_CATEGORIES:
        return True
    return any(term in name for term in _FERTILIZER_TERMS)


def project_public_fertilizer(item: dict[str, Any]) -> dict[str, Any]:
    """Return the small public projection used by the conversational layer."""
    name = _item_name(item)
    projected: dict[str, Any] = {
        "name": name,
        "category": str(item.get("product_category") or item.get("category") or "Phân bón").strip() or "Phân bón",
        "product_code": str(item.get("product_code") or item.get("item_code") or "").strip(),
        "usage_unit": str(item.get("usage_unit") or "").strip(),
        "source_id": PRODUCT_SNAPSHOT_KEY,
    }
    return {key: value for key, value in projected.items() if value not in (None, "")}


def parse_snapshot(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(str(raw or ""))
    except (TypeError, ValueError):
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def search_public_fertilizers(items: list[dict[str, Any]], query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search the filtered snapshot; formula queries require an exact formula."""
    query_norm = normalize_catalog_text(query)
    query_formula = _formula_key(query_norm)
    requested_category = _requested_category(query_norm)
    query_tokens = {token for token in query_norm.split() if len(token) > 1 and token not in {"phan", "bon", "cho", "cay", "co", "gi"}}
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for item in items:
        if not is_public_fertilizer_item(item):
            continue
        if not _matches_requested_category(item, requested_category):
            continue
        name = _item_name(item)
        name_norm = normalize_catalog_text(name)
        item_formula = _formula_key(name_norm)
        if query_formula and item_formula != query_formula:
            continue
        score = 0
        if query_norm and query_norm in name_norm:
            score += 100
        score += 12 * len(query_tokens.intersection(set(name_norm.split())))
        if query_formula:
            score += 80
        if _category(item) in _ALLOWED_CATEGORIES:
            score += 10
        if "npk" in name_norm:
            score += 5
        scored.append((score, name_norm, project_public_fertilizer(item)))
    scored.sort(key=lambda row: (-row[0], row[1]))
    # Avoid showing duplicate names from repeated exports.
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for _, _, item in scored:
        key = (normalize_catalog_text(item.get("name")), str(item.get("product_code") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max(1, min(limit, 8)):
            break
    return result


def formula_from_query(query: str) -> tuple[str, ...]:
    return _formula_key(query)
