# Kế hoạch nâng cấp chatbot hiểu ngữ cảnh và kiểm soát như hệ thống nghiệp vụ

Ngày lập: 2026-08-25  
Phạm vi: `chatbot/server/`, bridge Javis OS, hai workflow Messenger ZeO/CFC và Dashboard Reports.

## Quyết định đã chốt

- Hạng mục 1 về bí mật trong file cấu hình tạm thời không xử lý theo quyết định của chủ hệ thống. Kế hoạch này không sửa, xoá hoặc luân chuyển secret.
- Hạng mục 6 được triển khai ngay ở chế độ `shadow`. Ollama chỉ dự đoán trong task nền, không chọn route, không sửa câu trả lời và không cộng thời gian chờ model vào request của khách.
- Chưa bật `assist`. Model chỉ được phép đề xuất intent/tool, không được tự tạo giá, link, chính sách, tồn kho, công dụng hoặc liều lượng.
- Không có cơ chế tự học rồi tự đưa lên production. Mọi intent muốn chuyển từ `shadow` sang `assist` phải có dữ liệu đánh giá, chủ hệ thống duyệt và rollout canary riêng.
- ZeO và CFC dùng chung hạ tầng nhưng giữ policy, dữ liệu và bộ test riêng. CFC không tự deploy từ kế hoạch này.
- Nhánh Web tạm hoãn đào sâu. Chatbot chỉ dùng khi khách hỏi trực tiếp; chưa hợp nhất ranking Web/Shopee và chưa chủ động đề xuất Web.

## Trạng thái triển khai local 2026-08-25

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Gold multi-turn replay | Đã triển khai | `conversation_replay_eval.py`, 11 cuộc/19 lượt live đạt 100%, source coverage 100% |
| Idempotency Messenger | Đã triển khai local | Redis lease + response cache; smoke cùng MID trả `processed` rồi `duplicate=true/cached` |
| Conversation store | Đã triển khai local | Lưu Redis trước khi trả API, history TTL/limit, revision, sender lease, cache TTL/LRU |
| ConversationState v2 | Đã triển khai | pending action/question/slots/options, topic stack, corrections, takeover state |
| QueryPlan/router | Đã triển khai bước đầu | quantity, budget, channel, location, phủ định/sửa ý; router xử lý correction, unresolved ordinal, dealer và pending link |
| Lịch sử cho AI | Đã triển khai có giới hạn | Tối đa 6 turn, che phone/email, chỉ dùng khi đã có facts/catalog |
| Grounding policy | Audit | Trace `grounded/safe_fallback/missing_source`; chưa bật enforce production |
| Human handoff | Đã triển khai local | `pending`, `suppress_send`, API list/resolve; workflow local đã chặn gửi khi takeover |
| API chatbot | Localhost-only | Bỏ `/api/chat-pipeline` khỏi public auth paths; n8n local vẫn gọi `127.0.0.1` |
| Javis Reports governance | Chưa triển khai | Chờ đủ observation và phase API/UI có audit trước khi cho phép gắn nhãn hoặc duyệt intent |
| NLU assist | Chưa bật | Vẫn `shadow`; cần report, nhãn người duyệt và canary riêng |
| Web catalog nâng cao | Tạm hoãn | Theo quyết định chủ hệ thống |

Kiểm thử local hiện tại: 66/66 unit chatbot, 3/3 bridge runtime, security suite đạt, hai workflow đạt `n8nac skills validate`. Chưa push/deploy hai workflow Messenger.

## Hiện trạng ban đầu đã đối chiếu

