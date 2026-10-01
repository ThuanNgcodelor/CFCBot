# Phase 2 — QueryPlan v2, multi-intent, memory/reference và source challenge

> **Lưu trữ (08/09/2026):** Phase lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Trạng thái: `BLOCKED — LOCAL CORE IMPLEMENTED; chờ shadow/canary evidence`
Ưu tiên: P2 sau nền an toàn/evidence  
Ước lượng: 6–7 ngày  
Phụ thuộc: Phase 0 safety; Phase 1 có `answer_id`, evidence/claim ledger và runtime trace tối thiểu

> Cập nhật 2026-08-29. Đã sửa/test tại local; không push/deploy/activate workflow, không đổi credential, không flush Redis và không gọi CRM live. `DONE` chỉ sau shadow/replay/canary đạt exit metrics bên dưới.

## Kết quả triển khai local

| Work package | Trạng thái local | Thay đổi thực tế |
|---|---|---|
| WP1 QueryPlan v2 | Hoàn thành, backward-compatible | `QueryPlan` giữ mọi field v1 và thêm schema v2, candidate fact-free, primary/secondary IDs, risk, source family, context action và ambiguity. Legacy `intent` vẫn là route authority. |
| WP2 semantic planners | Hoàn thành phần safety | CFC semantic plan chỉ là proposal trace theo intent; không còn ghi đè deterministic intent bằng confidence `0.99`. Conversation shadow dùng API provider-agnostic hiện hành thay vì tên hàm Ollama cũ. |
| WP3 arbitration/multi-intent | Hoàn thành mức an toàn | Candidate primary áp thứ tự privacy/complaint/operational/purchase/advisory. Chỉ primary được execute; secondary chỉ được lưu pointer fact-free trong `pending_requests`, không tự chạy tool nhạy cảm. |
| WP4 GoalFrame/state v5 | Hoàn thành | Lazy migrate schema 4 -> 5, tối đa 5 goal frame; switch pause goal cũ, “quay lại …” resume frame đúng. Chỉ phone/area/location dùng chung; order/crop/product slot được rehydrate từ goal đang active, không rò sang goal khác. |
| WP5 references | Hoàn thành phần local | Giữ product/dealer ordinal hiện hữu, thêm `last_answer_reference` với answer/claim ID từ Phase 1 và chặn tool result đã hết hạn. Resolution vẫn giới hạn trong cùng session/brand/sender. |
| WP6 verify previous claim | Hoàn thành | Source challenge đọc claim ledger Phase 1 trước; verified chỉ nêu loại nguồn an toàn, stale yêu cầu kiểm tra lại, unverified/blocked rút claim và lưu correction link tới answer cũ. Session cũ chưa có ledger dùng safe fallback theo source type để không gãy lịch sử. |
| WP7 RAG ambiguity | Giữ guard hiện hữu | Rerank/margin/intent anchoring sẵn có không bị nới lỏng. Chưa tuyên bố các tỷ lệ exit gate khi chưa replay/live canary. |

### Khắc phục từ test Messenger ngày 2026-08-29

Các lỗi dưới đây được phát hiện khi chạy qua page thật sau knowledge sync, không phải suy đoán từ unit test:

- Mã đơn số thuần như `00005065` được QueryPlan nhận ra nhưng bị mất khi tạo `confirmed_slots`; đã dùng lại `query_entities.order_id` và thêm fallback cho dạng “đơn/mã đơn + số”, nên AMIS warm lookup nhận đủ mã đơn và SĐT trong cùng lượt.
- Source challenge nhận thêm cách nói tự nhiên như “thật ko, lấy từ đâu ra?”; vẫn chỉ trả loại nguồn an toàn từ ledger Phase 1.
- “À ok” được normalize thành `a ok`; nay được nhận là acknowledgement thay vì rơi về FAQ hỗ trợ chung.
- Câu hỏi mức tồn tại như “Có phân bón cho cây sầu riêng không?” trả lời trước ở mức dòng NPK/hữu cơ đã có knowledge; chỉ yêu cầu giai đoạn cây trước khi đi đến công thức/liều lượng. Không tự sinh quy trình hoặc dosage.

### File thay đổi

