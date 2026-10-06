# Plan nâng cấp tính năng CFCBot

Ngày lập: 01/10/2026  
Phạm vi: CFC Cò Bay trước, thiết kế có khả năng tái sử dụng cho ZeO.  
Trạng thái: **Product + Engineering Roadmap — chưa phải lệnh triển khai production.**

> **Cập nhật rà soát 06/10/2026:** Roadmap đã được tách thành bộ file thực thi tại
> [plans/feature-upgrade](plans/feature-upgrade/README.md). Phase 00 mới được ưu tiên
> trước mọi tính năng vì repo đã chuyển đường dẫn nhưng container/symlink production
> vẫn còn tham chiếu đường dẫn cũ.

## 1. Vai trò của tài liệu

Tài liệu này là plan riêng cho **tính năng mới và cải tiến sản phẩm CFCBot**.

- [Plan di chuyển khỏi Javis](PLAN_DI_CHUYEN_CHATBOT_TU_JAVIS_OS_2026-09-30.md)
  mô tả migration/cutover.
- [Master plan queue, OCR và Telegram](chatbot/plan/PLAN_DINH_HUONG_CAP_NHAT_CFCBOT_QUEUE_OCR_TELEGRAM_2026-10-01.md)
  mô tả kiến trúc kỹ thuật chi tiết cho các capability nền tảng.
- Tài liệu hiện tại quyết định **xây tính năng nào trước, giá trị kinh doanh, trải
  nghiệm người dùng, tiêu chí nghiệm thu và thứ tự rollout**.

Khi có xung đột, nguyên tắc an toàn production và dữ liệu trong master plan kỹ thuật
được ưu tiên.

## 2. Tầm nhìn sản phẩm

CFCBot không chỉ là bot trả lời FAQ. Mục tiêu là một trợ lý bán hàng và CSKH có thể:

1. Hiểu trọn một chuỗi tin nhắn rời rạc của khách.
2. Nhận biết sản phẩm từ text và ảnh nhưng không bịa dữ liệu.
3. Nhận ra tín hiệu mua hàng, thu thập đủ thông tin và chuyển đúng sale khu vực.
4. Biết khi nào tiếp tục tự động và khi nào nhường cho người thật.
5. Nhớ ngữ cảnh hợp lý giữa các lượt mà không trộn dữ liệu khách hàng.
6. Tra cứu nguồn tri thức/CRM có kiểm soát và giải thích được căn cứ trả lời.
7. Đo được chất lượng, lỗi, lead, SLA và hiệu quả bán hàng.
8. Vận hành được bằng một hệ thống độc lập, quan sát được và rollback được.

Kết quả kinh doanh mong muốn:

- Ít bỏ sót khách hỏi mua.
- Ít trả lời nhiều lần khi khách nhắn liên tục.
- Sale nhận lead đúng khu vực, đủ ngữ cảnh và đúng thời điểm.
- Giảm câu trả lời sai về giá, tồn kho, sản phẩm và kỹ thuật nông học.
- Quản trị nhìn thấy bot đang giúp hay làm mất cơ hội ở đâu.

## 3. Baseline hiện tại

### Đã có

- CFCBot chạy production độc lập; Javis runtime cũ đã tắt.
- FastAPI chatbot, Redis Stack, n8n, Ollama và Cloudflare hoạt động.
- Conversation state, idempotency cơ bản, deterministic fast path và RAG.
- CFC agronomy/product/order/loyalty/dealer routes hiện hữu.
- Qwen 2.5 7B cho hội thoại local và BGE-M3 cho embedding.
- Telegram notifier cơ bản và dashboard quản trị hiện hữu.
- n8n workflow source đã nằm trong CFCBot.

### Có một phần nhưng chưa đủ