1. `server/main.py` từng miễn đăng nhập cho `/api/chat-pipeline`; n8n gọi qua localhost nhưng endpoint cũng nằm trong nhóm public của Javis.
2. Hai workflow `zeo_chatbot.workflow.ts` và `cfc_cobay_chatbot.workflow.ts` đã lấy `messaging.message.mid` và gửi `message_id`, nhưng trước phase này `ChatPipelineRequest.message_id` chưa được dùng để chống xử lý lặp.
3. `chat_pipeline.py` ban đầu chỉ có lock theo sender và cache trong RAM; việc lưu session Redis chạy nền nên chưa nhất quán giữa nhiều worker hoặc khi process dừng.
4. `QueryPlan.constraints` ban đầu luôn là `{}` và chưa tham gia điều phối các route quan trọng.
5. `conversation_state.recent_turns` đã được lưu, nhưng các nhánh gọi AI trước đây chưa truyền lịch sử thật một cách nhất quán.
6. Workflow kiến thức đã ghi `zeo:web:catalog:active`; chatbot hiện chỉ tải Shopee catalog, nên nhánh Web chưa trở thành nguồn truy xuất thực tế.
7. Javis đã có `ai_reporter.py`, `/admin/reports/*` và trang Reports. Có thể mở rộng đúng chỗ này để chủ hệ thống duyệt, không cần dựng thêm một dashboard độc lập.

## Ánh xạ hạng mục 2-12 vào code

| # | Vấn đề cần xử lý | File hiện tại cần chạm | Thay đổi dự kiến | Phase |
|---|---|---|---|---|
| 2 | API chatbot chưa có xác thực service và rate limit riêng | `server/main.py`, `server/routes/javis_legacy.py`, `server/legacy_javis_runtime.py`, `workflows/local-n8n/zeo_chatbot.workflow.ts`, `workflows/local-n8n/cfc_cobay_chatbot.workflow.ts`, `server/settings.example.json` | Thêm HMAC hoặc service token, timestamp/nonce, giới hạn kích thước body và rate limit theo gateway/sender. Credential nằm trong n8n credential/env, không hardcode vào workflow | 1 |
| 3 | `message_id` chưa chống webhook/retry trùng | `chatbot/server/chat_pipeline.py`, hai workflow Messenger; file mới `chatbot/server/message_idempotency.py` | Redis `SET NX` cho lease, cache response theo `brand + message_id`, trả cờ `duplicate`; workflow không gửi lại Messenger khi là bản lặp | 1 |
| 4 | Chưa có vòng đo lường, gắn nhãn và duyệt intent có kiểm soát | `chatbot/server/nlu_shadow.py`, `chatbot/server/ai_reporter.py`, `chatbot/server/domains/reports/routes.py`, `chatbot/server/static/js/pages/reports.js`; file mới `chatbot/server/nlu_governance.py` | Metrics deterministic, danh sách mẫu đã che PII, thao tác gắn nhãn và quyết định `approve/reject/need_more_data`, audit revision và actor | 2 |
| 5 | QueryPlan chưa giữ đủ ràng buộc và chưa điều phối toàn bộ route | `chatbot/server/query_understanding.py`, `chatbot/server/chat_pipeline.py`; file mới `chatbot/server/dialogue_router.py` | Điền budget, số lượng, quy cách, khu vực, phủ định, thuộc tính; router nhận QueryPlan và chọn tool/fallback theo policy | 4 |
| 6 | Ollama NLU trước đây tắt; cách gọi inline có thể làm chậm khách | `chatbot/server/settings.json`, `settings.example.json`, `ai_engine.py`, `chat_pipeline.py`; file mới `nlu_shadow.py` và `tests/test_nlu_shadow.py` | Đã bật `shadow`, giới hạn task nền, timeout riêng, sample, retention, che PII và không ảnh hưởng response | 0, đã làm |
| 7 | Lịch sử thật có lưu nhưng chưa được dùng thống nhất | `chatbot/server/chat_pipeline.py`, `chatbot/server/ai_engine.py` | Chuẩn hoá tối đa 6 turn gần nhất, chỉ truyền dữ liệu cần thiết, cắt PII và không để lịch sử thay thế fact nguồn | 4 |
| 8 | Session có nguy cơ race, stale state và cache tăng không giới hạn | `chatbot/server/chat_pipeline.py`; file mới `chatbot/server/conversation_store.py` | Một `finalize_response()` cho mọi nhánh, Redis CAS/Lua hoặc transaction, TTL, lock phân tán khi cần, LRU/TTL cho cache RAM | 3 |
| 9 | Reference/link affirmation còn dựa nhiều vào regex và dễ nhầm số thứ tự với số lượng | `chatbot/server/chat_pipeline.py`, `query_understanding.py`; file mới `dialogue_router.py` | Thêm `pending_action`, `pending_options`, focus stack và phép phân biệt `số 2` với `2 chai`; câu mơ hồ phải hỏi lại | 4 |
| 10 | Web catalog đã sync nhưng chưa có tool đọc | `workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts`, `chatbot/server/chat_pipeline.py`; file mới `chatbot/server/web_catalog.py` | Loader Redis có schema/version/freshness, hợp nhất candidate Shopee/Web nhưng giữ provenance từng nguồn | 5 |
| 11 | Grounding/risk/escalation chưa thành policy thực thi tập trung | `chatbot/server/chat_pipeline.py`, `chatbot/server/ai_engine.py`, `chatbot/server/rag_search.py`; file mới `chatbot/server/grounding_policy.py` | Claim phải có source ID và freshness; policy/giá/tồn kho/an toàn thiếu nguồn thì hỏi lại hoặc handoff; prompt injection không được mở quyền tool | 5 |
| 12 | Pipeline lớn, quan sát lỗi và human handoff còn rời rạc | `chatbot/server/chat_pipeline.py`, `ai_reporter.py`, routes/UI Reports, tests | Tách dần theo store/router/tool/policy, thêm trace chuẩn, replay eval, trạng thái takeover và SLA cho admin | 3-6 |