- `chatbot/server/query_understanding.py`: QueryPlan v2 deterministic/fact-free.
- `chatbot/server/chat_pipeline.py`: GoalFrame v5, pending secondary, answer reference, ledger-driven source challenge và semantic proposal-only.
- `chatbot/server/conversation_orchestrator.py`: shadow dùng planner hiện hành; tool result hết hạn không còn được resolve.
- `chatbot/server/evidence_trace.py`: evaluator claim ledger không retrieval/tool call.
- Tests mới: `chatbot/server/tests/test_phase2_conversation_intelligence.py`; cập nhật regression orchestrator/router theo contract đang chạy.

### Bằng chứng kiểm thử local

| Kiểm tra | Kết quả |
|---|---|
| `py_compile` module Phase 2 | OK |
| `git diff --check` | OK |
| Phase 2 + QueryPlan + orchestrator + grounding/source challenge + AMIS/router/n8n regressions | `110/110 OK` ngày 2026-08-29 |

### Điều kiện còn lại trước `DONE`

1. Shadow replay cho paraphrase/multi-intent và đo agreement/timeout/cache-hit, không dùng agreement để nới protected route.
2. Canary sender bucket xác nhận GoalFrame switch/resume, ordinal/plural reference, answer challenge và không có cross-brand/cross-sender leak.
3. Đo đầy đủ các exit metrics tại mục 8; hiện chưa có bằng chứng live để tuyên bố các tỷ lệ đó.

## 1. Mục tiêu

Giúp chatbot hiểu cùng một ý định qua nhiều cách hỏi, tách được câu ghép, theo đúng tác vụ nhiều lượt, resolve tham chiếu và trả lời phản vấn nguồn — trong khi fact vẫn đến từ tool/FAQ/catalog/protocol chứ không từ planner LLM.

Phase này không bật lại trực tiếp multi-intent cũ cho CFC. Hiện có nhiều lớp semantic chồng nhau và mỗi lớp có contract khác. Cần hợp nhất chúng thành một QueryPlan fact-free duy nhất trước khi tăng quyền cho LLM.

## 2. Bằng chứng hiện trạng

- QueryPlan hiện thiên về một intent; câu ghép chỉ được xử lý một phần.
- CFC semantic planner có thể ghi đè intent bằng confidence cố định cao.
- Conversation orchestrator, CFC semantic planner và LLM NLU cũ có schema/role chồng nhau.
- State giữ 6 recent turns, semantic planner chỉ dùng 2; topic stack chưa phải goal stack hoàn chỉnh.
- Reference product/dealer xử lý một phần; claim/source reference chưa có.
- “Dữ liệu đó có thật không?” chưa map vào answer/claim gần nhất.
- Hot-cache đã chứng minh hai lỗi: company → address; brand overview → slogan.
- Bật một multi-intent detector cũ không giải quyết arbitration, ownership, freshness hoặc evidence.

## 3. Ngoài phạm vi

- LLM planner không được sinh answer hoặc fact.
- Không thêm regex riêng cho từng paraphrase.
- Không reset/flush Redis khi nâng state schema.
- Không cho secondary intent nhạy cảm chạy nếu thiếu quyền/tool.
- Không bật `primary` trước shadow/canary Phase 5.
- Không sửa protected output chỉ để tăng semantic agreement.

## 4. QueryPlan v2 contract

Giữ backward-compatible fields và thêm candidate plan:

```json
{
  "schema_version": 2,
  "intent": "legacy-primary-intent",
  "intent_candidates": [
    {
      "candidate_id": "c1",
      "clause_id": "clause-1",
      "intent": "purchase_request",
      "action": "purchase_intake",
      "source_family": "catalog",
      "entities": {},
      "attributes": {},
      "constraints": {},
      "reference": {},
      "risk": "low",
      "confidence": 0.94,
      "origin": "deterministic|semantic"
    }
  ],
  "primary_candidate_id": "c1",
  "secondary_candidate_ids": [],
  "context_action": "continue|switch|resume|clarify",
  "ambiguities": []
}
```

Planner output không được chứa answer, giá, stock, liều lượng, policy hoặc source ID. Nó chỉ mô tả intent/action/source family và tham chiếu.

## 5. Work packages

### P2-WP1 — Candidate-based query understanding

Việc làm:

1. Nâng `QueryPlan` lên schema v2 nhưng giữ reader/caller v1 trong migration window.
2. Tách clause theo cấu trúc câu và conjunction; không tạo regex theo từng câu test.
3. Mỗi clause sinh 0..n candidate qua ontology/entity/action detectors.
4. Dedupe candidate theo action/source/entity/constraints.
5. Ghi ambiguity khi thiếu slot hoặc hai candidate ngang nhau.
6. LLM semantic chỉ đề xuất candidate khi deterministic thấp confidence/thiếu candidate/có ambiguity.

