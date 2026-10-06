# Phase 07 — Dashboard vận hành, lead/SLA và product analytics

Trạng thái: **PENDING**  
Ưu tiên: **P1 Operations**  
Ước lượng: 4–7 ngày  
Phụ thuộc: Phase 03–06 cung cấp event/state ổn định.  
Thay đổi production: Read-only trước; action có auth mở sau.

## 1. Mục tiêu

- Một màn hình cho biết hệ thống có khỏe không và cơ hội kinh doanh đang mắc ở đâu.
- Operator tìm/replay dead-letter theo quyền và trace ID.
- Quản lý xem lead funnel, route, claim và SLA theo vùng.
- Product owner xem fallback, unanswered, OCR và quality trends.

## 2. Không làm

- Không biến dashboard thành source of truth mới.
- Không hiển thị raw token/prompt/full PII mặc định.
- Không cho action mutation trước khi auth/audit hoàn thiện.
- Không dùng dashboard để che việc thiếu metric/event contract.

## 3. Work packages

### WP07.1 — Operations overview

- API/n8n/Redis/Ollama/Cloudflare health.
- Queue depth/lag, bundle latency, worker heartbeat/error.
- Response/sales outbox pending/retry/dead.
- Model/RAG/OCR latency/error/fallback.

### WP07.2 — Lead/SLA dashboard

- Created/routed/claimed/contacted/closed funnel.
- Time-to-route/claim/contact.
- SLA overdue theo region/owner.
- Triage backlog và route confidence.

### WP07.3 — Quality dashboard

- Intent/fallback/unanswered trends.
- Grounding/evidence status.
- OCR confidence/confirmation rate.
- Evaluation baseline vs candidate releases.

### WP07.4 — Drill-down

- Search bằng lead ID/trace ID đã kiểm soát.
- Event timeline đã mask PII.
- Link tới evidence, outbox attempts và state transitions.
- Không fetch raw execution/media nếu user không có quyền.

### WP07.5 — Operator actions

Mở sau read-only gate:

- Replay dead-letter với confirmation/audit.
- Reassign/release lead.
- Close/resume conversation.
- Không cho sửa trực tiếp DB/state tùy ý.

## 4. Security

- Authentication + role-based authorization.
- CSKH, sale, quản lý và technical admin có permission khác nhau.
- Audit mọi action mutation/export.
- Rate limit và CSRF/session protections phù hợp UI.
- PII reveal là action có quyền và audit.

## 5. Test bắt buộc

1. Metric/API query không gây tải quá mức production.
2. User sai role không xem/action dữ liệu vượt quyền.
3. PII masked mặc định.
4. Lead/SLA số liệu reconcile với event store.
5. Replay action idempotent và có confirmation/audit.
6. Dashboard dependency lỗi không ảnh hưởng chatbot path.
7. Time range/filter/export đúng timezone Asia/Ho_Chi_Minh.

## 6. KPI/gate

- Operator phát hiện incident/lead stuck trong thời gian mục tiêu.
- Dashboard reconciliation sai lệch = 0 trong test window.
- Read-only queries không làm tăng đáng kể API/Redis P95.
- 100% mutation có actor/time/reason.
- Không PII/secret leakage qua UI/log/export.

## 7. Rollout/rollback

- Deploy read-only cho technical admin trước.
- Mở lead view cho quản lý/sale theo role.
- Mutation actions mở từng action bằng feature flag.
- Rollback UI/action không dừng chatbot; data pipeline vẫn ghi event.

## 8. Exit gate

- Security/permission review pass.
- Số liệu reconcile và performance gate pass.
- Runbook operator được viết và thử.
- Dashboard cung cấp evidence cần cho CRM write Phase 08.

