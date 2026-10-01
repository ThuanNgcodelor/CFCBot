# Kế hoạch nâng cấp Conversation Intelligence đa luồng cho CFC/ZeO

> **Lưu trữ (08/09/2026):** Roadmap lịch sử. Hiện trạng và backlog hiện hành xem [plan/README.md](../../README.md).

**Ngày cập nhật:** 27/08/2026  
**Phạm vi:** `chatbot/server`, bộ replay và regression tests  
**Mục tiêu:** hiểu hội thoại nhiều lượt, giữ đúng output đã grounded, không để Ollama tự bịa dữ liệu nghiệp vụ.

## 1. Hiện trạng cần giữ nguyên

Luồng hiện tại là:

```text
Messenger -> n8n transport -> chat_pipeline.py -> QueryPlan/routing
-> Redis/CRM/FAQ/catalog -> formatter -> lưu session -> Messenger
```

- n8n chỉ nhận tin nhắn, gọi `/api/chat-pipeline` và gửi `answer`; không xử lý memory.
- Redis giữ `recent_turns`, `active_goal`, `confirmed_slots`, `last_products_shown`, `last_tool_results` và trace.
- `query_understanding.py` và `dialogue_router.py` vẫn là lớp route chính.
- Ollama planner hiện chỉ chạy theo gate `assist`; Ollama agronomy là bộ sinh nội dung riêng, không phải conversation owner.
- Các nguồn nghiệp vụ vẫn là authority: Redis projection, AMIS, catalog, FAQ và tool contract.

## 2. Vấn đề cần giải quyết

1. Câu có cây trồng và câu có ý định mua hàng bị gom vào agronomy.
2. Câu ngắn như “là sao?”, “chưa hiểu” chưa bám vào câu trả lời trước.
3. Reference như “các chỗ đó”, “số của họ”, “loại lúc nãy” chưa có resolver dùng chung cho mọi domain.
4. Tool chỉ được gọi sau khi route đã chọn; chọn sai route thì tool đúng không có cơ hội chạy.
5. Topic switch và quay lại topic cũ chưa có policy thống nhất.
6. FAQ/RAG có thể nhận câu follow-up thành câu hỏi mới và trả nội dung gần nghĩa nhưng sai tác vụ.
7. Output agronomy có thể bị cắt vì generator nhận context hiện tại nhưng không có contract hoàn tất câu trả lời.

## 3. Nguyên tắc bất biến

- Không flush hoặc bulk rewrite Redis khi rollout.
- Không thay output của protected route đang đúng nếu không có regression golden chứng minh.
- Không cho Ollama tự tạo giá, số điện thoại, tồn kho, trạng thái đơn, chiết khấu, liều lượng hoặc chính sách.
- Tool/nguồn vẫn là nơi cung cấp fact; Ollama chỉ phân loại, resolve ngữ cảnh và diễn đạt dữ liệu đã được kiểm chứng.
- Privacy, ownership, handoff và capability boundary luôn có quyền cao hơn LLM.
- Ollama timeout, lỗi JSON, Redis lỗi hoặc model không chạy thì route cũ vẫn hoạt động.
- Không sửa hoặc deploy workflow n8n trong các phase đầu; n8n chỉ cần nhận `answer` như hiện tại.

## 4. Contract quyết định hội thoại

Mỗi lượt cần được mô tả bởi một quyết định thống nhất:

```json
{
  "active_goal": "product_purchase",
  "intent": "purchase_request",
  "topic": "cfc_fertilizer",
  "is_followup": true,
  "topic_changed": false,
  "reference": {"type": "last_turn", "result_id": ""},
  "extracted_slots": {"crop": "sầu riêng", "quantity": "200 kg"},
  "missing_slots": ["product", "phone", "area"],
  "next_action": "purchase_intake",
  "confidence": 0.0,
  "reason_code": ""
}
```

`next_action` mới là thứ quyết định route. `intent` của một lượt không được tự động ghi đè `active_goal` nếu đó chỉ là câu bổ sung slot hoặc câu clarification.

## 5. Phase triển khai

### Phase 0: Baseline, trace và replay

**Trạng thái:** hoàn thành phần tài liệu và replay contract trong lượt này.

- Tạo tài liệu phase này làm source of truth cho rollout mới.
- Bổ sung replay hai hội thoại CFC: tư vấn sầu riêng -> mua 200kg -> giải thích; đại lý -> xin SĐT -> giao hàng.
- Mỗi replay kiểm tra intent, answer invariant, source, active goal, confirmed slots và route trace.
- Không thay output production ở phase này ngoài các case đã được chỉ rõ trong phase sau.

**Gate:** test hiện tại xanh; replay mới chỉ fail khi behavior chưa triển khai, không được che bằng đổi expected.

### Phase 1: Explicit action arbitration

**Trạng thái:** hoàn thành bản đầu tiên trong lượt này.