File dự kiến:

- `chatbot/server/query_understanding.py`
- schema/validator mới hoặc trong `conversation_orchestrator.py`
- `chatbot/server/tests/test_query_understanding.py`

### P2-WP2 — Hợp nhất semantic planners

Việc làm:

1. `cfc_semantic_planner.py` chuyển từ intent override sang proposal-only.
2. Không gán confidence `0.99` chỉ vì LLM trả plan hợp schema.
3. Conversation orchestrator dùng cùng QueryPlan v2 validator.
4. LLM NLU cũ được shadow parity rồi retire hoặc làm adapter, không giữ ba source of decision.
5. Cache theo:

```text
brand + state_revision + normalized_turn + planner_version
```

6. Timeout ngắn; malformed/incompatible plan quay về deterministic/clarification.
7. Theo dõi proposal agreement, accepted/rejected reason, latency và cache hit.

File dự kiến:

- `chatbot/server/cfc_semantic_planner.py`
- `chatbot/server/conversation_orchestrator.py`
- `chatbot/server/ai_engine.py`
- semantic planner tests

### P2-WP3 — Arbitration và multi-intent

Thứ tự bất biến:

```text
privacy/ownership
> complaint/safety
> explicit operational action
> verify_previous_claim
> tool-result follow-up
> clarification
> active goal
> advisory/FAQ
```

Quy tắc:

1. Explicit purchase thắng agronomy advisory khi khách nói muốn mua/đặt/lấy.
2. Chỉ một primary được thực thi trước.
3. Secondary public/read-only chỉ trả trong cùng turn nếu mỗi ý có evidence riêng.
4. Secondary nhạy cảm hoặc thiếu tool được lưu `pending_requests` và trả capability boundary.
5. Không dùng LLM ghép hai FAQ thành claim mới.
6. Protected routes không bị semantic plan ghi đè: privacy, inventory, order, loyalty, complaint, B2B, dealer/purchase flow.

File dự kiến:

- `chatbot/server/dialogue_router.py`
- `chatbot/server/chat_pipeline.py`
- multi-intent/router tests

### P2-WP4 — GoalFrame và state schema v5

Nâng state bằng lazy read-time migration, không flush Redis.

