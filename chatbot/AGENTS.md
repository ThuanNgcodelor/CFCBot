# 🤖 AGENTS.md — AI AGENT CONTEXT & OPERATIONAL GUIDELINES
<!-- AI-CONTEXT-ROOT: chatbot/ -->
<!-- LAST-UPDATED: 2026-10-06 -->

> **DÀNH CHO AI / CODEX / COPILOT TIẾP THEO KHI MỞ THƯ MỤC NÀY:**
> Bạn **BẮT BUỘC** phải đọc kỹ toàn bộ tài liệu này trước khi phân tích hoặc chỉnh sửa bất kỳ file nào trong `chatbot/`.
> Mọi thay đổi lớn về kiến trúc hoặc tính năng sau phiên làm việc của bạn phải được **cập nhật bổ sung vào file này** để bảo toàn ngữ cảnh (Context Continuity).

---

## TÀI LIỆU MASTER — THỨ TỰ ĐỌC BẮT BUỘC

Khi cần hiểu hiện trạng trước khi sửa code hoặc workflow, đọc theo thứ tự sau:

1. [AGENTS.md](AGENTS.md) — quy tắc an toàn, kiến trúc và các thay đổi đã triển khai.
2. [Master plan cập nhật CFCBot: queue, OCR và Telegram Sales](plan/PLAN_DINH_HUONG_CAP_NHAT_CFCBOT_QUEUE_OCR_TELEGRAM_2026-10-01.md) — nguồn quyết định hiện hành sau cutover, gồm baseline, contract, phase/gate, test và rollback.
3. [Master plan CFC AI Agent: hiện tại và tương lai](plan/MASTER_PLAN_CFC_AI_AGENT_HIEN_TAI_VA_TUONG_LAI_2026-09-09.md) — nền tảng về luồng hệ thống, vai trò từng file, CRM đã có/chưa có và roadmap AI.
4. [Phase roadmap nâng cấp không làm mất hệ thống cũ](plan/PHASE_ROADMAP_CFC_AI_AGENT_NANG_CAP_KHONG_MAT_HE_THONG_CU_2026-09-09.md) — thứ tự thực thi, dependency, nghiệm thu và rollback cho từng phase.
5. [TAI_LIEU_HE_THONG_CFC_AI.md](TAI_LIEU_HE_THONG_CFC_AI.md) — tài liệu hệ thống/nghiệp vụ.
6. [Tổng hợp hiện trạng & bộ test Conversation Intelligence](plan/TONG_HOP_HIEN_TRANG_VA_BO_TEST_CONVERSATION_INTELLIGENCE_CFC.md) — hiện trạng vận hành, giới hạn và cách test.
7. [Plan khách hàng mới/cũ, tạo đơn CRM và dọn dẹp](PLAN_KHACH_HANG_MOI_CU_TAO_DON_CRM_VA_DON_DEP_2026-08-31.md) — backlog nghiệp vụ đang chờ duyệt.

Các audit và phase lịch sử nằm tại [plan/archive/2026-08](plan/archive/2026-08/). Chúng chỉ dùng để đối chiếu, không thay thế nguồn hiện trạng ở trên.

---

## 1. TỔNG QUAN HỆ THỐNG & NGHIỆP VỤ (SYSTEM CONTEXT)

Hệ thống `chatbot/` là **Nền tảng Quản trị & Trợ lý AI Bán hàng / CSKH Đa kênh (Enterprise Chatbot Engine)**, phục vụ đồng thời 2 thương hiệu:
1. **ZeO Vietnam**: Chăm sóc gia đình sinh học (Nước rửa chén, Nước giặt xả, Lau sàn sinh học ZeO, PANO, Oplus) -> Bán lẻ Shopee Mall + Tuyển đại lý/sỉ.
2. **CFC Cò Bay (Cần Thơ)**: Phân bón & Dinh dưỡng cây trồng nông nghiệp (NPK Cò Bay, Hữu cơ Cobanic, dinh dưỡng chuyên sâu cho Sầu riêng, Mít, Ổi, Lúa...) -> Tư vấn kỹ thuật nông học, tra cứu điểm hội viên & đơn hàng AMIS MISA CRM, kết nối đại lý địa phương.

