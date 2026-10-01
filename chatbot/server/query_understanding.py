"""
query_understanding.py — Deterministic Vietnamese QueryPlan for chatbot routing.

Module này chỉ hiểu câu hỏi và tạo kế hoạch truy xuất. Nó không tạo fact,
không báo giá, không quyết định link/tồn kho. Mọi fact vẫn phải lấy từ
Sheet/Redis/catalog/RAG ở các lớp phía sau.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import re
from typing import Any, Optional
import json
import os
from pathlib import Path
# pyrefly: ignore [missing-import]
import redis
import time

_redis_sync_client = None
_DYNAMIC_CROP_TERMS: list[str] = []
_DYNAMIC_PROVINCES: list[str] = []
_DYNAMIC_DISTRICTS: list[str] = []
_LAST_SYNC_TIME: float = 0.0
_DEFAULT_CROP_TERMS = (
    "sau rieng", "lua", "cay an trai", "rau mau", "ca phe", "tieu", "cao su", "dieu",
    "oi", "cay oi", "buoi", "cam", "quyt", "xoai", "mit", "thanh long", "man", "tao",
    "chanh", "tac", "mang cau", "chom chom", "nhan", "khoai lang", "dua hau",
)

def _get_redis_sync() -> redis.Redis:
    global _redis_sync_client
    if _redis_sync_client is None:
        try:
            settings_path = Path(__file__).resolve().parent / "settings.json"
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            r_cfg = settings.get("redis", {})
            _redis_sync_client = redis.Redis(
                host=r_cfg.get("host", "127.0.0.1"),
                port=r_cfg.get("port", 6379),
                password=r_cfg.get("password"),
                db=r_cfg.get("db", 0),
                decode_responses=True
            )
        except Exception:
            _redis_sync_client = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
    return _redis_sync_client

def _sync_dynamic_lists() -> None:
    global _DYNAMIC_CROP_TERMS, _DYNAMIC_PROVINCES, _DYNAMIC_DISTRICTS, _LAST_SYNC_TIME
    now = time.time()
    if now - _LAST_SYNC_TIME < 300:
        return
    try:
        r = _get_redis_sync()
        # Crop terms from Redis
        crops_raw = r.get("cfc:knowledge:crop_terms")
        if crops_raw:
            try:
                crops_list = json.loads(crops_raw)
                if isinstance(crops_list, dict) and "items" in crops_list:
                    crops_list = crops_list["items"]
                if isinstance(crops_list, list):
                    _DYNAMIC_CROP_TERMS = [str(c).strip().lower() for c in crops_list if str(c).strip()]
            except json.JSONDecodeError:
                _DYNAMIC_CROP_TERMS = [c.strip().lower() for c in str(crops_raw).split(",") if c.strip()]
        
        # Provinces/Districts from AMIS
        amis_locations_raw = r.get("amis:public:sales-locations:active")
        if amis_locations_raw:
            try:
                locations = json.loads(amis_locations_raw)
                if isinstance(locations, dict) and "items" in locations:
                    locations = locations["items"]
                provinces = set()
                districts = set()
                if isinstance(locations, list):
                    for loc in locations:
                        p = str(loc.get("province", "")).strip().lower()
                        d = str(loc.get("district", "")).strip().lower()
                        if p:
                            provinces.add(p)
                        if d:
                            districts.add(d)
                if provinces:
                    _DYNAMIC_PROVINCES = list(provinces)
                if districts:
                    _DYNAMIC_DISTRICTS = list(districts)
            except Exception:
                pass
        
        _LAST_SYNC_TIME = now
    except Exception:
        pass  # Fallback to hardcoded if Redis fails


@dataclass
class QueryPlan:
    original_query: str
    normalized_query: str
    brand: str
    intent: str = "unknown"
    intent_confidence: float = 0.0
    entities: dict[str, Any] = field(default_factory=dict)
    references: dict[str, Any] = field(default_factory=dict)
    attributes: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    needs_context: bool = False
    needs_retrieval: bool = True
    needs_product_tool: bool = False
    rewritten_query: str = ""
    ambiguity_reason: str = ""
    # V2 keeps every V1 field above. Candidates are planning metadata only: no
    # answer, business fact, source ID, price, stock or dosage may appear here.
    schema_version: int = 2
    intent_candidates: list[dict[str, Any]] = field(default_factory=list)
    primary_candidate_id: str = ""
    secondary_candidate_ids: list[str] = field(default_factory=list)
    context_action: str = "continue"
    ambiguities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _looks_like_cfc_sales_consultation(text: str) -> bool:
    """Recognize a commercial request before an advisory fallback claims it.

    This is a small business boundary, not a growing list of paraphrases: the
    customer explicitly says they want to buy/import fertiliser and asks sales
    to contact or advise them.  Technical advice without a commercial request
    continues to use the agronomy branch below.
    """
    wants_purchase = bool(re.search(
        r"\b(muon mua|can mua|dat mua|dat hang|lay hang|mua|nhap hang|can nhap|nhap)\b",
        text,
    ))
    mentions_fertiliser = bool(re.search(r"\b(phan|phan bon|npk|huu co)\b", text))
    asks_sales_help = bool(re.search(
        r"\b(tu van|add|lien he|bao gia|sale|kinh doanh|nhan vien)\b",
        text,
    ))
    return wants_purchase and mentions_fertiliser and asks_sales_help


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _ordinal_index(text: str) -> Optional[int]:
    patterns = [
        (1, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(dau tien|thu nhat|so 1|1)\b"),
        (2, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu hai|so 2|2)\b"),
        (3, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu ba|so 3|3)\b"),
        (4, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu tu|so 4|4)\b"),
        (5, r"\b(cai|loai|san pham|sp|muc|so|nhom)?\s*(thu nam|so 5|5)\b"),
    ]
    for idx, pattern in patterns:
        if re.search(pattern, text):
            return idx
    return None


def _detect_attributes(text: str) -> list[str]:
    attrs: list[str] = []
    if (
        re.search(r"\b(gia|bao nhieu|bao nhieu tien|nhiu|mac nhat|dat nhat|re nhat)\b", text)
        or re.search(r"\b(duoi|tren|tam|khoang|gan)\s*\d", text)
    ):
        attrs.append("price")
    if re.search(r"\b(link|shopee|mua online|dat mua|gian hang)\b", text):
        attrs.append("link")
    if re.search(r"\b(con hang|co san|ton kho|trong kho|het hang|con khong|con ko|con nhieu|co lien|kho con|con loai|con ma|co xuat kho|xuat kho khong|giao lien|giao duoc lien|giao ngay|lay lien)\b", text):
        attrs.append("availability")
    if re.search(
        r"\b(cach dung|huong dan|su dung|dung sao|dung nhu the nao|lieu(?: luong)?(?: bao nhieu| sao)?|"
        r"cach bon|nen bon|cong thuc nao|bon bao nhieu|bon may (?:kg|ky)|"
        r"(?:moi|mot) goc(?: bao nhieu| may (?:kg|ky))?|bao nhieu(?: kg| ky)? (?:moi|mot) goc)\b",
        text,
    ):
        attrs.append("usage")
    if re.search(r"\b(thom|mui|huong|luu huong)\b", text):
        attrs.append("fragrance")
    if re.search(r"\b(an da|hai da|troc da|di ung|da nhay cam|em be|tre nho|so sinh)\b", text):
        attrs.append("safety")
    if re.search(r"\b(cua truoc|cua ngang|it bot|trao bot|may giat)\b", text):
        attrs.append("compatibility")
    if re.search(r"\b(doi tra|tra hang|hoan tien|bao hanh|khieu nai|loi hang)\b", text):
        attrs.append("policy")
    return _unique(attrs)


def _detect_entities(text: str, query_entities: Optional[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    if query_entities:
        for key in ("product", "product_intent", "category"):
            value = query_entities.get(key)
            if value:
                entities[key] = value

    category_terms = {
        "dishwashing": ["rua chen", "rua bat", "chen dia", "zif"],
        "laundry": ["giat", "bot giat", "nuoc giat", "xa vai", "quan ao"],
        "floor_cleaner": ["lau san", "tay san", "san nha", "lau nha"],
        "toilet_cleaner": ["bon cau", "toilet", "wc", "men su", "can voi", "o vang nha tam"],
        "bleach": ["javen", "nuoc tay", "tay quan ao"],
    }
    for category, terms in category_terms.items():
        if _has_any(text, terms):
            entities.setdefault("category", category)
            break

    brands = [b for b in ["zeo", "pano", "oplus", "zif", "cfc", "co bay"] if b in text]
    if brands:
        entities["mentioned_brands"] = brands

    variant_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(kg|g|gram|lit|l|ml)\b", text)
    if variant_match:
        entities["variant"] = variant_match.group(0)

    formula_match = re.search(
        r"\b(?:npk\s+)?(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})(?:\s+(te))?\b",
        text,
    )
    if formula_match:
        entities["formula"] = "-".join(formula_match.group(index) for index in range(1, 4))
        if formula_match.group(4):
            entities["formula"] += " TE"

    order_match = (
        re.search(r"#([a-z0-9\-_]+)", text)
        or re.search(r"\b(?:don hang|ma don|don so|don)\s*(?:so|ma)?\s*[:#]?\s*([a-z0-9\-_]+)", text)
        or re.search(r"\b(0000\d{4}|dh[-_ ]?\d{4,8})\b", text)
    )
    if order_match:
        val = order_match.group(1) if order_match.groups() else order_match.group(0)
        val_clean = val.strip()
        if len(val_clean) >= 4 and not val_clean.startswith(("nay", "giup", "cho", "nha", "shop")):
            entities["order_id"] = val_clean
    if "order_id" not in entities:
        spaced_order = re.search(r"\bdh\s+(\d{2,8})\s+(\d{2,8})\b", text)
        if spaced_order:
            entities["order_id"] = f"DH-{spaced_order.group(1)}-{spaced_order.group(2)}"

    acreage_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(hecta|ha|cong)\b", text)
    if acreage_match:
        entities["acreage"] = f"{acreage_match.group(1)} {acreage_match.group(2)}"

    crop_terms = _DYNAMIC_CROP_TERMS if _DYNAMIC_CROP_TERMS else _DEFAULT_CROP_TERMS
    def _matches_crop_term(term: str) -> bool:
        normalized_term = str(term or "").strip().lower()
        if not normalized_term:
            return False
        # "mặn" is normalized to "man" too. Bare "man" is a crop only when
        # the message contains an explicit plum/crop context.
        if normalized_term == "man":
            return bool(
                re.search(r"\b(cay|trai|qua|vuon)\s+man\b", text)
                or re.search(r"\bman\s+(hau|tam|do|xanh|chin)\b", text)
            )
        # "tắc" is a crop, but the normalized token also appears inside the
        # business phrase "hợp tác xã". Do not persist that phrase as crop=tắc.
        if normalized_term == "tac" and re.search(r"\bhop tac xa\b", text):
            return bool(re.search(r"\b(cay|trai|qua|vuon|trong)\s+tac\b", text))
        return bool(re.search(rf"\b{re.escape(normalized_term)}\b", text))

    crop = next((term for term in crop_terms if _matches_crop_term(term)), "")
    if not crop:
        crop_match = re.search(r"\bcay\s+([a-z0-9\s]+?)(?:,|\.|\s+dien|\s+hecta|\s+ha|\s+o\b|\s+bi\b|\s+giai\b|$)", text)
        if crop_match:
            cand = crop_match.group(1).strip()
            if len(cand) >= 2 and cand not in {"an trai", "nong nghiep", "trong"}:
                crop = cand
    if crop:
        entities["crop"] = crop.replace("cay ", "").strip()

    stage_patterns = [
        "nuoi trai non", "trai non", "ra hoa", "xu ly ra hoa", "dau trai",
        "nuoi trai", "xuong giong", "de nhanh", "lam dong", "dot 1", "dot 2", "dot 3",
    ]
    crop_stage = next((term for term in stage_patterns if re.search(rf"\b{term}\b", text)), "")
    if crop_stage:
        entities["crop_stage"] = crop_stage

    symptom_match = re.search(r"\b(rung hat chuoi|rung trai non|vang la|thoi re|xoan la|cham lon)\b", text)
    if symptom_match:
        entities["symptom"] = symptom_match.group(1)

    dealer_level = re.search(r"\bdai ly cap\s*(\d+)\b", text)
    if dealer_level:
        entities["dealer_level"] = f"cap {dealer_level.group(1)}"

    return entities


def extract_understanding_entities(
    text: str,
    query_entities: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Expose the shared fact-free extractor to deterministic routes.

    Conversation memory must not keep a second crop/stage/symptom dictionary:
    a crop recognized by QueryPlan, including crop terms warmed from Redis,
    must be the same crop persisted by the chat pipeline.
    """
    _sync_dynamic_lists()
    return _detect_entities(text, query_entities)


