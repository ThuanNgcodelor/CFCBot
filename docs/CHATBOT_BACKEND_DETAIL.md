# CFCBot — Tài liệu Chi Tiết Backend Chatbot

> Cập nhật: 13/10/2026
> Mục đích: Giúp AI và developer hiểu rõ từng file, luồng dữ liệu, và logic xử lý của backend FastAPI.
> **Đọc file này trước khi đọc code** — đây là bản đồ toàn hệ thống.

---

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Entrypoint & App lifecycle](#2-entrypoint--app-lifecycle-mainpy)
3. [Chat Pipeline — Luồng xử lý tin nhắn chính](#3-chat-pipeline--luồng-xử-lý-tin-nhắn-chính-chat_pipelinepy)
4. [AI Engine — Đa nhà cung cấp & Grounding](#4-ai-engine--đa-nhà-cung-cấp--grounding-ai_enginepy)
5. [RAG Search — Tìm kiếm kiến thức](#5-rag-search--tìm-kiếm-kiến-thức-rag_searchpy)
6. [Query Understanding — Hiểu câu hỏi](#6-query-understanding--hiểu-câu-hỏi-query_understandingpy)
7. [Dialogue Router — Định tuyến hành động](#7-dialogue-router--định-tuyến-hành-động-dialogue_routerpy)
8. [Conversation Orchestrator — Điều phối hội thoại](#8-conversation-orchestrator--điều-phối-hội-thoại-conversation_orchestratorpy)
9. [Shopee Matcher — Tư vấn sản phẩm Shopee](#9-shopee-matcher--tư-vấn-sản-phẩm-shopee-shopee_matcherpy)
10. [Embedder & Knowledge Sync](#10-embedder--knowledge-sync)
11. [Domain: AMIS CRM](#11-domain-amis-crm)
12. [Domain: Messaging Queue](#12-domain-messaging-queue)
13. [Domain: Agronomy — Tư vấn nông nghiệp](#13-domain-agronomy--tư-vấn-nông-nghiệp)
14. [Domain: Knowledge — Kho tri thức](#14-domain-knowledge--kho-tri-thức)
15. [Admin Routes & Các Domain phụ](#15-admin-routes--các-domain-phụ)
16. [Grounding Policy & Evidence Trace](#16-grounding-policy--evidence-trace)
17. [Telegram Notifier — Cảnh báo Lead](#17-telegram-notifier--cảnh-báo-lead)
18. [Conversation Store — Bộ nhớ phiên](#18-conversation-store--bộ-nhớ-phiên)
19. [NLU Shadow — Giám sát LLM](#19-nlu-shadow--giám-sát-llm)
20. [Cấu hình hệ thống settings.json](#20-cấu-hình-hệ-thống-settingsjson)
21. [Sơ đồ luồng tổng thể](#21-sơ-đồ-luồng-tổng-thể)
22. [Redis Key Map](#22-redis-key-map)
23. [Test Suite](#23-test-suite)

---

## 1. Tổng quan kiến trúc

```text
Tin nhắn Meta/n8n
      │
      ▼
POST /api/chat-pipeline  ◄─── Đường chính
      │
      ▼
chat_pipeline.py         ◄─── Não của chatbot (6801 dòng)
  ├── query_understanding.py    Hiểu câu hỏi → QueryPlan
  ├── dialogue_router.py        Quyết định action/tool
  ├── rag_search.py             Tìm kiếm kiến thức (in-memory + KNN)
  ├── shopee_matcher.py         Tư vấn/link sản phẩm Shopee
  ├── ai_engine.py              Gọi LLM (Gemini/Groq/OpenRouter/Ollama)
  ├── conversation_orchestrator.py  Ngữ cảnh hội thoại
  ├── domains/amis/             Tra cứu đơn hàng, điểm thưởng, đại lý CRM
  ├── domains/agronomy/         Tư vấn kỹ thuật nông nghiệp
  ├── telegram_notifier.py      Báo lead qua Telegram
  └── evidence_trace.py         Ghi log PII-safe

POST /api/messaging/enqueue  ◄─── Đường queue (Redis Stream)
      │
      ▼
domains/messaging/service.py  MessagingRuntime
  ├── _consume_loop()     Đọc stream → bundle tin nhắn
  ├── _finalize_loop()    Xử lý bundle xong → chat_pipeline
  └── _sales_delivery_loop()  Gửi Telegram sales
```

**Hai brand hoạt động song song:** `zeo` (nước giặt ZeO) và `cfc` (phân bón Cò Bay).
Mỗi brand có knowledge index riêng trong Redis, logic khác nhau trong chat_pipeline.

---

## 2. Entrypoint & App lifecycle (`main.py`)

**File:** `chatbot/server/main.py` (422 dòng)

### FastAPI app

```python
app = FastAPI(title="ZeO/CFC Semantic RAG & CFC AI Admin", version="2.1.0")
```

### Middleware

| Middleware | Chức năng |
|---|---|
| `CORSMiddleware` | Cho phép tất cả origins (nội bộ) |
| `trace_request` | Gán `X-Trace-Id` cho mỗi request, log response time |

### Background tasks (chạy khi startup)

| Task | Chu kỳ | Chức năng |
|---|---|---|
| `_periodic_shopee_sync()` | 10 phút | Đồng bộ Shopee catalog từ Google Sheets |
| `_periodic_daily_snapshot()` | 1 giờ | Chụp analytics snapshot |
| `MessagingRuntime.start()` | liên tục | Khởi động Redis Stream workers |

### Các endpoint chính

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/health` | Kiểm tra service, Ollama, Redis, vector indexes |
| `POST` | `/sync?brand=zeo\|cfc\|all` | Đồng bộ FAQ từ Redis → vector index |
| `POST` | `/search` | Tìm kiếm ngữ nghĩa (n8n gọi trực tiếp) |
| `POST` | `/rewrite` | Viết lại câu trả lời RAG bằng Ollama |
| `POST` | `/api/chat-pipeline` | **Luồng chat chính** |
| `POST` | `/api/chat/pipeline` | Alias tương thích |
| `POST` | `/api/conversations/{brand}/{sender_id}/takeover` | Admin claim hội thoại |
| `POST` | `/api/conversations/{brand}/{sender_id}/close` | Admin trả bot |
| `POST` | `/api/shopee/refresh-cache` | Làm mới cache Shopee |
| `GET` | `/admin` | Giao diện Admin Dashboard (HTML) |

### Settings loading

`_load_settings()` đọc `settings.json` trong cùng thư mục với main.py.

---

## 3. Chat Pipeline — Luồng xử lý tin nhắn chính (`chat_pipeline.py`)

**File:** `chatbot/server/chat_pipeline.py` (~6801 dòng — file lớn nhất)

### Request model

```python
class ChatPipelineRequest(BaseModel):
    brand: str           # "zeo" hoặc "cfc"
    sender_id: str       # Facebook PSID hoặc ID khách
    message: str         # Tin nhắn của khách
    fb_name: str = ""    # Tên Facebook (nếu có)
    # ... và nhiều trường meta khác
```

### Các hằng số quan trọng

```python
CFC_SALES_CONTACT = ("Trưởng phòng Kinh doanh", "0981205448")
CFC_AGRONOMY_CONTACTS = [
    ("Khuyến nông Lê Thanh Đạm", "+84353857516"),
    ("Khuyến nông Cao Văn Được", "+84939852529"),
]
```

### Luồng xử lý `process_chat_pipeline(req)`

```
1. Per-Sender Lock (chống race condition)
   └── _get_sender_lock(f"{brand}:{sender_id}")

2. Idempotency check (tránh xử lý 2 lần)
   └── message_idempotency.begin_message()

3. Normalize input
   ├── Bỏ dấu tiếng Việt → fold text
   ├── Map VIETNAMESE_ALIASES (k→khong, dc→duoc, sp→san pham...)
   ├── PHONE_REGEX — trích xuất số điện thoại
   └── SENSITIVE_KEYWORDS — phát hiện khiếu nại nhạy cảm

4. Fast-Path (< 5ms, không cần AI)
   ├── Lời chào hỏi → trả lời cố định
   ├── Cảm ơn → phản hồi ngắn
   ├── SĐT mới → lưu profile
   └── Từ khóa khiếu nại → notify_urgent_complaint()

5. Customer Profile Recall
   └── Redis: {brand}:profile:{sender_id}
       (phone, area, tên, lịch sử intent)

6. QueryPlan (query_understanding.py)
   └── build_query_plan(message, brand) → QueryPlan
       (intent, entities, slots, crop_terms...)

7. Dialogue Router (dialogue_router.py)
   └── build_route_decision(plan, conversation_plan) → RouteDecision
       action: "fast_path" | "tool" | "rag" | "legacy"

8. Conversation Orchestrator (conversation_orchestrator.py)
   └── plan_conversation_turn_with_ai() — nếu mode=assist/shadow
       (LLM đọc lịch sử → quyết định next_action)

9. Tool Execution (theo RouteDecision.tool)
   ├── product_lookup        → shopee_matcher
   ├── dealer_contact_lookup → domains/amis/live_crm.py
   ├── order_status_lookup   → domains/amis/order_cache.py
   ├── loyalty_lookup        → domains/amis/loyalty_cache.py
   ├── agronomy_intake       → domains/agronomy/guidance.py
   ├── inventory_lookup      → AMIS + RAG
   └── sales_location_search → AMIS public catalog

10. RAG Search (rag_search.py)
    ├── In-memory lexical match (< 1ms)
    ├── Fast lexical/BM25-like token overlap
    └── RediSearch KNN vector search (bge-m3)

11. Shopee Catalog Match (shopee_matcher.py)
    ├── is_shopee_inquiry() → match trực tiếp
    ├── is_budget_inquiry() → gợi ý theo tầm giá
    ├── is_bestseller_inquiry() → hàng bán chạy
    └── ... nhiều matcher khác

12. Answer Generation
    ├── Direct answer (từ RAG/tool) — không qua LLM
    ├── grounded_rewrite (ai_engine.synthesize_cskh_answer) — LLM rewrite có grounding
    └── Fallback message — khi không tìm thấy thông tin

13. Grounding Validation (evidence_trace + grounding_policy)
    └── validate_grounded_rewrite() — kiểm tra LLM không bịa thông tin

14. Side effects
    ├── notify_new_lead() — Telegram khi khách để SĐT
    ├── notify_admin_unanswered() — khi bot không trả lời được
    ├── persist_session() — lưu lịch sử Redis
    └── LeadDraft → domains/messaging/repository.py

15. Trả về ChatPipelineResponse
    └── {answer, intent, confidence, trace_id, ...}
```

### Cơ chế Per-Sender Lock

```python
_sender_locks: dict[str, asyncio.Lock] = {}  # key = "{brand}:{sender_id}"
```

Đảm bảo tin nhắn cùng khách hàng không được xử lý song song (tránh race condition trên session Redis).

### Slot tracking (CFC)

```python
CFC_REQUIRED_SLOTS = {
    "dealer_lookup":          ("phone", "area"),
    "inventory_check":        ("phone", "area", "product"),
    "order_tracking":         ("phone", "order_id"),
    "loyalty_lookup":         ("phone",),
    "wholesale_policy":       ("phone", "area"),
    "price_quote":            ("phone", "area", "crop", "product"),
    "purchase_intake":        ("phone", "area", "product", "quantity"),
    "agronomy_consultation":  ("phone", "area", "crop", "crop_stage"),
}
```

Khi chưa đủ slot, bot hỏi thêm thay vì trả lời thiếu thông tin.

---

## 4. AI Engine — Đa nhà cung cấp & Grounding (`ai_engine.py`)

**File:** `chatbot/server/ai_engine.py` (1170 dòng)

### Chuỗi Fallback Provider

```
Execution mode = "cloud"
  1. Groq     (llama-3.3-70b-versatile) — nhanh, miễn phí
  2. Gemini   (gemini-2.0-flash)         — Google API
  3. OpenRouter (gemini-2.0-flash-exp:free)
  4. Ollama   (qwen2.5:7b-instruct)      — local, không internet

Execution mode = "local"
  → Chỉ dùng Ollama
```

### Các hàm gọi LLM chính

| Hàm | Provider | Mục đích |
|---|---|---|
| `call_gemini()` | Google | Gemini 2.0 Flash, JSON output |
| `call_openrouter()` | OpenRouter | Các model miễn phí |
| `call_groq()` | Groq Cloud | Llama 70B, siêu nhanh |
| `call_ollama()` | Ollama local | Offline fallback |
| `plan_chat_intent_with_ai()` | Auto-fallback | NLU planner cho shadow mode |
| `reason_and_answer_cskh()` | Auto-fallback | Trả lời trực tiếp CSKH |
| `synthesize_cskh_answer()` | Auto-fallback | Rewrite có grounding |
| `plan_conversation_turn_with_ai()` | Auto-fallback | Orchestrator planner |

### Grounding Validation — `validate_grounded_rewrite`

Hàm này **từ chối** rewrite nếu LLM:

| Lý do từ chối | Ý nghĩa |
|---|---|
| `REWRITE_TOO_SHORT` | Câu trả lời < 20 ký tự |
| `REWRITE_APPEARS_TRUNCATED` | Không kết thúc bằng dấu câu |
| `INTERNAL_TERMS_EXPOSED` | Lộ thuật ngữ nội bộ (Redis, vector...) |
| `UNSUPPORTED_URL` | URL không có trong evidence |
| `UNSUPPORTED_PHONE` | SĐT không có trong facts |
| `UNSUPPORTED_FORMULA` | Công thức pha chế không trong evidence |
| `UNSUPPORTED_QUANTITY` | Liều lượng (kg, ml...) không trong evidence |
| `UNSUPPORTED_PRICE_OR_DISCOUNT` | Giá/chiết khấu không có trong evidence |
| `UNCERTAINTY_WAS_DROPPED` | Evidence nói "chưa có" nhưng rewrite bỏ qua |
| `EXPERT_HANDOFF_WAS_DROPPED` | Phải gọi khuyến nông nhưng bỏ SĐT |

---

## 5. RAG Search — Tìm kiếm kiến thức (`rag_search.py`)

**File:** `chatbot/server/rag_search.py` (941 dòng)

### 3 lớp tìm kiếm (theo thứ tự ưu tiên)

```
Layer 1: In-Memory Hot Cache (< 1ms)
  _knowledge_items[brand] = List[FAQItem]
  _intent_map[brand]      = {intent → FAQItem}
  _phrase_map[brand]      = {phrase → intent}
  → Load lại khi /sync hoặc restart

Layer 2: Fast Lexical Matcher (< 5ms)
  - Exact phrase match
  - BM25-like token overlap
  - Vietnamese alias expansion
  - Entity anchor matching

Layer 3: RediSearch KNN (5-50ms)
  - Model: bge-m3 (1024 chiều)
  - Chỉ dùng khi Layer 1+2 không đủ tin cậy
  - FT.SEARCH {index} KNN 5 ...
```

### Confidence scoring

| Score | Mức | Ý nghĩa |
|---|---|---|
| >= 0.78 | HIGH | Trả lời trực tiếp |
| 0.55 – 0.77 | MEDIUM | Trả lời kèm disclaimer |
| < 0.55 | LOW | Fallback / hỏi lại khách |

### Redis keys cho RAG

```
zeo:kb:basic:active      → JSON snapshot FAQ ZeO
cfc:kb:basic:active      → JSON snapshot FAQ CFC
zeo:vec:faq              → RediSearch vector index ZeO
cfc:vec:faq              → RediSearch vector index CFC
```

### Degraded mode

Khi Ollama không phản hồi (embed bị lỗi), tự động fallback về `top lexical candidate` thay vì báo lỗi.

---

## 6. Query Understanding — Hiểu câu hỏi (`query_understanding.py`)

**File:** `chatbot/server/query_understanding.py` (797 dòng)

### Mục đích

Module **deterministic** (không dùng LLM) để phân tích tin nhắn đầu vào thành `QueryPlan`. Không tạo fact, chỉ hiểu và định hướng routing.

### QueryPlan dataclass

```python
@dataclass
class QueryPlan:
    brand: str           # "zeo" | "cfc"
    raw_query: str       # Tin nhắn gốc
    normalized: str      # Bỏ dấu, lowercase
    intent: str          # Intent chính
    entities: dict       # {phone, area, product, crop, crop_stage, order_id...}
    slots: dict          # Trạng thái đầy đủ/thiếu slot
    confidence: float    # 0.0 – 1.0
    route_hint: str      # "rag" | "tool" | "fast_path" | "fallback"
    crop_terms: list     # Cây trồng được nhận diện
```

### Dynamic list từ Redis

Cứ **5 phút** đồng bộ lại từ Redis:
- `cfc:knowledge:crop_terms` → danh sách cây trồng CFC
- `amis:public:sales-locations:active` → tỉnh/huyện của đại lý

### Regex patterns nội bộ

```python
PHONE_REGEX = r"(?:\+84|84|0)(?:3[2-9]|5[2689]|7[06789]|8[0-9]|9[0-9])[0-9]{7}\b"
AREA_KEYWORDS = ["tinh", "thanh pho", "tp", "can tho", "thai binh", ...]
```

---

## 7. Dialogue Router — Định tuyến hành động (`dialogue_router.py`)

**File:** `chatbot/server/dialogue_router.py` (298 dòng)

### RouteDecision dataclass

```python
@dataclass(frozen=True)
class RouteDecision:
    action: str      # "fast_path" | "tool" | "rag" | "legacy"
    tool: str        # "product_lookup" | "dealer_contact_lookup" | ...
    intent: str      # Intent đã xác nhận
    reason: str      # Lý do routing (debug)
    confidence: float
```

### Allowed tools

```
none, product_lookup, sales_location_search, dealer_contact_lookup,
delivery_policy_lookup, inventory_lookup, order_status_lookup,
loyalty_lookup, agronomy_intake, wholesale_intake, complaint_intake,
lead_status_lookup, purchase_intake, customer_profile_update
```

### Điều kiện semantic routing (từ Orchestrator)

Chỉ tin vào LLM Orchestrator nếu:
- `confidence >= 0.85`
- `tool` và `next_action` không phải `"none"`
- Tool nằm trong `ALLOWED_TOOLS` (whitelist cứng)

---

## 8. Conversation Orchestrator — Điều phối hội thoại (`conversation_orchestrator.py`)

**File:** `chatbot/server/conversation_orchestrator.py` (602 dòng)

### Mục đích

Dùng LLM để **đọc lịch sử hội thoại** (tối đa 6 turn gần nhất) và quyết định `next_action` phù hợp với ngữ cảnh. **Không tạo fact, không tạo câu trả lời** — chỉ planning.

### Modes

| Mode | Hành vi |
|---|---|
| `off` | Không chạy orchestrator |
| `shadow` | Chạy ngầm, ghi trace, không ảnh hưởng câu trả lời |
| `assist` | Cho phép orchestrator chọn tool deterministic |

### Supported follow-up intents

```
product_followup, product_price_followup, product_link_followup,
dealer_followup, order_status_followup, loyalty_followup,
agronomy_followup, wholesale_followup, complaint_followup,
topic_switch, clarification, unknown, ...
```

### Context building

Lịch sử được **redact PII** trước khi đưa vào LLM prompt (xoá SĐT, email).

---

## 9. Shopee Matcher — Tư vấn sản phẩm Shopee (`shopee_matcher.py`)

**File:** `chatbot/server/shopee_matcher.py` (1702 dòng — file lớn thứ 2)

### Dữ liệu nguồn

```
Redis: {brand}:shopee:catalog:active  → JSON catalog (ưu tiên)
Fallback: Google Sheet CSV            → nếu Redis chưa có
```

### Các hàm matcher chính

| Hàm | Điều kiện kích hoạt | Kết quả |
|---|---|---|
| `match_shopee_product()` | Hỏi sản phẩm cụ thể đích danh | Link + giá + mô tả |
| `match_shopee_product_reference()` | Đề cập tên SP trong context | Link ngắn gọn |
| `match_products_by_budget()` | "dưới 100k", "50k-100k" | Danh sách SP theo giá |
| `match_best_sellers()` | "bán chạy", "phổ biến nhất" | Top SP theo doanh số |
| `match_new_arrivals()` | "mới nhất", "mới ra" | SP theo ngày nhập kho |
| `match_need_preference()` | "thơm lâu", "tiết kiệm", "sạch sâu" | SP theo tính năng |
| `match_skin_care_dishwashing()` | "dịu nhẹ da tay", "rửa chén" | SP nước rửa chén |
| `match_baby_or_sensitive_laundry()` | "em bé", "da nhạy cảm" | SP giặt chuyên biệt |
| `match_front_load_washer()` | "máy giặt cửa trước", "HE" | SP cho máy HE |
| `match_stain_removal_or_efficacy()` | "tẩy vết bẩn", "hiệu quả mạnh" | SP chuyên tẩy |
| `match_fabric_softener_products()` | "nước xả vải", "mềm vải" | SP xả vải |
| `match_bulk_or_restaurant_need()` | "mua sỉ", "nhà hàng", "số lượng lớn" | SP bulk |
| `match_price_extreme()` | "rẻ nhất", "đắt nhất" | SP đầu/cuối bảng giá |

### Cache

```python
_catalog_cache: dict[str, list[dict]] = {}  # {brand → list of products}
refresh_shopee_cache(brand)  # Làm mới qua endpoint hoặc tự động 10 phút
```

---

## 10. Embedder & Knowledge Sync

### Embedder (`embedder.py`) — 89 dòng

**Model mặc định:** `bge-m3` (đa ngôn ngữ, hiểu tiếng Việt kể cả không dấu, 1024 chiều)
**Fallback model:** `qwen2.5:7b-instruct`

```python
async def embed_text(text: str, model=None) -> Optional[list[float]]:
    # Gọi Ollama /api/embed
    # Trả về vector 1024 chiều
    # Tự động fallback nếu model 404

def vec_to_bytes(vec: list[float]) -> bytes:
    # Chuyển sang float32 bytes để lưu Redis VECTOR field
```

### Knowledge Sync (`knowledge_sync.py`) — 340 dòng

**Luồng đồng bộ:**
```
1. Đọc snapshot từ Redis (zeo:kb:basic:active / cfc:kb:basic:active)
2. Parse từng FAQ item: intent, question_examples, answer
3. build_embed_text() — gom intent + examples + answer (cả dấu + không dấu)
4. embed_text() → vector 1024 chiều qua Ollama bge-m3
5. Upsert vào RediSearch vector index (FT.ADD)
6. Cập nhật in-memory hot cache _knowledge_items
```

---

## 11. Domain: AMIS CRM

**Thư mục:** `chatbot/server/domains/amis/`

Tích hợp với AMIS CRM (MISA) qua REST API để tra cứu đại lý, đơn hàng, điểm thưởng.

### Files

| File | Kích thước | Chức năng |
|---|---|---|
| `client.py` | 8 KB | HTTP client cho AMIS REST API v2 |
| `config.py` | 14 KB | AmisConfig — cấu hình, rate limit, field mapping |
| `service.py` | 12 KB | Publish snapshot vào Redis (fail-closed, có hash check) |
| `projection.py` | 21 KB | Lọc/transform dữ liệu AMIS thành public-safe format |
| `live_crm.py` | 22 KB | Tra cứu đại lý theo tỉnh/huyện real-time |
| `order_cache.py` | 12 KB | Cache đơn hàng khách (private, TTL 12h) |
| `loyalty_cache.py` | 12 KB | Cache điểm thưởng khách hàng |
| `warm_staging.py` | 8 KB | Pre-warm cache theo lịch |
| `catalog.py` | 7 KB | Danh mục sản phẩm công khai CFC |
| `routes.py` | 6 KB | FastAPI routes `/admin/amis/...` |

### Redis keys AMIS

```
amis:public:products:active         → Sản phẩm CFC công khai
amis:public:sales-locations:active  → Vị trí đại lý công khai
amis:internal:orders:active         → Đơn hàng (private, TTL 12h)
amis:internal:loyalty:active        → Điểm thưởng (private)
```

### Safety gate

`assert_public_projection_safe(envelope)` đảm bảo:
- Không lộ thông tin cá nhân khách hàng
- Chỉ publish field được đánh dấu `chatbot_public=true` trong CRM
- Snapshot phải có tối thiểu 1 sản phẩm và 1 địa điểm

---

## 12. Domain: Messaging Queue

**Thư mục:** `chatbot/server/domains/messaging/`

Hệ thống xếp hàng tin nhắn để xử lý burst traffic và bundling.

### Files

| File | Chức năng |
|---|---|
| `contracts.py` | Pydantic schemas versioned (InboundEventV1, ConversationBundleV1...) |
| `config.py` | MessagingConfig — queue_mode, stream key, consumer group |
| `repository.py` | SQLite persistence cho outbox, lead draft, delivery results |
| `service.py` | MessagingRuntime — 3 async workers |
| `routes.py` | `POST /api/messaging/enqueue` |
| `media.py` | Kiểm tra media attachment |

### MessagingRuntime workers

```python
class MessagingRuntime:
    async def _consume_loop():
        # XREADGROUP từ Redis Stream
        # Nhóm tin nhắn cùng sender trong 300ms → ConversationBundleV1
        # Ghi LeadDraft nếu phát hiện intent thương mại

    async def _finalize_loop():
        # Đọc bundle đã đủ thời gian chờ
        # Gọi process_chat_pipeline() cho toàn bộ bundle
        # Ghi ResponseOutboxEventV1 → SQLite

    async def _sales_delivery_loop():
        # Đọc SalesOutboxEventV1 pending
        # Gửi Telegram đến nhóm sales
        # Cập nhật trạng thái delivered/dead
```

### Versioned contracts

```python
InboundEventV1        # Tin nhắn đến từ Meta/test
ConversationBundleV1  # Nhóm tin nhắn cùng sender
ResponseOutboxEventV1 # Phản hồi chờ gửi về Meta
LeadDraftV1           # Lead từ khách có intent thương mại
SalesOutboxEventV1    # Thông báo cho sales team
MemoryFactV1          # Fact học được từ hội thoại
HandoffActionV1       # Hành động chuyển bot → người
```

### Deduplication

```python
dedup_key = f"cfcbot:inbound-dedup:v1:{event.idempotency_key}"
await redis.set(dedup_key, event_id, ex=86400, nx=True)
# nx=True → chỉ set nếu chưa có (TTL 24h)
```

---

## 13. Domain: Agronomy — Tư vấn nông nghiệp

**Thư mục:** `chatbot/server/domains/agronomy/`

| File | Chức năng |
|---|---|
| `facts.py` | `resolve_approved_agronomy_fact()` — tra approved facts |
| `guidance.py` | `build_grounded_agronomy_guidance()` — tổng hợp tư vấn kỹ thuật |
| `approved_facts.json` | Fact cứng đã duyệt (liều lượng, giai đoạn bón phân...) |

### Nguyên tắc hoạt động

- **Không bịa đặt liều lượng/công thức** — chỉ dùng fact từ RAG và `approved_facts.json`
- Khi câu hỏi kỹ thuật vượt knowledge, bắt buộc redirect đến khuyến nông:
  - Lê Thanh Đạm: +84353857516
  - Cao Văn Được: +84939852529

### `build_grounded_agronomy_guidance()`

```
Input: rag_results (danh sách FAQ agronomy)
Output: Chuỗi tư vấn ngắn gọn
Logic:
  1. Lọc rows có agronomy tags
  2. Xóa câu mời để lại SĐT (boilerplate)
  3. Giữ lại câu hướng dẫn thực tế (nên, cần, tránh...)
  4. Nếu khách hỏi liều lượng chính xác → append SĐT khuyến nông
```

---

## 14. Domain: Knowledge — Kho tri thức

**Thư mục:** `chatbot/server/domains/knowledge/`

| File | Chức năng |
|---|---|
| `service.py` | Fetch Google Sheet, ingest markdown, quản lý snapshot |
| `routes.py` | Admin routes `/admin/knowledge/...` |
| `schemas.py` | Pydantic schemas |

### Nguồn dữ liệu

```
1. Google Sheets FAQ → fetch qua API v4 hoặc CSV export
   → parse → lưu vào Redis (brand:kb:basic:active)
   → trigger /sync → embed → vector index

2. Markdown documents → parse → chunk → lưu Redis
   → dùng làm context bổ sung cho RAG

3. Shopee catalog CSV → từ Google Sheet
   → parse → lưu Redis (brand:shopee:catalog:active)
```

### `fetch_google_sheet_data(url, api_key, sheet_name)`

Thử lần lượt:
1. Google Sheets API v4 (nếu có api_key hoặc Bearer token)
2. GViz query URL
3. CSV export URL

---

## 15. Admin Routes & Các Domain phụ

### `admin_routes.py` — Facade DDD Router

Mount tất cả domain routers vào `/admin/`:

| Domain | Prefix | Chức năng |
|---|---|---|
| `domains/system` | `/admin/system/` | Health, settings, analytics |
| `domains/assistant` | `/admin/assistant/` | AI agent tools, autonomous actions |
| `domains/customers` | `/admin/customers/` | Quản lý khách hàng, leads, export CSV |
| `domains/n8n` | `/admin/n8n/` | Quản lý workflows, executions |
| `domains/reports` | `/admin/reports/` | Báo cáo kinh doanh, AI insights |
| `domains/learning` | `/admin/learning/` | Learning queue, gợi ý FAQ mới |
| `domains/knowledge` | `/admin/knowledge/` | Kho tri thức, Sheets, Shopee |
| `domains/rag_test` | `/admin/rag-test/` | Test semantic search, NLU eval |
| `domains/amis` | `/admin/amis/` | AMIS CRM sync, snapshot |
| `domains/messaging` | `/api/messaging/` | Queue enqueue |

### `ai_agent_tools.py` (31 KB)

AI Autonomous Tool Agent — khi admin hỏi trợ lý AI:
- Tra cứu đơn hàng, khách hàng
- Xem log, metrics
- Gọi tool tự động không cần chỉ định từng bước

### `domains/n8n/service.py` (15 KB)

- Kết nối n8n API để list/trigger workflow
- Real-time file watching cho workflow source

---

## 16. Grounding Policy & Evidence Trace

### `grounding_policy.py` — 110 dòng

Quyết định liệu một fact có cần phải được hỗ trợ bởi source cụ thể không.

```python
@dataclass(frozen=True)
class GroundingDecision:
    status: str          # "enforced" | "advisory" | "relaxed"
    claim_type: str      # "price" | "purchase_link" | "policy" | "technical_or_safety"...
    requires_source: bool
    source_id: str
    reason: str
```

Các `claim_type`:
- `official_contact` — SĐT, hotline, địa chỉ
- `price` — giá, chiết khấu
- `purchase_link` — link Shopee
- `policy` — chính sách đổi trả, bảo hành
- `technical_or_safety` — liều lượng, chứng nhận an toàn
- `inventory` — tồn kho
- `order_status` — trạng thái đơn

### `evidence_trace.py` — 198 dòng

PII-safe tracing cho mỗi request:

```python
# Tự động xóa SĐT và email trong trace
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)")
_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")

# Ghi lại từng lần thử LLM provider
record_provider_attempt(provider, model, prompt_id, status, latency_ms)
```

Kết quả: `build_answer_trace()` → dict đính kèm vào response để debug.

---

## 17. Telegram Notifier — Cảnh báo Lead (`telegram_notifier.py`)

**File:** `chatbot/server/telegram_notifier.py` (174 dòng)

### Các loại thông báo

| Hàm | Trigger | Nội dung |
|---|---|---|
| `notify_new_lead()` | Khách để lại SĐT | Tên, SĐT, khu vực, nhu cầu |
| `notify_admin_unanswered()` | Bot không trả lời được | Câu hỏi khách + intent |
| `notify_urgent_complaint()` | Phát hiện từ khóa khiếu nại | Alert khẩn cho admin |
| `send_telegram_message()` | Bất kỳ | Low-level gửi tin nhắn HTML |

### Safety gate

```python
if not external_side_effects_allowed():
    return {"success": False, "skipped": True, "reason": "EVALUATION_EXTERNAL_SIDE_EFFECT_BLOCKED"}
```

Trong môi trường test (`CFCBOT_PRODUCTION_ENABLED` không set), **không gửi Telegram thật**.

---

## 18. Conversation Store — Bộ nhớ phiên (`conversation_store.py`)

**File:** `chatbot/server/conversation_store.py` (184 dòng)

### BoundedTTLCache

```python
class BoundedTTLCache(MutableMapping[str, T]):
    maxsize: int = 5000     # Tối đa 5000 sender
    ttl_seconds: float = 3600  # Hết hạn sau 1 giờ
    # LRU eviction khi vượt maxsize
    # Tự động expire khi đọc lại
```

### Redis persistence

```
{brand}:session:{sender_id}   → TTL 30 ngày  (slot values, intent history)
{brand}:history:{sender_id}   → TTL 30 ngày, tối đa 50 turns
{brand}:lock:{sender_id}      → TTL 30 giây  (distributed lock)
```

### `sender_lease(redis, brand, sender_id)` (async context manager)

Distributed lock trên Redis để đảm bảo chỉ một process xử lý một sender tại một thời điểm.

---

## 19. NLU Shadow — Giám sát LLM (`nlu_shadow.py`)

**File:** `chatbot/server/nlu_shadow.py` (253 dòng)

### Mục đích

Chạy **ngầm song song** (không block response) để:
1. Gọi LLM planner (`plan_chat_intent_with_ai`)
2. So sánh với quyết định deterministic
3. Ghi kết quả vào Redis/file để phân tích sau

### Cấu hình trong settings.json → llm_nlu

```json
{
    "mode": "off",
    "shadow_timeout_seconds": 20.0,
    "shadow_max_pending": 2,
    "shadow_max_observations": 500,
    "shadow_retention_seconds": 604800,
    "shadow_sample_rate": 1.0
}
```

### `schedule_nlu_shadow()`

Tạo `asyncio.Task` background, **không await**, trả về ngay để pipeline không bị chậm.

---

## 20. Cấu hình hệ thống `settings.json`

**Template:** `chatbot/server/settings.example.json`
**File thật:** `runtime/settings.json` (không commit)

### Cấu trúc chính

```json
{
  "redis": {
    "host": "127.0.0.1",
    "port": 6379,
    "password": "",
    "db": 0
  },
  "ollama": {
    "base_url": "http://127.0.0.1:11434",
    "embed_model": "bge-m3",
    "embed_dim": 1024,
    "chat_model": "qwen2.5:7b-instruct",
    "fallback_embed_model": "qwen2.5:7b-instruct"
  },
  "llm_nlu": {
    "mode": "off",
    "timeout_seconds": 1.6,
    "min_confidence": 0.72
  },
  "conversation": {
    "session_ttl_seconds": 2592000,
    "history_limit": 50,
    "orchestrator_mode": "assist",
    "orchestrator_min_confidence": 0.85,
    "orchestrator_timeout_seconds": 6.0
  },
  "grounding_policy": {
    "mode": "enforce",
    "customer_fact_generation_mode": "grounded_rewrite",
    "grounded_rewrite_timeout_seconds": 4.0
  },
  "rag": {
    "top_k": 5,
    "high_confidence_threshold": 0.78,
    "medium_confidence_threshold": 0.55,
    "zeo_kb_key": "zeo:kb:basic:active",
    "cfc_kb_key": "cfc:kb:basic:active"
  },
  "ai_providers": {
    "execution_mode": "cloud",
    "preferred_provider": "groq",
    "groq":      {"api_key": "", "model": "llama-3.3-70b-versatile"},
    "gemini":    {"api_key": "", "model": "gemini-2.0-flash"},
    "openrouter":{"api_key": "", "model": "google/gemini-2.0-flash-exp:free"}
  },
  "telegram": {"enabled": false, "bot_token": "", "chat_id": ""},
  "shopee":   {"sheet_url": ""},
  "amis": {
    "base_url": "https://crmconnect.misa.vn/api/v2",
    "public_approval_field": "chatbot_public",
    "order_lookup_max_age_seconds": 43200
  }
}
```

---

## 21. Sơ đồ luồng tổng thể

```
[Meta Messenger / n8n]
        │
        │ POST /api/chat-pipeline
        ▼
┌────────────────────────────────────────────────────┐
│  main.py → chat_pipeline.process_chat_pipeline()   │
│                                                    │
│  1. Per-sender asyncio.Lock                        │
│  2. Idempotency (Redis dedup TTL 24h)              │
│  3. Normalize + alias expansion                    │
│  4. Fast-path (chào hỏi, cảm ơn, SĐT) ──────────► answer trực tiếp
│  5. CustomerProfile ← Redis                        │
│  6. QueryPlan ← query_understanding.py             │
│  7. Orchestrator ← conversation_orchestrator.py    │
│       (LLM shadow/assist, đọc lịch sử 6 turn)     │
│  8. DialogueRouter ← dialogue_router.py            │
│       action: fast_path / tool / rag               │
│                                                    │
│  ──── TOOL BRANCH ────                             │
│  9a. dealer_contact_lookup → amis/live_crm.py      │
│  9b. order_status_lookup   → amis/order_cache.py   │
│  9c. loyalty_lookup        → amis/loyalty_cache.py │
│  9d. agronomy_intake       → agronomy/guidance.py  │
│  9e. product_lookup        → shopee_matcher.py     │
│  9f. inventory_lookup      → amis + rag_search     │
│                                                    │
│  ──── RAG BRANCH ────                              │
│  10a. In-memory hot cache (< 1ms)                  │
│  10b. Lexical BM25-like (< 5ms)                    │
│  10c. RediSearch KNN bge-m3 (5-50ms)               │
│                                                    │
│  ──── SHOPEE BRANCH ────                           │
│  11. shopee_matcher.py (30+ matchers)              │
│                                                    │
│  ──── ANSWER GENERATION ────                       │
│  12a. Direct (từ RAG/tool, không LLM)              │
│  12b. Grounded rewrite → Groq/Gemini/Ollama        │
│       └── validate_grounded_rewrite() [STRICT]     │
│  12c. Fallback message                             │
│                                                    │
│  ──── SIDE EFFECTS (fire-and-forget) ────          │
│  13a. telegram_notifier.notify_new_lead()          │
│  13b. persist_session() → Redis                    │
│  13c. evidence_trace → append                      │
│  13d. nlu_shadow (background task)                 │
│                                                    │
│  14. Return ChatPipelineResponse                   │
└────────────────────────────────────────────────────┘
        │
        ▼
[n8n nhận answer → gọi Meta Graph API → khách nhận tin]
```

---

## 22. Redis Key Map

| Key | TTL | Kiểu | Nội dung |
|---|---|---|---|
| `zeo:kb:basic:active` | Vĩnh viễn | String JSON | FAQ snapshot ZeO |
| `cfc:kb:basic:active` | Vĩnh viễn | String JSON | FAQ snapshot CFC |
| `zeo:vec:faq` | Vĩnh viễn | RediSearch Index | Vector index ZeO |
| `cfc:vec:faq` | Vĩnh viễn | RediSearch Index | Vector index CFC |
| `zeo:shopee:catalog:active` | Vĩnh viễn | String JSON | Shopee catalog ZeO |
| `cfc:shopee:catalog:active` | Vĩnh viễn | String JSON | Shopee catalog CFC |
| `amis:public:products:active` | Vĩnh viễn | String JSON | Sản phẩm CFC public |
| `amis:public:sales-locations:active` | Vĩnh viễn | String JSON | Vị trí đại lý |
| `amis:internal:orders:active` | 12h | String JSON | Đơn hàng private |
| `amis:internal:loyalty:active` | Vĩnh viễn | String JSON | Điểm thưởng private |
| `{brand}:profile:{sender_id}` | 30 ngày | Hash | Profile khách |
| `{brand}:session:{sender_id}` | 30 ngày | String JSON | Session + slots |
| `{brand}:history:{sender_id}` | 30 ngày | List | Lịch sử hội thoại 50 turns |
| `{brand}:lock:{sender_id}` | 30s | String | Distributed lock |
| `cfcbot:inbound-dedup:v1:{key}` | 24h | String | Idempotency dedup |
| `cfcbot:bundle-due:v1` | N/A | ZSet | Bundle scheduling |
| `cfc:knowledge:crop_terms` | Vĩnh viễn | String JSON | Danh sách cây trồng |

---

## 23. Test Suite

**Thư mục:** `chatbot/server/tests/` (35 file test)

### Phân loại test

| Nhóm | Files | Mô tả |
|---|---|---|
| Unit — AMIS | `test_amis_*.py` (7 files) | Client, cache, sync, loyalty, order, projection |
| Unit — Conversation | `test_conversation_*.py` (3 files) | Store, orchestrator, regression guards |
| Unit — RAG | `test_knowledge_sync.py`, `test_query_understanding.py` | Sync và NLU |
| Unit — Messaging | `test_messaging_contracts.py` | Contracts versioning |
| Integration | `test_cfc_grounded_memory.py` (43 KB) | Grounding end-to-end |
| Contract | `test_n8n_phase0_contract.py`, `test_phase0_baseline_contract.py` | API contracts |
| Phase gates | `test_phase1_runtime_evidence.py`, `test_phase2_*` | Phase 01/02 checks |
| Feature | `test_handoff_flow.py`, `test_price_constraints.py`, `test_product_link_followup.py` | Business flows |
| Eval | `test_conversation_replay_eval.py`, `test_evaluation_ops.py` | Replay evaluation |

### Chạy test

```bash
# Test cô lập (port 7778, Redis 6380)
docker compose -f compose.test.yaml up -d
pytest chatbot/server/tests/ -v

# Hoặc dùng CLI
CFCbot test-start
curl http://127.0.0.1:7778/health
CFCbot test-stop
```

### `evaluation_ops.py` và `eval_test_suite.py`

Hệ thống đánh giá tự động:
- Chạy scenario từ `eval_conversation_replays.jsonl`
- So sánh output bot với expected answer
- Tính accuracy, grounding violation rate
- Ghi kết quả vào `eval_sheet_grounding_cases.jsonl`

---

## Ghi chú quan trọng cho AI đọc codebase này

1. **chat_pipeline.py** là file chứa toàn bộ business logic chatbot, dài ~6800 dòng. Khi trace bug, bắt đầu từ hàm `process_chat_pipeline()`.

2. **ai_engine.py** chứa fallback chain LLM. Groq thường là provider đầu tiên. Nếu Groq lỗi → Gemini → OpenRouter → Ollama.

3. **Grounding policy là bất khả xâm phạm**: Bot KHÔNG được trả lời giá, liều lượng, link Shopee nếu không có trong evidence từ RAG/catalog. `validate_grounded_rewrite()` sẽ từ chối và pipeline sẽ dùng câu trả lời fallback.

4. **Production lock**: Telegram và Meta Graph API chỉ hoạt động khi `CFCBOT_PRODUCTION_ENABLED=true`. Tests tự động bị block bởi `external_side_effects_allowed()`.

5. **Hai stack Redis**: Production dùng port `6379`, test cô lập dùng port `6380`. Không nhầm lẫn khi đọc config.

6. **AMIS data là private**: Đơn hàng và điểm thưởng chỉ hiển thị khi khách cung cấp đúng SĐT đã đăng ký với CRM. Không bao giờ dump toàn bộ list ra cho khách.

7. **Hai brand song song**: `zeo` và `cfc` có knowledge index riêng, logic khác nhau cho CFC (có slot agronomy, dealer lookup) so với ZeO (chủ yếu Shopee + FAQ).
