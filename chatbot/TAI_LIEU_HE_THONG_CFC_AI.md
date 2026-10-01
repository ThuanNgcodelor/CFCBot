# TÀI LIỆU HƯỚNG DẪN & BÁO CÁO HỆ THỐNG CFC AI
## CHATBOT CONTROL CENTER & SINGLE-BRAIN RAG v2.2

*Dự án Chatbot Thông Minh Đa Kênh — ZeO Vietnam & CFC Cò Bay*  
*Cập nhật: 19/08/2026 (Kiến trúc DDD & Modular Architecture + SPA Deep Linking + Single-Brain)*

---

## 1. TỔNG QUAN HỆ THỐNG VÀ KIẾN TRÚC CÔNG NGHỆ

Hệ thống **CFC AI Chatbot Control Center** là nền tảng quản trị và hỗ trợ khách hàng đa kênh (Messenger, Web, Telegram) cho hai thương hiệu:
1. **ZeO Vietnam** (Hóa mỹ phẩm gia dụng sinh học, nước giặt, nước rửa chén, chất tẩy rửa sinh học...)
2. **CFC Cò Bay** (Phân bón NPK & Dinh dưỡng cây trồng Cần Thơ)

### 🌟 Nguyên Tắc Hoạt Động Cốt Lõi (Single-Brain Architecture):
* **FastAPI Python là "Bộ Não Duy Nhất" (Single Brain):** Toàn bộ logic nhận diện intent, session memory, guardrails, semantic RAG và trích xuất số điện thoại được xử lý tập trung trong Python. n8n đóng vai trò I/O Adapter tiếp nhận webhook từ Facebook Messenger.
* **In-Memory Hot Knowledge Cache (< 1ms):** Tải trước toàn bộ FAQ lên RAM khi khởi động, cho tốc độ tra cứu tức thì.
* **Không Ảo Giác (Zero-Hallucination):** Nếu thông tin không có trong Google Sheet/Redis, bot tuyệt đối không tự bịa giá, thành phần hay chính sách.
* **Tốc Độ Xử Lý Siêu Tốc:** Phản hồi trung bình chỉ **~7.8ms/câu**, vượt qua **98/98 kịch bản kiểm thử NLU (100.0%)**.

### 🛠️ Công Nghệ Tích Hợp:
* **Backend Framework:** FastAPI (Python 3.9+) xây dựng theo mô hình **Domain-Driven Design (DDD)**.
* **Cơ sở dữ liệu Vector & Cache:** RediSearch Vector KNN (HNSW/FLAT, BGE-M3 1024 dims) lưu trữ FAQ, Session khách hàng và Learning Queue.
* **Mô hình AI Cục Bộ (Local AI):** Ollama phục vụ mô hình `bge-m3` tạo embedding tiếng Việt và `qwen2.5:7b-instruct` viết lại câu tự nhiên.
* **Mô hình AI Đám Mây (Cloud AI):** Groq (`openai/gpt-oss-120b`), Google Gemini 2.0 Flash, OpenRouter phục vụ Trợ lý điều hành AI và sinh báo cáo kinh doanh.
* **Telegram Notifier:** Tự động bắn thông báo Lead có SĐT mới và Báo cáo điều hành qua Telegram Bot.
* **Shopee Matcher:** Khớp chính xác tên sản phẩm, quy cách, từ khóa và gửi link mua hàng đúng chuẩn Shopee Mall.

---

## 2. DANH SÁCH CÁC TÍNH NĂNG ĐÃ HOÀN THIỆN ĐẦY ĐỦ

### 🤖 1. Trợ Lý Điều Hành AI & Thực Thi Công Cụ Tự Động (Autonomous Agent)
* **Trò chuyện trực tiếp:** Quản trị viên nhắn tin hỏi tình hình kinh doanh, số liệu leads, trạng thái bot.
* **Tự động thực thi công cụ (Autonomous Tool Calling):**
  * Hỏi về khách hàng/leads $\rightarrow$ Tự động đọc Redis CRM và trả thẻ số liệu trực quan.
  * Hỏi về n8n $\rightarrow$ Tự động quét danh sách workflows, phát hiện lỗi và cung cấp nút bật/tắt trực tiếp trong khung chat.
  * Hỏi về hàng đợi học $\rightarrow$ Tự động tóm tắt các câu hỏi khách hàng đang chờ admin duyệt.

