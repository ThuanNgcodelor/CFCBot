"""
domains.knowledge.service — Business logic cho Kho Tri Thức, Documents MD Ingestion, Google Sheets Live Hub và Shopee Catalog.
"""

import csv
import io
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, UploadFile
from domains.common.db import get_redis_client
from domains.common.config import get_cfg

logger = logging.getLogger(__name__)

_KNOWLEDGE_DIR = Path(__file__).resolve().parents[4] / "knowledge"


def extract_google_sheet_id(url: str) -> str:
    """Bóc tách Sheet ID từ đường link Google Sheets."""
    if "spreadsheets/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return url.strip()


async def fetch_google_sheet_data(
    url: str,
    api_key: Optional[str] = None,
    sheet_name: Optional[str] = None
) -> List[List[str]]:
    """Tải và parse dữ liệu Google Sheet qua Google Sheets API v4 hoặc CSV Export/GViz."""
    sheet_id = extract_google_sheet_id(url)
    api_key = (api_key or "").strip()
    headers = {"User-Agent": "CFC-AI-Viewer/2.0"}

    if api_key and (api_key.startswith("ya29.") or "bearer" in api_key.lower()):
        token = api_key.replace("Bearer ", "").replace("bearer ", "").strip()
        headers["Authorization"] = f"Bearer {token}"
        api_key = ""

    # 1. Gọi Google Sheets API v4 nếu có API Key hoặc Bearer Token
    if api_key or "Authorization" in headers:
        range_name = f"'{sheet_name}'!A1:Z1000" if sheet_name and sheet_name != "Trang tính 1 (Mặc định)" else "A1:Z1000"
        api_v4_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_name}"
        if api_key:
            api_v4_url += f"?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(api_v4_url, headers=headers)
                if resp.status_code == 200:
                    vals = resp.json().get("values", [])
                    if vals:
                        return vals
                elif resp.status_code == 401 or resp.status_code == 403:
                    err_msg = resp.json().get("error", {}).get("message", "API Key / Token không hợp lệ hoặc Sheet chưa cấp quyền.")
                    raise HTTPException(status_code=401, detail=f"Google API Error ({resp.status_code}): {err_msg}")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Google API v4 values fetch failed: %s", e)

    # 2. Thử qua GViz URL
    gviz_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    if sheet_name and sheet_name != "Trang tính 1 (Mặc định)":
        gviz_url += f"&sheet={sheet_name}"

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(gviz_url, headers=headers)
            if resp.status_code == 200:
                csv_text = resp.text
                reader = list(csv.reader(io.StringIO(csv_text)))
                if reader and len(reader) > 0 and len(reader[0]) > 0:
                    return reader
    except Exception:
        pass

    # 3. Thử qua CSV Export URL
    gid = ""
    if "gid=" in url:
        gid = url.split("gid=")[1].split("&")[0].split("#")[0]
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid:
        csv_url += f"&gid={gid}"

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(csv_url, headers=headers)
            if resp.status_code == 200:
                csv_text = resp.text
                reader = list(csv.reader(io.StringIO(csv_text)))
                if reader and len(reader) > 0:
                    return reader
            elif resp.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail=(
                        "Google Sheet đang ở chế độ Riêng tư (401 Unauthorized).\n\n"
                        "Cách 1: Mở Google Sheet -> Chia sẻ -> Bất kỳ ai có liên kết (Người xem).\n"
                        "Cách 2: Nhập Google Cloud API Key / Token."
                    )
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể tải Google Sheet: {str(e)}")

    raise HTTPException(status_code=400, detail="Không thể đọc dữ liệu bảng tính. Vui lòng kiểm tra quyền chia sẻ hoặc Google API Key.")


