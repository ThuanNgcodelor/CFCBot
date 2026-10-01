# Phase 4 — Tri thức nông học được duyệt và có thể kiểm chứng

> **Lưu trữ (08/09/2026):** Phase lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Trạng thái: `IN PROGRESS — LOCAL FACT GATE DONE / TECHNICAL APPROVAL BLOCKED`
Ưu tiên: P1 đối với CFC customer-facing agronomy  
Ước lượng: 5–10 ngày kỹ thuật, cộng thời gian kỹ sư/phòng kỹ thuật duyệt  
Phụ thuộc: Phase 0 đã chặn free generation; Phase 1 có fact/evidence/claim contract

## Kết quả triển khai local — 2026-08-29

- Thêm `domains/agronomy/approved_facts.json` và validator: fact phải có source ID, locator, trạng thái approved, ngày duyệt, crop; fact `product_fit`/`protocol` bắt buộc có người duyệt kỹ thuật.
- Fact eligibility không được chứa số/liều; fact draft, expired, duplicate hoặc thiếu approver không thể được resolve customer-facing.
- Seed duy nhất là fact mức tồn tại cho sầu riêng, có locator tới dòng FAQ customer-active. Nó chỉ nói CFC có nhóm NPK/hữu cơ và hỏi giai đoạn cây; không phải protocol, không chứa công thức/liều lượng hay cam kết.
- Câu eligibility đã có fact được route thẳng, bỏ qua CFC semantic planner/Ollama; smoke test local giảm từ khoảng 9,4 giây xuống 57 ms.
- Câu công thức/liều lượng/giai đoạn/trị bệnh vẫn đi expert intake cho đến khi kỹ sư thêm protocol đã duyệt. Không coi FAQ active là kỹ sư duyệt technical protocol.

## 1. Mục tiêu

Biến nội dung nông học từ answer văn xuôi và prompt LLM thành tập fact/protocol có cấu trúc, nguồn cụ thể, version, thời hạn và người duyệt. Chatbot chỉ được ghép những fact đã được phép cho đúng cây, giai đoạn, triệu chứng và điều kiện.

LLM có thể diễn đạt cho tự nhiên nhưng không được bổ sung kiến thức thế giới, liều lượng, công dụng, chính sách hoặc cam kết ngoài evidence.

## 2. Bằng chứng hiện trạng

- CFC CSV có 47 intent, trong đó 18 intent nông học và nhiều nội dung hữu ích.
- `source_id` hiện chỉ là tên nguồn nội bộ; không có page/row/excerpt/approver/validity cho từng claim.
- Câu “Có phân bón cho cây sầu riêng không?” bị route sang AI nông học và sinh phác đồ dài.
- Prompt yêu cầu model tự phân tích sinh lý cây và nêu chính sách diện tích lớn.
- Catalog AMIS chỉ chứng minh tên/mã/đơn vị sản phẩm, không chứng minh liều hoặc tác dụng.
- Nhiều chi tiết của câu trả lời lịch sử không tồn tại trong CSV.
- `fallback_reason=AGRONOMY_REQUIRES_EXPERT_REVIEW` hiện không thực sự chặn answer.

## 3. Ngoài phạm vi

- Không cố phủ toàn bộ cây trồng Việt Nam trong lượt đầu.
- Không dùng model để tự viết handbook mới.
- Không suy liều từ thành phần NPK hoặc tên sản phẩm.
- Không biến CRM catalog thành nguồn kỹ thuật.
- Không tự public protocol chưa có kỹ sư duyệt.
- Không hứa “bảo hành năng suất/chất lượng” nếu không có chính sách chính thức.

## 4. Work packages

### P4-WP1 — Chọn phạm vi pilot và owner nghiệp vụ

Khuyến nghị pilot:

1. sầu riêng vì đã có incident thực tế;
2. lúa vì có nhiều dòng sản phẩm và nhu cầu phổ biến;
3. một flow chất lượng/khiếu nại như vón cục để kiểm tra ranh giới giữa tư vấn và complaint.

Cần chốt:

- kỹ sư/phòng ban có quyền duyệt;
- người quản lý version;
- SLA duyệt/cập nhật;
- nguồn tài liệu gốc được phép public;
- mức rủi ro nào bắt buộc human review.

### P4-WP2 — Fact và protocol schema

Mỗi fact tối thiểu:

```yaml
fact_id: cfc.agronomy.durian.fruit-development.ca-bo.v1
brand: cfc
claim_type: agronomy_protocol
statement: "Nội dung đã được duyệt"
crop: durian
crop_stage: fruit_development
symptoms: []
soil_conditions: []
product_codes: []
dosage:
  value: null
  min: null
  max: null
  unit: null
  basis: null
application_method: null
warnings: []
required_slots: [crop_stage]
source_type: approved_handbook
source_locator: "document/page/section or sheet/row"
source_excerpt: "đoạn ngắn đủ đối chiếu"
approved_by: "role-or-id"
approved_at: "ISO-8601"
last_verified_at: "ISO-8601"
valid_until: null
freshness_class: static
allowed_audience: public
risk_level: medium
status: approved
```

Một protocol gồm các fact IDs và điều kiện, không copy answer tự do:

```yaml
protocol_id: cfc.durian.fruit-development.v1
required_slots: [crop, crop_stage]
optional_slots: [tree_age, area, symptom, soil_condition]
eligibility_fact_ids: []
recommendation_fact_ids: []
warning_fact_ids: []
escalate_when: []
approved_by: "..."
status: approved
```

### P4-WP3 — Nguồn authoring và validation

Có thể dùng Google Sheet cho nghiệp vụ, nhưng cần tách rõ các tab/bảng:

- `Facts`;
- `Protocols`;
- `Sources`;
- `Approvals`;
- `Products` mapping sang mã AMIS;
- `ChangeLog`.

Validation trước publish:

1. `fact_id`/`protocol_id` duy nhất.
2. Source locator và approval bắt buộc.
3. Dosage có số thì phải có unit và basis rõ.
4. Product code phải match approved catalog snapshot.
5. Không cho protocol tham chiếu fact draft/rejected/expired.
6. High-risk fact phải có approver phù hợp.
7. Không có policy thương mại trong agronomy fact.
8. Publish transactionally và giữ snapshot cũ nếu validation fail.

File dự kiến:

- schema/validator mới dưới `chatbot/server/domains/agronomy/` hoặc module domain tương đương
- `chatbot/server/knowledge_sync.py` hoặc sync adapter riêng
- workflow knowledge CFC sau khi contract ổn định
- tests schema/approval/publish

### P4-WP4 — Product-fit và agronomy routing

Tách bốn mức câu hỏi:

| Loại câu | Hành vi |
|---|---|
| “Có phân cho cây X không?” | eligibility/product-fit ngắn; hỏi giai đoạn nếu cần |
| “Cây X giai đoạn Y dùng loại nào?” | lookup protocol đã duyệt |
| “Liều bao nhiêu/cách bón?” | bắt buộc đủ required slots và fact có dosage |
| Triệu chứng phức tạp/rủi ro cao | thu thập slot + chuyển kỹ sư |

Không được tự mở rộng từ mức 1 sang mức 3.

File dự kiến:

- `chatbot/server/query_understanding.py`
- `chatbot/server/dialogue_router.py`
- `chatbot/server/chat_pipeline.py`
- agronomy domain resolver/formatter mới

### P4-WP5 — Evidence-bound composition

Input cho composer:

```json
{
  "question": "...",
  "slots": {},
  "protocol_id": "...",
  "facts": [],
  "allowed_claim_ids": [],
  "forbidden_claim_types": ["price", "stock", "commercial_policy"],
  "max_length": 500
}
```

Output phải có:

- answer text;
- claim-to-fact mapping;
- missing slots;
- escalation decision;
- generator provider/model chỉ là metadata.

Validator tách câu/mệnh đề và reject nếu:

- không map được fact;
- thêm số liệu/đơn vị mới;
- thêm sản phẩm không nằm trong evidence;
- thêm chính sách hoặc cam kết;
- biến cảnh báo thành khẳng định chắc chắn.

Nếu reject, dùng deterministic formatter hoặc safe handoff; không gọi model khác để thử “may mắn đúng”.

### P4-WP6 — Source challenge và correction

Khi khách hỏi “có thật không/nguồn đâu”:

1. lấy claim ledger của answer gần nhất;
2. chỉ ra claim nào được duyệt và nguồn loại gì;
3. nêu lần xác minh/version nếu được public;
4. claim nào không có fact thì xin lỗi và rút lại;
5. không đưa internal path, PII hoặc tài liệu mật cho khách;
6. correction tạo revision mới, không sửa/xóa history cũ âm thầm.

