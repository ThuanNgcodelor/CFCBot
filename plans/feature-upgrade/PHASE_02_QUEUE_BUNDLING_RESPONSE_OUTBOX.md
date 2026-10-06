# Phase 02 — Inbound queue, message bundling và response outbox

Trạng thái: **SHADOW VALIDATED — production adapter chưa chuyển tuyến**  
Ưu tiên: **P0 Core**  
Ước lượng: 3–5 ngày  
Phụ thuộc: Phase 01 `DONE`  
Thay đổi production: Shadow rồi canary theo sender bucket.

## 1. Mục tiêu

- Khách gửi 2–4 tin gần nhau tạo một bundle đúng thứ tự và một reply phù hợp.
- Webhook ACK nhanh sau khi event đã được ghi nhận.
- Không mất/trùng event hoặc reply khi worker/dependency restart.
- Tách outbound delivery khỏi conversation processing bằng outbox.

## 2. Quyết định mặc định

- Quiet window: 4 giây.
- Max window: 12 giây.
- Partition key: `brand + sender_id`.
- Redis Stream + consumer group cho inbound.
- Sorted set cho bundle due time.
- Sender lease/compare-and-set chỉ cho một worker finalize.
- Compatibility path đồng bộ hiện tại giữ nguyên đến hết canary.

## 3. Work packages

### WP02.1 — Ingress/enqueue

- Endpoint validate + enqueue + ACK.
- Reuse message idempotency hiện có; không tạo hệ dedup cạnh tranh.
- Payload theo `InboundEventV1`, có text/location/media descriptors.
- Dead-letter cho event invalid/retry exhausted.

### WP02.2 — Bundle scheduler

- Open/update bundle theo sender.
- Cập nhật `due_at` nhưng không vượt `max_due_at`.
- Sort theo platform timestamp và message ID.
- Đóng bundle atomically.

### WP02.3 — Conversation worker

- Claim bundle bằng lease.
- Gọi pipeline hiện tại qua adapter, không copy business logic.
- Giữ takeover/idempotency/grounding behavior hiện hữu.
- Commit result trước khi ACK event.

### WP02.4 — Response outbox

- Durable outbox record và idempotency key.
- Retry exponential backoff + jitter.
- Delivery result và dead-letter.
- n8n/Meta outbound chỉ là adapter gửi.

### WP02.5 — Shadow/canary

- Shadow tạo bundle/result nhưng không gửi khách.
- So output với synchronous path.
- Canary stable sender bucket 5% -> 20% -> 50% -> 100%.

## 4. Redis contract dự kiến

```text
cfcbot:inbound:v1
cfcbot:bundle:{brand}:{sender_id}
cfcbot:bundle-due:v1
cfcbot:bundle-lease:{brand}:{sender_id}
cfcbot:response-outbox:v1
cfcbot:dead-letter:inbound:v1
cfcbot:dead-letter:response:v1
```

Redis AOF hỗ trợ transport nhanh; outbox/lead quan trọng cần repository abstraction
để có thể dùng SQLite WAL single-host và chuyển PostgreSQL sau này.

## 5. File/module dự kiến

- `chatbot/server/domains/messaging/contracts.py`
- `chatbot/server/domains/messaging/ingress.py`
- `chatbot/server/domains/messaging/bundles.py`
- `chatbot/server/domains/messaging/workers.py`
- `chatbot/server/domains/messaging/outbox.py`
- `chatbot/server/main.py`
- Compose/API worker configuration.
- n8n workflow chỉ sửa sau pull/validate theo Phase 01.

Tên module là đề xuất; implementation được quyền điều chỉnh nhưng phải giữ domain boundary.

## 6. Test bắt buộc

1. Bốn text trong 4 giây -> một ordered bundle/reply.
2. Tin sau 12 giây -> bundle mới.
3. Text/location/media đến lệch thứ tự -> sort đúng.
4. Meta retry cùng message ID -> không thêm event/reply.
5. Hai worker -> một finalize.
6. Worker chết trước/sau commit -> replay không double-send.
7. Redis/n8n/Meta timeout/429 -> retry đúng.
8. Takeover `pending/human` -> suppress outbound đúng.
9. Queue lag/dead-letter metric/alert hoạt động.
10. Feature flag off -> synchronous path hoạt động như baseline.

## 7. SLO/gate

- Inbound accepted/enqueued >= 99,9%.
- Duplicate reply < 0,1%; mục tiêu test/canary = 0.
- P95 từ tin cuối đến reply 4–10 giây.
- Không event mất trong restart/failure simulation.
- Dead-letter có replay và owner.

## 8. Rollback

- Tắt `CHAT_QUEUE_ENABLED`/canary, trở về synchronous path.
- Không xóa stream/outbox; giữ để điều tra/replay.
- Dừng worker mới, không dừng toàn bộ API.
- Nếu n8n adapter đổi, pin lại published version trước canary.

## 9. Exit gate

- Shadow đủ mẫu và không có divergence nghiêm trọng.
- Canary 100% ổn định qua observation window được duyệt.
- Retry/dead-letter/replay đã diễn tập.
- Synchronous compatibility path vẫn dùng được cho rollback.

## 10. Bằng chứng triển khai 06/10/2026

- Redis Stream ingress, consumer group, sender bundle, quiet/max window và lease đã có.
- SQLite WAL response outbox có unique idempotency key; callback delivery được bảo vệ.
- Integration trên `7778/6380`: 4 event -> 1 bundle -> 1 response `shadow`;
  retry trùng -> `duplicate=true`; pipeline errors = 0.
- Endpoint đồng bộ `/api/chat-pipeline` vẫn pass sau test; production không đổi route.
- Chưa chuyển n8n/Meta sang `/api/messaging/enqueue` khi live workflow chưa pull.
- Báo cáo test/deploy: `docs/operations/PHASE_01_03_TEST_REPORT_2026-10-06.md`.
