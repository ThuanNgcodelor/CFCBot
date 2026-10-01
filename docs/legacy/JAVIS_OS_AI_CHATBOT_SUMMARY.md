# 🤖 JAVIS-OS: TỔNG QUAN DỰ ÁN HỆ THỐNG AI CHATBOT ĐA NHÃN HÀNG (ZEO & CFC CÒ BAY)

> **Tài liệu tổng hợp toàn diện kiến trúc, nghiệp vụ, dữ liệu CRM và tiến độ triển khai dành cho đối chiếu kỹ thuật & nạp vào Claude.**
> **Cập nhật ngày:** 27/08/2026

---

## 📌 I. TỔNG QUAN HỆ THỐNG (SYSTEM OVERVIEW)

Dự án **JAVIS-OS** là nền tảng AI Chatbot tự động hóa dịch vụ khách hàng (CSKH), tư vấn bán hàng (B2C & B2B) và tích hợp dữ liệu quản trị doanh nghiệp cho 2 thương hiệu độc lập:

1. **ZeO Vietnam (FMCG / Hóa phẩm gia dụng):**
   * Sản phẩm: Bột giặt công nghệ sinh học Enzyme Thụy Điển, Nước rửa chén Pano Vitamin E, Nước lau sàn Oplus, Hóa mỹ phẩm gia đình.
   * Kênh bán: Shopee Mall, Website thương mại điện tử `zeo.vn`, Đại lý tiêu dùng.
2. **CFC - Phân bón Cò Bay (Nông nghiệp / B2B & Đại lý):**
   * Sản phẩm: 932 SKU phân bón NPK (16-8-16, 20-20-15, 16-6-18...), Phân hữu cơ khoáng, Trung vi lượng.
   * Khách hàng: Đại lý cấp 1, Đại lý cấp 2, Hợp tác xã, Nhà vườn quy mô lớn.
   * Tích hợp: Dữ liệu thật từ **AMIS CRM (MISA)** gồm 4.845 hồ sơ đại lý và 6.718 đơn hàng.

---

## 🏗️ II. KIẾN TRÚC KỸ THUẬT (3-TIER HYBRID ARCHITECTURE)

```
[ Khách hàng nhắn tin trên Facebook Messenger / Web ]
                           │
                           ▼
             [ Cloudflare Tunnel / Gateway ]
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ TẦNG 1: FAST-PATH & AMIS CRM ENGINE (< 50ms)                │
│ • Kiểm tra Session, Reset bộ nhớ, Tách biệt SĐT             │
│ • Định tuyến Chéo Thương hiệu (ZeO ↔ CFC)                   │
│ • Tra cứu Realtime AMIS CRM (932 SKU, Hội viên, Đơn hàng)   │
│ • Bảo mật Bảng giá sỉ, Công nợ, Khiếu nại QA SOP, Khách B2B│
└──────────────┬──────────────────────────────┬───────────────┘
               │ (Nếu là câu hỏi nghiệp vụ)   │ (Nếu là câu hỏi FAQ)
               ▼                              ▼
     [ Trả lời trực tiếp ]      ┌─────────────────────────────┐
                                │ TẦNG 2: REDISEARCH VECTOR   │
                                │ • Embedding bằng Ollama     │
                                │ • RediSearch KNN (RAM)      │
                                └──────────────┬──────────────┘
                                               │ (Khớp Master FAQ)
                                               ▼
                                     [ Trả lời Master FAQ ]
                                               │ (Nếu là câu mở)
                                               ▼
                                ┌─────────────────────────────┐
                                │ TẦNG 3: OLLAMA LLM RAG      │
                                │ • Qwen 2.5 / Llama 3.2      │
                                │ • Tư vấn Nông học chuyên sâu│
                                └─────────────────────────────┘
```

### Các thành phần chính trong hệ thống:
* **Storage & In-Memory Database:** **Redis Stack (Port 6379)** lưu trữ Session, Customer Profile, RediSearch Vector Index, AMIS Snapshots, Shopee Catalog, Geo Location.
* **Workflow Automation & Sync:** **n8n (Port 5678)** đồng bộ tự động dữ liệu từ Google Sheets, Google Docs, Shopee và AMIS CRM.
* **Core Backend & APIs:** **FastAPI Core (Port 7777)** và **Chatbot Pipeline Engine (Port 8000)**.
* **AI Embeddings & Inference:** **Ollama (Port 11434)** chạy model embedding (`bge-m3`) và LLM (`qwen2.5` / `llama3.2`).

