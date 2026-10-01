# Phase 5 — Evaluation, shadow, canary và vận hành

> **Lưu trữ (08/09/2026):** Phase lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Trạng thái: `IN PROGRESS — LOCAL FOUNDATION DONE / NO LIVE CANARY OR N8N OPERATIONS ACTIVATED`
Ưu tiên: bắt đầu dựng baseline song song Phase 0; rollout production thực hiện sau các phase liên quan  
Ước lượng: 4–5 ngày dựng nền + 3–7 ngày lịch để đủ shadow/canary traffic  
Phụ thuộc rollout: Phase 1 trace; phase/capability cần thử đã qua local/replay gate

## 1. Mục tiêu

Chứng minh thay đổi làm chatbot đúng hơn trên real pipeline, không bịa, không lộ dữ liệu và không phá flow cũ; sau đó rollout theo capability và stable canary với điều kiện dừng/rollback tự động rõ ràng.

Không dùng một điểm semantic similarity hoặc vài câu exact-match để tuyên bố “đạt”.

## Kết quả triển khai local — 2026-08-29

- Thêm `evaluation_ops.py`: report replay được đóng dấu `runtime_manifest`, hash/ID của đúng file JSONL dataset và `report_id`. Vì vậy một kết quả eval luôn biết chính xác code/policy/dataset nào đã tạo ra nó.
- Replay scorer đã chấm thêm `source_family`, trạng thái claim, `fallback_reason`, QueryPlan ID và runtime manifest ID. Case mới có thể yêu cầu/không cho phép từng claim status, thay vì chỉ so text answer.
- Hai shadow collector NLU và Conversation nay ghi về một schema/key chung `*:shadow:v2:events`. Event chỉ có hash, route, source family, answer/claim metadata, provider/model và timing; **không lưu raw query, normalized query, raw sender hay raw model reason**.
- NLU shadow dùng đúng `shadow_timeout_seconds` cấu hình (trước đây có timeout hard-code khác cấu hình). Conversation shadow cũng đọc outcome sau xử lý nếu session đã được persist.
- Sửa trace: bật Conversation shadow không còn ghi đè `pipeline_trace_extra` đã có từ QueryPlan/route khác.
- Thêm primitive canary ổn định HMAC theo brand+sender. Mặc định luôn `control/off`; chỉ nhận nấc 0/5/25/100; cần salt + capability allowlist rõ. Các capability high-risk (đơn, tồn, giá, loyalty, protocol nông học) bị chặn trừ khi có cờ phê duyệt riêng. Primitive này **chưa được nối vào customer traffic**.
- Nhóm hồi quy CFC/Phase 2 xanh 35/35. Toàn bộ suite hiện có 195 test: 189 pass, 4 lỗi assertion và 2 lỗi metrics ở AMIS projection/workflow contract cũ; các lỗi này không do catalog CFC mới. Không sửa/push workflow n8n, không bật canary, không gọi AMIS realtime trong triển khai này.
- Bổ sung hai bộ manual real-world test: `chatbot/server/manual_tests/TEST_CFC_REAL_WORLD_PHASE_0_5.md` (56 case, ưu tiên CFC) và `chatbot/server/manual_tests/TEST_ZEO_REAL_WORLD_PHASE_0_5.md` (38 case). Các case chấm theo hành vi/source/privacy/fallback, không chấm exact wording.
- CFC catalog runtime hiện đọc `amis:public:products:active` qua projection allowlist; công thức NPK phải khớp chính xác và chỉ hiển thị tối đa 3–5 sản phẩm. Không có giá, tồn kho hay trường CRM trong projection.
- Bổ sung hai bộ manual real-world test: `chatbot/server/manual_tests/TEST_CFC_REAL_WORLD_PHASE_0_5.md` (56 case, ưu tiên CFC) và `chatbot/server/manual_tests/TEST_ZEO_REAL_WORLD_PHASE_0_5.md` (38 case). Các case chấm theo hành vi/source/privacy/fallback, không chấm exact wording.
- CFC catalog runtime hiện đọc `amis:public:products:active` qua projection allowlist; công thức NPK phải khớp chính xác và chỉ hiển thị tối đa 3–5 sản phẩm. Không có giá, tồn kho hay trường CRM trong projection.

Chưa thể tuyên bố Phase 5 hoàn tất vì chưa có baseline workbook được nghiệp vụ duyệt, chưa có shadow traffic đủ mẫu, chưa có approval canary và P5-WP4/P5-WP5 n8n operations chưa được reconcile với live.

## 2. Bằng chứng hiện trạng

