# Phase 01 — Event contracts, trace, observability và source synchronization

Trạng thái: **SHADOW — code/test DONE; n8n live sync BLOCKED**  
Ưu tiên: **P0 Foundation**  
Ước lượng: 2–4 ngày  
Phụ thuộc: Phase 00 `DONE`  
Thay đổi production: Chỉ instrumentation/shadow, không đổi reply.

## 1. Mục tiêu

- Khóa schema/version cho inbound, bundle, lead và outbox trước khi viết worker.
- Mọi request có trace ID xuyên API, Redis, n8n adapter và log.
- Có metrics/baseline để phát hiện regression ở các phase sau.
- Đồng bộ source workflow n8n local với live bằng quy trình read-before-write.
- Xác định rõ dữ liệu nào được phép log/lưu và retention.

## 2. Hiện trạng tận dụng

- `message_idempotency.py` đã dedup/cached response theo `message_id`.
- `conversation_store.py` đã có sender lease/session state.
- `runtime_manifest.py`, `evidence_trace.py`, evaluation/replay đã tồn tại.
- Bảy workflow source ở `workflows/local-n8n`.
- Chưa có Redis Stream, dead-letter và unified event schema.

## 3. Work packages

### WP01.1 — Versioned contracts

Định nghĩa schema và compatibility rule cho:

- `InboundEventV1`
- `ConversationBundleV1`
- `ResponseOutboxEventV1`
- `LeadDraftV1`
- `SalesOutboxEventV1`
- `DeliveryResultV1`

Mỗi schema có `schema_version`, `event_id`, `trace_id`, timestamps, idempotency key
và policy PII.

### WP01.2 — Trace propagation

- Nhận/generate `trace_id` tại ingress.
- Trả trace ID trong response/debug metadata phù hợp.
- Gắn trace vào session, evidence, outbound và alert.
- Không log prompt/raw payload mặc định.

### WP01.3 — Metrics và alert baseline

- Request count/latency/error theo endpoint/brand/intent.
- Duplicate/in-flight/cached idempotency decisions.
- Sender lease contention/timeouts.
- Model/RAG latency, fallback và circuit-breaker state.
- Redis/n8n/Ollama dependency health.

### WP01.4 — n8n source synchronization

- Cấu hình n8n-as-code environment bằng command chuẩn, không viết config thủ công.
- List và pull live workflow trước khi so drift.
- Không push/publish trong phase này.
- Ghi mapping workflow ID ↔ source file ↔ published status.

### WP01.5 — Security/data policy

- PII mask rules.
- Raw webhook/media retention.
- Log access/retention.
- Synthetic/evaluation dataset policy.

## 4. File dự kiến tác động

- `chatbot/server/phase0_contract.py` hoặc module contract version mới.
- `chatbot/server/main.py`
- `chatbot/server/chat_pipeline.py`
- `chatbot/server/evidence_trace.py`
- `chatbot/server/evaluation_ops.py`
- Test contract/evaluation tương ứng.
- `docs/operations/` và n8n mapping docs.

## 5. Test bắt buộc

1. Schema valid/invalid/backward compatibility.
2. Trace ID được giữ qua một request hoàn chỉnh.
3. Log không chứa phone/token/raw attachment URL trong test mẫu.
4. Duplicate message giữ cùng logical trace hoặc liên kết trace rõ ràng.
5. Dependency lỗi tạo metric/alert nhưng không làm lộ secret.
6. n8n local/live drift report không thực hiện write.

## 6. Rollout

- Instrumentation bật trước trên test.
- Production ở chế độ observe-only.
- Theo dõi overhead latency và log volume 24–48 giờ.
- Không đổi response routing hoặc side effect.

## 7. Rollback

- Feature flag/tắt exporter mới.
- Giữ contract code/test; không xóa evidence đã redact.
- Nếu overhead cao, giảm sampling nhưng giữ error/dead-letter events.

## 8. Exit gate

- Contracts được review và version hóa.
- Trace coverage đạt 100% synthetic path chính.
- Metric baseline có số liệu, không chỉ khai báo.
- PII/log policy pass test.
- n8n mapping và drift report hoàn tất, không có write ngoài ý muốn.
- Có quyết định `GO` cho queue shadow.

## 9. Deliverables

- Contract package + schema tests.
- Observability baseline/report.
- PII/retention policy.
- n8n source-of-truth mapping.
- Queue shadow test plan.

## 10. Bằng chứng triển khai 06/10/2026

- Sáu contract versioned nằm trong `domains/messaging/contracts.py`.
- Middleware trả `X-Trace-Id` và `X-Response-Time-Ms`; không log body/PII.
- `/api/messaging/status` cung cấp counters và durable storage counts.
- Data policy: `docs/operations/MESSAGING_DATA_POLICY.md`.
- Source workflow mapping: `docs/operations/N8N_SOURCE_MAPPING_2026-10-06.md`.
- `n8nac env status --json` báo `configured=false`; do chưa có API key/workspace,
  live list/pull/drift **không được thực hiện** và không có write/push nào xảy ra.
- Báo cáo test/deploy: `docs/operations/PHASE_01_03_TEST_REPORT_2026-10-06.md`.
