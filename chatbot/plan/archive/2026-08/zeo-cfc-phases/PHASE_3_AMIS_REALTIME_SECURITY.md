# Phase 3 — AMIS realtime, phân quyền và bảo mật

> **Lưu trữ (08/09/2026):** Phase lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Trạng thái: `IN PROGRESS — LOCAL FOUNDATION DONE / LIVE DECISIONS BLOCKED`
Ưu tiên: P1 đối với bảo mật public sync; P2 đối với realtime capabilities  
Ước lượng: 5–10 ngày kỹ thuật, chưa tính phê duyệt API/nghiệp vụ  
Phụ thuộc: Phase 0 containment; Phase 1 evidence/tool trace tối thiểu

## Kết quả triển khai local — 2026-08-29

- Order lookup customer-facing được xác định đúng là `protected_warm_cache`, không gọi là realtime: bắt buộc mã đơn chính xác + SĐT khớp HMAC và kiểm freshness trước khi trả lời.
- Chỉ field allowlist được trả: trạng thái đơn, tình trạng giao, ngày đặt/hạn giao và `Cập nhật gần nhất` từ `modified_date`; không trả thời điểm đồng bộ cache, PII, tiền, công nợ, địa chỉ hay dòng hàng.
- `live_crm.py` không còn báo `LIVE_AMIS_API` chỉ vì có credential/file cache. Status trả `PROTECTED_WARM_CACHE`, khai báo rõ inventory/loyalty/giá/chiết khấu/công nợ chưa có realtime customer-facing.
- Trace order chỉ lưu outcome/freshness/method ownership đã redaction, không lưu SĐT hay raw order.
- Test local: order access/freshness + formatter + status contract xanh. Không có AMIS API realtime nào được gọi hay được bật trong thay đổi này.

## 1. Mục tiêu

Tách rõ hai loại tích hợp AMIS:

1. **Public snapshot**: chỉ chứa dữ liệu tham chiếu đã duyệt như tên/mã/đơn vị sản phẩm và điểm bán public.
2. **Privileged realtime lookup**: order, shipment, ATP, current price, loyalty hoặc dữ liệu khách hàng; yêu cầu xác thực, quyền, freshness và audit.

Phase này không nhằm đưa toàn bộ CRM cho chatbot. Mục tiêu là cho phép chatbot trả lời đúng những câu cần realtime mà không làm lộ PII, tài chính hoặc dữ liệu bên thứ ba.

## 2. Bằng chứng hiện trạng

- Cả `AMIS CRM Full Warm` và `AMIS CRM Public Catalog Sync` đang active live và có thể ghi cùng Redis keys.
- Snapshot đang phục vụ tại lúc audit khớp thời điểm Full Warm ghi.
- Full Warm tải raw Customers, Products và SaleOrders qua n8n execution.
- Internal token chưa cấu hình.
- `pilot_approve_all=true`, allowlist rỗng.
- Direct AMIS audit timeout và route trả 500 thô.
- `live_crm.py` đọc `amis_real_crm_cache.json`; trạng thái `LIVE_AMIS_API` chỉ dựa vào credential có tồn tại.
- Một số ATP/loyalty behavior trong local cache là suy diễn/hard-code, không phải response realtime có request ID.

## 3. Ngoài phạm vi

- Không public công nợ, doanh thu, giá vốn, raw order hoặc hồ sơ khách.
- Không dùng số điện thoại khách làm khóa tra cứu tự do nếu chưa có ownership verification.
- Không đưa credential vào Git, workflow source hoặc command line.
- Không hứa realtime cho capability chưa có endpoint AMIS được xác minh.
- Không tự deactivate workflow live trong lúc code; cần phê duyệt riêng.

## 4. Work packages

### P3-WP1 — Quyết định một public snapshot writer

Việc làm:

1. Chọn `amis_crm_public_sync.workflow.ts` làm hướng mặc định vì projection nằm trong FastAPI và dễ kiểm soát hơn.
2. Lập kế hoạch deactivate/cô lập `amis_crm_full_warm.workflow.ts` sau phê duyệt.
3. Rotate/revoke secret từng được nhúng trong Full Warm.
4. Xác định retention và xử lý execution history có raw CRM theo chính sách nội bộ.
5. Đặt owner duy nhất cho Redis keys `amis:public:*`.

File/hệ thống dự kiến:

- `workflows/local-n8n/amis_crm_full_warm.workflow.ts`
- `workflows/local-n8n/amis_crm_public_sync.workflow.ts`
- n8n credentials và execution retention
- runbook bảo mật, không lưu secret trong tài liệu

Gate:

- chỉ một workflow có quyền ghi public snapshot;
- secret cũ không còn hiệu lực;
- execution mới không lưu raw Customers/SaleOrders.