- Workbook baseline: 14 case, trung bình 5.00/10, 2 pass.
- Không câu test nào trùng nguyên văn FAQ examples; paraphrase/routing/memory là phần quyết định.
- Có replay multi-turn và tests hiện hữu nhưng trạng thái tài liệu cũ không phải live proof.
- Trace hiện tại chưa đủ provider/model/runtime/evidence; Phase 1 phải bổ sung.
- n8n continue-on-error có thể làm execution xanh dù pipeline/rebuild lỗi.
- Knowledge/alert workflows có remote drift; local source không được push mù.

## 3. Ngoài phạm vi

- Không để model tự quyết expected answer.
- Không dùng production customer/sender raw làm fixture.
- Không gọi mocked test là live validation.
- Không rollout 100% chỉ vì offline score đạt.
- Không đổi nhiều capability cùng lúc trong một canary nếu không tách metric.

## 4. Work packages

### P5-WP1 — Versioned eval corpus

Việc làm:

1. Chuyển case hard-code về JSONL/schema versioned hoặc adapter tương đương.
2. Import 14 workbook cases làm baseline có nhãn, không sửa điểm lịch sử.
3. Giữ replay hiện có và gắn version/source.
4. Mỗi case có:
   - conversation turns;
   - setup/source/tool state;
   - expected intent/action/source family;
   - required/forbidden claims;
   - expected clarification/handoff;
   - privacy/ownership expectation;
   - applicable capability phase.
5. Paraphrase do model tạo chỉ là candidate; người duyệt expected behavior.

Families:

- direct;
- paraphrase/typo/không dấu/địa phương;
- multi-intent;
- follow-up/reference;
- source challenge/correction;
- switch/resume;
- PII/ownership;
- stale/timeout/tool unavailable;
- out-of-scope;
- prompt injection.

File dự kiến:

- `chatbot/server/eval_test_suite.py`
- `chatbot/server/conversation_replay_eval.py`
- `chatbot/server/eval_conversation_replays.jsonl`
- dataset/version manifest mới
- workbook giữ làm evidence baseline

### P5-WP2 — Multi-layer scoring

Không chỉ chấm answer text. Report phải chấm:

- QueryPlan candidates/primary action;
- tool/source family;
- reference/GoalFrame;
- evidence/claim status;
- required/forbidden claims;
- fallback/clarification correctness;
- latency/provider error;
- privacy/ownership;
- task completion qua nhiều lượt.

Bốn mode:

1. pure unit;
2. mocked-tool contract;
3. isolated Redis real-pipeline replay;
4. production shadow/canary.

Mỗi report pin:

- runtime manifest;
- queryplan/prompt/policy version;
- snapshot hashes;
- provider/model nếu có;
- dataset version.

Case cần realtime tool chưa triển khai không bị chấm “sai” nếu chatbot chọn đúng capability boundary. Chấm sai khi bot bịa hoặc chọn sai source/tool family.

### P5-WP3 — Unified shadow events

Hợp nhất shadow collectors thành schema chung:

```json
{
  "turn_hash": "...",
  "sender_hash": "...",
  "brand": "cfc",
  "runtime_manifest_id": "...",
  "mode": "shadow|canary|control",
  "bucket": 123,
  "deterministic_proposal": {},
  "semantic_proposal": {},
  "accepted_plan": {},
  "actual_route": "...",
  "source_family": "...",
  "answer_id": "...",
  "claim_statuses": [],
  "timings": {},
  "generator": {},
  "fallback_reason": "...",
  "error_code": "..."
}
```

Quy tắc:

- schedule event sau khi biết actual route/outcome;
- không lưu raw query/sender/PII;
- sender/message không dùng làm metric label cardinality cao;
- timeout dùng đúng config, không hard-code lệch;
- đo `scheduled`, `not_sampled`, `queue_full`, `error`, cache hit, agreement và route_changed.

File dự kiến:

- `chatbot/server/nlu_shadow.py`
- `chatbot/server/conversation_orchestrator.py`
- `chatbot/server/chat_pipeline.py`
- event store/report tests

### P5-WP4 — N8n chatbot error contract

Workflow chatbot:

1. Pull/reconcile drift trước khi sửa.
2. Success và error output tách hoàn toàn.
3. Success validate response schema, message correlation, duplicate và `suppress_send`.
4. Error tạo `PipelineErrorEvent` redacted → Operations Alert.
5. Nếu business muốn nhắn khách, dùng safe transport fallback cố định, gửi tối đa một lần.
6. Không lấy error body hoặc missing answer làm customer answer.

File dự kiến:

- `workflows/local-n8n/zeo_chatbot.workflow.ts`
- `workflows/local-n8n/cfc_cobay_chatbot.workflow.ts`
- operations alert workflow

### P5-WP5 — N8n knowledge/alert false-green