## Phase 0: NLU shadow không chặn khách, đã triển khai

### Code

- `chatbot/server/nlu_shadow.py`: schedule task nền có trần, sampling ổn định, che số điện thoại/email, hash sender/message, lưu tối đa 500 observation trong 7 ngày.
- `chatbot/server/chat_pipeline.py`: mode `shadow` chỉ schedule và ghi trace `affects_response=false`; mode `assist` cũ vẫn tách riêng.
- `chatbot/server/ai_engine.py`: planner giới hạn output 256 token để giảm thời gian sinh JSON.
- `chatbot/server/settings.json`: bật `llm_nlu.mode=shadow`; timeout nền 20 giây, tối đa 2 task đồng thời.
- `chatbot/server/settings.example.json`: mô tả đầy đủ cấu hình nhưng vẫn mặc định `off` cho bản cài mới.
- `chatbot/server/tests/test_nlu_shadow.py` và `test_conversation_regression_guards.py`: kiểm tra che PII, retention, so sánh intent, task nền và bất biến câu trả lời deterministic.
- `bin/start-all.sh` và `bin/start-terminals.sh`: uvicorn theo dõi cả `server/` lẫn `chatbot/server/`, tránh settings mới chạy trên module cũ trong RAM.
- `server/legacy_javis_runtime.py`: status trả thêm đường dẫn module thực tế để chẩn đoán deployment.

### Cổng kiểm thử

- `py_compile` cho ba module thay đổi.
- Test shadow và regression hội thoại phải đạt 100%.
- Full suite chatbot phải đạt trước khi kết thúc phase.
- Smoke thật phải chứng minh response không chờ Ollama và observation được ghi sau đó.

### Kết quả xác minh 2026-08-25

- `py_compile`: đạt.
- Unit/regression: 36/36 test chatbot và 2/2 assertion bridge đạt. `.venv` không cài `pytest`; bridge được chạy trực tiếp, còn CI cài `pytest` theo workflow của repo.
- Runtime sau reload: HTTP 200 trong 156 ms, pipeline báo 24,56 ms.
- Planner hoàn tất nền sau 7.558,88 ms; trace ghi `scheduled`, `affects_response=false`; intent LLM `price_extreme` khớp route thật `shopee_price_extreme` theo intent family.
- Toàn bộ Redis key và observation do smoke test tạo đã được xoá sau khi xác minh.

### Rollback