- Nhận diện action rõ ràng `mua/đặt/lấy` kèm khối lượng.
- Ưu tiên B2B và dealer lookup trước purchase intake để không phá luồng 30 tấn hoặc tìm đại lý.
- Với 200kg, chuyển sang `purchase_intake`, giữ crop/quantity và hỏi các slot còn thiếu.
- Agronomy thuần túy vẫn dùng output hiện tại.

**Gate:** “Có phân bón cho sầu riêng không?” vẫn là agronomy; “Tôi muốn mua 200kg...” là purchase intake; B2B 30 tấn và dealer lookup không đổi.

Đã triển khai:

- `cfc_purchase_request` trong QueryPlan với ưu tiên sau dealer và B2B.
- `purchase_intake` route và formatter không bịa giá/tồn kho.
- Lưu `quantity`, `crop` và các slot còn thiếu vào conversation state.
- Regression tests cho 200kg, 30 tấn và dealer query.

### Phase 2: Clarification và active goal

**Trạng thái:** hoàn thành bản đầu tiên trong lượt này.

- Khi khách nói “là sao”, “chưa hiểu”, “ý gì vậy”, route vào clarification dựa trên `last_bot_reply` và `active_goal`.
- Câu trả lời phải giải thích hoặc hỏi đúng phần còn thiếu, không rơi sang FAQ shipping/buy-online.
- Giữ goal đang mở, không xóa crop/quantity/phone/area đã xác nhận.

**Gate:** clarification accuracy >= 95%, không tạo fact mới, không đổi protected output.

Đã triển khai bản deterministic an toàn cho CFC: các cụm “là sao”, “chưa hiểu”, “ý là sao” khi có active goal sẽ dùng slot đã lưu, ghi trace `ACTIVE_GOAL_CLARIFICATION` và giữ nguyên goal cũ.

### Phase 3: Shared reference resolver

**Trạng thái:** đang triển khai bản đầu; dealer public-phone đã resolve được số thứ tự và nhiều lựa chọn từ kết quả lượt trước, các domain còn lại vẫn pending.

- Dùng chung `last_tool_results` cho product, dealer, inventory, order, loyalty và FAQ reference.
- Resolve ordinal, đại từ và mô tả: “số 2”, “các chỗ đó”, “phân vừa nói”.
- Nếu có nhiều ứng viên mà không đủ chắc, hỏi lại thay vì chọn ngẫu nhiên.

Đã triển khai bản đầu cho dealer public-phone:

- “Xin số đại lý số 2” chọn đúng item thứ 2 trong `last_tool_results`.
- “Xin số đại lý số 2 và 3” chọn đúng hai item được yêu cầu.
- Item không có `public_phone` được báo là chưa có SĐT công khai; không suy đoán, không lấy hotline công ty và không chạy lại tìm đại lý.
- Route follow-up được ưu tiên trước nhánh `ORDINAL_WITHOUT_OPTIONS`, nên câu hỏi số thứ tự không bị biến thành yêu cầu hỏi lại sản phẩm.

**Gate:** reference accuracy >= 95%; cross-sender và cross-brand isolation bằng 0.

### Phase 4: Ollama arbitration có kiểm soát

**Trạng thái:** đã triển khai bản đầu trong lượt này; còn mở rộng capability.

- Gửi Ollama conversation envelope gồm summary, recent turns, active goal, slots, tool results và deterministic plan.
- Ollama chỉ trả JSON decision; không trả fact cho khách.
- Ollama chỉ được can thiệp khi confidence, reference và tool nằm trong allowlist.
- Explicit deterministic route có priority; Ollama dùng để giải quyết ambiguity, follow-up và topic switch.

Đã triển khai bản đầu:

- Assist gọi semantic planner cho mọi turn sau khi session đã có context, không còn gate bằng danh sách từ khóa follow-up.
- Planner có `next_action` và `topic`, cho phép biểu diễn hành động thay vì chỉ đoán intent.
- Cách nói mới như “chốt giúp em 200kg phân nuôi trái sầu riêng” có thể được Ollama chuyển sang `purchase_intake` dù QueryPlan ban đầu nhận diện cây trồng.
- Follow-up dealer có `next_action=dealer_contact_lookup` để nối quyết định ngữ nghĩa vào kết quả đại lý đã lưu, nhưng dữ liệu số điện thoại vẫn do formatter grounded đọc từ tool result.
- Route nhạy cảm gồm privacy, inventory, order, loyalty, B2B, complaint và dealer vẫn được bảo vệ khi không có topic switch rõ ràng.
- Trace ghi `next_action` và `route_changed` để biết Ollama có thật sự thay đổi route hay chỉ được gọi.

**Gate:** timeout không làm tăng latency protected route; malformed plan không ảnh hưởng answer; shadow agreement được đo theo từng capability. Bản đầu đã có unit/integration test cho semantic purchase override và protected inventory route.

### Phase 5: Tool evidence và freshness

**Trạng thái:** kế tiếp.