### 📊 2. Báo Cáo Điều Hành Kinh Doanh (AI Executive Briefing)
* **Tổng hợp tự động:** Quét toàn bộ tương tác khách hàng, số lead thu thập SĐT và Learning Queue trong ngày.
* **Sinh bản tin Markdown:** Phân tích nhu cầu nổi bật, tỷ lệ chuyển đổi lead và đề xuất hành động cho ngày tiếp theo.
* **Cơ chế Zero-Fail Fallback:** Nếu mất mạng hoặc AI bên ngoài gián đoạn, hệ thống tự động sinh báo cáo từ số liệu thật của Redis, đảm bảo không bao giờ bị lỗi giao diện.

### 🌐 3. Google Sheets Live Hub (Chuẩn Cơ Chế n8n)
* **Tải danh sách Tab tự động (From List):** Kết nối Google Sheets API v4 metadata, tự động đọc toàn bộ danh sách Tab (Sheet Name) vào dropdown cho người dùng chọn.
* **Live Preview & 1-Click Sync:** Xem trước bảng tính trực tiếp trên web và đồng bộ 1 chạm vào Redis / Vector Index.
* **Hỗ trợ kéo thả CSV:** Cho phép nạp trực tiếp file `.csv` từ máy tính mà không cần cấp quyền Google Cloud.

### 🔗 4. SPA URL Hash Routing & Deep Linking
* **Đồng bộ URL Hash:** Chuyển tab tự động cập nhật URL (`/#assistant`, `/#customers`, `/#reports`, `/#n8n`, `/#learning`, `/#documents`, `/#test`, `/#settings`).
* **Giữ nguyên Tab khi F5 (Reload):** Tải lại trang sẽ mở đúng tab đang làm việc mà không bị nhảy về Dashboard.
* **Hỗ trợ nút Back/Forward:** Điều hướng mượt mà với lịch sử trình duyệt.

### 👥 5. Quản Lý Hội Thoại Khách Hàng & Leads CRM
* **Timeline hội thoại:** Xem toàn bộ lịch sử tin nhắn của khách và bot theo thời gian thực.
* **Bộ lọc đa chiều:** Lọc theo thương hiệu (ZeO / CFC), theo SĐT (Đã có / Chưa có), theo Lead Stage.
* **Xuất file CSV:** 1 click tải danh sách khách hàng và số điện thoại về máy tính cho đội ngũ sales.
* **Ghi chú nội bộ & Tags:** Gắn nhãn phân loại (`HOT LEAD`, `CHỜ BÁO GIÁ`, `ĐÃ CHỐT`...).

### 🧠 6. Hàng Đợi Học & AI Tự Đề Xuất FAQ (Learning Queue)
* **Ghi nhận câu hỏi chưa chắc:** Tự động gom các câu hỏi bot chưa tự tin trả lời vào hàng đợi.
* **AI Auto-Suggest:** AI tự động phân tích, gom nhóm câu hỏi tương tự và đề xuất câu trả lời mẫu.
* **1-Click Approve:** Duyệt câu hỏi nạp thẳng vào Redis Vector Index tức thì.

---

## 3. CẤU TRÚC THƯ MỤC SOURCE CODE (CHUẨN DDD)