Đặt `LLM_NLU_MODE=off` hoặc đổi `llm_nlu.mode` về `off`. Không cần rollback route vì shadow không điều khiển route.

## Phase 1: Bảo vệ API và chống xử lý trùng

Trạng thái: đã triển khai local theo phương án localhost-only và Redis idempotency. HMAC/service credential chưa cần cho n8n cùng máy; phải bổ sung nếu sau này cho gateway ngoài máy gọi endpoint.

### Thứ tự làm

1. Thêm xác thực service ở bridge Javis, chạy chế độ audit-only trong local test.
2. Cấu hình credential n8n rồi xác minh cả ZeO/CFC gọi được.
3. Bật enforce và bỏ `/api/chat-pipeline` khỏi nhóm public rộng; localhost vẫn đi qua cùng contract để không có hai chế độ khó kiểm soát.
4. Thêm idempotency lease/response cache và nhánh n8n bỏ qua `duplicate=true`.

### Test bắt buộc

- Thiếu, sai, hết hạn signature; timestamp lệch; nonce replay; body bị sửa sau khi ký.
- Cùng `message_id` gửi 2-10 lần chỉ chạy pipeline một lần và Messenger chỉ gửi một lần.
- Cùng nội dung nhưng `message_id` khác vẫn là hai tin hợp lệ.
- Redis mất kết nối phải fail theo policy rõ ràng, không âm thầm gửi lặp.
- Test workflow structure và syntax riêng cho JavaScript trong Code node trước khi push n8n.

### Duyệt và rollback

Chủ hệ thống xem log canary local và duyệt thời điểm đổi credential workflow. Rollback bằng cách trả workflow về credential revision trước; không rollback bằng cách để endpoint public vô thời hạn.

## Phase 2: Javis Reports, gắn nhãn và duyệt

Trạng thái: chưa triển khai API/UI governance. Chỉ bắt đầu sau khi shadow có đủ mẫu; báo cáo kinh doanh hiện tại không được dùng thay cho dữ liệu gắn nhãn và quyết định audit.

### Báo cáo cần hiển thị

- Số mẫu đủ điều kiện, số task được schedule, queue full, timeout/no prediction.
- Latency p50/p95 của planner; tỷ lệ vượt confidence threshold.
- Agreement giữa LLM và route thực tế chỉ là tín hiệu so sánh, không được coi là ground truth.
- Ma trận nhầm intent, nhóm disagreement lớn nhất và mẫu ngẫu nhiên trong nhóm agreement.
- Ví dụ hội thoại đã che PII, source/QueryPlan/actual/predicted đặt cạnh nhau.
- Lỗi grounding nghiêm trọng được tách riêng: giá, link, tồn kho, chính sách, riêng tư, an toàn và liều lượng.

### Cách chủ hệ thống duyệt

1. Javis tạo phần số liệu bằng code. AI chỉ viết tóm tắt tiếng Việt từ số liệu đó.
2. Telegram có thể gửi thông báo và link mở Reports, nhưng không dùng nút Telegram để duyệt vì chưa có session quản trị đáng tin cậy.
3. Trong Dashboard đã đăng nhập, chủ hệ thống gắn nhãn mẫu `đúng intent`, `sai intent`, `thiếu ngữ cảnh` hoặc `không đủ nguồn`.
4. Với từng intent, chọn `Duyệt thử nghiệm`, `Từ chối` hoặc `Cần thêm dữ liệu`. Redis lưu actor, thời gian, revision, số mẫu và snapshot metrics.
5. Quyết định duyệt không tự sửa settings. Một bước rollout riêng mới thêm intent đó vào allowlist canary.

### Gate duyệt tối thiểu

- Ít nhất 200 observation tổng và 30 mẫu đã được người duyệt gắn nhãn cho mỗi intent muốn thử.
- Precision trên mẫu người duyệt ít nhất 95% cho intent rủi ro thấp.
- Không có lỗi nghiêm trọng trong bộ privacy/policy/safety/price grounding.
- Các intent policy, khiếu nại, riêng tư, an toàn và tư vấn nông nghiệp vẫn deterministic hoặc handoff, chưa cho LLM tự route.