### P3-WP2 — Khóa public projection

Việc làm:

1. Tắt `pilot_approve_all`.
2. Bắt buộc `chatbot_public` hoặc allowlist đã duyệt rõ.
3. Quyết định có bắt buộc tọa độ hay cho phép location không GPS.
4. Tách `source_updated_at`, `synced_at`, `snapshot_hash`, `record_count`, `approval_policy_version`.
5. Giữ projection allowlist; reject mọi field/tự do text chứa giá, công nợ hoặc mã đơn.
6. Thêm comparison gate để snapshot giảm bất thường không được publish.

File dự kiến:

- `chatbot/server/domains/amis/config.py`
- `chatbot/server/domains/amis/projection.py`
- `chatbot/server/domains/amis/service.py`
- `chatbot/server/tests/test_amis_projection.py`
- `chatbot/server/tests/test_amis_sync_service.py`

Gate:

- public allowlist có owner và version;
- projection safety test quét đệ quy toàn payload;
- snapshot cũ được giữ nguyên nếu policy/min-count/freshness gate fail.

### P3-WP3 — Internal authentication contract

Việc làm:

1. Cấu hình `AMIS_SYNC_INTERNAL_TOKEN` bằng secret store/environment.
2. n8n gửi `X-Internal-Token` qua credential/header expression, không hard-code.
3. Server so token constant-time và không trả lại token trong status/error.
4. Phân biệt route public admin read-only với route sync/mutation nội bộ.
5. Ghi audit metadata bằng request ID, workflow ID và caller class; không ghi token/payload nhạy cảm.

File dự kiến:

- `chatbot/server/domains/amis/routes.py`
- `chatbot/server/domains/amis/config.py`
- `chatbot/server/tests/test_amis_routes.py`
- `workflows/local-n8n/amis_crm_public_sync.workflow.ts`

Gate:

- thiếu/sai token trả 401/403 rõ;
- đúng token hoạt động từ n8n;
- status không lộ secret;
- loopback policy được mô tả và test, không phụ thuộc mơ hồ vào proxy headers.

### P3-WP4 — Chuẩn hóa AMIS client reliability

Việc làm:

1. Catch riêng timeout, auth, rate limit, contract/pagination và upstream 5xx.
2. Chuẩn hóa mã lỗi: `AMIS_TIMEOUT`, `AMIS_AUTH_FAILED`, `AMIS_RATE_LIMITED`, `AMIS_CONTRACT_CHANGED`, `AMIS_PARTIAL_DATA_REJECTED`.
3. Retry có backoff/jitter, giới hạn attempt và deadline toàn request.
4. Token refresh một lần khi 401; không loop vô hạn.
5. Circuit breaker cho upstream lỗi liên tục.
6. Route không biến raw `httpx.ReadTimeout` thành HTTP 500 không cấu trúc.
7. Public sync fail phải giữ snapshot cũ và báo stale age.

File dự kiến:

- `chatbot/server/domains/amis/client.py`
- `chatbot/server/domains/amis/service.py`
- `chatbot/server/domains/amis/routes.py`
- `chatbot/server/scripts/amis_crm_sync.py`
- `chatbot/server/tests/test_amis_client.py`
- `chatbot/server/tests/test_amis_routes.py`

### P3-WP5 — Privileged realtime tool contracts

Không tạo một endpoint “CRM query” tổng quát. Tạo capability hẹp:

| Tool | Input tối thiểu | Output public/safe | Freshness |
|---|---|---|---|
| `order_status_lookup` | verified customer identity + order reference | trạng thái/last update được phép | realtime/short TTL |
| `inventory_atp_lookup` | product code + quantity + warehouse/area | available/unavailable/needs-human + timestamp | realtime/very short TTL |
| `current_price_lookup` | product/quantity/area + role scope | quote status hoặc handoff; chỉ giá nếu policy cho phép | realtime |
| `loyalty_lookup` | verified customer identity | điểm/hạng của chính chủ | realtime/short TTL |
| `dealer_location_search` | brand + public geography | approved public locations only | periodic snapshot |

Mỗi result phải có:

```json
{
  "result_id": "opaque-id",
  "tool": "order_status_lookup",
  "source_id": "amis:privileged:order-status",
  "source_timestamp": "...",
  "expires_at": "...",
  "authorization_scope": "self",
  "request_id": "...",
  "status": "ok|unavailable|denied|stale",
  "public_payload": {}
}
```

File dự kiến:

- module mới dưới `chatbot/server/domains/amis/` theo từng capability
- `chatbot/server/ai_agent_tools.py` hoặc tool registry hiện hành
- `chatbot/server/chat_pipeline.py` chỉ dùng sanitized `public_payload`
- tests ownership/privacy/tool contract

