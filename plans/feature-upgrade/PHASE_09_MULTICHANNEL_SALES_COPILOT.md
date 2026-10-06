# Phase 09 — Multi-channel gateway và Sale Copilot

Trạng thái: **LAST**  
Ưu tiên: **P2 Expansion**  
Ước lượng: 7–14 ngày  
Phụ thuộc: Phase 02–08 ổn định qua observation window.  
Thay đổi production: Từng channel/feature pilot riêng.

## 1. Vì sao làm cuối cùng

Multi-channel nhân số lượng event, identity, credential và failure mode. Sale copilot
dùng dữ liệu lead/memory/CRM. Nếu triển khai trước khi nền tảng ổn định, hệ thống sẽ
nhân rộng duplicate, route sai và dữ liệu không nhất quán.

## 2. Mục tiêu

- Một channel contract chung cho Messenger, Web và channel tiếp theo được duyệt.
- Một conversation/lead domain thống nhất nhưng identity được cô lập đúng scope.
- Sale copilot tóm tắt evidence và đề xuất bước tiếp theo, không tự commit hành động.
- Analytics đo funnel xuyên channel.

## 3. Work packages — Multi-channel

### WP09.1 — Channel adapter interface

```text
verify -> normalize inbound -> enqueue
deliver outbound -> delivery result
resolve identity/channel capabilities
```

- Adapter không chứa business logic.
- Mỗi channel có signature/token/rate limit riêng.
- Feature capability matrix: text, image, location, button, delivery receipt.

### WP09.2 — Identity policy

- Không tự merge Messenger/Zalo/Web chỉ vì phone giống.
- Identity link cần xác minh/consent/rule được duyệt.
- Memory/lead ownership và delete/export theo identity graph.

### WP09.3 — Channel rollout

- Messenger giữ làm reference.
- Web chat là channel pilot khuyến nghị.
- Zalo/channel khác chỉ sau khi credential/API policy sẵn sàng.
- Một channel lỗi không chặn worker channel khác.

## 4. Work packages — Sale Copilot

- Tóm tắt nhu cầu, lịch sử, sản phẩm, khu vực, OCR và CRM evidence.
- Gợi ý câu hỏi còn thiếu/bước tiếp theo theo playbook.
- Soạn nháp message; sale phải review/send ở MVP.
- Không tự báo giá, cam kết tồn kho hoặc thay đổi CRM.
- Hiển thị source/evidence và uncertainty.

## 5. Product analytics

- Funnel theo channel: inbound -> qualified -> routed -> claimed -> contacted -> outcome.
- Time-to-first-response/claim/contact.
- Conversion chỉ dùng khi outcome source được xác minh.
- Không xếp hạng sale bằng metric thiếu context/chưa được duyệt.

## 6. Test bắt buộc

1. Cùng payload semantics qua hai adapter cho cùng normalized contract.
2. Retry/dedup/idempotency cô lập theo channel.
3. Không cross-channel identity leak.
4. Channel outage không ảnh hưởng channel khác.
5. Copilot không đề xuất unsupported price/stock/policy.
6. Evidence/citation đúng source và freshness.
7. Draft không tự gửi khi chưa approve.
8. Analytics reconcile với lead/CRM events.

## 7. KPI/gate

- Adapter contract pass 100% capability tests.
- Cross-channel leakage/duplicate = 0.
- New channel đạt SLO reply/delivery riêng.
- Copilot suggestion helpfulness đạt ngưỡng pilot, safety violation = 0.
- Funnel metrics reconcile và có owner.

## 8. Rollout/rollback

- Mỗi channel có feature flag và worker pool riêng.
- Pilot internal -> limited audience -> canary -> expand.
- Copilot read-only/draft-only trước.
- Rollback channel/coplilot độc lập, Messenger core không đổi.

## 9. Exit gate

- Core pipeline đã ổn định qua observation window dài hạn.
- Identity/privacy/security review pass.
- Channel adapter và copilot pilot đạt KPI.
- Runbook credential/rate-limit/outage cho từng channel hoàn tất.
- Không còn dependency ngầm vào Javis hoặc workflow business logic rải rác.