### Test bắt buộc

- Metrics được tính từ fixture cố định, không phụ thuộc văn bản AI.
- PII không xuất hiện trong API/UI/Telegram report.
- Chỉ admin hợp lệ được gắn nhãn hoặc duyệt; mọi thay đổi có audit.
- Refresh/retry không tạo hai quyết định cho cùng revision.

## Phase 3: Conversation store nhất quán

Trạng thái: đã triển khai local. CAS hiện được bảo vệ bằng sender lease phân tán + revision; grounding enforce vẫn là gate riêng.

### Code

- Tạo `conversation_store.py` làm chủ sở hữu duy nhất của load/save/finalize state.
- Mọi return branch đi qua `finalize_response()`; xoá dần các lần `create_task(_async_save_session(...))` rải rác.
- Redis update có revision/CAS, TTL và lịch sử append giới hạn; cache RAM dùng TTL/LRU.
- Thêm `pending_action`, `pending_options`, `topic_stack` và `takeover_state` vào schema state có version.

### Test bắt buộc

- Kiểm tra mọi nhánh response đều lưu đúng `last_user_message`, `last_bot_reply`, intent và trace.
- Burst 10 tin cùng sender, hai sender song song và mô phỏng hai worker.
- Restart giữa lượt không mất pending action; state cũ migrate được.
- Test timeout Redis, write conflict và retry không làm đảo thứ tự turn.

### Rollback

Chạy dual-read/dual-write một thời gian. Store mới có feature flag; rollback đọc schema cũ nhưng không xoá dữ liệu schema mới.

## Phase 4: QueryPlan và Dialogue Router

Trạng thái: đã chuyển các route correction, unresolved ordinal, CFC dealer và pending link. Các intent còn lại vẫn chạy legacy và tiếp tục chuyển từng họ sau replay shadow.

### Code

- `query_understanding.py` chỉ trích xuất intent/entities/references/constraints, tuyệt đối không sinh fact.
- `dialogue_router.py` nhận QueryPlan, state và policy rồi trả `route_decision`: tool, clarify, fallback hoặc handoff.
- Truyền `recent_turns` đã sanitize cho planner/synthesizer khi thật sự cần; facts vẫn chỉ đến từ Sheet/Redis/catalog.
- Chuyển từng họ intent khỏi monolith, bắt đầu từ link/price/catalog vì rủi ro thấp và đã có test tốt.

### Test bắt buộc

- Paraphrase family, không chỉ exact string.
- `gửi link`, `ok`, `loại đó`, `cái thứ hai`, `2 chai loại đó`, sửa ý và đổi chủ đề.
- Một câu nhiều ý: giá + link + giao hàng; thiếu entity phải hỏi lại đúng một câu.
- Replay toàn bộ bộ test hiện có và so sánh old/new router trong shadow trước khi chuyển route.

## Phase 5: Web catalog và Grounding Policy

Trạng thái: Grounding Policy đang audit. Phần Web catalog nâng cao tạm hoãn; không chủ động hợp nhất Web/Shopee.

### Code

- `web_catalog.py` đọc snapshot Web, validate schema/version và cảnh báo stale.
- Product candidate giữ `source_type`, `source_id`, `source_updated_at`; không trộn giá Shopee với link Web mà mất nguồn.
- `grounding_policy.py` kiểm tra claim theo loại rủi ro trước khi gửi: allow, redact, clarify, fallback hoặc handoff.
- Không viết các câu khẳng định cứng về freeship, khuyến mãi, tồn kho hoặc công dụng nếu snapshot hiện tại không xác nhận.

### Test bắt buộc

- Snapshot đúng, thiếu cột, stale, rỗng và Redis lỗi.
- Mỗi claim giá/link/chính sách có source trong trace.
- Prompt injection trong FAQ/catalog không thể thay policy hoặc gọi tool ngoài allowlist.
- ZeO và CFC chạy eval riêng; CFC thiếu catalog không được mượn fact ZeO.