def get_known_crop_terms() -> tuple[str, ...]:
    """Return the current Redis-backed crop vocabulary used by QueryPlan."""
    _sync_dynamic_lists()
    return tuple(_DYNAMIC_CROP_TERMS or _DEFAULT_CROP_TERMS)


def _detect_constraints(text: str) -> dict[str, Any]:
    constraints: dict[str, Any] = {}

    quantity = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(chai|can|tui|goi|thung|hop|bao|bo|tan)\b", text)
    if quantity:
        raw_quantity = quantity.group(1).replace(",", ".")
        numeric_quantity = float(raw_quantity)
        constraints["quantity"] = int(numeric_quantity) if numeric_quantity.is_integer() else numeric_quantity
        constraints["quantity_unit"] = quantity.group(2)

    budget = re.search(r"\b(duoi|tren|tam|khoang|gan)\s*(\d+(?:[.,]\d+)?)\s*(k|nghin|trieu)?\b", text)
    if budget:
        value = float(budget.group(2).replace(",", "."))
        unit = budget.group(3) or ""
        if unit in {"k", "nghin"}:
            value *= 1000
        elif unit == "trieu":
            value *= 1_000_000
        constraints["budget_operator"] = budget.group(1)
        constraints["budget_vnd"] = int(value)

    # Location slots extraction (provinces, districts, wards)
    provinces = _DYNAMIC_PROVINCES if _DYNAMIC_PROVINCES else [
        "can tho", "an giang", "dong thap", "hau giang", "soc trang", "kien giang",
        "vinh long", "tien giang", "ben tre", "tra vinh", "ca mau", "bac lieu",
        "lam dong", "da lat", "tphcm", "ho chi minh", "ha noi", "da nang"
    ]
    for prov in provinces:
        if re.search(rf"\b{prov}\b", text):
            constraints["location"] = prov
            break

    # Districts in Mekong Delta
    districts = _DYNAMIC_DISTRICTS if _DYNAMIC_DISTRICTS else [
        "o mon", "thoi lai", "co do", "vinh thanh", "phong dien",
        "binh thuy", "ninh kieu", "cai rang", "thot not", "cho moi",
        "tri ton", "thoai son", "tan hiep", "giong rieng", "chau thanh"
    ]
    for dist in districts:
        if re.search(rf"\b{dist}\b", text):
            constraints["district"] = dist
            break

    # Wards / communes
    ward_match = re.search(r"\bxa\s+([a-z0-9\s]+?)(?:\s*,|\s+huyen|\s+quan|\s+tinh|\s+co\b|\s+gan\b|\s*$)", text)
    if ward_match:
        constraints["ward"] = ward_match.group(1).strip()

    channels = [channel for channel in ("shopee", "website", "lazada", "facebook", "zalo") if channel in text]
    if channels:
        constraints["channels"] = channels

    negated_brand = re.search(r"\bkhong phai\s+(pano|zeo|oplus|zif|cfc|co bay)\b", text)
    if negated_brand:
        constraints["negated_brands"] = [negated_brand.group(1)]
    corrected_brand = re.search(r"\b(?:y minh la|y toi la|ma la)\s+(pano|zeo|oplus|zif|cfc|co bay)\b", text)
    if corrected_brand:
        constraints["corrected_brand"] = corrected_brand.group(1)
    return constraints