- Chuẩn hóa tool result: `result_id`, `tool`, `source_id`, `match_scope`, `created_at`, `expires_at`, `items`.
- Public dealer/product có TTL phù hợp; stock/order/loyalty/price phải refresh hoặc dùng capability boundary.
- Formatter chỉ nhận các field được phép công khai.

**Gate:** 100% fact động có source/freshness; không trả dữ liệu riêng tư khi chưa ownership.

### Phase 6: Topic switch, handoff và expert flows

**Trạng thái:** kế tiếp.

- Đổi giữa dealer, purchase, agronomy, order, loyalty, complaint và B2B mà không làm lẫn slot.
- Topic ngoài phạm vi được trả lời an toàn nhưng goal cũ vẫn có thể resume.
- Agronomy/B2B/complaint dùng Ollama để tóm tắt tình huống và slot, không tự cam kết chính sách hoặc kỹ thuật ngoài nguồn.

**Gate:** replay multi-flow đạt task completion >= 95%, safety 100%.

## 6. Thứ tự ưu tiên quyết định

```text
privacy/ownership
> explicit action mới
> follow-up của tool result
> clarification của câu trả lời trước
> topic switch rõ ràng
> active goal bổ sung slot
> deterministic domain route
> FAQ/RAG
> grounded fallback
```

Các ngoại lệ phải ghi `reason_code` trong trace, không âm thầm rẽ nhánh.

## 7. Bộ test bắt buộc

### Hội thoại A: agronomy -> purchase -> clarification

1. `Có phân bón cho cây sầu riêng không?`
2. `Tôi muốn mua 200kg phân bón trồng sầu riêng`
3. `Là sao? Chưa hiểu`
4. `Tôi cần loại để nuôi trái, giao Kiên Giang`
5. `Số điện thoại 09xxxxxxxx`

Kỳ vọng: lượt 1 tư vấn; lượt 2 purchase intake; lượt 3 clarification đúng câu trước; lượt 4 giữ quantity/crop và bổ sung stage/area; lượt 5 giữ toàn bộ goal.

### Hội thoại B: dealer -> contact -> delivery -> topic switch

1. `Khu vực xã Định Môn, Thới Lai có đại lý nào không?`
2. `Cho xin số điện thoại các chỗ đó`
3. `Họ có giao tận nhà không?`
4. `Tôi muốn mua 30 tấn NPK`
5. `Quay lại mấy đại lý lúc nãy`

Kỳ vọng: lượt 2 lấy đúng phone từ tool result; lượt 3 không suy diễn delivery; lượt 4 B2B; lượt 5 resume dealer context.

### Nhiễu và paraphrase

- `vậy còn số mấy chỗ hồi nãy?`
- `mấy đại lý trên cho xin liên hệ`
- `phân lúc nãy lấy 200 ký được không`
- `ý bên bạn là sao vậy`
- `thôi bỏ qua, hỏi chuyện đơn hàng`
- `hỏi vu vơ ngoài phạm vi rồi quay lại mục tiêu cũ`

## 8. Rollout và rollback

```text
CHAT_CONVERSATION_MODE=off|shadow|assist|primary
CHAT_CONVERSATION_MIN_CONFIDENCE=0.85
CHAT_CONVERSATION_HISTORY_LIMIT=6
CHAT_CONVERSATION_TIMEOUT_SECONDS=6
```

- `off`: behavior hiện tại.
- `shadow`: đo decision, không ảnh hưởng output.
- `assist`: chỉ can thiệp ở flow đã có test và tool contract.
- `primary`: chỉ xem xét sau khi shadow/assist đủ dữ liệu; không tự bật.

Rollback là chuyển `mode=off`, không xóa Redis.

## 9. Files và phạm vi dự kiến

- `chatbot/server/query_understanding.py`: intent/constraint có thứ tự ưu tiên rõ, không mở rộng keyword vô hạn.
- `chatbot/server/conversation_orchestrator.py`: decision contract, context, reference và topic policy.
- `chatbot/server/dialogue_router.py`: chuyển decision thành route/tool allowlist.
- `chatbot/server/chat_pipeline.py`: hook quyết định trước route, giữ formatter và guard hiện tại.
- `chatbot/server/conversation_replay_eval.py` và `eval_conversation_replays.jsonl`: chấm multi-turn.
- `chatbot/server/tests/`: regression, isolation, timeout, malformed planner và multi-flow.
- `workflows/local-n8n/cfc_cobay_chatbot.workflow.ts`: không sửa trong các phase đầu.

## 10. Definition of Done

- Bot phân biệt được tư vấn, mua hàng, đại lý, giao hàng, B2B, đơn hàng, hội viên, khiếu nại và clarification.
- Câu follow-up dùng đúng entity/tool result của cùng sender.
- Topic switch không làm lẫn slot và có thể quay lại goal cũ.
- Output grounded hiện tại không bị thay đổi ngoài golden cases đã duyệt.
- Ollama lỗi không làm mất câu trả lời hoặc làm tăng latency protected route.
- Không có unsupported/private claim.
- Regression và replay đạt toàn bộ gate trước khi bật `primary`.