## Phase 6: Handoff và assist canary

Trạng thái: handoff local đã có state, pause và API resolve. Assist canary chưa bật và không được tự bật từ thay đổi này.

### Cách bật

1. Chỉ intent rủi ro thấp đã được duyệt mới vào `assist_intents` allowlist.
2. Canary 5% trong 48 giờ, sau đó 25%, rồi 100% nếu toàn bộ gate vẫn đạt.
3. Planner chỉ chọn deterministic tool. Tool trả fact có provenance; policy có quyền phủ quyết planner.
4. Khi confidence thấp, thiếu nguồn, khách khiếu nại hoặc khách yêu cầu người thật, đặt `takeover_state=pending` và dừng bot cho đến khi admin đóng handoff.

### Gate vận hành

- Không tăng p95 latency của response quá 50 ms so với baseline do planner chạy nền/được cache.
- Không giảm grounding pass rate và không tăng fallback sai chủ đề trong replay set.
- Zero duplicate reply trong canary.
- Có nút khẩn cấp đặt allowlist rỗng hoặc chuyển toàn bộ về `shadow`; thao tác được audit.

## Thứ tự bàn giao và điểm cần chủ hệ thống duyệt

| Mốc | Codex/Javis chuẩn bị | Chủ hệ thống duyệt |
|---|---|---|
| Sau Phase 0 | Test result, smoke result, thống kê shadow ban đầu | Xác nhận tiếp tục thu observation |
| Trước Phase 1 enforce | Diff auth, credential name, n8n dry-run và rollback revision | Thời điểm cập nhật hai workflow |
| Sau Phase 2 | Report deterministic, mẫu disagreement và nhãn | Duyệt/từ chối từng intent |
| Trước mỗi phase router/store | Shadow comparison và regression report | Cho phép chuyển module cụ thể |
| Trước assist | Allowlist, revision policy, canary 5% và emergency switch | Bấm duyệt canary |
| Sau canary | Metrics trước/sau và danh sách lỗi | Tăng 25%, 100% hoặc quay về shadow |

Javis chịu trách nhiệm tập hợp bằng chứng và lưu audit. Quyết định nghiệp vụ cuối cùng vẫn thuộc chủ hệ thống; báo cáo AI không có quyền tự deploy.

## Lệnh kiểm thử chuẩn

```bash
cd /Users/hyden/Documents/David-nguyen/javis-os
.venv/bin/python -m py_compile server/legacy_javis_runtime.py chatbot/server/chat_pipeline.py chatbot/server/ai_engine.py chatbot/server/query_understanding.py chatbot/server/conversation_store.py chatbot/server/message_idempotency.py chatbot/server/dialogue_router.py chatbot/server/grounding_policy.py chatbot/server/conversation_replay_eval.py
LLM_NLU_MODE=off .venv/bin/python -m unittest discover -s chatbot/server/tests -p 'test_*.py' -v
PYTHONPATH=tests/python .venv/bin/python -c 'import test_legacy_javis_runtime as t; t.test_legacy_javis_status_points_to_existing_runtime(); t.test_legacy_javis_modules_load(); t.test_handoff_list_and_resolve_update_redis_and_runtime_cache()'
.venv/bin/python chatbot/server/conversation_replay_eval.py
npx n8nac skills validate workflows/local-n8n/zeo_chatbot.workflow.ts
npx n8nac skills validate workflows/local-n8n/cfc_cobay_chatbot.workflow.ts
./bin/start-all.sh
npx n8nac push workflows/local-n8n/zeo_chatbot.workflow.ts --verify
```

`start-all.sh` chỉ dùng khi cần khởi động stack local; không chạy lại nếu các dịch vụ đang hoạt động. Lệnh `n8nac push` chỉ chạy sau khi chủ hệ thống duyệt phase có thay workflow. Với CFC, Codex chỉ chuẩn bị và test local; chủ hệ thống tự quyết định deploy.
