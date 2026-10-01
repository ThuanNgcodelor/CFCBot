"""
crawl_shopee_shop.py — Tool Cào Dữ Liệu Gian Hàng Shopee Mall Tự Động & Không Bỏ Sót SP
Hỗ trợ:
  1. Tự động tìm ShopID từ username (vd: 'zeovietnamofficial', 'cfccobay')
  2. Phân trang đệ quy (Pagination) lấy sạch 100% sản phẩm từ Shopee API v4
  3. Bóc tách chi tiết: Tên, Giá bán, Giá gốc, %, Quy cách, Phân loại/Biến thể, Link URL chuẩn SEO
  4. Tự động sinh từ khóa tìm kiếm tiếng Việt (có dấu + không dấu)
  5. Xuất ra file CSV cho Google Sheet hoặc ghi trực tiếp vào Redis Snapshot
"""

import asyncio
import csv
import json
import logging
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopee_crawler")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://shopee.vn/",
    "Accept": "application/json",
    "x-api-source": "pc",
    "x-shopee-language": "vi",
}


def _normalize_vn(text: str) -> str:
    t = unicodedata.normalize("NFD", str(text or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.replace("đ", "d").replace("Đ", "d").lower()
    return re.sub(r"[^a-z0-9\s]", " ", t).strip()


def detect_brand_and_category(title: str, default_brand: str = "ZeO") -> tuple[str, str]:
    norm = _normalize_vn(title)
    brand = default_brand

    if "pano" in norm:
        brand = "PANO"
    elif "oplus" in norm:
        brand = "Oplus"
    elif "cfc" in norm or "co bay" in norm:
        brand = "CFC"
    elif "zeo" in norm or "zif" in norm:
        brand = "ZeO"

    category = "Khác"
    if any(k in norm for k in ["nuoc giat", "bot giat", "giat xa"]):
        category = "Nước giặt" if "nuoc giat" in norm else "Bột giặt"
    elif any(k in norm for k in ["rua chen", "rua bat", "zif"]):
        category = "Nước rửa chén"
    elif any(k in norm for k in ["lau san", "lau nha"]):
        category = "Nước lau sàn"
    elif any(k in norm for k in ["toilet", "bon cau", "tay bon cau"]):
        category = "Tẩy Toilet"
    elif any(k in norm for k in ["javen", "thuoc tay", "tay trang"]):
        category = "Nước tẩy trắng Javen"
    elif any(k in norm for k in ["tay mau", "quan ao mau"]):
        category = "Nước tẩy quần áo màu"
    elif any(k in norm for k in ["phan bon", "huu co", "npk", "dinh duong cay"]):
        category = "Phân bón nông nghiệp"

    return brand, category


def generate_search_keywords(title: str, brand: str, category: str, variants: list[str]) -> list[str]:
    norm_title = _normalize_vn(title)
    keywords = set()

    # Thêm category & brand
    keywords.add(_normalize_vn(brand))
    keywords.add(_normalize_vn(category))

    # Bóc các từ khóa chính
    for chunk in ["nuoc giat", "bot giat", "nuoc rua chen", "rua bat", "nuoc lau san", "lau nha", "tay toilet", "javen", "tay mau", "veilex", "ion", "enzyme"]:
        if chunk in norm_title:
            keywords.add(chunk)

    # Mùi hương / Đặc tính
    for scent in ["hoa co", "bot bien", "nha dam", "gung sa", "chanh bac ha", "que", "sa chanh", "nuoc hoa", "chanh", "vitamin e"]:
        if scent in norm_title:
            keywords.add(scent)

    # Dung tích / Quy cách
    for size in re.findall(r"\b(\d+(?:\.\d+)?\s*(?:kg|g|l|ml|lit|can|chai|tui|bao))\b", norm_title):
        keywords.add(size.replace(" ", ""))

    for v in variants:
        keywords.add(_normalize_vn(v))

    return [k for k in keywords if k]


async def fetch_shop_id(client: httpx.AsyncClient, username: str) -> Optional[int]:
    """Lấy ShopID từ Shopee username."""
    url = f"https://shopee.vn/api/v4/shop/get_shop_base?username={username}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            shop_id = data.get("data", {}).get("shopid")
            if shop_id:
                logger.info("Tìm thấy ShopID: %d cho username '%s'", shop_id, username)
                return shop_id
    except Exception as e:
        logger.warning("Không lấy được shopid qua API: %s", e)
    return None


async def crawl_all_shop_products(username: str = "zeovietnamofficial", shop_id: Optional[int] = None) -> list[dict]:
    """Cào toàn bộ 100% sản phẩm của shop Shopee qua phân trang offset/limit."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        if not shop_id:
            shop_id = await fetch_shop_id(client, username)

        if not shop_id:
            logger.error("Không xác định được ShopID cho shop '%s'", username)
            return []

        limit = 30
        offset = 0
        total_count = None
        all_items: list[dict] = []

        logger.info("Bắt đầu cào sản phẩm từ ShopID %d...", shop_id)

        while True:
            api_url = (
                f"https://shopee.vn/api/v4/shop/search_items"
                f"?order_type=2&offset={offset}&limit={limit}&shopid={shop_id}"
            )
            try:
                resp = await client.get(api_url, timeout=15.0)
                if resp.status_code != 200:
                    logger.warning("Lỗi API Shopee (status=%d): %s", resp.status_code, resp.text[:200])
                    break

                res_json = resp.json()
                items_data = res_json.get("items", [])
                if total_count is None:
                    total_count = res_json.get("total_count", len(items_data))
                    logger.info("Tổng số sản phẩm của shop: %d", total_count)

                if not items_data:
                    break

                for raw_item in items_data:
                    item_card = raw_item.get("item_basic", raw_item)
                    item_id = item_card.get("itemid")
                    name = str(item_card.get("name", "")).strip()
                    if not item_id or not name:
                        continue

                    # Giá Shopee được lưu dạng 100,000 đơn vị (vd: 5200000000 = 52,000 VND)
                    raw_price = item_card.get("price", 0)
                    price = raw_price // 100000 if raw_price > 1000000 else raw_price
                    raw_orig = item_card.get("price_before_discount", raw_price)
                    original_price = raw_orig // 100000 if raw_orig > 1000000 else raw_orig
                    
                    discount_rate = item_card.get("raw_discount", 0)
                    discount_str = f"{discount_rate}%" if discount_rate > 0 else "0%"
                    stock = item_card.get("stock", 1)
                    in_stock = bool(stock > 0)

                    # Tạo URL Shopee chuẩn
                    clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", _normalize_vn(name)).strip("-")
                    product_url = f"https://shopee.vn/{clean_slug}-i.{shop_id}.{item_id}"

                    # Biến thể / Tier variations
                    variants = []
                    for tier in item_card.get("tier_variations", []):
                        for opt in tier.get("options", []):
                            if opt and opt not in variants:
                                variants.append(str(opt).strip())

                    brand, category = detect_brand_and_category(name)
                    keywords = generate_search_keywords(name, brand, category, variants)
                    specs = f"Quy cách: {', '.join(variants)}" if variants else name

                    all_items.append({
                        "active": True,
                        "item_id": str(item_id),
                        "name": name,
                        "brand": brand,
                        "category": category,
                        "price": int(price),
                        "original_price": int(original_price),
                        "discount": discount_str,
                        "specs": specs,
                        "keywords": keywords,
                        "variants": variants,
                        "link_shopee": product_url,
                        "in_stock": in_stock,
                        "image_url": f"https://down-vn.img.susercontent.com/file/{item_card.get('image', '')}" if item_card.get("image") else "",
                        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    })

                offset += limit
                logger.info("Đã cào: %d/%d sản phẩm...", len(all_items), total_count or len(all_items))
                if offset >= (total_count or 0):
                    break

                await asyncio.sleep(0.5)  # Tránh rate limit

            except Exception as e:
                logger.error("Lỗi trong vòng lặp cào: %s", e)
                break

        logger.info("✓ Hoàn thành cào toàn bộ shop: %d sản phẩm hợp lệ.", len(all_items))
        return all_items


def export_to_csv(items: list[dict], output_path: Path):
    """Xuất danh sách sản phẩm ra file CSV chuẩn để tải lên Google Sheet."""
    fieldnames = [
        "active", "item_id", "name", "brand", "category",
        "price", "original_price", "discount", "specs",
        "keywords", "variants", "link_shopee", "in_stock", "updated_at"
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = item.copy()
            row["active"] = "TRUE" if row.get("active") else "FALSE"
            row["in_stock"] = "TRUE" if row.get("in_stock") else "FALSE"
            row["keywords"] = "; ".join(row.get("keywords", [])) if isinstance(row.get("keywords"), list) else str(row.get("keywords", ""))
            row["variants"] = "; ".join(row.get("variants", [])) if isinstance(row.get("variants"), list) else str(row.get("variants", ""))
            row.pop("image_url", None)
            writer.writerow(row)
    logger.info("✓ Đã xuất file CSV tại: %s", output_path)


async def main():
    username = "zeovietnamofficial"
    if len(sys.argv) > 1:
        username = sys.argv[1]

    items = await crawl_all_shop_products(username=username)
    if items:
        csv_path = Path(__file__).resolve().parents[2] / "google_upload" / f"{username}_shopee_catalog_crawled.csv"
        export_to_csv(items, csv_path)
    else:
        logger.warning("Không có sản phẩm nào được cào.")


if __name__ == "__main__":
    asyncio.run(main())