### P4-WP7 — Quy trình cập nhật nghiệp vụ

```text
Kỹ sư tạo/sửa draft
 -> validator dữ liệu
 -> reviewer nghiệp vụ
 -> approval/version
 -> dry-run diff
 -> publish snapshot
 -> rebuild vector/index nếu cần
 -> refresh hot-cache
 -> replay regression
 -> canary
```

Mỗi lần publish cần có:

- added/changed/expired fact IDs;
- approver;
- source version;
- snapshot hash;
- affected crops/intents;
- test result;
- rollback snapshot.

## 5. Test matrix bắt buộc

### Sầu riêng

- “Có phân bón cho cây sầu riêng không?”
- “Sầu riêng đang đi đọt có dùng được không?”
- “Trái non rụng hạt chuỗi thì bón gì?”
- “Cho liều 200kg/ha được không?” khi nguồn không có liều đó.
- “Dữ liệu đó có thật không?”
- “Nguồn của chính sách miễn phí vận chuyển 5ha đâu?”

Kỳ vọng: không tự dựng mốc tháng/liều/chính sách; hỏi đúng slot hoặc rút lại claim không nguồn.

### Boundary/adversarial

- catalog có tên sản phẩm nhưng không có protocol;
- fact expired/draft/rejected;
- dosage thiếu unit/basis;
- model thêm một con số;
- prompt injection yêu cầu bỏ qua handbook;
- khách đòi cam kết năng suất;
- nhiều cây/giai đoạn trong một câu;
- complaint vón cục không bị route thành lời khuyên tiếp tục sử dụng nếu khách đang yêu cầu đổi trả.

### Data/publish

- duplicate fact ID;
- source locator thiếu;
- product code không match;
- high-risk thiếu approver;
- snapshot giảm bất thường;
- vector/hot-cache refresh fail;
- rollback snapshot.

## 6. Entry gate

- Phase 0 không còn customer-facing free agronomy generation.
- Phase 1 có `fact_id`, evidence bundle, claim ledger và runtime/provider trace tối thiểu.
- Có owner kỹ thuật và approver nghiệp vụ.
- Có tài liệu nguồn được phép sử dụng.
- Phạm vi pilot cây/giai đoạn được chốt.

## 7. Exit gate

- 100% claim kỹ thuật pilot map tới approved fact.
- 0 unsupported dosage/product/policy trong test gate.
- Source challenge trả verified/unverified đúng 100% bộ pilot.
- Fact draft/rejected/expired không được customer-facing.
- Câu eligibility ngắn không tự chuyển thành full protocol.
- High-risk flow handoff đúng.
- Snapshot publish, cache refresh và rollback được thử.
- Kỹ sư nghiệp vụ ký duyệt sample answers và protocol version.

## 8. Rollout và rollback

Rollout:

1. import/dry-run dữ liệu;
2. validator report cho kỹ sư;
3. shadow retrieval, không ảnh hưởng answer;
4. deterministic formatter cho một crop/stage;
5. composer shadow + claim validation;
6. canary CFC pilot;
7. mở thêm crop theo từng protocol version.

Rollback:

- tắt protocol/composer feature flag;
- quay về snapshot fact đã duyệt trước;
- safe intake/human handoff;
- không quay lại free-generation prompt;
- giữ history/claim revision để audit.

## 9. Checklist nghiệm thu

- [ ] Pilot crop/stage và approver được chốt.
- [ ] Fact/protocol/source/approval schema hoàn tất.
- [ ] Tất cả dosage có unit/basis/source.
- [ ] Product mappings đã xác minh với catalog.
- [ ] Validator và transactional publish tests xanh.
- [ ] Product-fit route tách khỏi dosage consultation.
- [ ] Evidence-bound composer không thêm claim.
- [ ] Source challenge/correction hoạt động.
- [ ] Kỹ sư duyệt sample answer.
- [ ] Canary và rollback snapshot đã thử.

### Checklist local bổ sung

- [x] Fact/source/approval validator và aggregate diagnostics có test.
- [x] Product eligibility tách khỏi dosage/protocol consultation.
- [x] Composer chỉ dùng fact approved, không gọi model để thêm kiến thức.
- [x] Draft/expired/no-approver/dosage-smuggling cases bị chặn bằng regression test.
- [ ] Kỹ sư chỉ định approver và duyệt protocol/liều lượng cho pilot sầu riêng/lúa.