### Kiến trúc Lõi (Hybrid Multi-Layer AI Architecture)
- **Fast-path (Deterministic & FSM)**: Dùng Regex & State Machine bóc tách SĐT, mã đơn, địa bàn với độ trễ <20ms, bảo toàn ngữ cảnh đa lượt.
- **RAG & Vector Search**: Redis Stack Vector Search (1024 dims BGE-M3 / Semantic Text Search) tra cứu FAQ, quy trình kỹ thuật từ Google Sheets & Markdown.
- **Single Brain AI Engine (`ai_engine.py`)**: Bộ não sinh câu trả lời tự nhiên, có Guardrails chống bịa đặt giá/chính sách, hỗ trợ Chit-chat tự nhiên.
- **CRM Integration (`domains/amis/`)**: Đồng bộ dữ liệu đọc từ MISA AMIS thành public/protected warm cache cho sản phẩm, điểm bán, đơn hàng và loyalty. Customer-facing pipeline hiện chưa có API tạo khách hoặc tạo đơn AMIS.
- **Control Center Dashboard (`static/`, `admin_routes.py`)**: UI quản trị Domain-Driven Design (DDD).

---

## 2. CÂY THƯ MỤC CHI TIẾT & CHỨC NĂNG TỪNG PHẦN

```
chatbot/
├── AGENTS.md                      # [FILE NÀY] Ngữ cảnh & Cẩm nang bắt buộc cho AI
├── README.md                      # Tài liệu tổng quan tính năng & hướng dẫn chạy
├── Bao_Cao_Doi_Chieu_Khach_Hang.md # Báo cáo phân tích đối soát dữ liệu khách hàng
├── TAI_LIEU_HE_THONG_CFC_AI.md  # Tài liệu hệ thống/nghiệp vụ hiện hành
├── PLAN_KHACH_HANG_...md        # Backlog CRM hiện hành, chờ chủ hệ thống duyệt
├── knowledge/                     # Kho tri thức tĩnh (Static Knowledge Base)
│   ├── cfc_faq.md                 # Bộ FAQ & kỹ thuật bón phân CFC Cò Bay
│   ├── zeo_faq.md                 # Bộ FAQ sản phẩm & chính sách ZeO
│   └── shopee_catalog.json        # Database cache sản phẩm Shopee Mall
├── plan/                          # Index, hiện trạng/test và archive lịch sử
├── skills/                        # Các kỹ năng & tài liệu nghiệp vụ mở rộng
└── server/                        # Backend FastAPI Lõi
    ├── main.py                    # Khởi tạo FastAPI App, Background Workers & Lifecycle
    ├── settings.json              # File cấu hình (ĐÃ ĐƯỢC GITIGNORE - Không commit)
    ├── settings.example.json      # Bản mẫu cấu hình an toàn cho Git
    ├── chat_pipeline.py           # Pipeline xử lý hội thoại chính (FSM, Fast-path, Fallback)
    ├── ai_engine.py               # Module điều phối AI (Groq, OpenRouter, Gemini, Ollama)
    ├── cfc_semantic_planner.py    # Bộ phân tích Intent chuyên sâu cho nhãn hàng CFC
    ├── admin_routes.py            # Gateway Admin Router theo mô hình DDD
    ├── domains/                   # Các Domain nghiệp vụ độc lập (Domain-Driven Design)
    │   ├── messaging/             # Redis Stream, bundle, SQLite outbox, LeadDraft, Telegram Sales
    │   ├── amis/                  # Tích hợp MISA AMIS CRM (Live CRM, Orders, Loyalty)
    │   │   ├── live_crm.py        # Cache & tra cứu đơn hàng (chỉ lấy "Đã ghi"), hội viên
    │   │   └── ...
    │   ├── assistant/             # Trợ lý AI điều hành & Agent công cụ
    │   ├── customers/             # Quản lý khách hàng, hội thoại, Lead CRM & Export CSV
    │   ├── knowledge/             # Kho tri thức, Markdown & Google Sheets Live Hub
    │   ├── learning/              # Hàng đợi học (Learning Queue) & AI gợi ý FAQ
    │   ├── n8n/                   # Điều khiển Workflow n8n & file watching
    │   ├── rag_test/              # Kiểm thử Semantic Search & NLU evaluation
    │   ├── reports/               # Báo cáo điều hành kinh doanh & AI Insights
    │   ├── system/                # Trạng thái hệ thống, Settings, Health & Analytics
    │   └── common/                # Cấu hình chung, kết nối Redis, DB helpers
    ├── rag_search.py              # Tìm kiếm ngữ nghĩa RAG (Vector + BM25 + Intent Match)
    ├── embedder.py                # Sinh vector embedding (BGE-M3 / Fallback)
    ├── shopee_matcher.py          # Thuật toán so khớp thông minh sản phẩm Shopee Mall
    ├── telegram_notifier.py       # Module bắn thông báo Telegram (Lead nóng, Fallback)
    ├── ai_reporter.py             # Sinh báo cáo kinh doanh tự động qua AI
    ├── conversation_orchestrator.py # Quản lý trạng thái ngữ cảnh hội thoại đa lượt
    ├── conversation_store.py      # Lưu trữ & truy xuất session chat từ Redis
    ├── dialogue_router.py         # Định tuyến luồng hội thoại
    ├── document_ingestor.py       # Bóc tách, chunking & nạp tài liệu Markdown vào Redis
    ├── grounding_policy.py        # Chính sách kiểm soát chống ảo giác (Anti-Hallucination)
    ├── knowledge_sync.py          # Đồng bộ dữ liệu tri thức vào Redis Cache
    ├── message_idempotency.py     # Chống trùng lặp tin nhắn khi Fanpage gửi webhook lặp
    ├── nlu_shadow.py              # Chạy ngầm đánh giá NLU song song để cải tiến
    ├── query_understanding.py     # Chuẩn hóa tiếng Việt, tách từ lóng & thực thể
    ├── run_test_md_scenarios.py   # Tool chạy tự động 20 kịch bản kiểm thử trong test_script.md
    └── static/                    # Frontend Giao diện Quản trị Admin Dashboard (HTML/CSS/JS)
```