def _detect_intent(text: str, attrs: list[str], entities: dict[str, Any], brand: str) -> tuple[str, float]:
    mentioned = set(entities.get("mentioned_brands", []))
    if brand == "zeo" and re.search(
        r"\b(hotline|tong dai|so dien thoai|so lien he|so cham soc|cham soc khach hang)\b",
        text,
    ):
        return "company_contact_information", 0.94
    if brand == "cfc" and (
        re.search(r"\b(hotline|tong dai|so lien he|so cham soc|cham soc khach hang)\b", text)
        or re.search(
            r"\b(so dien thoai|sdt).{0,25}\b(cong ty|cty|cfc|co bay|shop|admin|ben minh)\b",
            text,
        )
    ):
        return "cfc_contact_information_request", 0.94
    if brand == "zeo" and "compatibility" in attrs:
        return "product_compatibility", 0.94
    if brand == "zeo" and re.search(
        r"\b(nuoc lau san|nuoc lau bep|tay da nang|rua chen|tay bon cau|lau kinh|vien giat|nuoc giat)\b",
        text,
    ):
        return "product_category_query", 0.95
    if brand == "cfc" and (
        re.search(
            r"\b(hop tac xa|htx|30 tan|20 tan|50 tan|100 tan|don hang lon|so luong lon|giam doc kinh doanh|gdkd|thuong luong hop dong|hop dong lon|mua si so luong|muon lam dai ly|dang ky dai ly|phan phoi)\b",
            text,
        )
    ):
        return "cfc_b2b_large_order_request", 0.98
    if brand == "cfc" and (
        re.search(r"\b(von cuc|dong cuc|chay nuoc|rach bao|hong bao|hang loi|hang kem|kem chat luong)\b", text)
        or (re.search(r"\b(khieu nai|doi tra ngay|doi tra gap|tra hang)\b", text) and not re.search(r"\b(chinh sach|quy dinh)\b", text))
    ):
        return "cfc_product_complaint_request", 0.98
    if brand == "cfc" and (
        re.search(r"\b(tien do don hang|kiem tra don hang|kiem tra giup don|kiem tra don|tra cuu don|xe da boc|boc hang xong|da xuat kho chua|tien do xuat kho|van don|giao den dau|giao toi dau|dh[-\s]?\d+)\b", text)
        or (re.search(r"\b(don hang|don so|ma don)\b", text) and not re.search(r"\b(30 tan|20 tan|50 tan|100 tan|hop tac xa|htx)\b", text))
        or entities.get("order_id")
    ):
        return "cfc_order_status_request", 0.97
    if re.search(r"\b(vay tien|cho vay|tin dung|tra gop|vay von|cho muon tien)\b", text):
        return "financial_service_unsupported", 0.98
    if brand == "cfc" and re.search(
        r"\b(bang gia si|gia si|chiet khau quy|muc chiet khau|chinh sach chiet khau|dai ly cap|chiet khau cho dai ly|chiet khau cap)\b",
        text,
    ):
        return "cfc_wholesale_policy_request", 0.97
    if brand == "cfc" and re.search(
        r"\b(tich diem|diem thuong|diem tich luy|hang thanh vien|tai khoan dai ly|uu dai gi ko|uu dai gi khong|uu dai gi chua|uu dai gi|duoc bao nhieu %|tra cuu chiet khau)\b",
        text,
    ):
        return "cfc_loyalty_lookup_request", 0.96
    if brand == "cfc" and (
        ("availability" in attrs and (
            re.search(r"\b(npk|phan|cong thuc|bao|kho|chuyen lua|con loai|con ma|sieu tang truong)\b", text)
            or entities.get("formula")
        ))
        or re.search(r"\b(con hang|lay \d+ tan|co lien khong|trong kho con|kho con|con loai|con ma)\b", text)
    ):
        return "cfc_inventory_request", 0.97
    if re.search(r"\b(thong tin khach hang|khach hang .* la ai|so dien thoai .* cua|con no|no tien|cong no|no bao nhieu|tien no|chua thanh toan)\b", text):
        return "privacy_sensitive_lookup", 0.98
    if _has_any(text, ["tra hang", "doi tra", "hoan tien", "khieu nai"]):
        return "return_policy_or_claim", 0.95
    # Keep the dealer branch safe for short location follow-ups such as
    # "ở đó có không"; build_query_plan computes the same constraints later.
    constraints = _detect_constraints(text) if brand == "cfc" else {}
    if brand == "cfc" and (
        re.search(r"\b(dai ly|nha phan phoi|npp|diem mua|diem ban|cho ban|cho mua|cua hang|mua o dau|giao tan nha|giao tan noi)\b", text)
        or (
            re.search(r"\b(o dau|cho nao|co khong|co ko|gan nhat)\b", text)
            and (constraints.get("district") or constraints.get("ward") or constraints.get("location") or re.search(r"\b(o mon|thoi lai|co do|vinh thanh|dinh mon)\b", text))
        )
    ):
        return "cfc_dealer_location_request", 0.95
    if brand == "cfc" and (
        (
            re.search(r"\b(muon mua|can mua|dat mua|dat hang|lay hang|mua|nhap)\b", text)
            and re.search(r"\b\d+(?:[.,]\d+)?\s*(kg|tan|bao|thung)\b", text)
        )
        or (
            re.search(r"\bcan\b", text)
            and re.search(r"\b\d+(?:[.,]\d+)?\s*(kg|tan|bao|thung)\b", text)
            and re.search(r"\b(phan|phan bon|npk|huu co)\b", text)
        )
        or _looks_like_cfc_sales_consultation(text)
    ):
        return "cfc_purchase_request", 0.97
    if brand == "cfc" and (
        "usage" in attrs
        or entities.get("symptom")
        or entities.get("crop")
        or entities.get("acreage")
        or re.search(r"\b(sau rieng|cay an trai|lua|ca phe|tieu|rau mau|hecta|ha|dien tich|nen bon|bon cong thuc|cong thuc nao|lieu luong|giai doan|bi rung|tu van|ky thuat)\b", text)
    ):
        return "cfc_agronomy_review_request", 0.95
    if brand == "cfc" and re.search(r"\b(gia|bao gia|xin gia|bang gia|bao nhieu tien)\b", text):
        return "cfc_price_unverified", 0.93
    if {"zeo", "pano", "oplus"}.issubset(mentioned) and re.search(r"\b(khac nhau|hay sao|la sao|cung|thuoc|hang|thuong hieu)\b", text):
        return "brand_ecosystem_overview", 0.90
    if _has_any(text, ["bon cau", "toilet", "wc", "men su", "can voi"]) and _has_any(text, ["o vang", "vet o", "tay", "can voi", "sach"]):
        return "cleaning_toilet_stain", 0.93
    if "compatibility" in attrs:
        return "product_compatibility", 0.86
    if len([a for a in attrs if a in {"price", "link", "availability"}]) >= 2:
        return "multi_attribute_product_query", 0.86
    if "price" in attrs:
        if _has_any(text, ["mac nhat", "dat nhat", "cao nhat", "gia chat nhat"]):
            return "price_extreme", 0.92
        return "product_price_query", 0.86
    if "link" in attrs:
        return "product_link_query", 0.84
    if "availability" in attrs:
        return "product_availability_query", 0.84
    if "fragrance" in attrs:
        return "product_fragrance_need", 0.82
    if "safety" in attrs:
        return "product_safety_need", 0.80
    if entities.get("category") or entities.get("product") or entities.get("product_intent"):
        return "product_information_query", 0.72
    if brand == "cfc" and _has_any(text, ["lua", "cay", "phan bon", "npk"]):
        return "agriculture_advisory_query", 0.72
    return "unknown", 0.35