async def get_sheet_tabs_metadata(sheet_url: str, api_key: Optional[str] = None) -> dict:
    """Lấy danh sách các Tab (Sheet Name) từ Google Sheet."""
    sheet_id = extract_google_sheet_id(sheet_url)
    if not sheet_id:
        raise HTTPException(status_code=400, detail="URL Google Sheet không hợp lệ")

    api_key = (api_key or "").strip()
    headers = {"User-Agent": "CFC-AI-Client/2.0"}
    if api_key and (api_key.startswith("ya29.") or "bearer" in api_key.lower()):
        token = api_key.replace("Bearer ", "").replace("bearer ", "").strip()
        headers["Authorization"] = f"Bearer {token}"
        api_key = ""

    if api_key or "Authorization" in headers:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        if api_key:
            url += f"?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    sheets_meta = data.get("sheets", [])
                    tabs = []
                    for s in sheets_meta:
                        props = s.get("properties", {})
                        tabs.append({
                            "title": props.get("title", "Sheet1"),
                            "sheet_id": props.get("sheetId", 0),
                            "index": props.get("index", 0),
                            "row_count": props.get("gridProperties", {}).get("rowCount", 0),
                        })
                    return {
                        "success": True,
                        "spreadsheet_title": data.get("properties", {}).get("title", "Google Spreadsheet"),
                        "tabs": tabs,
                        "total_tabs": len(tabs),
                    }
                elif resp.status_code in [401, 403]:
                    err_msg = resp.json().get("error", {}).get("message", "API Key không có quyền.")
                    raise HTTPException(status_code=401, detail=f"Google API Error ({resp.status_code}): {err_msg}")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Google API v4 metadata call failed: %s", e)

    return {
        "success": True,
        "spreadsheet_title": "Google Spreadsheet",
        "tabs": [
            {"title": "Trang tính 1 (Mặc định)", "sheet_id": 0, "index": 0},
            {"title": "FAQ Knowledge", "sheet_id": 1, "index": 1},
            {"title": "Shopee Catalog", "sheet_id": 2, "index": 2}
        ],
        "total_tabs": 3,
        "note": "Nếu cần tự động tải đúng tên tab riêng tư, hãy nhập Google API Key."
    }


async def preview_sheet_content(sheet_url: str, api_key: Optional[str] = None, sheet_name: Optional[str] = None, max_rows: int = 50) -> dict:
    """Xem trước dữ liệu Google Sheet dạng bảng trên giao diện."""
    reader = await fetch_google_sheet_data(sheet_url, api_key, sheet_name)
    if not reader or len(reader) == 0:
        return {"success": False, "message": "Bảng tính rỗng"}

    headers = [h.strip() for h in reader[0] if h.strip()]
    rows = []
    for r in reader[1:max_rows + 1]:
        if any(r):
            row_dict = {headers[i]: r[i].strip() if i < len(r) else "" for i, h in enumerate(headers)}
            rows.append(row_dict)

    sheet_id = extract_google_sheet_id(sheet_url)
    return {
        "success": True,
        "sheet_id": sheet_id,
        "sheet_name": sheet_name or "Sheet1",
        "columns": headers,
        "rows": rows,
        "total_rows": len(reader) - 1,
        "preview_count": len(rows),
    }


