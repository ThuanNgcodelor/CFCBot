


# Checklist triển khai Phase 3–5 — 2026-08-29

> **Lưu trữ (08/09/2026):** Checklist lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Phạm vi checklist này phân biệt rõ **đã kiểm chứng local** với **cần quyết định nghiệp vụ/live**. Không mục nào bên dưới đồng nghĩa đã deploy production.

## Phase 3 — AMIS, phân quyền và freshness

- [x] Lookup đơn customer-facing dùng protected warm cache, không tự nhận là AMIS realtime.
- [x] Bắt buộc mã đơn chính xác và SĐT khớp HMAC; chỉ trả allowlist trạng thái/giao hàng/ngày đặt/hạn giao/cập nhật nghiệp vụ.
- [x] Chặn PII, tài chính, công nợ, địa chỉ, dòng hàng và raw CRM khỏi câu trả lời/trace.
- [x] Gắn freshness và ownership outcome vào trace đã redaction.
- [x] Test contract lookup/freshness/formatter/status local.
- [x] Catalog public CFC có projection/allowlist riêng; không trả giá, tồn kho hoặc raw CRM.
- [x] Mua số lượng lớn có đầu mối Kinh doanh công khai, không tự hứa giá/chiết khấu.
- [x] Catalog public CFC có projection/allowlist riêng; không trả giá, tồn kho hoặc raw CRM.
- [x] Mua số lượng lớn có đầu mối Kinh doanh công khai, không tự hứa giá/chiết khấu.
- [ ] Chốt identity binding/OTP cho tool realtime privileged.
- [ ] Chốt endpoint AMIS chính thức + SLA cho tồn/giá/loyalty/realtime order.
- [ ] Bật internal token qua secret store; test live 401/403/success.
- [ ] Chọn một snapshot writer, xử lý credential cũ và retention execution có raw CRM.

## Phase 4 — tri thức nông học được duyệt

- [x] Có schema/validator fact: source locator, approval, expiry, risk, crop và product/protocol approver.
- [x] Không resolve fact draft/expired/duplicate; eligibility không được chứa liều lượng.
- [x] Seed fact sầu riêng chỉ ở mức eligibility, có nguồn; không phải phác đồ hay cam kết thương mại.
- [x] Câu eligibility có fact bypass AI planner; công thức/liều/triệu chứng vẫn expert intake.
- [x] Test validator, trace và regression câu nông học local.
- [x] Câu thiếu protocol có đầu mối Khuyến nông; Ollama không được tự kê liều customer-facing.
- [x] Câu thiếu protocol có đầu mối Khuyến nông; Ollama không được tự kê liều customer-facing.
- [ ] Kỹ sư duyệt fact/protocol thật cho sầu riêng, lúa và các case pilot.
- [ ] Nối Sheets authoring + publish transaction/versioned snapshot sau khi owner kỹ thuật duyệt schema.
- [ ] Đánh giá protocol bằng case thật trước khi public bất kỳ liều lượng nào.

## Phase 5 — evaluation, shadow, canary và vận hành

- [x] Replay eval có dataset hash/version, runtime manifest và report ID.
- [x] Scorer hỗ trợ route/source-family/claim/fallback/state; không chỉ so câu trả lời.
- [x] Unified shadow v2 không lưu raw query/sender/model reason; queue bounded + TTL.
- [x] Shadow NLU dùng timeout cấu hình; trace shadow không ghi đè trace pipeline.
- [x] Canary primitive stable HMAC, default off, nấc 0/5/25/100 và chặn high-risk theo mặc định.
- [x] Nhóm hồi quy liên quan CFC/Phase 2 xanh 35/35; toàn bộ suite đã chạy 195 test (189 pass, 4 lỗi assertion và 2 lỗi metrics thuộc AMIS projection/workflow contract cũ, cần xử lý riêng).
- [x] Có bộ test hỏi thật CFC ưu tiên và ZeO, gồm typo, follow-up, source challenge, CRM, nông học, B2B, khiếu nại và prompt injection.
- [x] Có test regression public catalog: loại mặt hàng lẫn, khớp công thức chính xác, projection không có giá/tồn.
- [x] Có bộ test hỏi thật CFC ưu tiên và ZeO, gồm typo, follow-up, source challenge, CRM, nông học, B2B, khiếu nại và prompt injection.
- [x] Có test regression public catalog: loại mặt hàng lẫn, khớp công thức chính xác, projection không có giá/tồn.
- [ ] Import/duyệt 14 workbook baseline, gắn expected behavior/source/privacy trước khi dùng làm quality gate.
- [ ] Chạy replay với snapshot/runtime được chốt; ghi baseline control, p50/p95/error rate.
- [ ] Reconcile/pull workflow live trước P5-WP4/P5-WP5; tách error contract, false-green và alert delivery.
- [ ] Bật shadow có retention/owner/dashboard read-only được duyệt; thu đủ mẫu theo gate.
- [ ] Chỉ sau đó xin duyệt canary capability thấp rủi ro 5% → 25% → 100%; không đưa order/giá/tồn/loyalty/protocol vào canary chung.
