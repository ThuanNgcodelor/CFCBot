"""
crawl_shopee_playwright.py — Cào 100% Sản Phẩm Shopee Qua Headless Browser (Vượt Anti-bot WAF)
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

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopee_playwright")


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

    category = "Tẩy rửa & Giặt giũ"
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

    keywords.add(_normalize_vn(brand))
    keywords.add(_normalize_vn(category))

    for chunk in ["nuoc giat", "bot giat", "nuoc rua chen", "rua bat", "nuoc lau san", "lau nha", "tay toilet", "javen", "tay mau", "veilex", "ion", "enzyme"]:
        if chunk in norm_title:
            keywords.add(chunk)

    for scent in ["hoa co", "bot bien", "nha dam", "gung sa", "chanh bac ha", "que", "sa chanh", "nuoc hoa", "chanh", "vitamin e"]:
        if scent in norm_title:
            keywords.add(scent)

    for size in re.findall(r"\b(\d+(?:\.\d+)?\s*(?:kg|g|l|ml|lit|can|chai|tui|bao))\b", norm_title):
        keywords.add(size.replace(" ", ""))

    for v in variants:
        keywords.add(_normalize_vn(v))

    return [k for k in keywords if k]


async def crawl_shopee_store(username: str = "zeovietnamofficial") -> list[dict]:
    products_map: dict[str, dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="vi-VN",
        )
        page = await context.new_page()

        async def handle_response(response):
            url = response.url
            if any(k in url for k in ["search_items", "rcmd_items", "recommend", "item/get"]):
                try:
                    data = await response.json()
                    items = data.get("items") or data.get("data", {}).get("items") or []
                    for raw_item in items:
                        item_card = raw_item.get("item_basic", raw_item)
                        item_id = str(item_card.get("itemid") or item_card.get("item_id", ""))
                        name = str(item_card.get("name", "")).strip()
                        shop_id = str(item_card.get("shopid") or item_card.get("shop_id", ""))
                        if not item_id or not name:
                            continue

                        raw_price = item_card.get("price", 0)
                        price = raw_price // 100000 if raw_price > 1000000 else raw_price
                        raw_orig = item_card.get("price_before_discount", raw_price)
                        original_price = raw_orig // 100000 if raw_orig > 1000000 else raw_orig
                        discount_rate = item_card.get("raw_discount", 0)
                        discount_str = f"{discount_rate}%" if discount_rate > 0 else "0%"
                        stock = item_card.get("stock", 1)

                        clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", _normalize_vn(name)).strip("-")
                        product_url = f"https://shopee.vn/{clean_slug}-i.{shop_id}.{item_id}" if shop_id else f"https://shopee.vn/product/{item_id}"

                        variants = []
                        for tier in item_card.get("tier_variations", []):
                            for opt in tier.get("options", []):
                                if opt and opt not in variants:
                                    variants.append(str(opt).strip())

                        brand, category = detect_brand_and_category(name)
                        keywords = generate_search_keywords(name, brand, category, variants)

                        products_map[item_id] = {
                            "active": True,
                            "item_id": item_id,
                            "name": name,
                            "brand": brand,
                            "category": category,
                            "price": int(price),
                            "original_price": int(original_price),
                            "discount": discount_str,
                            "specs": f"Quy cách: {', '.join(variants)}" if variants else name,
                            "keywords": keywords,
                            "variants": variants,
                            "link_shopee": product_url,
                            "in_stock": bool(stock > 0),
                            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        }
                        logger.info("✓ [Shopee API] %s (Giá: %s)", name, price)
                except Exception:
                    pass

        page.on("response", handle_response)

        target_url = f"https://shopee.vn/{username}"
        logger.info("Opening Shopee store URL: %s", target_url)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)

        # Try to click on "TẤT CẢ SẢN PHẨM" tab or scroll down
        try:
            tab_btn = await page.query_selector("a[href*='shop'], .navbar-link, .shop-tab-all")
            if tab_btn:
                await tab_btn.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # Scroll down multiple times to trigger all pagination requests
        for i in range(8):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(1500)

        # Fallback: Extract from DOM links if API was missing items
        dom_links = await page.evaluate(r"""() => {
            const list = [];
            const anchors = document.querySelectorAll('a[href*="-i."]');
            anchors.forEach(a => {
                const href = a.href;
                const text = (a.innerText || '').trim();
                if (href && text && text.length > 5) {
                    list.push({ href: href.split('?')[0], text });
                }
            });
            return list;
        }""")

        for d in dom_links:
            href = d["href"]
            match = re.search(r"-i\.(\d+)\.(\d+)", href)
            if match:
                shop_id, item_id = match.groups()
                if item_id not in products_map:
                    lines = [ln.strip() for ln in d["text"].split("\n") if ln.strip()]
                    name = lines[0] if lines else "Sản phẩm Shopee"
                    price_match = re.search(r"(\d+(?:\.\d+)?)\s*đ", d["text"])
                    price = int(price_match.group(1).replace(".", "")) if price_match else 0

                    brand, category = detect_brand_and_category(name)
                    keywords = generate_search_keywords(name, brand, category, [])

                    products_map[item_id] = {
                        "active": True,
                        "item_id": item_id,
                        "name": name,
                        "brand": brand,
                        "category": category,
                        "price": price,
                        "original_price": price,
                        "discount": "Ưu đãi",
                        "specs": name,
                        "keywords": keywords,
                        "variants": [],
                        "link_shopee": href,
                        "in_stock": True,
                        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    }
                    logger.info("✓ [Shopee DOM] %s (%s)", name, href)

        await browser.close()

    items_list = list(products_map.values())
    logger.info("✓ Tổng kết cào được: %d sản phẩm từ gian hàng Shopee.", len(items_list))
    return items_list


def export_to_csv(items: list[dict], output_path: Path):
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
            writer.writerow(row)
    logger.info("✓ Đã xuất file CSV tại: %s", output_path)


async def main():
    username = "zeovietnamofficial"
    if len(sys.argv) > 1:
        username = sys.argv[1]

    items = await crawl_shopee_store(username=username)
    if items:
        csv_path = Path(__file__).resolve().parents[2] / "google_upload" / f"{username}_shopee_catalog_crawled.csv"
        export_to_csv(items, csv_path)
    else:
        logger.warning("Không tìm thấy sản phẩm nào từ gian hàng '%s'.", username)


if __name__ == "__main__":
    asyncio.run(main())
