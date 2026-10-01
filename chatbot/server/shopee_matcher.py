"""
shopee_matcher.py — Module Khớp, Tư Vấn & Gửi Link Shopee Động cho ZeO & CFC
Hỗ trợ AI Customer Service Specialist:
  1. Đọc danh mục sản phẩm Shopee động từ Redis (zeo:shopee:catalog:active / cfc:shopee:catalog:active)
  2. Tự động dự phòng đọc từ Google Sheet CSV nếu Redis chưa có snapshot
  3. Lọc & gợi ý sản phẩm theo Tầm Giá / Ngân Sách (dưới 100k, 50k-100k...)
  4. Lọc Bán Chạy & Mới Nhất theo từng Danh Mục (nước rửa chén, bột giặt, nước giặt...)
  5. Báo giá & gửi link trực tiếp Shopee Mall cho sản phẩm đích danh
  6. Tư vấn theo nhu cầu khách hàng (tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ da tay)
  7. Làm mới cache tức thì qua refresh_shopee_cache()
"""

import csv
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

# In-memory Hot Cache phân theo brand
_catalog_cache: dict[str, list[dict]] = {}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "d").lower()


def _format_price(price: Any) -> str:
    try:
        num = int(str(price).replace(".", "").replace(",", "").replace("đ", "").strip())
        return f"{num:,.0f}đ".replace(",", ".")
    except Exception:
        return str(price or "Ưu đãi")


def _price_number(price: Any) -> int:
    try:
        return int(str(price).replace(".", "").replace(",", "").replace("đ", "").strip())
    except Exception:
        return 0


def _format_discount(disc: Any) -> str:
    s = str(disc or "").strip()
    if not s or s in ("0", "0%", "0.0"):
        return ""
    try:
        if "." in s and not s.endswith("%"):
            val = float(s)
            if 0 < val < 1:
                return f"{int(round(val * 100))}%"
        if s.endswith("%"):
            return s
        num = float(s)
        return f"{int(num)}%"
    except Exception:
        return s if s.endswith("%") else f"{s}%"


def _get_redis_sync_client() -> Optional[redis.Redis]:
    settings_path = Path(__file__).parent / "settings.json"
    if not settings_path.exists():
        settings_path = Path(__file__).parent / "settings.example.json"
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
        rcfg = cfg.get("redis", {})
        return redis.Redis(
            host=rcfg.get("host", "127.0.0.1"),
            port=int(rcfg.get("port", 6379)),
            password=rcfg.get("password"),
            db=int(rcfg.get("db", 0)),
            decode_responses=True,
        )
    except Exception as e:
        logger.warning("Không kết nối được Redis sync client: %s", e)
        return None


def _load_catalog_from_csv(brand: str) -> list[dict]:
    """Fallback đọc catalog từ file CSV template nếu Redis chưa có."""
    csv_candidates = [
        Path(__file__).resolve().parents[2] / "google_upload" / "zeo_shopee_catalog_template.csv",
    ]
    for p in csv_candidates:
        if p.exists():
            try:
                products = []
                with open(p, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        active = str(row.get("active", "true")).lower() in ("true", "1", "yes")
                        if not active:
                            continue
                        row_brand = row.get("brand", "").upper()
                        if brand.upper() == "ZEO" and row_brand in ["ZEO", "PANO", "OPLUS"]:
                            pass
                        elif brand.upper() == "CFC" and row_brand == "CFC":
                            pass
                        elif brand.upper() != row_brand:
                            continue

                        raw_kw = row.get("keywords", "")
                        kw_list = [k.strip() for k in raw_kw.split(";") if k.strip()] if isinstance(raw_kw, str) else list(raw_kw)
                        products.append({
                            "item_id": row.get("item_id", ""),
                            "name": row.get("name", ""),
                            "brand": row.get("brand", "ZeO"),
                            "category": row.get("category", ""),
                            "price": row.get("price", ""),
                            "original_price": row.get("original_price", ""),
                            "discount": row.get("discount", ""),
                            "badge": row.get("badge", "STANDARD"),
                            "specs": row.get("specs", ""),
                            "keywords": kw_list,
                            "variants": [v.strip() for v in str(row.get("variants", "")).split(";") if v.strip()],
                            "link_shopee": row.get("link_shopee") or row.get("shopee_url", ""),
                            "in_stock": str(row.get("in_stock", "true")).lower() in ("true", "1", "yes"),
                        })
                if products:
                    logger.info("Loaded %d Shopee products from CSV fallback (%s)", len(products), p.name)
                    return products
            except Exception as e:
                logger.warning("Error reading Shopee CSV fallback: %s", e)
    return []


def load_shopee_catalog(brand: str = "zeo") -> list[dict]:
    """Đọc danh mục sản phẩm Shopee động từ Redis hoặc fallback CSV."""
    global _catalog_cache
    b = brand.lower()
    if b in _catalog_cache and _catalog_cache[b]:
        return _catalog_cache[b]

    # 1. Thử đọc từ Redis key: {brand}:shopee:catalog:active
    r = _get_redis_sync_client()
    if r:
        try:
            redis_key = f"{b}:shopee:catalog:active"
            raw_data = r.get(redis_key)
            if not raw_data and b == "zeo":
                raw_data = r.get("zeo:shopee:catalog:active")

            if raw_data:
                # pyrefly: ignore [bad-argument-type]
                parsed = json.loads(raw_data)
                items = parsed if isinstance(parsed, list) else parsed.get("products", [])
                if items:
                    _catalog_cache[b] = items
                    logger.info("Loaded %d Shopee products from Redis [%s]", len(items), redis_key)
                    return items
        except Exception as e:
            logger.warning("Lỗi đọc Shopee catalog từ Redis: %s", e)
        finally:
            try:
                r.close()
            except Exception:
                pass

    # 2. Fallback đọc từ file CSV template
    csv_products = _load_catalog_from_csv(b)
    if csv_products:
        _catalog_cache[b] = csv_products
        return csv_products

    return []


def refresh_shopee_cache(brand: str = "all"):
    """Làm mới lại in-memory cache cho Shopee catalog."""
    global _catalog_cache
    if brand == "all":
        _catalog_cache.clear()
        load_shopee_catalog("zeo")
        load_shopee_catalog("cfc")
    else:
        _catalog_cache.pop(brand.lower(), None)
        load_shopee_catalog(brand.lower())
    logger.info("✓ Shopee hot in-memory cache refreshed for brand=%s", brand)


def _detect_category_from_text(text: str) -> Optional[str]:
    folded = _fold(text)
    if any(k in folded for k in ["rua chen", "rua bat", "chen bat"]):
        return "Nước rửa chén"
    if any(k in folded for k in ["bot giat"]):
        return "Bột giặt"
    if any(k in folded for k in ["nuoc giat", "giat xa", "giat quan ao"]):
        return "Nước giặt"
    if any(k in folded for k in ["lau san", "lau nha"]):
        return "Nước lau sàn"
    if any(k in folded for k in ["toilet", "bon cau", "tay toilet"]):
        return "Tẩy Toilet"
    if any(k in folded for k in ["javel", "javen", "tay trang"]):
        return "Nước tẩy trắng Javen"
    if any(k in folded for k in ["tay mau", "oxy active"]):
        return "Nước tẩy quần áo màu"
    if any(k in folded for k in ["xa vai", "nuoc xa"]):
        return "Nước xả vải"
    if any(k in folded for k in ["lau kinh"]):
        return "Nước lau kính"
    if any(k in folded for k in ["tinh dau", "treo xe", "nuoc hoa xe"]):
        return "Tinh dầu & Nước hoa"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. PARSE BUDGET & GỢI Ý THEO TẦM GIÁ / NGÂN SÁCH
# ─────────────────────────────────────────────────────────────────────────────
class PriceOperator(str, Enum):
    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"
    BETWEEN = "BETWEEN"
    EXACT = "EXACT"
    APPROX = "APPROX"


@dataclass(frozen=True)
class PriceConstraint:
    operator: PriceOperator
    target: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    inclusive_min: bool = True
    inclusive_max: bool = True
    currency: str = "VND"
    raw_span: str = ""
    confidence: float = 1.0

    def matches(self, price: int) -> bool:
        if self.operator == PriceOperator.LT:
            return self.max_value is not None and price < self.max_value
        if self.operator == PriceOperator.LTE:
            return self.max_value is not None and price <= self.max_value
        if self.operator == PriceOperator.GT:
            return self.min_value is not None and price > self.min_value
        if self.operator == PriceOperator.GTE:
            return self.min_value is not None and price >= self.min_value
        if self.operator == PriceOperator.EXACT:
            return self.target is not None and price == self.target
        lower_ok = self.min_value is None or price >= self.min_value
        upper_ok = self.max_value is None or price <= self.max_value
        return lower_ok and upper_ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator.value,
            "target": self.target,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "inclusive_min": self.inclusive_min,
            "inclusive_max": self.inclusive_max,
            "currency": self.currency,
            "raw_span": self.raw_span,
            "confidence": self.confidence,
        }


_MONEY_TOKEN_RE = re.compile(
    r"(?<![a-z0-9])(?P<number>\d+(?:[.,]\d+)?)(?![.,]\d)\s*"
    r"(?P<unit>trieu|tr|k|ngan|nghin|000|d|dong)?(?![a-z0-9])"
)
_MEASUREMENT_SUFFIX_RE = re.compile(r"^(kg|g|gam|ml|lit|l|chai|can|tui|goi|bo)\b")