---

## 3. CÁCH CHUYỂN ĐỔI (SWITCH) GIỮA CLOUD API VÀ OLLAMA LOCAL

Hệ thống hỗ trợ chuyển đổi tức thì thông qua file `chatbot/server/settings.json` tại khối `"ai_providers"`:

```json
"ai_providers": {
    "execution_mode": "cloud",
    "preferred_provider": "groq",
    "gemini": {
        "api_key": "",
        "model": "gemini-2.0-flash"
    },
    "openrouter": {
        "api_key": "sk-or-v1-...",
        "model": "google/gemini-2.0-flash-exp:free"
    },
    "groq": {
        "api_key": "gsk_...",
        "model": "llama-3.3-70b-versatile"
    }
}
```

### Hướng Dẫn Switch Nhanh (Chỉ cần sửa 1 trường `execution_mode`):

> **Hiệu chỉnh sau source audit 09/09/2026:** mô tả switch dưới đây áp dụng cho đường `generate_ai_text` của customer pipeline. `run_assistant_agent_chat` có nhánh Groq riêng khi tồn tại API key, nên chưa được coi là local-only theo cùng flag cho đến khi contract này được thống nhất và kiểm tra runtime.

1. **Chế độ 100% Cloud (Khuyên dùng khi test / chạy thật):**
   - Đổi `"execution_mode": "cloud"`
   - Bot sẽ **chỉ** gọi Cloud API (ưu tiên `preferred_provider` -> fallback sang các cloud còn lại). Hoàn toàn **ngắt kết nối** với Ollama Local để tránh bị kéo chậm/treo do hết RAM máy.
2. **Chế độ 100% Local (Chạy Offline không cần mạng / Bảo mật tuyệt đối):**
   - Đổi `"execution_mode": "local"`
   - Bot sẽ **chỉ** gọi Ollama Local (`qwen2.5:7b-instruct`). Không gửi bất kỳ byte dữ liệu nào ra Cloud.
3. **Chế độ Tự động (Auto Fallback):**
   - Đổi `"execution_mode": "auto"`
   - Thử Cloud trước, nếu lỗi toàn bộ Cloud sẽ tự động rớt về Local Ollama.

---

## 4. CÁC ĐỢT REFACTOR & FIX QUAN TRỌNG ĐÃ HOÀN THÀNH

1. **Bảo mật Git & API Key:**
   - Đã gỡ `chatbot/server/settings.json` khỏi Git tracking và thêm vào `.gitignore`.
2. **Tích hợp AMIS CRM (`domains/amis/live_crm.py`):**
   - Đã lọc triệt để `revenue_status == "Đã ghi"`, loại bỏ các đơn "Bản nháp" khi khách tra cứu.
   - Sửa thứ tự ưu tiên Regex nhận diện mã đơn trong `chat_pipeline.py` (ưu tiên `DHxxxx` và `0000xxxx` trước cụm từ "đơn hàng").
3. **Nâng cấp NLU & Xử lý số điện thoại:**
   - Bổ sung từ lóng `"ne", "day ne", "zalo"` vào regex bóc tách SĐT `_is_phone_only_submission`.
   - Khi khách cung cấp SĐT trong luồng tư vấn kỹ thuật bón phân, hệ thống giữ chặt ngữ cảnh `agronomy`, không bị nhảy nhầm sang tra cứu tích điểm (`loyalty_lookup`).