```json
{
  "goal_id": "...",
  "name": "purchase|dealer|agronomy|order|complaint|...",
  "status": "active|paused|completed|abandoned",
  "slots": {},
  "entity_refs": [],
  "result_ids": [],
  "last_answer_id": "...",
  "pending_action": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

Việc làm:

1. Tối đa 5 GoalFrame gần nhất.
2. Profile slots dùng chung như SĐT chính chủ tách khỏi goal-local slots.
3. Topic switch pause goal cũ; “quay lại...” resume đúng GoalFrame.
4. Không copy slot giữa goal nếu không có rule rõ.
5. Session revision tăng khi state thay đổi để semantic cache không dùng context cũ.
6. Backward-compatible reader cho schema 4.

File dự kiến:

- `chatbot/server/chat_pipeline.py`
- `chatbot/server/conversation_store.py`
- `chatbot/server/conversation_orchestrator.py`
- tests state migration/goal resume/isolation

### P2-WP5 — Reference resolver chung

Reference types:

- `last_answer`;
- `claim`;
- `tool_result`;
- `entity`;
- `goal`;
- ordinal/plural reference.

Validation:

1. Cùng brand/sender/session.
2. Result/answer ID tồn tại và chưa hết hạn.
3. Audience/authorization hợp lệ.
4. Một ứng viên đủ confidence; nếu nhiều ứng viên ngang nhau thì hỏi lại.
5. Không chạy lại tool/RAG từ đầu nếu khách đang hỏi về result cụ thể còn hiệu lực.

Ví dụ cần đạt:

- “số 2”, “số 2 và 3”;
- “mấy đại lý đó”;
- “loại phân lúc nãy”;
- “dữ liệu vừa nói”;
- “quay lại đơn hồi nãy”.

### P2-WP6 — `verify_previous_claim`

Luồng:

1. Detect intent family source challenge.
2. Resolve `last_answer_id` hoặc answer/claim được nhắc.
3. Đọc claim ledger từ Phase 1, không chạy RAG lại từ đầu.
4. Trả theo `verified`, `unverified`, `stale`, `realtime_required`.
5. Claim không fact: xin lỗi, rút lại, tạo correction revision liên kết answer cũ.
6. Source có thể public: nêu loại nguồn/version/last verified; không lộ internal path/PII.
7. Claim tool hết hạn: nói cần kiểm tra lại và chỉ gọi tool nếu quyền cho phép.

File dự kiến:

- `chatbot/server/query_understanding.py`
- `chatbot/server/chat_pipeline.py`
- evidence/claim module Phase 1
- `chatbot/server/grounding_policy.py`
- tests source challenge/correction

### P2-WP7 — RAG rerank và ambiguity gate

Việc làm:

1. Rerank bằng intent prior, entity overlap và negative evidence.
2. Category/source/risk compatibility ảnh hưởng score.
3. Top-1/top-2 margin thấp hoặc candidate khác intent family thì clarify.
4. Direct exact intent match có thể thắng broad lexical similarity nếu evidence đủ.
5. Log explanation feature, không log raw customer data.

Golden regressions:

- company overview không thành address;
- brand overview không thành slogan;
- complaint không thành storage FAQ;
- product-fit không thành dosage protocol.

File dự kiến:

- `chatbot/server/rag_search.py`
- RAG/query tests và real-pipeline debug

## 6. Test families bắt buộc

### Query/arbitration

- product + price + stock;
- dealer + phone + delivery;
- agronomy + purchase;
- order + loyalty;
- complaint + contact;
- explicit new action trong active goal;
- missing slot và equal-confidence ambiguity.

### Follow-up/reference

- ordinal/plural/ellipsis;
- entity nickname/typo;
- topic switch → nested topic → resume;
- expired result/answer;
- wrong brand/sender/result ID;
- correction sau source challenge.

### Robustness

- planner timeout/malformed/incompatible tool;
- deterministic low confidence;
- prompt injection;
- Redis/cache unavailable;
- provider failure;
- tiếng Việt không dấu, typo, tiếng địa phương.

Files test dự kiến:

- `tests/test_query_understanding.py`
- `tests/test_dialogue_router.py`
- `tests/test_conversation_orchestrator.py`
- test mới state migration/source challenge/multi-intent
- `eval_conversation_replays.jsonl`

## 7. Entry gate

- Phase 0 safety guards đã bật.
- Phase 1 có `answer_id`, claim ledger và runtime/provider trace.
- Baseline/replay được đóng băng; feature flags mặc định off.
- Protected routes và Redis schema migration có rollback.

## 8. Exit gate

| Chỉ số | Gate |
|---|---:|
| Unsupported critical claim | 0 |
| Protected-route regression | 0 |
| Intent family accuracy | ≥ 90% |
| High-risk family correctness | 100% |
| Correct source/tool family | ≥ 95% |
| Multi-intent set F1 | ≥ 93% |
| Bỏ sót high-risk secondary intent | 0 |
| Reference accuracy | ≥ 95% |
| Cross-sender/cross-brand leak | 0 |
| Source challenge gold set | 100% |
| Missing-slot clarification | ≥ 95% |
| Unnecessary clarification | ≤ 5% |

Deterministic route p95 không tăng quá 10%. Semantic timeout luôn fallback an toàn.

## 9. Rollout và rollback

Rollout:

1. QueryPlan v2 dual-run/shadow;
2. compare candidate/route với v1;
3. enable theo capability: clarification/reference/source challenge trước;
4. topic switch sau;
5. multi-intent cuối;
6. canary theo stable sender bucket ở Phase 5.

Rollback:

- `CHAT_QUERYPLAN_V2_MODE=off` hoặc feature flag tương đương;
- schema 5 reader vẫn đọc schema 4;
- không xóa GoalFrame/session;
- tắt semantic assist không được tắt claim safety hoặc bật lại free generation;
- deterministic protected routes luôn còn.

## 10. Checklist nghiệm thu

- [x] QueryPlan v2 + validator backward-compatible.
- [x] Semantic planners proposal-only.
- [x] Arbitration priority được test.
- [ ] Multi-intent không bỏ high-risk intent.
- [x] State schema 5 lazy migration, không reset Redis.
- [x] GoalFrame switch/resume hoạt động.
- [x] Reference cùng sender/brand/freshness.
- [x] Source challenge dùng ledger và rút lại claim sai.
- [ ] Bốn RAG ranking regressions được sửa.
- [ ] Toàn bộ exit metrics đạt trước canary.
