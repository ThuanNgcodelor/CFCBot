"""
domains.knowledge.routes — FastAPI Router cho Documents MD, Google Sheets Live Hub và Shopee Catalog.
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from .schemas import SheetTabsRequest, SheetPreviewRequest, SheetSyncRequest, ExtractFaqRequest, ShopeeProduct
from .service import (
    get_sheet_tabs_metadata,
    preview_sheet_content,
    sync_sheet_to_redis_direct,
    upload_csv_file_direct,
    list_knowledge_documents,
    sync_knowledge_documents,
    save_uploaded_document_file,
    import_faq_sheet_to_markdown,
    get_shopee_catalog_items,
    sync_shopee_from_sheet,
)

router = APIRouter(tags=["Knowledge, Sheets & Documents"])


# ── Google Sheets Live Hub ──

@router.post("/sheets/get-tabs")
async def get_google_sheet_tabs_endpoint(req: SheetTabsRequest):
    """Lấy danh sách các Tab (Sheet Name) từ Google Sheet tương tự n8n."""
    return await get_sheet_tabs_metadata(sheet_url=req.sheet_url, api_key=req.api_key)


@router.post("/sheets/preview")
async def preview_google_sheet_endpoint(req: SheetPreviewRequest):
    """Xem trước dữ liệu Google Sheet trực tiếp trên trình duyệt."""
    return await preview_sheet_content(
        sheet_url=req.sheet_url,
        api_key=req.api_key,
        sheet_name=req.sheet_name,
    )


@router.post("/sheets/sync-direct")
async def sync_google_sheet_direct_endpoint(req: SheetSyncRequest):
    """Đồng bộ trực tiếp Google Sheet vào Redis FAQ RAG hoặc Shopee Catalog."""
    return await sync_sheet_to_redis_direct(
        sheet_url=req.sheet_url,
        target_type=req.target_type,
        brand=req.brand,
        sheet_name=req.sheet_name,
        api_key=req.api_key,
    )


@router.post("/sheets/upload-csv")
async def upload_csv_direct_endpoint(
    file: UploadFile = File(...),
    target_type: str = Form("faq"),
    brand: str = Form("zeo"),
):
    """Tải lên file CSV trực tiếp từ máy tính mà không cần kết nối Google Drive."""
    content = await file.read()
    return await upload_csv_file_direct(content_bytes=content, target_type=target_type, brand=brand)


# ── Documents MD Ingestion ──

@router.get("/documents")
async def list_documents_endpoint():
    """Danh sách các file tài liệu trong thư mục knowledge/."""
    return await list_knowledge_documents()


@router.post("/documents/sync")
async def sync_documents_endpoint():
    """Trigger quét lại toàn bộ thư mục knowledge/ và vector hóa."""
    return await sync_knowledge_documents()


@router.post("/documents/upload")
async def upload_document_endpoint(file: UploadFile = File(...), brand: str = Query("auto")):
    """Upload file .md trực tiếp từ trình duyệt vào thư mục knowledge/ và vector hóa ngay."""
    if not file.filename or not (file.filename.endswith(".md") or file.filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .md và .txt")
    content = await file.read()
    return await save_uploaded_document_file(filename=file.filename, content=content)


@router.post("/documents/import-sheet")
async def import_document_from_sheet_endpoint(sheet_url: str = Query(...), brand: str = Query("zeo")):
    """Import nội dung tài liệu từ Google Sheets vào Vector Index."""
    return await import_faq_sheet_to_markdown(sheet_url=sheet_url, brand=brand)


# ── Shopee Catalog CRUD ──

@router.get("/shopee/catalog")
async def get_shopee_catalog_endpoint():
    """Lấy danh sách catalog sản phẩm Shopee hiện có."""
    return await get_shopee_catalog_items()


@router.post("/shopee/sync-sheet")
async def sync_shopee_sheet_endpoint(sheet_url: str = Query("")):
    """Đồng bộ Shopee Catalog từ Google Sheets."""
    return await sync_shopee_from_sheet(sheet_url=sheet_url)