def _build_rewritten_query(original: str, entities: dict[str, Any], references: dict[str, Any], attrs: list[str]) -> str:
    parts: list[str] = []
    product = references.get("product") or entities.get("product") or ""
    if product:
        parts.append(str(product))
    category = entities.get("category") or references.get("category") or ""
    if category and category not in parts:
        parts.append(str(category))
    variant = entities.get("variant")
    if variant:
        parts.append(str(variant))
    parts.extend(attrs)
    return " ".join(parts).strip() or original


def _candidate_spec(intent: str, attrs: list[str], brand: str) -> tuple[str, str, str]:
    """Return action/source-family/risk for planning only, never a fact route."""
    normalized = str(intent or "unknown")
    protected = {
        "privacy_sensitive_lookup": ("privacy_boundary", "none", "high"),
        "cfc_product_complaint_request": ("complaint_intake", "none", "high"),
        "cfc_order_status_request": ("order_status_lookup", "privileged_tool", "high"),
        "cfc_loyalty_lookup_request": ("loyalty_lookup", "privileged_tool", "high"),
        "cfc_inventory_request": ("inventory_lookup", "privileged_tool", "high"),
        "cfc_b2b_large_order_request": ("b2b_intake", "none", "high"),
        "cfc_purchase_request": ("purchase_intake", "catalog", "medium"),
        "cfc_dealer_location_request": ("sales_location_search", "public_tool", "medium"),
        "cfc_agronomy_review_request": ("agronomy_intake", "approved_protocol", "high"),
        "cfc_price_unverified": ("price_review", "catalog", "high"),
        "product_price_query": ("product_lookup", "catalog", "medium"),
        "product_link_query": ("product_lookup", "catalog", "low"),
        "product_availability_query": ("product_lookup", "catalog", "medium"),
        "multi_attribute_product_query": ("product_lookup", "catalog", "medium"),
    }
    if normalized in protected:
        return protected[normalized]
    if "contact" in normalized or "website" in normalized:
        return "faq_lookup", "faq", "low"
    if "return" in normalized or "policy" in normalized:
        return "faq_lookup", "faq", "medium"
    if "price" in attrs or "availability" in attrs or "link" in attrs:
        return "product_lookup", "catalog", "medium" if "availability" in attrs else "low"
    return "faq_lookup", "faq", "low"


