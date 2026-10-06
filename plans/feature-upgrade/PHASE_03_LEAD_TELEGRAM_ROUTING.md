# Phase 03 — LeadDraft, định tuyến khu vực và Telegram Sales

Trạng thái: **SHADOW VALIDATED — chờ mapping/group Telegram thật**  
Ưu tiên: **P0 Business**  
Ước lượng: 3–5 ngày  
Phụ thuộc: Phase 02 `DONE`; mapping sale/Telegram đã được chủ hệ thống duyệt.  
Thay đổi production: Shadow/dry-run rồi pilot một vùng.

## 1. Mục tiêu

- Mọi commercial intent hợp lệ tạo/cập nhật LeadDraft theo dõi được.
- Lead đi đúng nhóm sale theo tỉnh/huyện; không chắc thì vào triage.
- Telegram lỗi không làm mất lead và không gửi trùng.
- Không yêu cầu SĐT mới được tạo lead; tiếp tục xin kênh liên hệ phù hợp.

## 2. Hiện trạng tận dụng

- Pipeline đã nhận diện `cfc_purchase_request` và giữ purchase goal qua nhiều lượt.
- `telegram_notifier.py` đã gửi lead trực tiếp khi có phone.
- Area/phone/profile state đã có một phần.
- Chưa có LeadDraft versioned, region route, outbox, claim hoặc SLA.

## 3. Quyết định cần chốt trước code

1. Danh sách nhóm Telegram và tỉnh/huyện phụ trách.
2. Destination triage mặc định.
3. Owner và SLA từng vùng.
4. Trường PII được phép gửi.
5. Lead không có SĐT xử lý thế nào.
6. Khiếu nại/QA có group riêng hay dashboard.

## 4. Work packages

### WP03.1 — Lead domain

- `LeadDraftV1` có ID, version, state, source và audit.
- Commercial intent rules tách khỏi điều kiện “có phone”.
- Merge/update lead theo conversation, không tạo lead mới mỗi lượt.
- Durable repository: SQLite WAL single-host qua interface; chuẩn bị PostgreSQL adapter.

### WP03.2 — Region router

- Versioned province/district -> region -> destination key.
- Model/parser chỉ trích xuất địa danh + confidence.
- Rule table quyết định destination.
- Unknown/low confidence -> triage, không đoán.

### WP03.3 — Sales outbox

- Dedup `lead:{lead_id}:v:{version}:sales-handoff`.
- Retry/backoff, delivery result, dead-letter.
- Chỉ set `routed` sau Telegram success.
- Telegram message ID lưu vào audit.

### WP03.4 — Message template

Thông tin tối thiểu:

- Lead ID, brand, nguồn và thời gian.
- Tên/contact theo policy.
- Nhu cầu, sản phẩm/candidate, số lượng.
- Khu vực/confidence.
- Conversation summary ngắn; không gửi full history mặc định.

### WP03.5 — Shadow/pilot

- Shadow ghi route/destination nhưng không gửi.
- Dry-run vào group nội bộ test.
- Pilot một vùng và triage trước.
- Mở vùng tiếp theo khi SLO đạt.

## 5. Test bắt buộc

1. Có ý định mua nhưng chưa phone vẫn tạo draft.
2. Phone-only lượt sau merge đúng lead/purchase goal.
3. Cần Thơ/Hậu Giang/... route đúng mapping duyệt.
4. Thiếu/không chắc khu vực -> triage.
5. Khách sửa khu vực -> version/update event, không gửi âm thầm hai nhóm.
6. Telegram timeout/429 -> retry, không duplicate.
7. Restart worker -> lead/outbox còn nguyên.
8. Khiếu nại -> CSKH/QA route, không sale thường.
9. PII/message template tuân thủ policy.

## 6. KPI/gate

- Route đúng >= 98%; phần không chắc đi triage.
- Duplicate Telegram lead = 0.
- Lead delivery có trạng thái 100%: pending/sent/retry/dead.
- Lead không có phone không bị mất.
- Dead-letter có alert và owner.

## 7. Rollback

- Tắt `SALES_HANDOFF_ENABLED`, giữ `SALES_HANDOFF_SHADOW` nếu an toàn.
- Không xóa LeadDraft/outbox/audit.
- Telegram notifier cũ chỉ được bật lại có chủ đích, tránh gửi song song.
- Route sai: đóng destination key bị lỗi và chuyển triage.

## 8. Exit gate

- Mapping/PII/SLA được owner ký duyệt.
- Shadow và pilot đạt KPI.
- Không double-send giữa notifier cũ và sales outbox.
- Rollback đã diễn tập.
- Lead state sẵn sàng cho Phase 04.

## 9. Bằng chứng triển khai 06/10/2026

- LeadDraft được tạo theo commercial intent dù chưa có số điện thoại và merge theo
  `brand + sender_id` ở lượt sau.
- Route theo file runtime `sales-routes.json`; không chắc luôn về `triage`.
- Sales outbox dedup theo `lead:{lead_id}:v:{version}:sales-handoff`, retry/backoff
  và trạng thái `dead` sau khi cạn retry.
- Integration tạo đúng 1 LeadDraft + 1 sales outbox `shadow`; `sales_sent=0`.
- Runbook setup/pilot: `docs/operations/TELEGRAM_SALES_SETUP.md`.
- Báo cáo test/deploy: `docs/operations/PHASE_01_03_TEST_REPORT_2026-10-06.md`.