- Tin nhắn có session memory nhưng chưa có bundle/debounce bền vững.
- Telegram gửi thông báo nhưng chưa có LeadDraft, route theo vùng, claim và SLA.
- Workflow nhận biết attachment nhưng API chưa nhận media descriptor đầy đủ.
- Có test/replay nhưng chưa có quality dashboard và release gate thống nhất.
- Có AMIS read/cache nhưng chưa có customer-facing CRM write an toàn.
- Human takeover đã có state `pending/human/closed`, API claim/close và test suppress
  bot; chưa có durable claim audit, Telegram callback, SLA và escalation hoàn chỉnh.

### Chưa có

- OCR/vision pipeline cho ảnh bao phân bón.
- Durable inbound/outbound/sales outbox và dead-letter.
- Human takeover end-to-end có sale identity, durable audit, SLA và callback.
- Learning loop có phê duyệt để biến câu chưa trả lời thành tri thức mới.
- Product analytics nối từ hội thoại -> lead -> sale claim -> kết quả.

## 4. Nguyên tắc chọn tính năng

Mỗi tính năng chỉ được đưa vào roadmap nếu trả lời được bốn câu hỏi:

1. Vấn đề khách hàng hoặc sale nào đang được giải quyết?
2. Dữ liệu nguồn sự thật là gì?
3. Khi AI không chắc thì hệ thống làm gì?
4. Đo thành công và rollback bằng cách nào?

Nguyên tắc chung:

- Reliability trước intelligence; không thêm model để che lỗi luồng dữ liệu.
- Rule quyết định quyền, route và commit; model chỉ hiểu/đề xuất.
- Một nguồn sự thật cho giá, tồn kho, sản phẩm và CRM.
- Mỗi capability có feature flag, shadow mode, canary và rollback riêng.
- Không bật chức năng gửi ra khách/sale thật khi chưa có test và owner duyệt.
- Không đưa secret, token, PII hoặc ảnh khách vào Git.

## 5. Danh mục ưu tiên

| Mức | Tính năng | Giá trị chính | Phụ thuộc |
|---|---|---|---|
| P0 | Gom chuỗi tin nhắn + queue | Một khách nhắn nhiều câu chỉ nhận một reply đúng ngữ cảnh | Redis Stream, worker, outbox |
| P0 | LeadDraft + Telegram theo vùng | Không bỏ sót khách mua, sale đúng khu vực nhận đủ dữ kiện | Route map, Telegram groups, SLA |
| P0 | Human takeover | Bot không tranh trả lời với sale/CSKH | Lead state, claim, policy |
| P0 | Observability và dead-letter | Biết tin/lead nào lỗi và replay được | Trace ID, metrics, alert |
| P1 | OCR ảnh bao phân | Hiểu ảnh sản phẩm để hỏi/xác nhận đúng | Media ingest, OCR, catalog |
| P1 | Memory/profile nâng cấp | Nhớ cây trồng, nhu cầu, khu vực đúng khách | Identity, TTL, privacy |
| P1 | Knowledge governance | RAG có nguồn, version, phê duyệt và rollback | Dataset, evaluation |
| P1 | Quality/Evaluation Center | Ngăn regression trước release | Replay set, scoring, release gate |
| P1 | Dashboard lead/SLA | Quản trị thấy pipeline và bottleneck sale | LeadDraft, audit events |
| P2 | CRM write có phê duyệt | Tạo/cập nhật lead CRM mà không ghi sai | AMIS contract, approval, idempotency |
| P2 | Sale copilot | Gợi ý tóm tắt và bước tiếp theo cho sale | Lead history, policy |
| P2 | Multi-channel gateway | Dùng cùng bộ não cho Messenger/Zalo/Web | Stable channel contract |
| P2 | Phân tích hiệu quả kinh doanh | Đo từ cuộc chat tới kết quả lead | Funnel event model |

P0 là nền móng bắt buộc. Không triển khai P2 để né một dependency P0 chưa hoàn thành.

## 6. Các hành trình người dùng mục tiêu

