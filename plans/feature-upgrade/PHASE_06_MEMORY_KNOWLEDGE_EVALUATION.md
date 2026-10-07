# Phase 06 — Conversation Memory 2.0, Knowledge Governance và Evaluation Gate

Trạng thái: **FACT API IMPLEMENTED / GOVERNANCE PENDING**
Ưu tiên: **P1 Quality**  
Ước lượng: 5–10 ngày  
Phụ thuộc: Phase 02 `DONE`; Phase 01 contracts/trace ổn định.  
Thay đổi production: Shadow/canary theo từng capability.

## 1. Mục tiêu

- Nhớ đúng dữ kiện hữu ích của đúng khách, đúng brand, có source/confidence/TTL.
- Quản lý tri thức RAG theo lifecycle được duyệt và rollback được.
- Mọi release AI/business logic phải qua evaluation gate đo được.
- Giảm fallback và regression mà không nới lỏng grounding.

## 2. Hiện trạng tận dụng

- Conversation state, GoalFrame, sender lease và history đã có.
- RAG, approved agronomy facts, evidence trace và grounding policy đã có.
- Replay/evaluation modules và nhiều regression tests đã có.
- Chưa có durable fact model thống nhất, knowledge approval lifecycle và release gate chung.

## 3. Work packages

### WP06.1 — Memory model

Tách:

- Turn memory: vài lượt gần nhất, TTL ngắn.
- Active goal: mục tiêu hiện tại và slots còn thiếu.
- Durable fact: cây trồng, khu vực, nhu cầu đã xác nhận.

Mỗi fact có:

```text
fact_type, value, source_event_id, confidence
collected_at, confirmed_at, expires_at, brand, identity_scope
```

### WP06.2 — Conflict/identity policy

- Khách sửa fact -> version mới, không merge mù.
- Fact cũ/nhạy cảm -> hỏi xác nhận lại.
- Không cross-brand hoặc cross-sender nếu chưa có identity link được duyệt.
- Reset/export/delete theo privacy policy.

### WP06.3 — Knowledge lifecycle

```text
draft -> review -> approved -> published -> retired
```

- Mỗi item có source, owner, audience, effective dates và version.
- Không cho model tự publish.
- Dataset version pin theo runtime/release.
- Rollback knowledge version độc lập code deploy.

### WP06.4 — Evaluation center

- Golden/replay sets cho product, agronomy, order, loyalty, dealer, handoff, OCR.
- Score intent, grounding, evidence, safety, latency và state transition.
- High-risk cases là blocking gate.
- Báo cáo diff baseline vs candidate.

### WP06.5 — Learning queue có phê duyệt

- Capture unanswered/low-confidence đã redact.
- Dedupe/cluster suggestions.
- Human review trước khi tạo knowledge draft.
- Không dùng feedback khách/sale làm truth tự động.

## 4. Test bắt buộc

1. Hai khách/brand không lẫn fact/history.
2. Fact conflict tạo version/confirmation đúng.
3. Expired fact không dùng như truth.
4. Reset/delete xóa đúng scope, không xóa khách khác.
5. Knowledge draft/unapproved không vào production RAG.
6. Retired/version rollback hoạt động.
7. Grounding chặn giá/tồn/chính sách không nguồn.
8. Replay baseline không regression route chính.
9. Learning suggestion không tự publish.
10. Evaluation artifacts không lộ PII.

## 5. KPI/gate

- Cross-customer/brand leakage = 0.
- High-risk regression = 0.
- Grounded answer rate tăng mà unsupported claims không tăng.
- Fallback/unanswered giảm trên dataset đại diện.
- 100% published knowledge có source/owner/version.
- Release gate chạy lặp lại được từ commit/runtime manifest.

## 6. Rollout

- Fact extraction shadow trước, chưa ảnh hưởng reply.
- Knowledge lifecycle áp dụng cho content mới trước, migrate content cũ sau.
- Evaluation gate advisory trước, blocking khi baseline ổn định.
- Canary memory read theo sender bucket.

## 7. Rollback

- Tắt durable memory read, quay về turn/session state hiện tại.
- Pin knowledge dataset version trước.
- Evaluation gate có thể chuyển advisory trong incident, không bỏ safety tests.
- Không xóa fact/version audit trong rollback.

## 8. Exit gate

- Privacy/identity/conflict policies được duyệt.
- Memory shadow/canary không leakage/regression.
- Knowledge lifecycle và rollback diễn tập.
- Blocking evaluation gate hoạt động trong CI/release flow.
- Dashboard data contract sẵn sàng cho Phase 07.

## 9. Đã triển khai

- `MemoryFactV1` và SQLite `memory_facts` có scope brand/sender, confidence,
  source event, confirmation và expiry.
- Authenticated save/list API; `MEMORY_FACTS_ENABLED=false` production.
- Knowledge lifecycle, replay evaluation gate và dashboard quality chưa bật; cần
  dataset/owner review trước khi chuyển blocking gate.