```
javis/
├── TAI_LIEU_HE_THONG_CFC_AI.md  # Tài liệu hệ thống chi tiết (Markdown)
├── README.md                    # Hướng dẫn nhanh dự án
├── server/
│   ├── domains/                 # 📂 9 Domain Packages theo mô hình DDD
│   │   ├── common/              # Shared Kernel: Redis connection pool, Settings I/O, Config
│   │   │   ├── config.py
│   │   │   └── db.py
│   │   ├── system/              # Status, Health check, Cài đặt & Analytics
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── assistant/           # Trợ lý điều hành AI & Autonomous Tool Execution
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── customers/           # Quản lý khách hàng, hội thoại, Leads CRM & Export CSV
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── n8n/                 # Quản trị Workflow n8n, Executions & Real-time File Watching
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── reports/             # Báo cáo điều hành kinh doanh AI Insights
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── learning/            # Hàng đợi học (Learning Queue) & AI gợi ý FAQ
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── knowledge/           # Kho kiến thức Markdown, Google Sheets Live Hub & Shopee
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   └── rag_test/            # Kiểm thử Semantic Search RAG & NLU
│   │       ├── service.py
│   │       └── routes.py
│   │
│   ├── scripts/                 # 📂 Thư mục chứa các tool cào Shopee & xử lý CSV chạy 1 lần
│   │   ├── crawl_shopee_playwright.py
│   │   ├── crawl_shopee_shop.py
│   │   ├── crawl_shopee_with_auth.py
│   │   ├── shopee_interactive_crawler.py
│   │   ├── clean_shopee_crawled_csv.py
│   │   ├── format_crawled_shopee_catalog.py
│   │   ├── build_exact_shopee_catalog.py
│   │   ├── shopee_auth.json
│   │   └── generate_doc.py
│   │
│   ├── main.py                  # Server FastAPI chính (port 8000)
│   ├── admin_routes.py          # Facade Gateway Router kết nối 9 domains
│   ├── chat_pipeline.py         # Não bộ xử lý tin nhắn & NLU
│   ├── rag_search.py            # Semantic Search FAQ (In-memory RAM < 1ms)
│   ├── embedder.py              # Tạo vector embedding Ollama (bge-m3)
│   ├── knowledge_sync.py        # Đồng bộ FAQ vào RediSearch Vector Index
│   ├── ai_engine.py             # Kết nối LLMs (Groq, Gemini, OpenRouter, Ollama)
│   ├── ai_agent_tools.py        # Autonomous Tool Calling cho Trợ lý AI
│   ├── ai_reporter.py           # Sinh Báo Cáo Điều Hành Kinh Doanh Hàng Ngày
│   ├── document_ingestor.py     # Nạp và phân đoạn tài liệu .md vào Vector Index
│   ├── shopee_matcher.py        # Nhận diện và khớp link Shopee Mall
│   ├── telegram_notifier.py     # Gửi thông báo Lead, Cảnh báo Fallback qua Telegram
│   ├── eval_test_suite.py       # Bộ 98 test cases kiểm thử NLU tự động
│   ├── settings.json            # File lưu toàn bộ cấu hình API Keys & Ngưỡng RAG
│   ├── requirements.txt         # Danh sách thư viện Python
│   │
│   └── static/                  # Giao diện Admin Dashboard (SPA)
│       ├── admin.html           # Shell HTML bố cục Sidebar, Topbar, Modals
│       ├── css/
│       │   ├── base.css         # Dark Mode Palette, Typography
│       │   ├── layout.css       # Bố cục Sidebar, Topbar Breadcrumb, Footer
│       │   └── components.css   # Cards, Tables, Buttons, Badges, Modals, Action Cards
│       └── js/
│           ├── core.js          # SPA Hash Routing, Markdown Formatter, State
│           └── pages/
│               ├── assistant.js # Trợ lý AI & Action Cards tương tác
│               ├── dashboard.js # Dashboard Stats & Trend Analytics
│               ├── documents.js # Nạp tài liệu Markdown & Tự học
│               ├── shopee.js    # Google Sheets Live Hub Modal & Sync
│               ├── customers.js # Lịch sử chat, Bộ lọc, Export CSV, Notes & Tags
│               ├── learning.js  # Learning Queue & AI Auto-Suggest FAQ
│               ├── n8n.js       # Quản lý Workflows n8n & File Watcher
│               ├── test.js      # Công cụ Test Bot ngữ nghĩa
│               ├── reports.js   # Báo cáo điều hành AI
│               └── settings.js  # Cấu hình API Keys trực quan
│
└── knowledge/
    ├── zeo_faq.md               # Tài liệu kiến thức chuẩn ZeO
    └── cfc_faq.md               # Tài liệu kiến thức chuẩn CFC Cò Bay
```

---

## 4. HƯỚNG DẪN VẬN HÀNH & CÁC LỆNH CẦN THIẾT

### 1. Khởi động Server:
```bash
cd /Users/hyden/Documents/David-nguyen/N8n/ChatbotN8n/javis/server
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Chạy Bộ Kiểm Thử NLU Regression Suite:
```bash
python eval_test_suite.py
```
* Tiêu chí đạt: **98/98 test cases passed (100.0%)**, thời gian phản hồi trung bình **~7.8ms/câu**.

### 3. Truy Cập Giao Diện Admin:
Mở trình duyệt truy cập: **`http://localhost:8000/admin`** (hoặc `http://127.0.0.1:8000/admin`)
* Trợ lý AI: `http://localhost:8000/admin#assistant`
* Quản lý Lead: `http://localhost:8000/admin#customers`
* Báo cáo AI: `http://localhost:8000/admin#reports`
* n8n Control: `http://localhost:8000/admin#n8n`
* Learning Queue: `http://localhost:8000/admin#learning`
* Cài đặt & API: `http://localhost:8000/admin#settings`

---

## 5. BẢO MẬT & QUY TẮC PHÁT TRIỂN
* Tuyệt đối **không đưa API Key, mật khẩu Redis, Token n8n thật** vào tài liệu công khai hoặc Git commit.
* Mọi tính năng mới mở rộng nên được đặt vào đúng Domain Folder tương ứng trong `server/domains/` để giữ gìn tính độc lập và sạch sẽ của kiến trúc DDD.