### 6.1 Khách nhắn nhiều câu liên tục

```text
Khách: Tôi cần mua phân
Khách: NPK 20-20-15
Khách: 10 bao
Khách: giao ở Ô Môn

CFCBot: gom trong quiet window -> hiểu một nhu cầu -> trả lời một lần
```

Tiêu chí:

- Giữ đúng thứ tự sự kiện.
- Không reply bốn lần.
- Không chờ quá max window.
- Meta retry không tạo reply trùng.

### 6.2 Khách gửi ảnh bao phân

```text
Ảnh -> secure download -> OCR -> đối chiếu catalog -> candidate + confidence
```

- Confidence cao: hỏi khách xác nhận ngắn.
- Confidence vừa/thấp: xin ảnh rõ hơn hoặc tên sản phẩm.
- Không suy ra hàng thật/giả, giá hay tồn kho từ ảnh.
- Khiếu nại có ảnh đi CSKH/QA, không đi sale thường.

### 6.3 Khách có ý định mua

```text
Commercial intent -> LeadDraft -> hỏi dữ kiện còn thiếu
-> route tỉnh/vùng -> sales outbox -> Telegram group
```

- Không bắt buộc có SĐT mới tạo draft.
- Không rõ địa bàn thì hỏi lại và route group triage.
- Mỗi lead/version chỉ gửi đúng một lần.

### 6.4 Sale nhận và tiếp quản

```text
New -> Routed -> Claimed -> Contacted -> Closed
```

- Khi sale claim, bot ngừng luồng bán hàng liên quan.
- Bot chỉ tiếp tục FAQ không liên quan nếu policy cho phép.
- Quá SLA thì reminder/escalation tới owner đã cấu hình.

### 6.5 Khách quay lại

- Nhận diện đúng theo Page/brand/sender, không trộn identity.
- Nhớ dữ kiện hữu ích có TTL: cây trồng, khu vực, nhu cầu gần nhất.
- Dữ kiện nhạy cảm hoặc cũ phải hỏi xác nhận lại.
- Khách có thể yêu cầu reset/xóa context theo policy.

## 7. Đặc tả nhóm tính năng

### Feature A — Conversation Inbox và message bundling

Mục tiêu: biến các event rời thành một yêu cầu hội thoại có ngữ cảnh.

Phạm vi MVP:

- Inbound queue bền vững.
- Quiet window 4 giây, max window 12 giây.
- Per-sender lease và ordered bundle.
- Response outbox, retry và dead-letter.
- Replay một bundle lỗi theo trace ID.

Ngoài MVP: tự động tối ưu quiet window theo từng khách.

### Feature B — Sales Lead Router

Mục tiêu: mọi tín hiệu mua hàng hợp lệ trở thành lead theo dõi được.

Phạm vi MVP:

- `LeadDraft` có version và audit.
- Rule province/district -> sales region -> destination key.
- Group triage khi không chắc.
- Sales outbox và dedup.
- Nội dung Telegram tối thiểu: nhu cầu, sản phẩm, số lượng, khu vực, contact,
  nguồn và thời điểm.

Không để model tự chọn chat ID hoặc nhóm Telegram.

### Feature C — OCR Product Assistant

Mục tiêu: dùng ảnh để hỗ trợ nhận diện candidate, không thay catalog.

Phạm vi MVP:

- Media descriptor, secure downloader và TTL storage.
- PaddleOCR worker riêng.
- Exact/fuzzy/catalog retrieval bằng BGE-M3.
- Confidence/evidence contract và confirmation flow.
- Bộ test ảnh thật đã được duyệt và ẩn PII.

Vision model là thử nghiệm P2 của feature này, không phải dependency MVP.

### Feature D — Human Handoff và SLA

Mục tiêu: chuyển từ bot sang người thật mà không mất context hoặc trả lời chồng.

Phạm vi MVP:

- Claim, release, contacted và close.
- Human takeover flag theo conversation/lead.
- SLA timer, reminder và escalation.
- Audit actor/time/action.
- Fallback khi Telegram callback không hoạt động.

### Feature E — Knowledge Quality Center

Mục tiêu: quản lý RAG như dữ liệu production, không phải tập file rời.

Phạm vi MVP:

- Source, owner, version, audience và hiệu lực của từng knowledge item.
- Draft -> review -> approved -> retired.
- Evaluation set cho product, agronomy, order, loyalty và dealer.
- Citation/evidence nội bộ trong trace.
- Rollback dataset/version.

Không cho model tự ghi trực tiếp câu mới vào knowledge production.

### Feature F — Conversation Memory 2.0

Mục tiêu: nhớ đủ để hữu ích, không nhớ quá mức hoặc sai người.

Phạm vi MVP:

- Tách short-term turn memory và durable customer facts.
- Mỗi fact có source, confidence, collected_at và TTL.
- Conflict resolution khi khách sửa khu vực/cây trồng/số lượng.
- Không dùng dữ kiện của brand khác nếu chưa có identity link được duyệt.
- Reset/export/delete theo privacy policy.

### Feature G — Operations và Product Dashboard

Mục tiêu: nhìn thấy cả sức khỏe kỹ thuật lẫn hiệu quả nghiệp vụ.

Dashboard MVP:

- Queue depth/lag, bundle latency và worker errors.
- Reply success/retry/dead-letter.
- Lead created/routed/claimed/contacted/closed.
- SLA overdue theo vùng/owner.
- Top unanswered/fallback intents.
- OCR confidence và tỷ lệ cần hỏi lại.
- Model latency/error/fallback nhưng không log prompt chứa PII mặc định.

### Feature H — CRM Write Gateway

Mục tiêu: tạo hoặc cập nhật lead CRM an toàn sau khi lead đã được xác nhận.

Điều kiện bắt buộc:

- Schema AMIS write được xác minh trên sandbox/test record.
- Idempotency key và reconciliation job.
- Approval mode trước auto mode.
- Audit request/response đã che secret/PII.
- Không tự tạo Sale Order trong phase đầu.

## 8. Roadmap triển khai

### Phase 0 — Ổn định đường dẫn runtime và sau cutover (7–14 ngày)

Trạng thái: **cần xử lý ngay việc repo đã move trước khi tiếp tục observation**.

- Theo dõi CFCBot API, Redis, n8n, Ollama và Cloudflare.
- Ghi baseline latency, lỗi, duplicate và fallback.
- Không xóa Javis source/container/volume cũ.
- Chốt incident/rollback runbook.
- Rebind Compose labels, bind mount và symlink lifecycle từ đường dẫn cũ sang repo mới.

Gate: không có lỗi nghiêm trọng chưa hiểu nguyên nhân; rollback đã kiểm tra.

### Phase 1 — Event foundation + observability (2–4 ngày)

- Khóa event schemas và trace ID.
- Inbound stream, idempotency, dead-letter và metrics.
- Chạy shadow, chưa đổi reply production.

Gate: không mất/trùng event trong failure simulation.

### Phase 2 — Message bundling + response outbox (3–5 ngày)

- Bundle scheduler/worker, quiet/max window và lease.
- Response outbox và adapter delivery result.
- Canary 5% -> 20% -> 50% -> 100% theo stable sender bucket.

Gate: duplicate reply < 0,1%; P95 từ tin cuối tới reply trong 4–10 giây.

### Phase 3 — LeadDraft + Telegram Router (3–5 ngày)

- Lead state, route config, sales outbox và group triage.
- Shadow/dry-run trước khi gửi group thật.
- Mở một vùng pilot trước khi mở toàn bộ.

Gate: route đúng >= 98%; duplicate lead = 0; lỗi Telegram không mất lead.