def _candidate_priority(candidate: dict[str, Any]) -> tuple[int, float, str]:
    """Stable arbitration order. Lower rank wins; confidence only breaks ties."""
    action = str(candidate.get("action") or "")
    rank = {
        "privacy_boundary": 0,
        "complaint_intake": 1,
        "order_status_lookup": 2,
        "loyalty_lookup": 2,
        "inventory_lookup": 2,
        "b2b_intake": 2,
        "purchase_intake": 3,
        "price_review": 4,
        "product_lookup": 5,
        "sales_location_search": 5,
        "agronomy_intake": 6,
        "faq_lookup": 7,
    }.get(action, 9)
    return rank, -float(candidate.get("confidence") or 0.0), str(candidate.get("candidate_id") or "")


def _make_candidate(
    *,
    clause_id: str,
    intent: str,
    confidence: float,
    entities: dict[str, Any],
    attributes: list[str],
    constraints: dict[str, Any],
    references: dict[str, Any],
    brand: str,
    origin: str = "deterministic",
) -> dict[str, Any]:
    action, source_family, risk = _candidate_spec(intent, attributes, brand)
    identity = {
        "clause": clause_id,
        "intent": intent,
        "action": action,
        "entities": entities,
        "attributes": attributes,
        "constraints": constraints,
        "reference": references,
        "origin": origin,
    }
    return {
        "candidate_id": "qc:" + hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20],
        "clause_id": clause_id,
        "intent": intent,
        "action": action,
        "source_family": source_family,
        "entities": dict(entities),
        "attributes": list(attributes),
        "constraints": dict(constraints),
        "reference": dict(references),
        "risk": risk,
        "confidence": round(max(0.0, min(float(confidence), 1.0)), 3),
        "origin": origin,
    }


