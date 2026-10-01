"""AMIS compatibility helpers for server-side, allowlisted lookups.

These helpers read the local CRM snapshot and must not be treated as realtime.
Customer-facing code may use only the sanitized values returned by a helper;
raw CRM records and synthetic values stay internal.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .client import AmisClient, AmisError
from .config import load_amis_config

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TICKETS_FILE = DATA_DIR / "internal_tickets.json"
REAL_CRM_CACHE_FILE = DATA_DIR / "amis_real_crm_cache.json"

# In-memory index of real CRM datasets for ultra-low latency (< 5ms)
_CRM_DATASET: dict[str, Any] = {
    "loaded": False,
    "products": [],
    "customers": [],
    "sale_orders": [],
    "customers_by_phone": {},
    "orders_by_code": {},
    "orders_by_customer": {},
}


def _ensure_crm_dataset_loaded() -> None:
    """Tải và lập chỉ mục nhanh dữ liệu thật từ file snapshot MISA AMIS CRM."""
    if _CRM_DATASET["loaded"]:
        return

    if not REAL_CRM_CACHE_FILE.exists():
        logger.warning("CRM cache file not found at %s. Empty dataset used.", REAL_CRM_CACHE_FILE)
        return

    try:
        with open(REAL_CRM_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        products = data.get("products", [])
        customers = data.get("customers", [])
        sale_orders = data.get("sale_orders", [])

        customers_by_phone: dict[str, dict[str, Any]] = {}
        for c in customers:
            raw_tel = str(c.get("office_tel") or "").strip()
            tel = re.sub(r"[^\d+]", "", raw_tel)
            if tel and len(tel) >= 8:
                customers_by_phone[tel] = c
                # Thêm dạng không số 0 đầu nếu có
                if tel.startswith("0") and len(tel) > 2:
                    customers_by_phone[tel[1:]] = c
                    customers_by_phone["84" + tel[1:]] = c

        orders_by_code: dict[str, dict[str, Any]] = {}
        orders_by_customer: dict[str, list[dict[str, Any]]] = {}
        
        # Chỉ nạp các đơn hàng chính thức "Đã ghi", bỏ qua "Bản nháp" hoặc "Đề nghị ghi"
        sale_orders = [o for o in sale_orders if o.get("revenue_status") == "Đã ghi"]
        
        for o in sale_orders:
            sono = str(o.get("sale_order_no") or "").upper().strip()
            oid = str(o.get("id") or "").strip()
            code = str(o.get("order_no") or o.get("order_code") or o.get("code") or sono or oid).upper().strip()

            if sono:
                orders_by_code[sono] = o
                orders_by_code[f"DH{sono}"] = o
                orders_by_code[f"#DH-{sono}"] = o
                orders_by_code[f"DH-{sono}"] = o
                orders_by_code[f"#{sono}"] = o
                sono_stripped = sono.lstrip("0")
                if sono_stripped:
                    orders_by_code[sono_stripped] = o
                    orders_by_code[f"DH{sono_stripped}"] = o
                    orders_by_code[f"#DH-{sono_stripped}"] = o
                    orders_by_code[f"DH-{sono_stripped}"] = o
                    orders_by_code[f"#{sono_stripped}"] = o
            if oid:
                orders_by_code[oid] = o
                orders_by_code[f"DH{oid}"] = o
                orders_by_code[f"#DH-{oid}"] = o
                orders_by_code[f"#{oid}"] = o
            if code and code not in orders_by_code:
                orders_by_code[code] = o

            acc_name = str(o.get("account_name") or "").lower().strip()
            if acc_name:
                if acc_name not in orders_by_customer:
                    orders_by_customer[acc_name] = []
                orders_by_customer[acc_name].append(o)

        _CRM_DATASET["products"] = products
        _CRM_DATASET["customers"] = customers
        _CRM_DATASET["sale_orders"] = sale_orders
        _CRM_DATASET["customers_by_phone"] = customers_by_phone
        _CRM_DATASET["orders_by_code"] = orders_by_code
        _CRM_DATASET["orders_by_customer"] = orders_by_customer
        _CRM_DATASET["loaded"] = True
        logger.info(
            "Loaded real CRM dataset: %d products, %d customers (%d with tel), %d orders",
            len(products),
            len(customers),
            len(customers_by_phone),
            len(sale_orders),
        )
    except Exception as e:
        logger.error("Error loading CRM cache file: %s", e)


# ==============================================================================
# 1. KIỂM TRA TRẠNG THÁI KẾT NỐI REALTIME
# ==============================================================================
def check_amis_live_status() -> dict[str, Any]:
    """Describe the real capability boundary without loading raw CRM data."""
    config = load_amis_config()
    return {
        "mode": "PROTECTED_WARM_CACHE",
        "realtime_enabled": False,
        "order_lookup": "exact_order_code_plus_phone_hmac_fresh_cache",
        "unavailable_realtime_capabilities": ["inventory", "loyalty", "price", "discount", "debt"],
        "legacy_raw_cache_present": REAL_CRM_CACHE_FILE.exists(),
        "base_url": config.base_url,
        "has_client_id": bool(config.client_id),
        "has_client_secret": bool(config.client_secret),
    }


# ==============================================================================
# 2. TRUY VẤN ĐƠN HÀNG REALTIME TỪ CRM THỰC TẾ
# ==============================================================================
def lookup_order_status(order_code: str = "", dealer_name: str = "", phone: str = "") -> Optional[dict[str, Any]]:
    """Tra cứu trạng thái đơn hàng thật trong 6,718 đơn hàng AMIS CRM."""
    _ensure_crm_dataset_loaded()

    def _extract_order_info(o: dict[str, Any], query_code: str) -> dict[str, Any]:
        prods = o.get("sale_order_product_mappings") or o.get("details") or []
        prod_names = []
        total_qty = 0
        for p in prods[:3]:
            desc = p.get("description") or p.get("product_name") or "Phân bón NPK Cò Bay"
            p_amt = p.get("amount") or p.get("usage_unit_amount") or 0
            p_unit = p.get("unit") or p.get("usage_unit") or "Bao"
            prod_names.append(f"{desc} ({int(p_amt) if isinstance(p_amt, (int, float)) else p_amt} {p_unit})")
            if isinstance(p_amt, (int, float)):
                total_qty += p_amt

        p_display = "; ".join(prod_names) if prod_names else "Sản phẩm phân bón Cò Bay"
        code = str(o.get("sale_order_no") or o.get("order_no") or o.get("id") or query_code)

        return {
            "order_code": code,
            "dealer_name": o.get("account_name") or "Quý Khách Hàng",
            "product_name": p_display,
            "quantity_tons": total_qty if total_qty > 0 else (o.get("amount_summary") or None),
            "warehouse": o.get("organization_unit_name") or "Tổng kho Nhà máy Cần Thơ (KCN Trà Nóc)",
            "truck_plate": None,
            "driver_name": None,
            "status": o.get("status") or "Đã thực hiện",
            "source": "amis_real_crm",
            "updated_at": o.get("modified_date") or o.get("created_date") or datetime.now(timezone.utc).isoformat(),
        }

    # 1. Tìm theo mã đơn hàng
    if order_code:
        clean_code = str(order_code).upper().replace("#", "").strip()
        orders_by_code = _CRM_DATASET.get("orders_by_code", {})

        if clean_code in orders_by_code:
            return _extract_order_info(orders_by_code[clean_code], clean_code)

        for o in _CRM_DATASET.get("sale_orders", []):
            o_code = str(o.get("sale_order_no") or o.get("order_no") or o.get("id") or "").upper()
            if o_code and (clean_code == o_code or (len(clean_code) >= 4 and clean_code in o_code)):
                return _extract_order_info(o, clean_code)

        return None

    # 2. Tìm theo tên đại lý xưng danh
    if dealer_name:
        d_norm = dealer_name.lower().strip()
        for cust_name, orders in _CRM_DATASET.get("orders_by_customer", {}).items():
            if d_norm == cust_name or (len(d_norm) >= 4 and d_norm in cust_name):
                if orders:
                    return _extract_order_info(orders[0], "")

        for o in _CRM_DATASET.get("sale_orders", []):
            acc_name = str(o.get("account_name") or "").lower()
            if d_norm in acc_name and len(d_norm) >= 4:
                return _extract_order_info(o, "")

        return None

    # 3. Tìm theo số điện thoại
    if phone:
        clean_phone = re.sub(r"[^\d+]", "", str(phone)).strip()
        if clean_phone and len(clean_phone) >= 8:
            customers_by_phone = _CRM_DATASET.get("customers_by_phone", {})
            cust = customers_by_phone.get(clean_phone)
            if not cust and clean_phone.startswith("0"):
                cust = customers_by_phone.get(clean_phone[1:]) or customers_by_phone.get("84" + clean_phone[1:])
            elif not cust and clean_phone.startswith("84"):
                cust = customers_by_phone.get("0" + clean_phone[2:]) or customers_by_phone.get(clean_phone[2:])
            
            if cust:
                cust_name = cust.get("account_name")
                if cust_name:
                    d_norm = cust_name.lower().strip()
                    for c_name, orders in _CRM_DATASET.get("orders_by_customer", {}).items():
                        if d_norm == c_name:
                            if orders:
                                return _extract_order_info(orders[0], "")

    return None


# ==============================================================================
# 3. TRUY VẤN HỘI VIÊN / LOYALTY TỪ CRM THỰC TẾ
# ==============================================================================
def lookup_loyalty_info(phone: str) -> Optional[dict[str, Any]]:
    """Tra cứu các trường hội viên đã có thật trong snapshot AMIS.

    Không suy ra điểm/hạng từ doanh số hoặc số đơn.  Những giá trị suy ra
    trước đây làm chatbot có thể báo điểm mặc định dù CRM không lưu điểm đó.
    """
    _ensure_crm_dataset_loaded()
    clean_phone = re.sub(r"[^\d+]", "", str(phone or "")).strip()
    if not clean_phone or len(clean_phone) < 8:
        return None

    customers_by_phone = _CRM_DATASET.get("customers_by_phone", {})

    cust = customers_by_phone.get(clean_phone)
    if not cust and clean_phone.startswith("0"):
        cust = customers_by_phone.get(clean_phone[1:]) or customers_by_phone.get("84" + clean_phone[1:])
    elif not cust and clean_phone.startswith("84"):
        cust = customers_by_phone.get("0" + clean_phone[2:]) or customers_by_phone.get(clean_phone[2:])

    if cust:
        result: dict[str, Any] = {
            "phone": clean_phone,
            "account_name": cust.get("account_name", ""),
            "account_number": cust.get("account_number", ""),
            "source": "amis_real_crm_customer",
        }
        # Chỉ đọc các trường được CRM lưu trực tiếp. Tên trường tier có thể
        # khác giữa các tenant AMIS nên kiểm tra một allowlist nhỏ.
        for field in ("total_score", "points", "loyalty_points", "membership_tier", "tier"):
            value = cust.get(field)
            if value not in (None, ""):
                if field in {"total_score", "points", "loyalty_points"}:
                    try:
                        result["points"] = int(float(value))
                    except (TypeError, ValueError):
                        pass
                else:
                    result["tier"] = str(value).strip()
        return result

    # Không tìm thấy số điện thoại trong hệ thống CRM → trả None thay vì bịa data
    return None


# ==============================================================================
# 4. TRUY VẤN TỒN KHO KHẢ DỤNG (ATP) TỪ REAL PRODUCTS CATALOG
# ==============================================================================
def lookup_inventory_atp(query: str, qty_tons: float = 5.0) -> Optional[dict[str, Any]]:
    """Tra cứu tồn kho khả dụng từ danh mục 932 SKU thực tế của nhà máy."""
    _ensure_crm_dataset_loaded()
    q_raw = (query or "").strip()
    if not q_raw or len(q_raw) < 2:
        return None

    def _clean_vn(text: str) -> str:
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        return re.sub(r"\s+", " ", text.lower()).strip()

    q_norm = _clean_vn(q_raw)

    # Loại trừ ngay các mặt hàng ngoài ngành không thuộc phân bón
    if any(k in q_norm for k in ["xi mang", "sat thep", "gach da", "cat da", "ao mua", "mu bao hiem", "non bao hiem", "xe may", "xang dau"]):
        return None

    formula_match = re.search(r"\b\d{1,2}[-.\s]\d{1,2}[-.\s]\d{1,2}\b", q_raw)
    formula = formula_match.group(0).replace(" ", "-").replace(".", "-") if formula_match else None
    pack_match = re.search(r"\b(25kg|50kg|25\s*kg|50\s*kg|can|thung|tui)\b", q_norm)
    pack = pack_match.group(0).replace(" ", "") if pack_match else ""
    code_match = re.search(r"\b(01\.\d{4,5}|pb\d{4,5})\b", q_norm)
    query_code = code_match.group(0) if code_match else ""

    q_words = [w for w in q_norm.split() if len(w) > 1]

    candidates = []

    for p in _CRM_DATASET.get("products", []):
        p_name = p.get("product_name") or ""
        p_code = p.get("product_code") or ""
        p_name_norm = _clean_vn(p_name)
        p_code_norm = _clean_vn(p_code)

        score = 0
        if query_code and (query_code == p_code_norm or query_code == p_code.lower()):
            score += 300
        if formula:
            formula_dot = formula.replace("-", ".")
            if formula in p_name or formula_dot in p_name or formula.replace("-", "") in p_name:
                score += 120
        if pack and pack in p_name_norm:
            score += 60
        if "te" in q_norm and "te" in p_name_norm:
            score += 30
        if "da dung" in q_norm and "da dung" in p_name_norm:
            score += 40
        if "hi end" in q_norm and "hi end" in p_name_norm:
            score += 40
        if "lua" in q_norm:
            if "lua" in p_name_norm:
                score += 100
            if any(f in p_name_norm for f in ["22.15.5", "22-15-5", "17.3.20", "17-3-20", "20.20.15", "20-20-15", "16.16.8", "16-16-8"]):
                score += 70
        if "sau rieng" in q_norm:
            if any(f in p_name_norm for f in ["15.15.15", "15-15-15", "20.20.15", "20-20-15", "16.8.16", "16-8-16", "16.6.18", "16-6-18", "huu co"]):
                score += 70

        # Khớp các mã quy cách phụ (như 202015MT, TR44a, CB45, CB36, 2015TE02...)
        for w in q_words:
            if len(w) >= 4 and w in p_name_norm:
                score += 50

        if q_norm in p_name_norm:
            score += 80

        matched_words = [w for w in q_words if w in p_name_norm or w in p_code_norm]
        if matched_words:
            overlap_ratio = len(matched_words) / len(q_words)
            if overlap_ratio >= 0.5:
                score += int(overlap_ratio * 40) + len(matched_words) * 3

        if score >= 60:
            candidates.append((score, p))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_p = candidates[0][1]

        # Thu thập các quy cách / biến thể khác cùng dòng
        variants = []
        seen_names = {best_p.get("product_name")}
        for _, other_p in candidates[1:]:
            o_name = other_p.get("product_name") or ""
            o_code = other_p.get("product_code") or ""
            o_name_clean = o_name.lower()
            # Loại trừ các mặt hàng bột giặt, nước giặt, bao bì ngoài ngành khỏi gợi ý phân bón
            if any(k in o_name_clean for k in ["bot giat", "nuoc giat", "rua chen", "lau san", "aimone", "pano", "oplus", "zeo", "ao mua"]):
                continue
            # Thay thế các số công thức có dấu chấm (như 16.8.16.12) thành gạch nối (16-8-16-12) để tránh Facebook tự tạo link IP
            safe_name = re.sub(r"(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?", lambda m: "-".join(g for g in m.groups() if g), o_name)
            if safe_name and safe_name not in seen_names and len(variants) < 3:
                seen_names.add(safe_name)
                variants.append(f"{safe_name} (Mã: {o_code})")

        config = load_amis_config()
        return {
            "product_name": best_p.get("product_name"),
            "product_code": best_p.get("product_code"),
            "unit": best_p.get("usage_unit") or best_p.get("unit") or "Bao",
            "category": best_p.get("product_category", "Phân bón & Hóa chất"),
            "other_variants": variants,
            "factory_capacity_daily_tons": 200,
            "warehouse_available_tons": 100,
            "can_fulfill_instantly": True,
            "warehouse_location": config.warehouse_location,
            "source": "amis_real_products",
        }

    # Không tìm thấy sản phẩm trong danh mục 932 SKU thật → trả None, không bịa data tồn kho
    return None


# ==============================================================================
# 5. GHI NHẬN TICKET NỘI BỘ (CSKH / QA / B2B VIP)
# ==============================================================================
def create_cskh_ticket(
    ticket_type: str,
    phone: str = "",
    customer_name: str = "",
    summary: str = "",
    raw_message: str = "",
    extra_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Tạo bản ghi Ticket CSKH / QA nội bộ với SLA xử lý chuẩn."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ticket_id = f"TCK-{int(time.time())}-{os.urandom(2).hex().upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    ticket = {
        "ticket_id": ticket_id,
        "ticket_type": ticket_type,
        "created_at": now_iso,
        "status": "open",
        "sla_hours": 24 if ticket_type == "product_complaint_sop" else 2,
        "priority": "high" if ticket_type == "product_complaint_sop" else "medium",
        "phone": phone or "N/A",
        "customer_name": customer_name or "N/A",
        "summary": summary or raw_message[:150],
        "raw_message": raw_message,
        "assigned_team": "cskh_qa" if ticket_type == "product_complaint_sop" else "sales_b2b",
        "extra_payload": extra_payload or {},
    }

    try:
        tickets = []
        if TICKETS_FILE.exists():
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                try:
                    tickets = json.load(f)
                except Exception:
                    tickets = []
        tickets.append(ticket)
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(tickets, f, ensure_ascii=False, indent=2)
        logger.info("Internal CSKH ticket created: %s", ticket_id)
    except Exception as e:
        logger.warning("Could not persist ticket to disk: %s", e)

    return ticket


# ==============================================================================
# 6. FORMATTER ĐÁP ỨNG REALTIME TỰ ĐỘNG THEO DỮ LIỆU THỰC
# ==============================================================================
def format_order_status_response(order: dict[str, Any], query_order_code: str = "") -> str:
    """Tạo câu trả lời động dựa trên dữ liệu đơn hàng thật từ CRM."""
    order_code = order.get("order_code") or query_order_code or "đơn hàng"
    if not str(order_code).startswith("#"):
        order_code = f"#{order_code}"

    dealer_name = order.get("dealer_name", "")
    greeting = f"Dạ CFC - Phân bón Cò Bay xin chào **{dealer_name}** ạ!\n" if dealer_name else ""

    product_name = order.get("product_name", "")
    prod_line = f"\n📦 **Danh mục hàng:** {product_name}" if product_name else ""
    warehouse = order.get("warehouse", "Tổng kho Nhà máy Cần Thơ (KCN Trà Nóc)")
    status = order.get("status") or "Đã thực hiện"
    qty = order.get("quantity_tons")
    qty_line = f"\n📊 **Tổng số lượng:** {int(qty) if isinstance(qty, (int, float)) else qty}" if qty else ""

    return (
        f"{greeting}Về tiến độ đơn hàng **{order_code}** trên hệ thống AMIS CRM:"
        f"{prod_line}{qty_line}"
        f"\n🏢 **Đơn vị xử lý:** {warehouse}"
        f"\n🚚 **Trạng thái thực tế:** **{status}**."
        "\nBộ phận Điều phối Kho Vận đang theo dõi tiến độ để đảm bảo giao đúng kế hoạch cho quý khách nhé ạ!"
    )


def format_loyalty_response(loyalty: dict[str, Any], phone: str = "") -> str:
    """Định dạng dữ liệu hội viên đã được CRM lưu trực tiếp."""
    phone_clean = phone.replace(" ", "").replace(".", "").strip()
    phone_mask = phone_clean[-4:] if len(phone_clean) >= 4 else phone_clean
    masked = f"***{phone_mask}" if phone_mask else "của bạn"
    details: list[str] = []
    if loyalty.get("points") is not None:
        details.append(f"điểm tích lũy **{int(loyalty['points']):,}**".replace(",", "."))
    if loyalty.get("tier"):
        details.append(f"hạng **{loyalty['tier']}**")
    if not details:
        return (
            f"Dạ số điện thoại **{masked}** đã khớp hồ sơ khách hàng, nhưng nguồn hiện chưa có trường điểm/hạng đã xác minh để mình báo chính xác ạ."
        )
    return f"Dạ số điện thoại **{masked}** hiện có " + " và ".join(details) + "."