4. **Grounding cho Trí thông minh & Giao tiếp (hiện trạng source 09/09/2026):**
   - `reason_and_answer_cskh` hiện vẫn yêu cầu facts phù hợp trước khi sinh câu trả lời; mô tả lịch sử về việc xóa hoàn toàn gate này không còn đúng với source hiện hành.
   - CFC dùng fast path/template/RAG có nguồn cho dữ kiện nghiệp vụ và fallback khi thiếu nguồn.
   - Chit-chat có thể dùng model trong phạm vi an toàn; giá, sản phẩm, tồn kho, chính sách và dữ liệu CRM không được tự bịa.
5. **Cơ chế Switch Mode Local / Cloud tức thì:**
   - Cập nhật `ai_engine.py` nhận diện `execution_mode: "cloud" | "local" | "auto"`.
6. **AMIS order cache last-known-good:**
   - Full Warm chỉ publish sau khi stage/commit đầy đủ; một execution lỗi không xoá snapshot đơn đang active.
   - Protected order lookup dùng snapshot thành công gần nhất trong tối đa 12 giờ. Sau 12 giờ không có sync thành công, bot fail-closed thay vì trả trạng thái đơn quá cũ.
7. **Messaging queue và Sales handoff Phase 01–03 (06/10/2026):**
   - `domains/messaging/` định nghĩa contract versioned, Redis Stream ingress,
     quiet/max-window bundling, response outbox SQLite WAL và LeadDraft merge theo hội thoại.
   - `/api/chat-pipeline` vẫn là compatibility path. Production flags mặc định off;
     test stack `7778/6380` chạy shadow và chặn side effect Telegram cũ.
   - Route sale chỉ đọc `runtime/data/sales-routes.json`; chat ID/token chỉ từ `.env`.
     Không chắc khu vực phải về `triage`, không đoán group.
   - n8n live chưa được đổi vì `n8nac` chưa có workspace/API key. Bắt buộc pull
     live trước mọi sửa/push và không được bật queue production trước adapter gate.
   - Telegram Sales template dùng ngôn ngữ sale tự nhiên: không gửi UUID dài hoặc
     nhãn kỹ thuật “AI”; chỉ hiển thị mã tiếp nhận ngắn, khách, số điện thoại có
     link gọi, khu vực, nhu cầu và nhóm phân công.
8. **TC01/TC12 — Catalog-grounded price intake & dynamic agronomy retrieval:**
   - Câu hỏi giá CFC có sản phẩm/công thức rõ ràng đi thẳng danh mục AMIS public, hiển thị tối đa các tên/quy cách khớp rồi chỉ hỏi một lần các dữ kiện còn thiếu; không hiển thị mã nội bộ, giá hoặc tồn kho.
   - Câu nông học có crop + stage/symptom rõ ràng bỏ qua semantic planner/orchestrator, nhưng truy xuất động các FAQ `category=agronomy` theo nguyên câu hỏi và ngữ cảnh đã nhớ; không còn ánh xạ riêng TC12/sầu riêng sang intent hoặc công thức cố định trong code.
   - `QueryPlan` là nguồn nhận diện crop/stage/symptom duy nhất cho conversation memory. Danh sách cây warm từ Redis và mẫu `cây <tên>` giúp ổi, nhãn và cây mới đi cùng một tuyến; không duy trì danh sách cây thứ hai trong `chat_pipeline.py`.
   - `domains/agronomy/guidance.py` chỉ dùng row có nguồn/audience hợp lệ, không áp câu trả lời riêng của cây khác, bỏ CTA lặp, giới hạn vài câu trọng tâm. Thiếu liều, nguồn mơ hồ hoặc ca rủi ro cao thì chuyển Khuyến nông Lê Thanh Đạm/Cao Văn Được.
   - Hai tuyến giá/nông học rõ được đánh dấu `protected_fast_path` để giảm độ trễ; Ollama chat planner chỉ còn cần cho câu mơ hồ, còn RAG có thể gọi embedding khi lexical chưa đủ chắc.

---

## 5. NGUYÊN TẮC LÀM VIỆC DÀNH CHO CODEX / AI TIẾP THEO

- **Không phá vỡ Fast-path**: Không bỏ các hàm Regex nhận diện nhanh (như `_is_phone_only_submission`) vì đây là chốt chặn đảm bảo độ trễ <20ms cho khách hàng.
- **Bảo toàn Zero-Hallucination cho giá và tồn kho**: Khi bổ sung prompt, luôn nhắc nhở AI không được tự bịa giá tĩnh hoặc cam kết tồn kho nếu không có trong Data/Tool.
- **Cập nhật tài liệu**: Bất cứ khi nào bạn tạo thêm router trong `domains/`, thêm hàm trong `ai_engine.py` hoặc chỉnh sửa flow chính trong `chat_pipeline.py`, hãy ghi chú lại vào mục **4. CÁC ĐỢT REFACTOR** của file này.