def _money_value(number: str, unit: str) -> tuple[Optional[int], float]:
    """Chuẩn hóa một token tiền Việt về VND và trả confidence của đơn vị."""
    raw = number.strip()
    unit = unit.strip()
    try:
        if unit in {"trieu", "tr"}:
            return int(round(float(raw.replace(",", ".")) * 1_000_000)), 1.0
        if unit in {"k", "ngan", "nghin", "000"}:
            return int(round(float(raw.replace(",", ".")) * 1_000)), 1.0

        # 200.000đ / 200,000đ: dấu ngăn cách hàng nghìn, không phải số thập phân.
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
            return int(re.sub(r"[.,]", "", raw)), 0.98 if unit else 0.9

        value = float(raw.replace(",", "."))
        if unit in {"d", "dong"}:
            return int(round(value)), 1.0
        if value < 1_000:
            # Tương thích cách nói phổ biến "dưới 200" trong ngữ cảnh ngân sách,
            # nhưng hạ confidence vì người dùng không nói rõ nghìn/triệu.
            return int(round(value * 1_000)), 0.65
        return int(round(value)), 0.85
    except (TypeError, ValueError):
        return None, 0.0


def _extract_money_tokens(folded: str) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for match in _MONEY_TOKEN_RE.finditer(folded):
        unit = match.group("unit") or ""
        suffix = folded[match.end():].lstrip()
        if not unit and _MEASUREMENT_SUFFIX_RE.match(suffix):
            continue
        value, confidence = _money_value(match.group("number"), unit)
        if value is None:
            continue
        tokens.append({
            "value": value,
            "confidence": confidence,
            "start": match.start(),
            "end": match.end(),
            "raw": match.group(0),
        })
    return tokens


def _approx_bounds(target: int, tolerance: float) -> tuple[int, int]:
    return int(round(target * (1.0 - tolerance))), int(round(target * (1.0 + tolerance)))


def parse_price_constraint(text: str, approx_tolerance: float = 0.15) -> Optional[PriceConstraint]:
    """Parse comparator + số tiền thành constraint có kiểu dữ liệu và semantics rõ ràng."""
    original_lower = str(text or "").lower()
    folded = re.sub(r"\s+", " ", _fold(text)).strip()
    tokens = _extract_money_tokens(folded)
    if not tokens:
        return None

    # Khoảng A-B / từ A đến B. Cho phép đơn vị chỉ xuất hiện ở một đầu.
    if len(tokens) >= 2:
        first, second = tokens[0], tokens[1]
        connector = folded[first["end"]:second["start"]]
        prefix = folded[max(0, first["start"] - 12):first["start"]]
        if re.search(r"(?:-|–|—|\bden\b|\btoi\b|\bva\b)", connector) or re.search(r"\btu\s*$", prefix):
            low, high = sorted((first["value"], second["value"]))
            return PriceConstraint(
                operator=PriceOperator.BETWEEN,
                min_value=low,
                max_value=high,
                raw_span=folded[first["start"]:second["end"]],
                confidence=min(first["confidence"], second["confidence"]),
            )

    token = tokens[0]
    value = token["value"]
    confidence = token["confidence"]
    raw_span = token["raw"].strip()

    # Comparator rõ ràng phải thắng các từ đệm "tầm/khoảng".
    if re.search(r"(?:khong qua|toi da|do lai|quay dau|<=)", folded):
        return PriceConstraint(PriceOperator.LTE, max_value=value, inclusive_min=True, inclusive_max=True, raw_span=raw_span, confidence=confidence)
    if re.search(r"(?:it nhat|toi thieu|tu\s+[^,;]+\s+tro len|>=)", folded):
        return PriceConstraint(PriceOperator.GTE, min_value=value, inclusive_min=True, inclusive_max=True, raw_span=raw_span, confidence=confidence)
    if re.search(r"(?:duoi|thap hon|re hon|it hon|(?<!<)<(?![=>]))", folded):
        return PriceConstraint(PriceOperator.LT, max_value=value, inclusive_min=True, inclusive_max=False, raw_span=raw_span, confidence=confidence)
    if re.search(r"(?:tren|cao hon|lon hon|(?<!>)>(?![=]))", folded):
        return PriceConstraint(PriceOperator.GT, min_value=value, inclusive_min=False, inclusive_max=True, raw_span=raw_span, confidence=confidence)
    if re.search(r"\b(?:khoang|tam|quanh|gan|xap xi|loanh quanh)\b|~", folded) or re.search(r"\bcỡ\b", original_lower):
        low, high = _approx_bounds(value, approx_tolerance)
        return PriceConstraint(
            PriceOperator.APPROX,
            target=value,
            min_value=low,
            max_value=high,
            raw_span=raw_span,
            confidence=confidence,
        )
    has_explicit_exact = bool(re.search(r"\bđúng\b", original_lower)) or bool(
        re.search(r"(?:chinh xac|muc gia|ngan sach|\bgia\b)", folded)
    )
    if has_explicit_exact or confidence >= 0.9:
        return PriceConstraint(PriceOperator.EXACT, target=value, min_value=value, max_value=value, raw_span=raw_span, confidence=confidence)
    return None


def parse_budget_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """API tương thích cũ; logic mới nên dùng parse_price_constraint()."""
    constraint = parse_price_constraint(text)
    if constraint is None:
        return None, None
    if constraint.operator in {PriceOperator.LT, PriceOperator.LTE}:
        return 0, constraint.max_value
    if constraint.operator in {PriceOperator.GT, PriceOperator.GTE}:
        return constraint.min_value, None
    return constraint.min_value, constraint.max_value


def is_budget_inquiry(text: str) -> bool:
    """Nhận diện trực tiếp từ PriceConstraint, không dùng keyword gate riêng."""
    return parse_price_constraint(text) is not None


def is_price_extreme_inquiry(text: str) -> bool:
    folded = _fold(text)
    return bool(re.search(
        r"\b(mac nhat|dat nhat|cao nhat|gia cao nhat|gia mac nhat|gia dat nhat|"
        r"re nhat|gia re nhat|thap nhat|gia thap nhat)\b",
        folded,
    ))


def match_price_extreme(query: str, brand: str = "zeo", mode: Optional[str] = None) -> Optional[dict]:
    """Trả sản phẩm có giá cao nhất/thấp nhất từ Shopee catalog hiện hành."""
    folded = _fold(query)
    target_category = _detect_category_from_text(query)
    forced_mode = (mode or "").strip().lower()
    is_lowest = forced_mode == "lowest" or bool(re.search(r"\b(re nhat|gia re nhat|thap nhat|gia thap nhat)\b", folded))
    is_highest = forced_mode == "highest" or bool(re.search(r"\b(mac nhat|dat nhat|cao nhat|gia cao nhat|gia mac nhat|gia dat nhat)\b", folded))
    if not (is_lowest or is_highest):
        return None

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    brand_upper = brand.upper()
    candidates = []
    for item in catalog:
        item_brand = str(item.get("brand", "")).upper()
        if not (item_brand == brand_upper or (brand_upper == "ZEO" and item_brand in ["ZEO", "PANO", "OPLUS"])):
            continue
        if not item.get("in_stock", True):
            continue
        if target_category and item.get("category") != target_category:
            continue
        try:
            product = dict(item)
            product["_price_num"] = int(str(item.get("price", 0)).replace(".", "").replace(",", ""))
            candidates.append(product)
        except Exception:
            continue

    if not candidates:
        category_text = f" trong nhóm **{target_category}**" if target_category else ""
        reply = (
            f"Dạ hiện mình chưa tìm thấy sản phẩm còn hàng{category_text} để so sánh giá. "
            "Bạn muốn mình gợi ý theo nhóm nước giặt, rửa chén, lau sàn hay tẩy rửa không ạ?"
        )
        return {
            "matched": True,
            "intent": "shopee_price_extreme_no_result",
            "confidence": "high",
            "score": 0.98,
            "suggested_reply": reply,
            "selected_products": [],
            "no_results": True,
        }

    candidates.sort(key=lambda item: item["_price_num"], reverse=is_highest)
    selected = candidates[:3]
    mode_label = "mắc nhất" if is_highest else "rẻ nhất"
    category_text = f" trong nhóm **{target_category}**" if target_category else ""

    lines = []
    for index, product in enumerate(selected, start=1):
        price_str = _format_price(product.get("price"))
        original_str = _format_price(product.get("original_price"))
        discount_str = _format_discount(product.get("discount", ""))
        discount_text = f" (Giảm {discount_str} từ giá gốc {original_str})" if discount_str else ""
        url = product.get("link_shopee") or product.get("shopee_url") or "https://shopee.vn/zeovietnamofficial"
        lines.append(f"{index}. **{product['name']}** — Giá ưu đãi: **{price_str}**{discount_text}\n   👉 {url}")

    reply = (
        f"Dạ sản phẩm **{mode_label}**{category_text} hiện đang có trong Shopee catalog của ZeO là:\n\n"
        f"{chr(10).join(lines)}\n\n"
        "Giá có thể thay đổi theo voucher/sàn, bạn bấm link để xem ưu đãi mới nhất nha."
    )
    return {
        "matched": True,
        "intent": "shopee_price_extreme",
        "confidence": "high",
        "score": 0.99,
        "product_name": selected[0].get("name"),
        "shopee_url": selected[0].get("link_shopee") or selected[0].get("shopee_url"),
        "suggested_reply": reply,
        "matched_product": selected[0],
        "selected_products": selected,
        "price_extreme": "highest" if is_highest else "lowest",
    }


