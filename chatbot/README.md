# ⚡ CFC AI — Chatbot Control Center v2.1

Hệ thống quản trị và trợ lý AI thông minh đa kênh cho **ZeO Vietnam** và **CFC Cò Bay (Cần Thơ)**.

---

## 🎯 Danh Sách Tính Năng Đã Triển Khai

### 🔴 Nhóm A — Nạp Kiến Thức & Tự Học
1. **Upload File `.md` / `.txt` từ Web:** Tải lên trực tiếp qua giao diện, tự động phân đoạn (chunking) và vector hóa vào Redis ngay lập tức.
2. **Import Google Sheets FAQ:** Dán URL Google Sheets công khai (cột *Câu hỏi | Câu trả lời*), hệ thống tự đọc và nạp vào Vector Store.
3. **Quản Lý Shopee Catalog (CRUD):** Thêm mới, sửa giá, khuyến mãi, quy cách, từ khóa nhận diện và link Shopee trực tiếp trên web.
4. **Auto-Sync Shopee 10 phút:** Background worker tự động sync bảng giá từ Google Sheets mỗi 10 phút.
5. **3-Layer Fallback Thông Minh:**
   - **Score ≥ 78%:** Trả lời trực tiếp từ FAQ.
   - **Score ≥ 55%:** Trả lời + AI Rewrite tự nhiên.
   - **Score < 55%:** Trả lời lịch sự chuyển admin, tự động bắn thông báo Telegram cho Admin và đẩy câu hỏi vào Learning Queue.

### 🟡 Nhóm B — Quản Lý Hội Thoại & Khách Hàng
1. **Xem Lịch Sử Chat Đầy Đủ:** Bấm nút **💬 Chat** trên từng khách hàng để xem dòng thời gian tin nhắn, intent và mốc thời gian.
2. **Bộ Lọc Nâng Cao:** Lọc nhanh theo thương hiệu (ZeO / CFC), lọc khách có SĐT / chưa có SĐT, lọc theo Lead Stage.
3. **Xuất Dữ Liệu CSV:** Nút **📤 Xuất File CSV** tải danh sách khách hàng về máy tính.
4. **Admin Notes & Tags:** Ghi chú nội bộ cho từng khách và gắn tags phân loại (`HOT LEAD`, `CHỜ BÁO GIÁ`, `ĐÃ CHỐT`...).

### 🟢 Nhóm C — AI & Phân Tích Thông Minh
1. **AI Tự Đề Xuất FAQ (1-Click):** AI quét toàn bộ câu hỏi trong Learning Queue, gom nhóm các câu hỏi cùng ý, đề xuất Intent + Câu trả lời chuẩn.
2. **Biểu Đồ Xu Hướng 7 Ngày (Trend Analytics):** Theo dõi số lượng khách mới và leads SĐT theo biểu đồ trực quan ngay trên Dashboard.
3. **Báo Cáo Điều Hành AI (Executive Briefing):** Quét số liệu trong ngày, tổng hợp bản tin kinh doanh và bắn qua Telegram.
4. **Cài Đặt API Keys Không Cần Code:** Cấu hình Telegram Bot Token, Chat ID, Google Gemini API Key, Shopee Sheet URL trực tiếp trên web.

---

## 🏗 Cấu Trúc Thư Mục

```
javis/
├── TAI_LIEU_HE_THONG_CFC_AI.docx  # File tài liệu DOCX hoàn chỉnh
├── README.md                      # Hướng dẫn chi tiết
├── server/
│   ├── main.py                    # FastAPI server + Background Workers
│   ├── admin_routes.py            # Toàn bộ API Endpoints cho Admin
│   ├── rag_search.py              # Semantic search + 3-Layer Fallback
│   ├── embedder.py                # Ollama BGE-M3 embedding (1024 dims)
│   ├── knowledge_sync.py          # Đồng bộ KB snapshot vào Redis
│   ├── document_ingestor.py       # Phân đoạn & vector hóa tài liệu .md
│   ├── shopee_matcher.py          # Khớp sản phẩm Shopee Mall
│   ├── telegram_notifier.py       # Bắn thông báo Lead & Fallback qua Telegram
│   ├── ai_engine.py               # Free Cloud AI (Gemini, OpenRouter, Groq)
│   ├── ai_reporter.py             # Báo Cáo Điều Hành Hàng Ngày
│   ├── settings.json              # File cấu hình API Keys & Ngưỡng RAG
│   └── static/                    # Frontend Admin Dashboard tách đa file
│       ├── admin.html             # Shell HTML chính
│       ├── css/
│       │   ├── base.css           # Variables, Reset, Dark mode
│       │   ├── layout.css         # Sidebar nhóm, Topbar breadcrumb, Footer
│       │   └── components.css     # Cards, Tables, Chat Timeline, Trend Charts
│       └── js/
│           ├── core.js            # Utilities & Navigation
│           └── pages/
│               ├── dashboard.js   # Stats & Weekly Trend
│               ├── documents.js   # Upload .md & Import Sheet
│               ├── shopee.js      # Shopee CRUD & Sheet Sync
│               ├── customers.js   # Chat history, Filters, CSV, Notes
│               ├── learning.js    # Learning Queue & AI Auto-Suggest
│               ├── n8n.js         # n8n workflows control
│               ├── test.js        # Test Bot Semantic Search
│               ├── reports.js     # AI Executive Reports
│               └── settings.js    # Settings & API Keys
└── knowledge/
    ├── shopee_catalog.json        # Database sản phẩm Shopee
    ├── zeo_faq.md                 # Tài liệu ZeO
    └── cfc_faq.md                 # Tài liệu CFC Cò Bay
```

---

## 🚀 Hướng Dẫn Chạy Hệ Thống

1. **Khởi động Server:**
   ```bash
   cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
   source .venv/bin/activate
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Truy cập Giao Diện Admin:**
   Mở trình duyệt: [http://localhost:8000/admin](http://localhost:8000/admin)