async def sync_sheet_to_redis_direct(
    sheet_url: str,
    target_type: str = "faq",
    brand: str = "zeo",
    sheet_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> dict:
    """Đồng bộ trực tiếp dữ liệu Google Sheet vào Redis và Vector Index."""
    reader = await fetch_google_sheet_data(sheet_url, api_key, sheet_name)
    if not reader or len(reader) < 2:
        raise HTTPException(status_code=400, detail="Bảng tính rỗng hoặc không có dữ liệu hợp lệ")

    headers = [h.strip() for h in reader[0]]

    # FAQ Knowledge Sync
    if target_type == "faq":
        items = []
        for r in reader[1:]:
            if not any(r):
                continue
            row = {headers[i]: r[i].strip() if i < len(r) else "" for i in range(len(headers))}

            def g(*keys):
                for k in keys:
                    for col in row:
                        if col.lower().strip() == k.lower():
                            return str(row[col]).strip()
                return ""

            answer = g("câu trả lời", "cau tra loi", "answer", "noi dung")
            if not answer:
                continue

            items.append({
                "category": g("danh mục", "category", "nhóm"),
                "intent": g("intent", "chủ đề", "ma chu de") or f"intent_{len(items)+1}",
                "question_examples": g("câu hỏi mẫu", "cau hoi mau", "question_examples"),
                "answer": answer,
                "learning_tags": g("learning_tags", "từ khóa", "tags"),
                "risk_level": g("risk_level", "mức rủi ro") or "low",
                "brand": brand.lower(),
                "active": True,
            })

        r = get_redis_client()
        await r.set(f"{brand.lower()}:kb:basic:active", json.dumps(items, ensure_ascii=False))
        await r.aclose()

        from knowledge_sync import sync_brand
        vector_res = await sync_brand(brand.lower())

        return {
            "success": True,
            "target": "faq",
            "brand": brand.lower(),
            "synced_count": len(items),
            "vector_sync": vector_res,
            "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # Shopee Catalog Sync
    new_items = []
    for r in reader[1:]:
        if not any(r):
            continue
        row = {headers[i]: r[i].strip() if i < len(r) else "" for i in range(len(headers))}

        def g_s(*keys):
            for k in keys:
                for col in row:
                    if col.lower().strip() == k.lower():
                        return str(row[col]).strip()
            return ""

        name = g_s("tên sp", "ten san pham", "ten sp", "name", "tên sản phẩm")
        link = g_s("link shopee", "link", "url", "shopee link")
        if not name or not link:
            continue

        raw_kw = g_s("từ khóa", "tu khoa", "keywords")
        kws = [k.strip() for k in raw_kw.split(",") if k.strip()] if raw_kw else []

        new_items.append({
            "brand": (g_s("brand", "thương hiệu") or brand).upper(),
            "name": name,
            "variant": g_s("quy cách", "quy cach", "variant"),
            "price": g_s("giá", "gia", "price", "giá bán"),
            "promotion": g_s("ưu đãi", "uu dai", "promotion", "khuyến mãi"),
            "link": link,
            "keywords": kws,
        })

    r = get_redis_client()
    await r.set("zeo:shopee:catalog:active", json.dumps(new_items, ensure_ascii=False))
    await r.set("zeo:shopee:catalog:last_sync", datetime.now().isoformat())
    await r.aclose()

    try:
        # pyrefly: ignore [missing-module-attribute]
        from shopee_matcher import reload_catalog
        reload_catalog()
    except Exception:
        pass

    return {
        "success": True,
        "target": "shopee",
        "synced_count": len(new_items),
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


async def upload_csv_file_direct(content_bytes: bytes, target_type: str = "faq", brand: str = "zeo") -> dict:
    """Nạp file CSV trực tiếp từ máy tính vào Redis và Vector Index."""
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content_bytes.decode("latin-1")

    reader = list(csv.reader(io.StringIO(text)))
    if not reader or len(reader) < 2:
        raise HTTPException(status_code=400, detail="File CSV rỗng hoặc không có dữ liệu hợp lệ")

    headers = [h.strip() for h in reader[0]]

    if target_type == "faq":
        items = []
        for r in reader[1:]:
            if not any(r):
                continue
            row = {headers[i]: r[i].strip() if i < len(r) else "" for i in range(len(headers))}

            def g(*keys):
                for k in keys:
                    for col in row:
                        if col.lower().strip() == k.lower():
                            return str(row[col]).strip()
                return ""

            answer = g("câu trả lời", "cau tra loi", "answer", "noi dung")
            if not answer:
                continue

            items.append({
                "category": g("danh mục", "category", "nhóm"),
                "intent": g("intent", "chủ đề", "ma chu de") or f"intent_{len(items)+1}",
                "question_examples": g("câu hỏi mẫu", "cau hoi mau", "question_examples"),
                "answer": answer,
                "learning_tags": g("learning_tags", "từ khóa", "tags"),
                "risk_level": g("risk_level", "mức rủi ro") or "low",
                "brand": brand.lower(),
                "active": True,
            })

        r = get_redis_client()
        await r.set(f"{brand.lower()}:kb:basic:active", json.dumps(items, ensure_ascii=False))
        await r.aclose()

        from knowledge_sync import sync_brand
        vector_res = await sync_brand(brand.lower())

        return {
            "success": True,
            "target": "faq",
            "brand": brand.lower(),
            "synced_count": len(items),
            "vector_sync": vector_res,
            "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # Shopee
    new_items = []
    for r in reader[1:]:
        if not any(r):
            continue
        row = {headers[i]: r[i].strip() if i < len(r) else "" for i in range(len(headers))}

        def g_s(*keys):
            for k in keys:
                for col in row:
                    if col.lower().strip() == k.lower():
                        return str(row[col]).strip()
            return ""

        name = g_s("tên sp", "ten san pham", "ten sp", "name", "tên sản phẩm")
        link = g_s("link shopee", "link", "url", "shopee link")
        if not name or not link:
            continue

        raw_kw = g_s("từ khóa", "tu khoa", "keywords")
        kws = [k.strip() for k in raw_kw.split(",") if k.strip()] if raw_kw else []

        new_items.append({
            "brand": (g_s("brand", "thương hiệu") or brand).upper(),
            "name": name,
            "variant": g_s("quy cách", "quy cach", "variant"),
            "price": g_s("giá", "gia", "price", "giá bán"),
            "promotion": g_s("ưu đãi", "uu dai", "promotion", "khuyến mãi"),
            "link": link,
            "keywords": kws,
        })

    r = get_redis_client()
    await r.set("zeo:shopee:catalog:active", json.dumps(new_items, ensure_ascii=False))
    await r.set("zeo:shopee:catalog:last_sync", datetime.now().isoformat())
    await r.aclose()

    try:
        # pyrefly: ignore [missing-module-attribute]
        from shopee_matcher import reload_catalog
        reload_catalog()
    except Exception:
        pass

    return {
        "success": True,
        "target": "shopee",
        "synced_count": len(new_items),
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


async def list_knowledge_documents() -> dict:
    """Lấy danh sách các tài liệu trong thư mục knowledge/."""
    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(_KNOWLEDGE_DIR.glob("*.md")) + sorted(_KNOWLEDGE_DIR.glob("*.txt")):
        stat = f.stat()
        files.append({
            "name": f.name,
            "size_kb": round(stat.st_size / 1024, 1),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "path": str(f),
        })
    return {"total": len(files), "files": files}


async def sync_knowledge_documents() -> dict:
    """Quét toàn bộ thư mục knowledge/ và nạp vào Vector Index."""
    try:
        from document_ingestor import ingest_knowledge_folder
        res = await ingest_knowledge_folder()
        return {"success": True, "result": res}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def save_uploaded_document_file(filename: str, content: bytes) -> dict:
    """Lưu file tài liệu Markdown và tự động ingest vào Vector Index."""
    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _KNOWLEDGE_DIR / filename
    dest.write_bytes(content)
    try:
        # pyrefly: ignore [missing-module-attribute]
        from document_ingestor import ingest_single_file
        res = await ingest_single_file(str(dest))
    except Exception:
        from document_ingestor import ingest_knowledge_folder
        res = await ingest_knowledge_folder()
    return {"success": True, "filename": filename, "ingest_result": res}


async def import_faq_sheet_to_markdown(sheet_url: str, brand: str = "zeo") -> dict:
    """Tải Google Sheet và chuyển thành tài liệu Markdown trong knowledge/."""
    reader = await fetch_google_sheet_data(sheet_url)
    if not reader or len(reader) < 2:
        raise HTTPException(status_code=400, detail="Sheet trống hoặc không đọc được")

    headers = reader[0]
    md_lines = [f"# Import từ Google Sheets — {datetime.now().strftime('%Y-%m-%d')}\n"]
    if len(headers) >= 2:
        q_idx, a_idx = 0, 1
        for row in reader[1:]:
            q = row[q_idx].strip() if len(row) > q_idx else ""
            a = row[a_idx].strip() if len(row) > a_idx else ""
            if q and a:
                md_lines.append(f"## {q}\n{a}\n")
    else:
        for row in reader[1:]:
            md_lines.append(" | ".join(row))

    md_content = "\n".join(md_lines)
    fname = f"{brand.lower()}_sheet_import_{int(time.time())}.md"
    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    fpath = _KNOWLEDGE_DIR / fname
    fpath.write_text(md_content, encoding="utf-8")

    # pyrefly: ignore [missing-module-attribute]
    from document_ingestor import ingest_single_file
    res = await ingest_single_file(str(fpath))

    return {
        "success": True,
        "rows_imported": len(reader) - 1,
        "filename": fname,
        "ingest_result": res,
        "message": f"Đã import {len(reader) - 1} dòng và vector hóa thành công!"
    }


async def get_shopee_catalog_items() -> dict:
    """Lấy danh sách catalog sản phẩm Shopee hiện có trong Redis."""
    r = get_redis_client()
    try:
        raw = await r.get("zeo:shopee:catalog:active")
        items = json.loads(raw) if raw else []
        last_sync = await r.get("zeo:shopee:catalog:last_sync")
        return {"total": len(items), "items": items, "last_sync": last_sync}
    finally:
        await r.aclose()


async def sync_shopee_from_sheet(sheet_url: str = "") -> dict:
    """Đồng bộ Shopee Catalog từ Google Sheets vào Redis."""
    cfg = get_cfg()
    url = sheet_url or cfg.get("shopee", {}).get("sheet_url", "")
    if not url:
        return {"success": False, "error": "Chưa cấu hình Shopee Sheet URL"}
    return await sync_sheet_to_redis_direct(sheet_url=url, target_type="shopee")