### Phase 4 — Human takeover + SLA (2–4 ngày)

- Claim/contact/close, takeover policy, reminder và escalation.
- Dashboard trạng thái lead cơ bản.

Gate: bot/sale không trả lời chồng trong test và pilot.

### Phase 5 — OCR Product Assistant (4–7 ngày)

- Media ingest, OCR worker, catalog match và confirmation flow.
- Shadow trên bộ ảnh thật; CFC pilot trước.

Gate: precision đạt ngưỡng đã chốt; không vi phạm policy ảnh.

### Phase 6 — Memory + Knowledge Quality (5–10 ngày)

- Fact memory có source/TTL.
- Knowledge lifecycle và evaluation release gate.
- Dashboard fallback/unanswered.

Gate: không regression test hiện hữu; không cross-customer/brand leakage.

### Phase 7 — CRM Write Gateway (sau khi Phase 3–6 ổn định)

- Sandbox/approval mode.
- Idempotent create/update lead.
- Reconciliation và audit.

Gate: 100% test record reconcile đúng trước canary production.

### Phase 8 — Multi-channel và sale copilot

Chỉ bắt đầu khi channel contract, lead state và observability đã ổn định.

## 9. Release strategy

Mỗi feature đi qua cùng một chuỗi:

```text
Unit/contract test
-> failure simulation
-> shadow mode
-> dry-run internal
-> canary 5%
-> 20%
-> 50%
-> 100%
-> observation
```

Không tăng canary khi:

- Có duplicate reply/lead chưa giải thích được.
- Queue lag tăng liên tục.
- Dead-letter chưa có owner xử lý.
- Dữ liệu route/knowledge chưa được duyệt.
- Rollback chưa diễn tập.

## 10. Bộ test nghiệm thu xuyên suốt

1. 2–4 tin liên tục tạo một response có đủ context.
2. Meta retry cùng message ID không tạo side effect lặp.
3. Restart worker giữa chừng không mất event/outbox/lead.
4. Hai worker cùng claim chỉ một worker được finalize.
5. Ollama timeout có fallback và không khóa sender.
6. Telegram/Meta timeout hoặc 429 retry đúng, không gửi đôi.
7. Route có địa bàn đúng group; không rõ đi triage.
8. Sale claim thì bot dừng luồng mua hàng liên quan.
9. Ảnh mờ hỏi lại; OCR không khớp không bịa sản phẩm.
10. Không suy ra giá/tồn/hàng thật giả từ ảnh.
11. Memory không lẫn khách, Page hoặc brand.
12. Knowledge chưa approved không xuất hiện trong production answer.
13. CRM write retry không tạo duplicate record.
14. Feature flag off rollback về hành vi cũ mà không mất dữ liệu.
15. Log/test/alert không lộ token hoặc PII ngoài policy.

## 11. KPI và SLO

### Kỹ thuật

- Inbound accepted/enqueued >= 99,9%.
- Duplicate customer reply < 0,1%.
- Duplicate Telegram lead = 0 trong test và canary.
- P95 bundle-to-reply theo mục tiêu 4–10 giây.
- Dead-letter có owner và thời gian xử lý đo được.
- Restore/replay được sau restart hoặc dependency outage.

### Sản phẩm/kinh doanh

- Tỷ lệ commercial intent tạo LeadDraft.
- Tỷ lệ lead route đúng vùng.
- Tỷ lệ sale claim/contact đúng SLA.
- Tỷ lệ lead từ chat chuyển sang cơ hội/đơn hàng khi dữ liệu CRM cho phép.
- Tỷ lệ bot hỏi lại do thiếu thông tin.
- Tỷ lệ fallback/unanswered theo intent.
- Tỷ lệ OCR candidate được khách xác nhận đúng.

Không tối ưu số lượng tin bot gửi; ưu tiên giải quyết đúng nhu cầu và tạo handoff tốt.