Quyết định bắt buộc trước code:

- Messenger sender được liên kết customer identity bằng cách nào?
- Có OTP hay human verification không?
- Role nào được xem giá/chiết khấu/công nợ?
- Endpoint AMIS chính thức nào cung cấp từng field và SLA/freshness?

### P3-WP6 — Xóa tên gọi “live” gây hiểu nhầm

Việc làm:

1. `live-status` phải phân biệt:
   - `credentials_configured`;
   - `public_snapshot_fresh`;
   - `privileged_realtime_verified`;
   - `last_live_probe_at`;
   - `last_live_probe_result`.
2. Local JSON cache chỉ được báo `LOCAL_CACHE`, không phải `LIVE_AMIS_API`.
3. Loại hard-coded ATP/loyalty khỏi customer-facing path hoặc gắn `mock/test-only` và fail-closed ở production.

File dự kiến:

- `chatbot/server/domains/amis/live_crm.py`
- AMIS status routes/tests
- dashboard/admin status consumer nếu có

## 5. Test matrix bắt buộc

### Unit/contract

- secret thiếu/sai/đúng;
- token refresh 401 đúng một lần;
- timeout và rate limit;
- pagination lặp/partial page;
- public projection không chứa price/debt/order/customer IDs;
- allowlist/approval/coordinates/recency;
- snapshot transaction và preserve-on-failure;
- tool result schema/freshness/authorization.

### Privacy/ownership

- hỏi đơn của chính mình nhưng chưa xác thực;
- hỏi đơn/công nợ/điểm của người khác;
- đổi SĐT giữa hội thoại;
- sender khác dùng lại order code;
- prompt injection đòi raw CRM;
- n8n error/execution không chứa raw payload.

### Live validation có kiểm soát

Chỉ chạy sau credential và phê duyệt:

1. status không lộ secret;
2. dry-run aggregate-only;
3. một request read-only với test identity/dataset được phép;
4. xác nhận request ID/freshness;
5. không publish nếu record count/policy gate fail;
6. canary lookup không đưa PII vào trace/prompt.

Mocked test không được ghi là live proof.

## 6. Entry gate

- Phase 0 đã chặn Full Warm gây thêm raw execution hoặc có quyết định containment tương đương.
- Có owner nghiệp vụ AMIS và owner bảo mật.
- Có danh sách public fields/location approval.
- Có tài liệu endpoint/quyền cho capability realtime mục tiêu.
- Phase 1 có result/evidence trace tối thiểu.

## 7. Exit gate

- Chỉ một public snapshot writer active.
- Internal token hoạt động, không lộ secret.
- `pilot_approve_all=false`; public location có approval rõ.
- AMIS timeout không tạo 500 thô hoặc câu trả lời bịa.
- `live-status` phản ánh đúng snapshot/cache/realtime.
- Capability realtime được test ownership và freshness.
- 0 raw CRM/PII/financial payload trong public Redis, LLM prompt và execution mới.
- Chỉ capability đã qua live canary mới được customer-facing.

## 8. Rollout và rollback

Rollout:

1. public sync dry-run;
2. write shadow key hoặc compare-only;
3. publish snapshot mới sau safety gate;
4. realtime tool shadow không ảnh hưởng answer;
5. canary theo capability, không bật toàn CRM;
6. mở dần sau privacy/error-budget gate.

Rollback:

- disable riêng capability flag;
- giữ snapshot active trước đó bằng transactional publish;
- không quay lại Full Warm raw path;
- revoke token/credential nếu nghi lộ;
- chuyển chatbot về capability boundary/human handoff;
- không xóa Redis session.

## 9. Checklist nghiệm thu

- [ ] Một public writer.
- [ ] Secret cũ đã rotate/revoke.
- [ ] Internal token và n8n credential hoàn tất.
- [ ] Public approval policy được ký duyệt.
- [ ] Timeout/rate-limit/auth/partial-data tests xanh.
- [ ] `LOCAL_CACHE` không còn báo `LIVE_AMIS_API`.
- [ ] Ít nhất một privileged tool có ownership + freshness + audit.
- [ ] Privacy/adversarial suite xanh.
- [ ] Live canary dùng test identity được phép.
- [ ] Runbook incident/rollback được thử.

### Checklist local bổ sung

- [x] Warm order cache dùng exact code + phone HMAC, freshness gate và minimal response allowlist.
- [x] Business `updated_at` được hiển thị theo giờ Việt Nam; `synced_at` không customer-facing.
- [x] Legacy status không còn gắn nhãn realtime sai.
- [ ] Privileged realtime adapter có endpoint AMIS, ownership link/OTP và business approval.