---

## 🎯 III. CÁC TÍNH NĂNG VÀ NGHIỆP VỤ ĐÃ HOÀN THÀNH 100%

### 1. Phân Luồng Chéo Nhãn Hàng Tuyệt Đối (Zero Cross-Brand Hallucination)
* Hỏi về **bột giặt, nước giặt, ZeO, Oplus** trên Fanpage Phân bón CFC $\rightarrow$ Bot tự động phân luồng, hướng dẫn khách truy cập `https://zeo.vn/` hoặc Shopee Mall ZeO.
* Hỏi về **phân bón, NPK, Cò Bay, sầu riêng** trên Fanpage ZeO $\rightarrow$ Bot tự động phân luồng sang `https://cfccobay.com/` và Fanpage Phân bón Cò Bay.

### 2. Tra Cứu Realtime AMIS CRM Minh Bạch & Trung Thực (Không Fake Data)
* **Đơn hàng không tồn tại (`#DH-9999-999`, `#DH-2026-889`):** Báo trung thực: *"Dạ CFC Cò Bay đã tra cứu trực tiếp trên hệ thống AMIS CRM nhưng không tìm thấy mã đơn hàng..."*, tuyệt đối không bịa số xe tải 65C hay tài xế.
* **SĐT lạ không có trong CRM (`038850946`):** Báo trung thực không tìm thấy hồ sơ hội viên trên CRM.
* **SĐT đại lý thật CRM (`0976535396`, `0917725727`):** Nhận diện chính xác tên Đại lý (HKD Trần Quốc Tuấn, Hộ KD VTNN Ngọc Yến), Hạng hội viên (Thân Thiết, Kim Cương), Sản lượng tấn thật và che SĐT an toàn (`*****5396`).
* **Công thức ảo (`NPK 99-99-99`) / Hàng ngoài ngành (`Xi măng Hà Tiên`):** Báo trung thực không có trong danh mục 932 SKU của nhà máy.
* **Dịch vụ vay tiền / trả góp:** Báo trung thực công ty không kinh doanh dịch vụ tín dụng/cho vay.

### 3. Bộ Lọc Đại Lý Hoạt Động Thực Tế (Active Recency Window $\le$ 200 Ngày)
* Hệ thống tự động lọc dữ liệu CRM:
  * Lọc bỏ **4.304 tài khoản 0 đơn** (khách tiềm năng/danh bạ trắng).
  * Lọc bỏ **275 đại lý ngưng hợp tác** (quá 200 ngày không phát sinh đơn hàng mới).
  * Chỉ giữ lại **196 đại lý hoạt động thực tế** có doanh số mua hàng trong vòng 200 ngày gần nhất để gợi ý cho khách kèm link Google Maps.
* **Cơ chế hoàn toàn tự động:** Khi n8n chạy lịch đồng bộ từ CRM, nếu có đại lý mới phát sinh đơn, Redis sẽ tự động ghi nhận mà không cần sửa code.

### 4. Tách Biệt SĐT Tra Cứu vs SĐT Liên Hệ Khách Hàng
* SĐT xuất hiện trong câu hỏi tra cứu hội viên/đơn hàng chỉ dùng cho riêng câu hỏi đó, **không lưu đè** vào hồ sơ cá nhân của người chat.
* Khi khách chuyển sang hỏi đặt hàng B2B cho hợp tác xã, bot yêu cầu để lại SĐT người đại diện mới, không lấy nhầm SĐT đã tra cứu trước đó.

### 5. Chuẩn Hóa Định Dạng Chống Facebook Tự Tạo Link IP
* Chuyển toàn bộ công thức phân bón sang dạng gạch nối: `Phân NPK 16-8-16-12S TE` $\rightarrow$ Triệt tiêu lỗi Facebook tự nhận chuỗi `16.8.16.12` thành địa chỉ IP để gắn link web ngoài.
* Lọc bỏ hoàn toàn các mặt hàng bột giặt, nước giặt ngoài ngành khỏi danh mục gợi ý biến thể phân bón.