def _build_intent_candidates(
    *,
    intent: str,
    confidence: float,
    attrs: list[str],
    entities: dict[str, Any],
    constraints: dict[str, Any],
    references: dict[str, Any],
    brand: str,
) -> list[dict[str, Any]]:
    """Build deterministic candidates without executing secondary requests."""
    candidates = [_make_candidate(
        clause_id="clause-1", intent=intent, confidence=confidence,
        entities=entities, attributes=attrs, constraints=constraints,
        references=references, brand=brand,
    )]
    attr_intents = {
        "price": "product_price_query",
        "availability": "product_availability_query",
        "link": "product_link_query",
    }
    # The primary legacy intent remains untouched. Attribute candidates make a
    # compound turn observable and can become pending work in a later turn.
    for index, attr in enumerate(attrs, start=2):
        candidate_intent = attr_intents.get(attr)
        if not candidate_intent or candidate_intent == intent:
            continue
        candidates.append(_make_candidate(
            clause_id=f"clause-{index}", intent=candidate_intent,
            confidence=min(confidence, 0.86), entities=entities,
            attributes=[attr], constraints=constraints, references=references,
            brand=brand,
        ))
    # Explicit purchase must be visible separately from an advisory crop
    # request. It is only a candidate; routing still retains P0 capability
    # boundaries and executes one primary action.
    if brand.lower() == "cfc" and intent == "cfc_purchase_request" and entities.get("crop"):
        candidates.append(_make_candidate(
            clause_id=f"clause-{len(candidates) + 1}",
            intent="cfc_agronomy_review_request", confidence=0.82,
            entities={"crop": entities["crop"]}, attributes=["usage"],
            constraints={}, references=references, brand=brand,
        ))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            str(candidate["action"]),
            str(candidate["source_family"]),
            json.dumps(candidate["entities"], ensure_ascii=False, sort_keys=True),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return sorted(deduped, key=_candidate_priority)