Knowledge sync:

1. `last_success` chỉ sau snapshot/vector/hash/hot-cache checkpoints.
2. Không dùng continue-regular để biến rebuild lỗi thành xanh.
3. Failure → alert + execution fail; giữ last-known-good snapshot.

Operations alert:

1. schema/fingerprint/dedupe/redaction;
2. chỉ ghi delivered sau Telegram success;
3. Telegram lỗi → durable dead-letter + execution fail;
4. không đưa raw sender/query/payload vào notification.

AMIS writer được chọn:

- timeout/invalid snapshot phải fail/alert;
- không làm thay đổi trên cả hai writer cùng lúc;
- metrics phân biệt public snapshot với privileged realtime.

### P5-WP6 — Stable canary policy

Bucket:

```text
hash(salt + brand + sender_id) -> stable bucket
```

Không đổi nhánh giữa một session. Rollout theo capability:

1. clarification;
2. reference resolver;
3. source challenge;
4. topic switch/resume;
5. multi-intent;
6. realtime tools/agronomy protocol theo gate riêng.

Nấc:

```text
off -> shadow -> 5% -> 25% -> 100%
```

Mỗi nấc giữ ít nhất 24 giờ và 200 eligible turns, hoặc lâu hơn nếu traffic thấp. 100% cần duyệt nghiệp vụ; high-risk operational routes vẫn deterministic/capability-boundary nếu chưa có tool/protocol.

### P5-WP7 — Admin/report dashboard

Read-only, internal-only:

- eval report;
- shadow agreement/disagreement;
- canary allocation/error budget;
- unsupported claim/source challenge;
- p50/p95/provider timeout;
- workflow false-green/alert delivery;
- rollback reason/manifest.

Có thể mở rộng domain test/admin hiện có. Endpoint cần loopback/internal token, không trả raw query/sender.

## 5. Gates và stop conditions

### Immediate stop

Canary dừng ngay nếu:

- unsupported critical claim > 0;
- PII/financial leak hoặc ownership bypass > 0;
- duplicate Messenger send > 0;
- n8n false-green > 0;
- wrong high-risk tool execution > 0.

### Quality gates

| Chỉ số | Gate |
|---|---:|
| Source challenge gold set | 100% |
| Correct source/tool family | ≥ 95% |
| Intent family | ≥ 90% |
| Reference accuracy | ≥ 95% |
| Clarification khi thiếu slot | ≥ 95% |
| Provider/runtime trace | 100% AI calls |
| Error-rate delta so với control | ≤ 0.5 điểm % |
| Shadow queue full | < 1% |

Deterministic p95 không tăng quá 15% hoặc 250 ms, lấy ngưỡng lớn hơn. Planner timeout/error phải đo riêng, không được tính là agreement.

## 6. Entry gate

- Capability target đã đạt phase-specific exit gate local/replay.
- P1 runtime/evidence trace hoạt động.
- Dataset/expected behavior được nghiệp vụ duyệt.
- Control behavior và error budget được ghi nhận.
- Workflow drift/conflict có hướng reconcile được chủ hệ thống chọn.
- Rollback flag/revision đã sẵn sàng.

## 7. Exit gate

- Offline/replay/shadow và từng canary nấc đạt toàn bộ safety/quality gates.
- 100% traffic ổn định tối thiểu 7 ngày.
- Rollback drill hoàn thành dưới 5 phút.
- Alert canary chứng minh workflow lỗi không còn false-green.
- Report pin được manifest/policy/snapshot/dataset.
- Có post-rollout review và danh sách lỗi còn mở.

## 8. Rollback

- đặt capability/mode về `off`;
- stable control tiếp tục phục vụ;
- không flush Redis, giữ GoalFrame/events để điều tra;
- rollback theo runtime manifest, QueryPlan version và snapshot hash;
- n8n rollback theo revision đã pin, không force workflow cũ chưa pull;
- last-known-good snapshot không bị ghi đè;
- safety guards Phase 0 luôn giữ bật.

## 9. Checklist nghiệm thu

- [ ] Eval corpus/version manifest hoàn tất.
- [ ] 14 baseline cases được import đúng nhãn.
- [ ] Paraphrase expected được người duyệt.
- [ ] Multi-layer scorer pin manifest/snapshot.
- [ ] Unified shadow event redacted.
- [ ] N8n chatbot error path tách success.
- [ ] Knowledge/alert workflow không false-green.
- [ ] Stable bucket và capability flags hoạt động.
- [ ] Immediate stop rules được test.
- [ ] 5%/25%/100% gates có report.
- [ ] Rollback drill dưới 5 phút.
- [ ] Production ổn định 7 ngày trước `DONE`.