### 6. Quản Lý Session & Test Suite Độc Lập
* Người dùng chỉ cần gõ `reset` hoặc `test mới` là hệ thống dọn sạch 100% Redis Session và In-Memory Cache.
* Tạo 2 bộ test case hoàn chỉnh:
  * [TEST_PAGE_PHAN_BON_CFC.md](file:///Users/hyden/Documents/David-nguyen/javis-os/test_suites/TEST_PAGE_PHAN_BON_CFC.md): 20 test case copy-paste kiểm tra Fanpage Phân bón CFC.
  * [TEST_PAGE_ZEO_VIETNAM.md](file:///Users/hyden/Documents/David-nguyen/javis-os/test_suites/TEST_PAGE_ZEO_VIETNAM.md): 10 test case copy-paste kiểm tra Fanpage ZeO Vietnam.

---

## 📊 IV. THỐNG KÊ DỮ LIỆU ĐANG VẬN HÀNH TRÊN REDIS

| Dữ liệu | Key / Index trên Redis | Số lượng bản ghi | Trạng thái |
| :--- | :--- | :---: | :---: |
| **Sản phẩm AMIS CRM** | `amis:public:products:active` | **932 SKU** | 🟢 Live |
| **Đại lý Active ($\le 200$ ngày)** | `amis:public:sales-locations:active` | **196 Đại lý** | 🟢 Live |
| **Tọa độ Geo Đại lý** | `amis:public:sales-locations:geo` | **196 Điểm** | 🟢 Live |
| **Catalog Shopee Mall ZeO** | `zeo:shopee:catalog:active` | **52 SKU** | 🟢 Live |
| **Vector Index FAQ ZeO** | `zeo:vec:faq` | **82 FAQ Vectors** | 🟢 Live |
| **Vector Index FAQ CFC** | `cfc:vec:faq` | **19 FAQ Vectors** | 🟢 Live |
| **Tổng số Keys trên Redis** | Toàn bộ Database | **111 Keys** | 🟢 Hoạt động tối ưu |

---

## 📁 V. CẤU TRÚC THƯ MỤC CỐT LÕI

```
javis-os/
├── chatbot/
│   └── server/
│       ├── main.py                     # Entrypoint Chatbot Server (:8000)
│       ├── chat_pipeline.py            # Core Pipeline xử lý tin nhắn & Fast-Path
│       ├── knowledge_sync.py           # Đồng bộ Vector Embeddings vào RediSearch
│       ├── shopee_matcher.py           # Đối chiếu sản phẩm Shopee Mall ZeO
│       └── domains/
│           └── amis/
│               ├── config.py           # Cấu hình AMIS CRM (recency_days = 200)
│               ├── live_crm.py         # Tra cứu realtime đơn hàng, SKU, SĐT
│               ├── projection.py       # Lọc và tạo Snapshot an toàn từ CRM
│               ├── service.py          # Đồng bộ dữ liệu CRM vào Redis
│               └── routes.py           # API Admin đồng bộ CRM
├── server/
│   ├── main.py                         # FastAPI Core Server (:7777)
│   ├── routes/javis_legacy.py          # Legacy Routes (/api/web/refresh-cache, sync)
│   └── legacy_javis_runtime.py         # Runtime xử lý gọi nội bộ
├── workflows/local-n8n/                # Workflows n8n đồng bộ tự động
│   ├── amis_crm_public_sync.workflow.ts
│   ├── zeo_knowledge_sync_basic.workflow.ts
│   └── cfc_knowledge_sync_basic.workflow.ts
├── test_suites/
│   ├── TEST_PAGE_PHAN_BON_CFC.md       # 20 Test Cases Fanpage Phân bón CFC
│   └── TEST_PAGE_ZEO_VIETNAM.md        # 10 Test Cases Fanpage ZeO Vietnam
└── JAVIS_OS_AI_CHATBOT_SUMMARY.md      # Tài liệu tổng hợp toàn diện dự án
```