def build_query_plan(
    *,
    raw_text: str,
    norm_text: str,
    brand: str,
    query_entities: Optional[dict[str, Any]] = None,
    reference_resolution: Optional[dict[str, Any]] = None,
    conversation_state: Optional[dict[str, Any]] = None,
) -> QueryPlan:
    """Build a fact-free QueryPlan used for routing, tracing and tests."""
    _sync_dynamic_lists()
    reference_resolution = reference_resolution or {}
    conversation_state = conversation_state or {}
    attrs = _detect_attributes(norm_text)
    entities = _detect_entities(norm_text, query_entities)
    constraints = _detect_constraints(norm_text)

    references: dict[str, Any] = {
        "mentions_previous_turn": bool(
            reference_resolution.get("references_previous_turn")
            or re.search(r"\b(cai nay|cai do|san pham do|loai do|loai nay|no|cai kia|muc do|cai dau tien|cai thu|so \d)\b", norm_text)
        ),
        "resolved": bool(reference_resolution.get("resolved")),
    }
    ordinal = _ordinal_index(norm_text)
    if ordinal:
        references["ordinal"] = ordinal
    for key in ("product", "product_intent", "category", "product_id", "shopee_url", "price", "answer_id", "claim_ids", "reference_type"):
        if reference_resolution.get(key):
            references[key] = reference_resolution[key]

    intent, confidence = _detect_intent(norm_text, attrs, entities, brand.lower())
    active_goal = conversation_state.get("active_goal") or {}
    active_goal_name = active_goal if isinstance(active_goal, str) else str(active_goal.get("name") or "")
    if (
        brand.lower() == "cfc"
        and active_goal_name
        and re.fullmatch(
            r"(?:(?:la sao|y la sao|sao vay|noi gi vay|la nhu nao|giai thich lai)(?:\s+(?:chua hieu|khong hieu))?|(?:chua hieu|khong hieu)(?:\s+(?:la sao|y la sao))?)",
            norm_text.strip(),
        )
    ):
        intent, confidence = "cfc_clarification_request", 0.96
    if (
        brand.lower() == "cfc"
        and active_goal_name == "agronomy_consultation"
        and intent in {"unknown", "agriculture_advisory_query", "product_information_query"}
        and (
            entities.get("crop")
            or entities.get("crop_stage")
            or entities.get("acreage")
            or re.search(r"\b(dien tich|khu vuc|giai doan|trieu chung|hien tuong)\b", norm_text)
        )
    ):
        intent, confidence = "cfc_agronomy_review_request", 0.94
    needs_context = bool(references.get("mentions_previous_turn") and not references.get("resolved"))
    needs_product_tool = bool(
        brand.lower() == "zeo"
        and (
            intent in {
                "product_price_query",
                "price_extreme",
                "product_link_query",
                "product_availability_query",
                "multi_attribute_product_query",
                "product_fragrance_need",
                "product_safety_need",
                "product_compatibility",
            }
            or entities.get("category") in {"dishwashing", "laundry", "floor_cleaner", "toilet_cleaner", "bleach"}
        )
    )

    candidates = _build_intent_candidates(
        intent=intent,
        confidence=confidence,
        attrs=attrs,
        entities=entities,
        constraints=constraints,
        references=references,
        brand=brand,
    )
    primary_candidate_id = str(candidates[0].get("candidate_id") or "") if candidates else ""
    active_goal = conversation_state.get("active_goal") or {}
    active_goal_name = active_goal if isinstance(active_goal, str) else str(active_goal.get("name") or "")
    resume_requested = bool(re.search(r"\b(quay lai|tro lai|noi tiep)\b", norm_text))
    context_action = "resume" if resume_requested and active_goal_name else (
        "clarify" if needs_context else "continue"
    )
    ambiguities = ["UNRESOLVED_REFERENCE"] if needs_context else []
    if len(candidates) > 1 and candidates[0].get("risk") == candidates[1].get("risk") and abs(
        float(candidates[0].get("confidence") or 0.0) - float(candidates[1].get("confidence") or 0.0)
    ) < 0.04:
        ambiguities.append("EQUAL_PRIORITY_CANDIDATES")

    plan = QueryPlan(
        original_query=raw_text,
        normalized_query=norm_text,
        brand=brand.lower(),
        intent=intent,
        intent_confidence=confidence,
        entities=entities,
        references=references,
        attributes=attrs,
        constraints=constraints,
        needs_context=needs_context,
        needs_retrieval=not needs_product_tool or intent in {"unknown", "return_policy_or_claim", "agriculture_advisory_query"},
        needs_product_tool=needs_product_tool,
        rewritten_query=_build_rewritten_query(raw_text, entities, references, attrs),
        ambiguity_reason="UNRESOLVED_REFERENCE" if needs_context else "",
        intent_candidates=candidates,
        primary_candidate_id=primary_candidate_id,
        secondary_candidate_ids=[
            str(candidate.get("candidate_id") or "") for candidate in candidates[1:]
        ],
        context_action=context_action,
        ambiguities=ambiguities,
    )
    return plan