## 12. Dữ liệu, bảo mật và quyền riêng tư

- Secret chỉ nằm trong `.env` ignored hoặc secret store.
- File backup/pre-cutover là dữ liệu nhạy cảm, không chỉnh sửa hoặc commit.
- Ảnh gốc có TTL; mặc định đề xuất 24 giờ.
- Telegram chỉ nhận dữ liệu tối thiểu được duyệt.
- PII trong log phải mask; raw payload chỉ lưu có mục đích, TTL và access control.
- Admin/claim/CRM write cần authentication, authorization và audit.
- Không dùng hội thoại khách thật làm dataset nếu chưa ẩn danh và có policy.

## 13. Dependency và blocker

### Cần chủ hệ thống cung cấp/chốt

1. Danh sách group Telegram và vùng phụ trách.
2. Group triage, owner và SLA.
3. Trường dữ liệu được phép gửi Telegram.
4. Retention ảnh và raw webhook.
5. Quy tắc bot khi sale đã claim.
6. Bộ ảnh sản phẩm thật dùng đánh giá OCR.
7. Owner duyệt tri thức nông học, sản phẩm và chính sách.
8. Sandbox hoặc test scope cho AMIS write.
9. Lưu lượng cao điểm dự kiến.
10. Thứ tự CFC trước ZeO hay cần song song.

### Blocker kỹ thuật hiện tại

- n8n-as-code trong repo CFCBot chưa được cấu hình environment/API key để pull và
  đối chiếu workflow live. Không sửa/publish workflow cho tới khi hoàn thành bước này.
- Telegram route thật chưa thể triển khai nếu chưa có mapping vùng/destination.
- OCR chưa thể đặt ngưỡng nghiệm thu nếu chưa có bộ ảnh đại diện.

## 14. Sprint đầu tiên đề xuất

Mục tiêu sprint: khóa baseline và foundation, chưa thay đổi reply production.

1. Chốt 10 quyết định ở mục 13.
2. Định nghĩa versioned schemas cho inbound, bundle, lead và outbox.
3. Bổ sung trace ID và baseline metrics.
4. Viết test failure/idempotency trước implementation worker.
5. Cấu hình n8n-as-code read access và pull snapshot live.
6. Tạo route config mẫu bằng destination key, không điền secret.
7. Chuẩn bị bộ hội thoại và ảnh test đã ẩn PII.
8. Review gate rồi mới phê duyệt Phase 1 implementation.

Deliverable sprint:

- Contract docs + schema tests.
- Baseline report.
- Route matrix bản nháp.
- Evaluation dataset manifest.
- Rollout/rollback checklist.
- Quyết định Go/No-Go cho queue shadow.

## 15. Definition of Done của roadmap

Roadmap chỉ được xem là hoàn thành khi:

- Khách gửi text/ảnh liên tục nhận một phản hồi đúng ngữ cảnh.
- Commercial lead đi đúng sale, có SLA, claim và audit.
- Bot/sale không trả lời chồng nhau.
- OCR có evidence, confidence và không vượt policy.
- Knowledge/memory có source, version, TTL và không lẫn dữ liệu.
- Có metric từ inbound tới reply và từ lead tới kết quả.
- Mọi feature có test, shadow/canary evidence và rollback đã diễn tập.
- CFCBot là source of truth; không còn dependency runtime ngầm vào Javis.

## 16. Ngoài phạm vi trước mắt

- Không đổi model production chỉ để tạo cảm giác “AI hơn”.
- Không bật CRM write trước khi lead/outbox/audit ổn định.
- Không tự động chạy marketing outbound hoặc spam khách.
- Không gửi ảnh/PII vào group Telegram chưa được duyệt.
- Không xây Meta Gateway mới cùng lúc với queue/OCR/Telegram.
- Không xóa rollback artifacts trong observation window.
- Không publish workflow live khi chưa pull/validate bằng n8n-as-code.