def match_products_by_budget(query: str, brand: str = "zeo") -> Optional[dict]:
    """Lọc và gợi ý các sản phẩm phù hợp nhất trong khoảng giá người dùng yêu cầu."""
    constraint = parse_price_constraint(query)
    if constraint is None:
        return None

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    # Category và tồn kho là hard constraints: không được fallback sang category khác.
    target_category = _detect_category_from_text(query)
    eligible = []
    for p in catalog:
        if not p.get("in_stock", True):
            continue
        if target_category and p.get("category") != target_category:
            continue
        try:
            price = int(str(p.get("price", 0)).replace(".", "").replace(",", ""))
            candidate = dict(p)
            candidate["_price_num"] = price
            eligible.append(candidate)
        except Exception:
            continue

    matched = [p for p in eligible if constraint.matches(p["_price_num"])]
    range_widened = False

    # APPROX: chỉ mở rộng một lần khi primary range không có kết quả.
    if not matched and constraint.operator == PriceOperator.APPROX and constraint.target is not None:
        expanded_min, expanded_max = _approx_bounds(constraint.target, 0.25)
        matched = [p for p in eligible if expanded_min <= p["_price_num"] <= expanded_max]
        range_widened = bool(matched)

    # APPROX ưu tiên độ gần ngân sách; các operator khác ưu tiên badge nghiệp vụ.
    def sort_p(p):
        badge = str(p.get("badge", ""))
        badge_rank = 1 if "BEST_SELLER" in badge else (2 if "NEW_ARRIVAL" in badge else 3)
        if constraint.operator == PriceOperator.APPROX and constraint.target is not None:
            return abs(p["_price_num"] - constraint.target), badge_rank
        return badge_rank, p["_price_num"]

    matched.sort(key=sort_p)

    # Chọn 3-4 sản phẩm tiêu biểu đa dạng nhóm
    selected = []
    seen_cats = set()
    for p in matched:
        c = p.get("category", "")
        if c not in seen_cats or len(selected) < 2:
            selected.append(p)
            seen_cats.add(c)
        if len(selected) >= 4:
            break

    if len(selected) < 3 and matched:
        selected = matched[:4]

    labels = {
        PriceOperator.LT: f"dưới {_format_price(constraint.max_value)}",
        PriceOperator.LTE: f"không quá {_format_price(constraint.max_value)}",
        PriceOperator.GT: f"trên {_format_price(constraint.min_value)}",
        PriceOperator.GTE: f"từ {_format_price(constraint.min_value)} trở lên",
        PriceOperator.BETWEEN: f"từ {_format_price(constraint.min_value)} đến {_format_price(constraint.max_value)}",
        PriceOperator.EXACT: f"đúng {_format_price(constraint.target)}",
        PriceOperator.APPROX: f"khoảng {_format_price(constraint.target)}",
    }
    budget_label = labels[constraint.operator]

    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "CFC Cò Bay"

    if not matched:
        category_text = f" thuộc nhóm **{target_category}**" if target_category else ""
        reply = (
            f"Dạ hiện mình chưa tìm thấy sản phẩm còn hàng{category_text} phù hợp mức giá **{budget_label}**. "
            "Bạn có muốn mình nới ngân sách hoặc gợi ý lựa chọn gần nhất không ạ?"
        )
        return {
            "matched": True,
            "intent": "shopee_budget_filter_no_result",
            "confidence": "high",
            "score": 1.0,
            "suggested_reply": reply,
            "shopee_url": general_link,
            "selected_products": [],
            "price_constraint": constraint.to_dict(),
            "range_widened": False,
            "no_results": True,
        }

    lines = []
    medals = ["1.", "2.", "3.", "4."]
    for idx, p in enumerate(selected, start=1):
        num = medals[idx - 1] if idx <= len(medals) else f"{idx}."
        price_str = _format_price(p.get("price"))
        d_str = _format_discount(p.get("discount"))
        disc = f" (Giảm {d_str})" if d_str else ""
        lines.append(f"{num} **{p['name']}** — Giá ưu đãi: **{price_str}**{disc}")

    products_text = "\n".join(lines)
    widened_note = " (đã mở rộng nhẹ để lấy lựa chọn gần nhất)" if range_widened else ""
    reply = (
        f"Dạ trong phân khúc giá **{budget_label}**{widened_note}, các lựa chọn phù hợp của {brand_display} gồm có:\n\n"
        f"{products_text}\n\n"
        f"👉 Bạn có thể xem trọn bộ ưu đãi và áp mã Freeship Extra tại gian hàng Shopee: {general_link}\n"
        f"Bạn đang quan tâm dòng giặt xả, rửa chén hay tẩy rửa gia đình để mình tư vấn chi tiết hơn nha! 💙"
    )

    return {
        "matched": True,
        "intent": "shopee_budget_filter",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
        "selected_products": [{k: v for k, v in p.items() if k != "_price_num"} for p in selected],
        "price_constraint": constraint.to_dict(),
        "range_widened": range_widened,
        "no_results": False,
    }


def is_bestseller_inquiry(text: str) -> bool:
    """Kiểm tra xem khách có hỏi về sản phẩm bán chạy / hot nhất không."""
    folded = _fold(text)
    return bool(re.search(r"\b(ban chay|hot nhat|top ban chay|mat hang ban chay|san pham hot|loai nao ban chay|dong nao ban chay|nhieu nguoi mua|mua nhieu nhat|top seller|best seller|top san pham)\b", folded))


def is_new_arrival_inquiry(text: str) -> bool:
    """Kiểm tra xem khách có hỏi về sản phẩm mới nhất / mới ra mắt không."""
    folded = _fold(text)
    return bool(re.search(r"\b(moi ra|moi nhat|hang moi|san pham moi|dong moi|moi ve|moi ra mat|hang moi ve|new arrival|vua ra)\b", folded))


def match_best_sellers(query: str, brand: str = "zeo") -> dict:
    """Trả lời danh sách Top sản phẩm Bán Chạy Nhất (hỗ trợ lọc theo danh mục)."""
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    brand_display = "ZeO & PANO" if brand.lower() == "zeo" else "CFC Cò Bay"

    catalog = load_shopee_catalog(brand=brand)
    target_category = _detect_category_from_text(query)

    if target_category:
        cat_items = [p for p in catalog if p.get("category") == target_category and p.get("in_stock", True)]
        cat_items.sort(key=lambda p: 1 if "BEST_SELLER" in str(p.get("badge", "")) else 2)
        top_items = cat_items[:3]
        if top_items:
            best_one = top_items[0]
            price_str = _format_price(best_one.get("price"))
            d_str = _format_discount(best_one.get("discount"))
            disc = f" (Giảm {d_str})" if d_str else ""
            url = best_one.get("link_shopee") or general_link

            reply = (
                f"Dạ trong nhóm **{target_category}**, dòng sản phẩm **BÁN CHẠY NHẤT** hiện nay là:\n\n"
                f"🥇 **{best_one['name']}**\n"
                f"• **Giá ưu đãi:** **{price_str}**{disc}\n"
                f"• **Ưu đãi:** Freeship Extra toàn quốc\n\n"
                f"👉 Link đặt mua chính hãng trên Shopee Mall: {url}\n\n"
                f"Bạn cần tư vấn thêm về dung tích hay mùi hương nào cứ nhắn mình hỗ trợ nhé! 💙"
            )
            return {
                "matched": True,
                "intent": "bestsellers",
                "confidence": "high",
                "score": 0.99,
                "suggested_reply": reply,
                "shopee_url": url,
            }

    bestsellers = [p for p in catalog if "BEST_SELLER" in str(p.get("badge", ""))]
    if not bestsellers:
        bestsellers = [p for p in catalog if p.get("in_stock", True)][:7]

    lines = []
    medals = ["🥇", "🥈", "🥉", "⭐️", "⭐️", "⭐️", "⭐️", "⭐️", "⭐️", "⭐️"]
    for idx, p in enumerate(bestsellers[:10], start=1):
        medal = medals[idx - 1] if idx <= len(medals) else "⭐️"
        price_str = _format_price(p.get("price"))
        d_str = _format_discount(p.get("discount"))
        disc = f" ({d_str})" if d_str else ""
        lines.append(f"{idx}. {medal} **{p['name']}** - Giá: **{price_str}**{disc}")

    products_text = "\n".join(lines)
    reply = (
        f"Dạ các dòng sản phẩm **BÁN CHẠY NHẤT** hiện nay của {brand_display} trên Shopee Mall gồm có:\n\n"
        f"{products_text}\n\n"
        f"👉 Xem toàn bộ gian hàng và nhận mã Freeship Extra tại: {general_link}\n"
        f"Bạn quan tâm dòng sản phẩm nào cứ nhắn mình tư vấn kỹ hơn nhé! 💙"
    )

    return {
        "matched": True,
        "intent": "bestsellers",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


def match_new_arrivals(query: str, brand: str = "zeo") -> dict:
    """Trả lời danh sách sản phẩm Mới Ra Mắt (hỗ trợ lọc theo danh mục)."""
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    brand_display = "ZeO & PANO" if brand.lower() == "zeo" else "CFC Cò Bay"

    catalog = load_shopee_catalog(brand=brand)
    target_category = _detect_category_from_text(query)

    if target_category:
        cat_items = [p for p in catalog if p.get("category") == target_category and p.get("in_stock", True)]
        cat_items.sort(key=lambda p: 1 if "NEW_ARRIVAL" in str(p.get("badge", "")) else 2)
        top_items = cat_items[:3]
        if top_items:
            best_one = top_items[0]
            price_str = _format_price(best_one.get("price"))
            d_str = _format_discount(best_one.get("discount"))
            disc = f" (Giảm {d_str})" if d_str else ""
            url = best_one.get("link_shopee") or general_link

            reply = (
                f"Dạ trong nhóm **{target_category}**, dòng sản phẩm **MỚI RA MẮT** nổi bật nhất là:\n\n"
                f"✨ **{best_one['name']}**\n"
                f"• **Giá ưu đãi:** **{price_str}**{disc}\n"
                f"• **Ưu đãi:** Freeship Extra toàn quốc\n\n"
                f"👉 Xem chi tiết và nhận quà tặng kèm tại: {url}\n\n"
                f"Bạn cần tư vấn chi tiết hơn cứ nhắn mình nhé! 💙"
            )
            return {
                "matched": True,
                "intent": "new_arrivals",
                "confidence": "high",
                "score": 0.99,
                "suggested_reply": reply,
                "shopee_url": url,
            }

    new_items = [p for p in catalog if "NEW_ARRIVAL" in str(p.get("badge", ""))]
    if not new_items:
        new_items = [p for p in catalog if p.get("in_stock", True)][:7]

    lines = []
    for idx, p in enumerate(new_items[:10], start=1):
        price_str = _format_price(p.get("price"))
        d_str = _format_discount(p.get("discount"))
        disc = f" ({d_str})" if d_str else ""
        lines.append(f"{idx}. ✨ **{p['name']}** - Giá ưu đãi: **{price_str}**{disc}")

    products_text = "\n".join(lines)
    reply = (
        f"Dạ các dòng sản phẩm **MỚI RA MẮT** cực hot của {brand_display} trên Shopee Mall gồm có:\n\n"
        f"{products_text}\n\n"
        f"👉 Xem chi tiết các sản phẩm mới và nhận quà tặng kèm tại: {general_link}\n"
        f"Bạn nhắn mình nhu cầu giặt giũ / tẩy rửa để mình gợi ý combo phù hợp nhất nha! 💙"
    )

    return {
        "matched": True,
        "intent": "new_arrivals",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. MATCH BÁO GIÁ & GỬI LINK CHO SẢN PHẨM ĐÍCH DANH
# ─────────────────────────────────────────────────────────────────────────────
def match_specific_product_price(query: str, brand: str = "zeo", context: Optional[dict] = None) -> Optional[dict]:
    """
    Nhận diện câu hỏi giá cho một sản phẩm cụ thể (vd: xin giá nước rửa chén vitamin e, bột giặt pano bao nhiêu, can 3.8kg giá bao nhiêu...).
    Trả về giá niêm yết, giá khuyến mãi và link Shopee Mall trực tiếp.
    """
    query_folded = _fold(query)

    # Tách bỏ tên sản phẩm được prepend / bổ sung trong ngoặc để chỉ kiểm tra đúng ý định người dùng
    user_part = query_folded.split("(", 1)[0]
    if "]" in user_part:
        user_part = user_part.split("]", 1)[-1]
    user_part = re.sub(r"\bgia re\b", "", user_part)
    target_category = _detect_category_from_text(user_part)

    # Loại trừ câu hỏi về tính năng / hiệu quả làm sạch / tẩy vết bẩn / dùng ổn không
    if re.search(r"\b(tay duoc|tay sach|vet mau|vet o|vet ban|dung on|dung tot|co tot|co sach|co tay|on ko|on khong|tay trang|thom ko|thanh phan|cong dung|huong dan|cach dung|di ung|an da tay)\b", user_part):
        return None

    # Loại trừ câu hỏi về liều lượng / cách dùng hoặc chính sách sỉ/đại lý
    if re.search(r"\b(bao nhieu (?:bo|kg|lit|goi|can|gam|muong|nap)|cho \d+ bo|bon bao nhieu|bao nhieu do|lieu luong|cach dung)\b", user_part):
        return None
    if re.search(r"\b(gia si|mua si|lay si|chinh sach si|chiet khau|dai ly|kinh doanh zeo|nhap so luong lon)\b", user_part):
        return None

    # Kiểm tra xem có từ khóa hỏi giá rõ ràng bằng word boundary không
    has_price_ask = bool(re.search(r"\b(gia|gia ban|gia ca|bao nhieu|nhieu tien|bao gia|bang gia|xin gia|ton bao nhieu|mua het bao|gia sao|gia the nao|y la gia|gia bao nhieu)\b", user_part))
    if not has_price_ask:
        return None

    explicit_product_terms = [
        "rua chen", "rua bat", "bot giat", "nuoc giat", "lau san", "toilet", "bon cau",
        "javel", "javen", "tay mau", "xa vai", "nuoc xa", "lau kinh", "treo xe", "tinh dau",
        "vitamin e", "nha dam", "cam chanh", "oai huong", "tao dua", "bio enzyme", "2in1",
        "nano clean", "pano", "oplus", "zif",
    ]
    has_explicit_product_in_user_text = bool(target_category) or any(k in user_part for k in explicit_product_terms)

    # Chỉ bổ sung ngữ cảnh khi câu hỏi thiếu định danh sản phẩm, ví dụ "can 3.8kg giá bao nhiêu".
    # Nếu khách đã nêu rõ "nước xả vải"/"nước rửa chén", context cũ không được làm lệch matching.
    if context and isinstance(context, dict) and not has_explicit_product_in_user_text:
        active_entities = context.get("active_entities")
        if isinstance(active_entities, list):
            query_folded = query_folded + " " + " ".join(_fold(e) for e in active_entities)
        elif isinstance(active_entities, dict):
            query_folded = query_folded + " " + " ".join(_fold(v) for v in active_entities.values() if isinstance(v, str))
        
        last_prods = context.get("last_products_shown")
        if isinstance(last_prods, list) and last_prods:
            query_folded = query_folded + " " + " ".join(_fold(p.get("name", "")) for p in last_prods if isinstance(p, dict))

        last_bot_reply = _fold(context.get("last_bot_reply", ""))
        if "rua chen" in last_bot_reply or "pano" in last_bot_reply:
            query_folded += " rua chen pano"
        elif "nuoc giat" in last_bot_reply:
            query_folded += " nuoc giat"

    # Phải có từ khóa định danh sản phẩm
    has_product_mention = any(k in query_folded for k in [
        "rua chen", "rua bat", "bot giat", "nuoc giat", "lau san", "toilet", "bon cau",
        "javel", "javen", "tay mau", "xa vai", "lau kinh", "treo xe", "tinh dau",
        "vitamin e", "nha dam", "cam chanh", "oai huong", "tao dua", "bio enzyme", "2in1",
        "nano clean", "pano", "oplus", "zif", "can"
    ])
    if not has_product_mention:
        return None

    # Phải có tên thương hiệu con hoặc biến thể hoặc mùi hương / quy cách cụ thể để báo giá chính xác
    has_specific_subbrand_or_variant = any(k in query_folded for k in [
        "pano", "oplus", "zif", "javen", "javel", "bio enzyme", "nano clean", "2in1", "4in1",
        "vitamin e", "nha dam", "cam chanh", "oai huong", "tao dua", "trai cay", "chanh",
        "toilet", "bon cau", "lau kinh", "treo xe", "tinh dau", "tay mau", "chai", "zeo",
        "300g", "400g", "720g", "2.4kg", "3.5kg", "3.8kg", "5.5kg", "9kg", "650ml", "1000ml"
    ])
    if not has_specific_subbrand_or_variant:
        return None

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    brand_products = [
        p for p in catalog
        if p.get("brand", "").upper() == brand.upper() or (brand.upper() == "ZEO" and p.get("brand", "").upper() in ["ZEO", "PANO", "OPLUS"])
    ]
    if not brand_products:
        brand_products = catalog
    if target_category:
        brand_products = [
            p for p in brand_products
            if p.get("category") == target_category and p.get("in_stock", True)
        ]
        if not brand_products:
            return None

        has_specific_variant = bool(re.search(
            r"\b(combo|goi|can|chai|tui|hop)\b|nano clean|"
            r"\b(300g|400g|720g|750g|1kg|1\.8kg|2\.4kg|2\.7kg|3\.5kg|3\.8kg|5\.5kg|9kg|650ml|1000ml)\b",
            user_part,
        ))
        if len(brand_products) > 1 and not has_specific_variant:
            lines = []
            for idx, product in enumerate(brand_products[:3], start=1):
                price_str = _format_price(product.get("price"))
                orig_str = _format_price(product.get("original_price"))
                d_str = _format_discount(product.get("discount", ""))
                disc_text = f" (Giảm {d_str})" if d_str else ""
                url = product.get("link_shopee") or product.get("shopee_url") or "https://shopee.vn/zeovietnamofficial"
                lines.append(f"{idx}. **{product['name']}** — Giá ưu đãi: **{price_str}**{disc_text}\n   👉 {url}")

            reply = (
                f"Dạ nhóm **{target_category}** của ZeO hiện có các lựa chọn chính hãng trên Shopee Mall:\n\n"
                f"{chr(10).join(lines)}\n\n"
                "Giá có thể thay đổi theo voucher/sàn, bạn bấm link để xem ưu đãi mới nhất nha."
            )
            return {
                "matched": True,
                "intent": "specific_product_pricing",
                "confidence": "high",
                "score": 0.99,
                "product_name": target_category,
                "shopee_url": brand_products[0].get("link_shopee") or brand_products[0].get("shopee_url"),
                "suggested_reply": reply,
                "matched_product": brand_products[0],
                "selected_products": brand_products[:3],
            }

    best_match = None
    highest_score = 0

    for prod in brand_products:
        prod_name_folded = _fold(prod.get("name", ""))
        keywords = prod.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(";") if k.strip()]

        score = 0
        cat_folded = _fold(prod.get("category", ""))
        if cat_folded and cat_folded in query_folded:
            score += 5

        for kw in keywords:
            kw_folded = _fold(kw)
            if kw_folded and kw_folded in query_folded:
                score += 4

        words = prod_name_folded.split()
        for w in words:
            if len(w) >= 3 and w in query_folded:
                score += 1

        variants = prod.get("variants", [])
        if isinstance(variants, str):
            variants = [v.strip() for v in variants.split(";") if v.strip()]
        for v in variants:
            v_folded = _fold(v)
            if v_folded and v_folded in query_folded:
                score += 3

        if score > highest_score:
            highest_score = score
            best_match = prod

    # Ngưỡng tin cậy cao: ít nhất 7 điểm (đảm bảo khớp đúng sản phẩm chứ không bắt nhầm)
    if not best_match or highest_score < 7:
        return None

    price_str = _format_price(best_match.get("price"))
    orig_str = _format_price(best_match.get("original_price"))
    d_str = _format_discount(best_match.get("discount", ""))
    disc_text = f" (Đang giảm {d_str} từ giá gốc {orig_str})" if d_str else ""
    url = best_match.get("link_shopee") or best_match.get("shopee_url") or "https://shopee.vn/zeovietnamofficial"

    reply = (
        f"Dạ giá của **{best_match['name']}** chính hãng hiện tại là:\n\n"
        f"• **Giá ưu đãi:** **{price_str}**{disc_text}\n"
        f"• **Ưu đãi sàn:** Hỗ trợ mã Freeship Extra toàn quốc\n\n"
        f"👉 Bạn có thể bấm vào link Shopee Mall sau để đặt hàng giao tận nơi nha:\n"
        f"{url}\n\n"
        f"Cần tư vấn thêm quy cách hay mùi hương nào bạn cứ nhắn mình hỗ trợ nhé! 💙"
    )

    return {
        "matched": True,
        "intent": "specific_product_pricing",
        "confidence": "high",
        "score": 0.99,
        "product_name": best_match.get("name"),
        "shopee_url": url,
        "suggested_reply": reply,
        "matched_product": best_match,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. TƯ VẤN THEO NHU CẦU NỐI TIẾP (NEED-BASED MULTI-TURN) - LOAD 100% REDIS
# ─────────────────────────────────────────────────────────────────────────────
def match_need_preference(need_type: str, brand: str = "zeo") -> Optional[dict]:
    """Tư vấn thông minh khi khách chọn nhu cầu: tiết kiệm, thơm lâu, sạch sâu, dịu nhẹ — Load 100% động từ Redis catalog."""
    catalog = load_shopee_catalog(brand=brand)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    if need_type == "tiet_kiem":
        matched = [
            p for p in catalog
            if any(term in _fold(p.get("name", "")) for term in ["oplus", "pano", "can to", "tiet kiem", "gia re", "5.5kg", "3.8kg"])
        ][:3]
        lines = []
        for i, p in enumerate(matched, 1):
            p_price = _format_price(p.get("price"))
            p_disc = _format_discount(p.get("discount"))
            disc_text = f" (Giảm {p_disc})" if p_disc else ""
            p_url = p.get("link_shopee") or general_link
            lines.append(f"{i}. ⭐️ **{p['name']}** — Giá: **{p_price}**{disc_text}\n   👉 {p_url}")
        items_str = "\n".join(lines) if lines else (
            f"1. ⭐️ **Bột giặt Oplus 4in1** (Giá từ 66.000đ)\n"
            f"2. ⭐️ **Bột giặt Pano Hương Cam Chanh** (Chỉ từ 46.350đ)\n"
            f"3. ⭐️ **Nước giặt Pano Can to 3.8kg** (Giá 123.291đ)"
        )

        reply = (
            "Dạ nếu bạn đang ưu tiên **tiết kiệm chi phí**, bên mình gợi ý các lựa chọn kinh tế nhất trên Shopee Mall:\n\n"
            f"{items_str}\n\n"
            f"👉 Xem toàn bộ ưu đãi tại: {general_link}\n"
            "Bạn muốn chọn túi nhỏ dùng thử hay can lớn để tiết kiệm tối đa ạ? 💙"
        )
    elif need_type == "thom_lau":
        matched = [
            p for p in catalog
            if any(term in _fold(p.get("name", "")) for term in ["huong nuoc hoa", "oai huong", "luu huong", "fresh", "warmish", "elegant", "active", "xa vai", "tinh dau"])
        ][:3]
        lines = []
        for i, p in enumerate(matched, 1):
            p_price = _format_price(p.get("price"))
            p_disc = _format_discount(p.get("discount"))
            disc_text = f" (Giảm {p_disc})" if p_disc else ""
            p_url = p.get("link_shopee") or general_link
            lines.append(f"{i}. 🌸 **{p['name']}** — Giá: **{p_price}**{disc_text}\n   👉 {p_url}")
        items_str = "\n".join(lines) if lines else (
            f"1. 🌸 **Nước giặt & Bột giặt PANO Hương Nước Hoa Pháp**\n"
            f"2. 🌸 **Nước giặt 2in1 Oplus Hương Nước Hoa Pháp**\n"
            f"3. 🌸 **Combo Nước xả vải Nano Clean ZeO**"
        )

        reply = (
            "Dạ với nhu cầu **lưu hương thơm lâu quyến rũ**, bạn không nên bỏ qua các dòng sản phẩm hương nước hoa Pháp:\n\n"
            f"{items_str}\n\n"
            f"👉 Bạn có thể đặt mua ngay tại: {general_link}\n"
            "Bạn thích phong cách hương nước hoa nồng nàn hay hương hoa dịu nhẹ thanh mát hơn ạ? 💙"
        )
    elif need_type == "sach_sau":
        matched = [
            p for p in catalog
            if any(term in _fold(p.get("name", "")) for term in ["enzyme", "active", "sach sau", "tay mau", "toilet", "dam dac"])
        ][:3]
        lines = []
        for i, p in enumerate(matched, 1):
            p_price = _format_price(p.get("price"))
            p_disc = _format_discount(p.get("discount"))
            disc_text = f" (Giảm {p_disc})" if p_disc else ""
            p_url = p.get("link_shopee") or general_link
            lines.append(f"{i}. ⚡️ **{p['name']}** — Giá: **{p_price}**{disc_text}\n   👉 {p_url}")
        items_str = "\n".join(lines) if lines else (
            f"1. ⚡️ **Bột giặt ZeO Sinh Học (Công nghệ Enzyme Thụy Điển)**\n"
            f"2. ⚡️ **Nước giặt Pano Active**\n"
            f"3. ⚡️ **Nước tẩy quần áo màu Oxy Active ZeO**"
        )

        reply = (
            "Dạ với nhu cầu **sạch sâu đánh bay vết bẩn cứng đầu**, dòng sản phẩm tối ưu nhất là:\n\n"
            f"{items_str}\n\n"
            f"👉 Tham khảo gian hàng chính hãng tại: {general_link}\n"
            "Bạn đang cần xử lý loại vết bẩn nào cứ nhắn mình tư vấn giải pháp phù hợp nha! 💙"
        )
    elif need_type == "diu_nhe":
        matched = [
            p for p in catalog
            if any(term in _fold(p.get("name", "")) for term in ["nha dam", "vitamin e", "diu da tay", "chanh tu nhien", "aloe"])
        ][:3]
        lines = []
        for i, p in enumerate(matched, 1):
            p_price = _format_price(p.get("price"))
            p_disc = _format_discount(p.get("discount"))
            disc_text = f" (Giảm {p_disc})" if p_disc else ""
            p_url = p.get("link_shopee") or general_link
            lines.append(f"{i}. 🌿 **{p['name']}** — Giá: **{p_price}**{disc_text}\n   👉 {p_url}")
        items_str = "\n".join(lines) if lines else (
            f"1. 🌿 **Bột giặt ZeO Nha Đam (Aloe Vera)**\n"
            f"2. 🌿 **Nước rửa chén PANO Vitamin E**\n"
            f"3. 🌿 **Nước rửa chén ZeO / ZIF 100% Cốt Chanh Tự Nhiên**"
        )

        reply = (
            "Dạ nếu bạn cần sản phẩm **dịu nhẹ, bảo vệ da tay và an toàn cho quần áo em bé / da nhạy cảm**:\n\n"
            f"{items_str}\n\n"
            f"👉 Xem chi tiết tại: {general_link}\n"
            "Bạn cần mua nước rửa chén hay bột giặt dịu da tay ạ? 💙"
        )
    else:
        return None

    return {
        "matched": True,
        "intent": f"need_consultation_{need_type}",
        "confidence": "high",
        "score": 0.98,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


def is_bulk_or_restaurant_inquiry(text: str) -> bool:
    """Kiểm tra xem khách có hỏi về can lớn, mua cho quán ăn, nhà hàng, bếp ăn không."""
    folded = _fold(text)
    return bool(re.search(r"\b(quan an|nha hang|bep an|dung cho bep|can lon|can to|can 3\.8kg|can 3,8kg|can 9kg|tui 5\.5kg|tui 5,5kg|dung cho quan|mua dung cho quan|mua can|dung can|so luong lon|can lon nhat)\b", folded))


def match_bulk_or_restaurant_need(query: str, brand: str = "zeo") -> Optional[dict]:
    """Tư vấn thông minh cho khách hàng quán ăn, nhà hàng, bếp ăn cần can lớn tiết kiệm chi phí — Load 100% từ Redis catalog."""
    folded = _fold(query)
    catalog = load_shopee_catalog(brand=brand)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    # 1. Nước rửa chén can lớn (Quán ăn / Nhà hàng / Bếp)
    if any(k in folded for k in ["rua chen", "rua bat", "chen", "bat", "bep", "quan an", "nha hang"]):
        matched_items = [
            p for p in catalog
            if any(term in _fold(p.get("name", "")) for term in ["3.8kg", "9kg", "nha hang", "quan an", "can"])
            and ("rua chen" in _fold(p.get("category", "")) or "rua chen" in _fold(p.get("name", "")))
        ]
        if not matched_items:
            matched_items = [p for p in catalog if "rua chen" in _fold(p.get("category", ""))][:2]

        lines = []
        for i, p in enumerate(matched_items[:3], 1):
            p_name = p.get("name", "")
            p_price = _format_price(p.get("price"))
            p_disc = _format_discount(p.get("discount"))
            disc_text = f" (Giảm {p_disc})" if p_disc else ""
            p_url = p.get("link_shopee") or general_link
            lines.append(f"{i}. ⭐️ **{p_name}** — Giá ưu đãi: **{p_price}**{disc_text}\n   👉 Mua ngay: {p_url}")

        items_str = "\n".join(lines)
        reply = (
            "Dạ đối với quán ăn, nhà hàng, bếp ăn cần can lớn tiết kiệm chi phí tối đa, ZeO Vietnam có các dòng can lớn chuyên dụng:\n\n"
            f"{items_str}\n\n"
            f"👉 Bạn có thể đặt mua trực tiếp tại Shopee Mall: {general_link}\n"
            "Nếu bạn cần mua số lượng lớn định kỳ hàng tháng cho quán, bạn để lại Số Điện Thoại và Khu Vực để phòng kinh doanh B2B gửi bảng giá sỉ chiết khấu tốt nhất nha! 💙"
        )
        return {
            "matched": True,
            "intent": "pano_dishwashing_product_overview",
            "confidence": "high",
            "score": 0.99,
            "suggested_reply": reply,
            "shopee_url": general_link,
            "products": matched_items,
        }

    # 2. Giặt giũ can lớn (Nước giặt can 3.8kg / Bột giặt 5.5kg)
    if any(k in folded for k in ["giat", "quan ao", "do giat", "tiem giat", "khach san"]):
        matched_items = [
            p for p in catalog
            if any(term in _fold(p.get("name", "")) for term in ["3.8kg", "3.5kg", "5.5kg", "can"])
            and ("giat" in _fold(p.get("category", "")) or "giat" in _fold(p.get("name", "")))
        ]
        if not matched_items:
            matched_items = [p for p in catalog if "giat" in _fold(p.get("category", ""))][:2]

        lines = []
        for i, p in enumerate(matched_items[:3], 1):
            p_name = p.get("name", "")
            p_price = _format_price(p.get("price"))
            p_disc = _format_discount(p.get("discount"))
            disc_text = f" (Giảm {p_disc})" if p_disc else ""
            p_url = p.get("link_shopee") or general_link
            lines.append(f"{i}. ⭐️ **{p_name}** — Giá ưu đãi: **{p_price}**{disc_text}\n   👉 Mua ngay: {p_url}")

        items_str = "\n".join(lines)
        reply = (
            "Dạ đối với nhu cầu giặt giũ can lớn tiết kiệm cho gia đình đông người hoặc tiệm giặt:\n\n"
            f"{items_str}\n\n"
            f"👉 Link gian hàng Shopee Mall chính hãng: {general_link}\n"
            "Bạn muốn chọn dạng Nước giặt can to hay Bột giặt bao 5.5kg ạ? 💙"
        )
        return {
            "matched": True,
            "intent": "zeo_laundry_product_overview",
            "confidence": "high",
            "score": 0.99,
            "suggested_reply": reply,
            "shopee_url": general_link,
            "products": matched_items,
        }

    return None


def is_skin_care_dishwashing_inquiry(text: str) -> bool:
    """Kiểm tra xem khách có băn khoăn về ăn da tay, tróc da tay khi rửa chén / giặt đồ không."""
    folded = _fold(text)
    has_skin_issue = bool(re.search(r"\b(an da tay|an tay|troc da|troc tay|kho da|kho tay|diu da tay|hai da tay|rat da|da nhay cam|hai tay|rat tay|di ung|diu nhe da|khong hai da)\b", folded))
    has_product = any(k in folded for k in ["rua chen", "rua bat", "nuoc rua", "bot giat", "nuoc giat", "tay"])
    return has_skin_issue and has_product


def match_skin_care_dishwashing(query: str, brand: str = "zeo") -> Optional[dict]:
    """Tư vấn chuyên sâu khi khách hàng băn khoăn về ăn da tay, tróc da tay khi dùng nước rửa chén / giặt đồ — Load 100% từ Redis catalog."""
    folded = _fold(query)
    catalog = load_shopee_catalog(brand=brand)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    matched_items = [
        p for p in catalog
        if any(term in _fold(p.get("name", "")) for term in ["vitamin e", "nha dam", "diu da tay", "chanh tu nhien"])
        and ("rua chen" in _fold(p.get("category", "")) or "rua chen" in _fold(p.get("name", "")))
    ]

    lines = []
    for i, p in enumerate(matched_items[:3], 1):
        p_name = p.get("name", "")
        p_price = _format_price(p.get("price"))
        p_disc = _format_discount(p.get("discount"))
        disc_text = f" (Giảm {p_disc})" if p_disc else ""
        p_url = p.get("link_shopee") or general_link
        lines.append(f"{i}. 🌿 **{p_name}** — Giá ưu đãi: **{p_price}**{disc_text}\n   👉 Link đặt mua: {p_url}")

    items_str = "\n".join(lines) if lines else (
        f"1. 🌿 **Nước rửa chén PANO Vitamin E** — Dưỡng ẩm bảo vệ da tay.\n"
        f"2. 🌿 **Nước rửa chén Oplus Nha Đam** — Dịu nhẹ êm dịu cho da mẫn cảm."
    )

    reply = (
        "Dạ nếu tay bạn mỏng, nhạy cảm hoặc dễ khô ráp khi rửa bát, mình khuyên ưu tiên các dòng có định hướng dịu nhẹ/dưỡng ẩm như Vitamin E, Nha Đam hoặc Chanh tự nhiên.\n\n"
        "Mình không cam kết tuyệt đối “không ăn da tay” cho mọi cơ địa; nếu da đang kích ứng, bạn nên dùng găng tay hoặc thử lượng nhỏ trước nha.\n\n"
        f"{items_str}\n\n"
        f"👉 Bạn có thể xem thêm tại Shopee Mall: {general_link}\n"
        "Cần tư vấn thêm quy cách nào bạn cứ nhắn mình hỗ trợ nhé! 💙"
    )
    return {
        "matched": True,
        "intent": "pano_dishwashing_features",
        "confidence": "high",
        "score": 0.99,
        "suggested_reply": reply,
        "shopee_url": general_link,
        "products": matched_items,
    }


def is_baby_or_sensitive_laundry_inquiry(text: str) -> bool:
    """Kiểm tra câu hỏi giặt giũ cho trẻ em, em bé, con nít hoặc da nhạy cảm."""
    folded = _fold(text)
    has_baby = bool(re.search(r"\b(em be|con nit|tre em|tre nho|so sinh|da nhay cam|di ung da|diu nhe)\b", folded))
    has_laundry = any(k in folded for k in ["giat", "bot giat", "nuoc giat", "xa vai", "quan ao", "do em be", "do tre"])
    return has_baby and (has_laundry or "giat" in folded)


def match_baby_or_sensitive_laundry(query: str, brand: str = "zeo") -> Optional[dict]:
    """Tư vấn dòng giặt xả dịu nhẹ, an toàn cho trẻ nhỏ và da nhạy cảm."""
    catalog = load_shopee_catalog(brand=brand)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    matched_items = [
        p for p in catalog
        if any(term in _fold(p.get("name", "")) for term in ["nha dam", "bio enzyme", "nano clean", "diu nhe"])
    ]

    lines = []
    for i, p in enumerate(matched_items[:3], 1):
        p_name = p.get("name", "")
        p_price = _format_price(p.get("price"))
        p_disc = _format_discount(p.get("discount"))
        disc_text = f" (Giảm {p_disc})" if p_disc else ""
        p_url = p.get("link_shopee") or general_link
        lines.append(f"{i}. 🌿 **{p_name}** — Giá ưu đãi: **{p_price}**{disc_text}\n   👉 Link Shopee: {p_url}")

    items_str = "\n".join(lines) if lines else (
        "1. 🌿 **Bột giặt ZeO Nha Đam** — Dịu nhẹ sạch vết bẩn, an toàn cho da mẫn cảm.\n"
        "2. 🌿 **Nước giặt Bio Enzyme ZeO** — Men sinh học đánh bay vết bẩn an toàn, không kích ứng da."
    )

    reply = (
        "Dạ đối với quần áo trẻ nhỏ, em bé hoặc người có làn da nhạy cảm, bên mình khuyên dùng các dòng giặt sinh học dịu nhẹ sau:\n\n"
        f"{items_str}\n\n"
        "Các lựa chọn này được định hướng dịu nhẹ hơn cho nhu cầu giặt xả hằng ngày. Hiện dữ liệu chat chưa có chứng nhận da liễu riêng để mình cam kết tuyệt đối cho mọi cơ địa, nên nếu bé có da quá nhạy cảm bạn nên thử lượng nhỏ trước nha. 💙\n"
        f"👉 Link gian hàng chính hãng: {general_link}"
    )
    return {
        "matched": True,
        "intent": "zeo_laundry_product_overview",
        "confidence": "high",
        "score": 0.99,
        "suggested_reply": reply,
        "shopee_url": general_link,
        "products": matched_items,
    }


def is_front_load_washer_inquiry(text: str) -> bool:
    """Kiểm tra câu hỏi giặt máy cửa trước, máy cửa ngang, ít bọt hoặc trào bọt."""
    folded = _fold(text)
    return bool(re.search(r"\b(cua truoc|cua ngang|it bot|trao bot|co bi trao bot|may giat cua truoc|may giat cua ngang|may cua truoc|may cua ngang)\b", folded))


def match_front_load_washer(query: str, brand: str = "zeo") -> Optional[dict]:
    """Tư vấn nước giặt công thức đậm đặc ít bọt an toàn cho máy giặt cửa trước."""
    catalog = load_shopee_catalog(brand=brand)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    matched_items = [
        p for p in catalog
        if ("nuoc giat" in _fold(p.get("name", "")) or "2in1" in _fold(p.get("name", "")))
        and any(term in _fold(p.get("name", "")) for term in ["pano", "oplus", "bio enzyme"])
    ]

    lines = []
    for i, p in enumerate(matched_items[:3], 1):
        p_name = p.get("name", "")
        p_price = _format_price(p.get("price"))
        p_disc = _format_discount(p.get("discount"))
        disc_text = f" (Giảm {p_disc})" if p_disc else ""
        p_url = p.get("link_shopee") or general_link
        lines.append(f"{i}. ⭐️ **{p_name}** — Giá: **{p_price}**{disc_text}\n   👉 Link Shopee: {p_url}")

    items_str = "\n".join(lines) if lines else (
        "1. ⭐️ **Nước giặt PANO Hương nước hoa Pháp** — Đậm đặc, ít bọt, chuyên dụng cho máy cửa trước.\n"
        "2. ⭐️ **Nước giặt 2in1 Oplus** — Giặt xả kết hợp, bảo vệ lồng giặt."
    )

    reply = (
        "Dạ máy giặt cửa trước/cửa ngang thường nên ưu tiên nước giặt dễ hòa tan và dùng đúng liều lượng để hạn chế trào bọt.\n\n"
        "Mình chưa có tài liệu kỹ thuật riêng trong dữ liệu chat để cam kết từng mã là chuyên dụng cho mọi dòng máy, nhưng có thể gợi ý các lựa chọn nước giặt phù hợp để bạn tham khảo:\n\n"
        f"{items_str}\n\n"
        "Bạn muốn dùng dạng túi 3.5kg hay can to 3.8kg để mình gửi link ưu đãi tốt nhất cho bạn nhé? 💙"
    )
    return {
        "matched": True,
        "intent": "zeo_laundry_product_overview",
        "confidence": "high",
        "score": 0.99,
        "suggested_reply": reply,
        "shopee_url": general_link,
        "products": matched_items,
    }


def is_stain_removal_or_efficacy_inquiry(text: str) -> bool:
    """Kiểm tra câu hỏi về tẩy vết bẩn (vết máu, vết ố, dầu mỡ), hiệu quả làm sạch hoặc hỏi 'dùng ổn không'."""
    folded = _fold(text)
    # Loại trừ hỏi giá rõ ràng
    if bool(re.search(r"\b(bao nhieu tien|gia bao nhieu|xin gia|bang gia)\b", folded)):
        return False
    # Bồn cầu/toilet/cặn vôi là nhóm tẩy rửa vệ sinh, không phải vết bẩn quần áo.
    if any(k in folded for k in ["bon cau", "toilet", "wc", "men su", "can voi", "nha tam"]):
        return False
    triggers = [
        "vet mau", "vet o", "vet ban", "vet dau mo", "vet mo hoi", "vet cafe", "vet tra",
        "tay mau", "tay duoc", "tay sach", "co sach ko", "co sach khong", "tay trang", "o vang",
        "dung on ko", "dung on khong", "dung tot ko", "dung tot khong", "co tot ko", "co tot khong",
        "giat sach ko", "giat sach khong", "tay vet", "danh bay vet ban", "sach vet", "co bay mau"
    ]
    return any(t in folded for t in triggers)


def match_stain_removal_or_efficacy(query: str, brand: str = "zeo", context: Optional[dict] = None) -> Optional[dict]:
    """Tư vấn chuyên sâu về hiệu quả làm sạch, tẩy vết máu/vết ố/vết bẩn cứng đầu và hướng dẫn sử dụng tối ưu."""
    folded = _fold(query)
    catalog = load_shopee_catalog(brand=brand)
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    # Phân loại vết bẩn
    is_blood = bool(re.search(r"\b(vet mau|mau)\b", folded))
    is_yellow_stain = bool(re.search(r"\b(o vang|vet o|moc|tham kim)\b", folded))

    if is_blood:
        reply = (
            "Dạ với vết máu và các vết bẩn gốc protein như mồ hôi/sữa, các dòng giặt giũ ZeO/PANO có thể hỗ trợ xử lý tốt nếu giặt đúng cách và xử lý sớm. Mình không cam kết sạch 100% cho mọi chất liệu/vết bẩn lâu ngày nha bạn. 💙\n\n"
            "🌟 **Mẹo xử lý vết máu:**\n"
            "1. **Xả ngay bằng nước lạnh:** Tuyệt đối không dùng nước nóng vì nhiệt độ cao sẽ làm protein trong máu đông chặt vào thớ vải.\n"
            "2. **Thoa trực tiếp:** Lấy một lượng nhỏ Bột giặt/Nước giặt PANO hoặc Bio Enzyme ZeO thoa trực tiếp lên vết máu, ngâm 10–15 phút để hoạt chất men phân hủy vết bẩn.\n"
            "3. **Vò nhẹ & giặt lại:** Vò nhẹ rồi giặt bình thường bằng tay hoặc máy giặt.\n\n"
            "👉 Với quần áo trắng bị ố máu lâu ngày, bạn có thể kết hợp thêm **Nước tẩy Javen ZeO** để áo trắng tinh tươm như mới nha!\n"
            f"👉 Xem sản phẩm chính hãng tại Shopee Mall: {general_link}"
        )
    elif is_yellow_stain:
        reply = (
            "Dạ đối với quần áo bị ố vàng, thâm kim hoặc cặn mồ hôi lâu ngày, bạn có thể dùng các giải pháp chuyên dụng sau của ZeO:\n\n"
            "1. ⭐️ **Bột giặt ZeO Enzyme Thụy Điển / Bột giặt PANO**: Công thức đánh bay vết ố vàng sâu trong sợi vải.\n"
            "2. ⭐️ **Nước tẩy Javen ZeO (cho vải trắng)** hoặc **Nước tẩy màu ZeO (cho vải màu)**: Đánh bay vết ố vàng, thâm kim và khử khuẩn 99.9%.\n\n"
            "💡 **Cách dùng:** Hòa nước tẩy với nước và bột giặt theo tỉ lệ trên bao bì, ngâm áo từ 15-20 phút trước khi giặt xả lại.\n"
            f"👉 Link Shopee Mall: {general_link}"
        )
    else:
        reply = (
            "Dạ các sản phẩm giặt giũ của ZeO/PANO/Oplus được ứng dụng công nghệ làm sạch sinh học (Enzyme Thụy Điển, ION hòa tan nhanh và hạt VEILEX khử mùi), "
            "hỗ trợ xử lý các vết bẩn thường gặp như dầu mỡ, bùn đất, thức ăn, mồ hôi. Với đồ dễ phai màu hoặc chất liệu đặc biệt, bạn nên thử ở vùng nhỏ trước và làm theo hướng dẫn trên bao bì nha. 💙\n\n"
            "Sản phẩm ít cặn, dễ hòa tan kể cả trong nước lạnh và giữ hương thơm bền lâu suốt cả ngày.\n"
            f"👉 Link gian hàng Shopee Mall chính hãng: {general_link}\n"
            "Bạn đang cần giặt đồ trắng, đồ màu hay quần áo trẻ em để mình hướng dẫn cách giặt tối ưu nhất nhé!"
        )

    return {
        "matched": True,
        "intent": "laundry_stain_removal_guide",
        "confidence": "high",
        "score": 0.99,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }




# ─────────────────────────────────────────────────────────────────────────────
# 5. GENERAL MATCHING & FALLBACK
# ─────────────────────────────────────────────────────────────────────────────
def is_promotion_inquiry(text: str) -> bool:
    """Kiểm tra xem câu hỏi có chứa ý định hỏi về Sale / Khuyến Mãi / Giảm Giá / Ưu Đãi / Voucher không."""
    folded = _fold(text)
    triggers = [
        "sale", "khuyen mai", "giam gia", "uu dai", "voucher", "ma giam",
        "co giam", "co sale", "co khuyen mai", "dang sale", "dang giam", "deal",
        "chiet khau", "tang kem", "qua tang", "combo", "gia re"
    ]
    return any(t in folded for t in triggers)


def is_shopee_inquiry(text: str) -> bool:
    """Kiểm tra xem câu hỏi có chứa ý định mua qua Shopee / xin link mua sàn Shopee không."""
    folded = _fold(text)
    # Loại trừ hỏi website công ty
    if any(w in folded for w in ["website", "trang web", "link web", "zeo vn", "zeo.vn", "cfccobay"]):
        return False
    # Loại trừ mua offline / đại lý
    if any(w in folded for w in ["dai ly", "tap hoa", "sieu thi", "cua hang", "offline"]):
        return False
    triggers = [
        "shopee", "shoppe", "sopi", "sope", "shopi", "san tmdt",
        "link shopee", "gian hang shopee", "shopee mall", "shopee cua shop",
        "link nuoc", "link bot", "link san pham", "cho xin link", "cho link", "gui link",
        "xin link", "link mua", "cho minh xin link", "cho minh link", "gui link cho minh", "cho link mua",
        "mua o dau", "mua o cho nao", "mua tai dau", "dat online o dau", "dat tren mang o dau"
    ]
    return any(t in folded for t in triggers)


def is_fabric_softener_inquiry(text: str) -> bool:
    """Nhận diện hỏi/mua/tìm nước xả vải độc lập, không lẫn nước giặt xả 2in1."""
    folded = _fold(text)
    return bool(re.search(r"\b(nuoc xa vai|nuoc xa|xa vai|fabric softener)\b", folded))


def match_fabric_softener_products(query: str, brand: str = "zeo") -> Optional[dict]:
    """Trả danh mục nước xả từ catalog hiện hành, ưu tiên dữ liệu bán hàng hơn FAQ cũ."""
    if brand.lower() != "zeo" or not is_fabric_softener_inquiry(query):
        return None

    folded = _fold(query)
    catalog = load_shopee_catalog(brand=brand)
    candidates = []
    for product in catalog:
        name_folded = _fold(product.get("name", ""))
        category_folded = _fold(product.get("category", ""))
        if not product.get("in_stock", True):
            continue
        if "nuoc xa vai" not in category_folded and "nuoc xa vai" not in name_folded:
            continue
        candidates.append(product)

    requested_subbrand = ""
    for subbrand in ("oplus", "pano", "zeo"):
        if re.search(rf"\b{subbrand}\b", folded):
            requested_subbrand = subbrand
            break

    if requested_subbrand:
        exact_brand = [
            product for product in candidates
            if _fold(product.get("brand", "")) == requested_subbrand
        ]
        if exact_brand:
            candidates = exact_brand
        elif requested_subbrand in {"oplus", "pano"}:
            return {
                "matched": True,
                "intent": "fabric_softener_brand_unavailable",
                "confidence": "high",
                "score": 0.99,
                "selected_products": [],
                "suggested_reply": (
                    f"Dạ trong Shopee catalog hiện hành, mình chưa thấy nước xả vải riêng của {requested_subbrand.title()} còn bán. "
                    "Hiện catalog có dòng Nước xả vải Nano Clean ZeO; bạn có muốn mình gửi sản phẩm và link chính hãng không ạ?"
                ),
                "shopee_url": None,
            }

    if not candidates:
        return {
            "matched": True,
            "intent": "fabric_softener_catalog_empty",
            "confidence": "high",
            "score": 0.99,
            "selected_products": [],
            "suggested_reply": (
                "Dạ hiện Shopee catalog chưa có sản phẩm nước xả vải còn hàng để mình giới thiệu chính xác. "
                "Mình không tự đoán sản phẩm; admin sẽ kiểm tra lại catalog giúp bạn nha."
            ),
            "shopee_url": None,
        }

    candidates.sort(key=lambda product: (_price_number(product.get("price")), str(product.get("name", ""))))
    selected = candidates[:3]
    lines = []
    for index, product in enumerate(selected, start=1):
        url = product.get("link_shopee") or product.get("shopee_url") or ""
        line = f"{index}. **{product.get('name', 'Nước xả vải ZeO')}** — {_format_price(product.get('price'))}"
        if url:
            line += f"\n👉 {url}"
        lines.append(line)

    return {
        "matched": True,
        "intent": "zeo_fabric_softener_catalog",
        "confidence": "high",
        "score": 0.99,
        "matched_product": selected[0],
        "selected_products": selected,
        "shopee_url": selected[0].get("link_shopee") or selected[0].get("shopee_url"),
        "suggested_reply": (
            "Dạ có nha bạn. Shopee catalog hiện có các sản phẩm nước xả vải ZeO sau:\n\n"
            + "\n\n".join(lines)
            + "\n\nBạn muốn dạng gói dùng thử hay can lớn để mình tư vấn đúng loại ạ?"
        ),
    }


def _product_link_result(product: dict, brand: str) -> dict:
    """Tạo câu trả lời link từ đúng record catalog đã được resolve."""
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
    price_str = _format_price(product.get("price"))
    url = product.get("link_shopee") or product.get("shopee_url") or general_link

    reply = (
        f"Dạ, link mua **{product['name']}** chính hãng trên Shopee Mall đây nha bạn:\n\n"
        f"👉 {url}\n\n"
        f"• **Giá tham khảo hiện tại:** {price_str}\n"
        f"• **Ưu đãi:** Freeship Extra toàn quốc\n\n"
        "Bạn bấm vào link để xem giá và ưu đãi mới nhất trên Shopee nhé! 💙"
    )

    return {
        "matched": True,
        "intent": "shopee_product_link",
        "is_general_store": False,
        "product_id": product.get("item_id") or product.get("id"),
        "product_name": product.get("name"),
        "shopee_url": url,
        "matched_product": product,
        "suggested_reply": reply,
    }


def match_shopee_product_reference(reference: dict, brand: str = "zeo") -> Optional[dict]:
    """Resolve follow-up theo product_id trước, rồi mới fallback exact product name."""
    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    product_id = str(reference.get("product_id") or "").strip()
    product_name = str(reference.get("product") or reference.get("name") or "").strip()
    matched = None

    if product_id:
        matched = next(
            (
                product
                for product in catalog
                if str(product.get("item_id") or product.get("id") or "").strip() == product_id
            ),
            None,
        )

    if matched is None and product_name:
        folded_name = _fold(product_name).strip()
        matched = next(
            (product for product in catalog if _fold(product.get("name", "")).strip() == folded_name),
            None,
        )

    if matched is None:
        return None
    return _product_link_result(matched, brand)


def match_promotions_and_deals(query: str, brand: str = "zeo") -> dict:
    """Trả lời trung thực về các chương trình Sale & Khuyến mãi hiện có của ZeO / CFC."""
    brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "CFC Cò Bay"
    general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"

    if brand.lower() == "zeo":
        reply = (
            f"Dạ các chương trình khuyến mãi, Flash Sale và Voucher giảm giá độc quyền được {brand_display} "
            f"cập nhật liên tục trực tiếp trên gian hàng chính hãng Shopee Mall:\n\n"
            f"👉 {general_link}\n\n"
            f"• Gian hàng đang hỗ trợ mã **Freeship Extra** toàn quốc cùng các mã giảm giá theo từng đợt khuyến mãi của sàn.\n"
            f"• Bạn có thể bấm vào link trên để xem giá ưu đãi mới nhất hoặc nhắn tên dòng sản phẩm bạn quan tâm để mình hỗ trợ nhé! 💙"
        )
    else:
        reply = (
            f"Dạ các chương trình ưu đãi và chiết khấu phân bón {brand_display} được áp dụng theo từng vụ mùa và số lượng đặt hàng. "
            f"Bạn vui lòng để lại Số Điện Thoại và Cây Trồng cần bón để kỹ sư Cò Bay liên hệ gửi chính sách ưu đãi tốt nhất cho mình nhé ạ!"
        )

    return {
        "matched": True,
        "intent": "promotion_deals",
        "confidence": "high",
        "score": 0.96,
        "suggested_reply": reply,
        "shopee_url": general_link,
    }


def match_shopee_product(query: str, brand: str = "zeo") -> Optional[dict]:
    """Khớp câu hỏi của khách với sản phẩm Shopee phù hợp nhất."""
    query_folded = _fold(query)
    brand_upper = brand.upper()

    # 0. Kiểm tra hỏi về hiệu quả làm sạch / tẩy vết bẩn (vết máu, vết ố, dùng ổn không)
    if is_stain_removal_or_efficacy_inquiry(query):
        stain_res = match_stain_removal_or_efficacy(query, brand=brand)
        if stain_res:
            return stain_res

    # 1. Kiểm tra hỏi tầm giá / ngân sách
    if is_price_extreme_inquiry(query):
        extreme_res = match_price_extreme(query, brand=brand)
        if extreme_res:
            return extreme_res

    # 1. Kiểm tra hỏi tầm giá / ngân sách
    if is_budget_inquiry(query):
        budget_res = match_products_by_budget(query, brand=brand)
        if budget_res:
            return budget_res

    # 2. Kiểm tra hỏi giá cụ thể cho một sản phẩm
    price_res = match_specific_product_price(query, brand=brand)
    if price_res:
        return price_res

    # 3. Kiểm tra hỏi Bán chạy / Mới nhất
    if is_bestseller_inquiry(query):
        return match_best_sellers(query, brand=brand)
    if is_new_arrival_inquiry(query):
        return match_new_arrivals(query, brand=brand)

    # 4. Kiểm tra hỏi khuyến mãi / flash sale
    if is_promotion_inquiry(query):
        return match_promotions_and_deals(query, brand=brand)

    # 5. Kiểm tra tư vấn theo nỗi đau & nhu cầu chuyên biệt
    if is_skin_care_dishwashing_inquiry(query):
        res = match_skin_care_dishwashing(query, brand=brand)
        if res:
            return res
    if is_baby_or_sensitive_laundry_inquiry(query):
        res = match_baby_or_sensitive_laundry(query, brand=brand)
        if res:
            return res
    if is_front_load_washer_inquiry(query):
        res = match_front_load_washer(query, brand=brand)
        if res:
            return res
    if is_bulk_or_restaurant_inquiry(query):
        res = match_bulk_or_restaurant_need(query, brand=brand)
        if res:
            return res

    catalog = load_shopee_catalog(brand=brand)
    if not catalog:
        return None

    brand_products = [
        p for p in catalog
        if p.get("brand", "").upper() == brand_upper or (brand_upper == "ZEO" and p.get("brand", "").upper() in ["ZEO", "PANO", "OPLUS"])
    ]
    if not brand_products:
        brand_products = catalog

    best_match = None
    highest_score = 0

    for prod in brand_products:
        prod_name_folded = _fold(prod.get("name", ""))
        keywords = prod.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(";") if k.strip()]

        score = 0
        cat_folded = _fold(prod.get("category", ""))
        if cat_folded and cat_folded in query_folded:
            score += 5

        for kw in keywords:
            kw_folded = _fold(kw)
            if kw_folded and kw_folded in query_folded:
                score += 4

        words = prod_name_folded.split()
        for w in words:
            if len(w) >= 3 and w in query_folded:
                score += 1

        variants = prod.get("variants", [])
        if isinstance(variants, str):
            variants = [v.strip() for v in variants.split(";") if v.strip()]
        for v in variants:
            v_folded = _fold(v)
            if v_folded and v_folded in query_folded:
                score += 3

        if score > highest_score:
            highest_score = score
            best_match = prod

    if not best_match or highest_score < 4:
        if is_shopee_inquiry(query):
            general_link = "https://shopee.vn/zeovietnamofficial" if brand.lower() == "zeo" else "https://shopee.vn/cfccobay"
            brand_display = "ZeO Vietnam" if brand.lower() == "zeo" else "Cò Bay"
            return {
                "matched": True,
                "is_general_store": True,
                "product_name": f"Gian hàng Shopee chính thức {brand_display}",
                "shopee_url": general_link,
                "suggested_reply": (
                    f"Dạ, bạn có thể ghé gian hàng Shopee chính thức của {brand_display} tại link này nha:\n"
                    f"👉 {general_link}\n\n"
                    f"Gian hàng đang có đầy đủ các dòng sản phẩm cùng nhiều mã Freeship Extra và Voucher ưu đãi độc quyền ạ! 💙"
                ),
            }
        return None

    return _product_link_result(best_match, brand)
