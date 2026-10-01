# Báo cáo triển khai Phase 0 — Baseline và hàng rào tương thích

Ngày chạy: 09/09/2026.

Trạng thái: `LOCAL_COMPLETE`.

Phase 0 đã hoàn thành mục tiêu đóng băng hành vi và dựng hàng rào local. Full suite xanh, Redis integration replay đã chạy trên máy local và cleanup được xác nhận. Không có thay đổi endpoint, schema trả lời, n8n workflow, AMIS hay deployment. Replay có ghi tạm đúng key eval rồi xóa; không chạm session khách hàng hoặc business record.

## 1. Những gì đã khóa

- Hợp đồng request `/api/chat-pipeline`: 9 field hiện hành.
- Hợp đồng response: 19 field hiện hành; không xóa hoặc đổi tên field.
- Conversation state schema v5: toàn bộ field legacy, GoalFrame và `state_revision`.
- 12 capability hiện có: product, dealer, order, loyalty, price intake, purchase intake, agronomy, contact, complaint, B2B, handoff và fallback.
- Redis key contract cho session, history, customer, lease, idempotency, FAQ/vector và AMIS public/private cache.
- Năm loại bằng chứng kiểm tra: `unit_static`, `pipeline_fixture`, `ollama_local`, `redis_integration`, `live_canary`.
- Protected order/loyalty route có test cho found, missing input, not-found/ownership mismatch, stale và cache read failure.

Nguồn contract nằm ở `chatbot/server/phase0_contract.py`. Test drift nằm ở `chatbot/server/tests/test_phase0_baseline_contract.py`.

## 2. Dataset manifest

| Dataset | Số case | SHA-256 |
|---|---:|---|
| `chatbot/server/eval_conversation_replays.jsonl` | 19 | `sha256:ad7434c5a2da2efcd8c7a1931811782864584ad108dbb34c301a147dc877faff` |
| `chatbot/server/eval_sheet_grounding_cases.jsonl` | 40 | `sha256:9859bdfea701e576d4702377f1102f74fa37cffec09657da9aab58fc4df6c2e1` |

Dataset manifest ID: `sha256:9b613904d46d5d0abefb8ad6b7fe0626cee5023c84c0c44fa6c657d15f0ccc2e`.

Runner đã được sửa để manifest dùng đúng file truyền bằng `--cases`; trước đây runner luôn ghi hash file mặc định.

## 3. Hàng rào replay

- Mỗi lần chạy có namespace riêng: `eval-replay:<run_id>:<case_id>`.
- Hàm cleanup từ chối sender và message ID không thuộc đúng namespace của lần chạy.
- Telegram bị chặn bằng context-local guard trong suốt eval, kể cả task async kế thừa context.
- Runner không gọi AMIS write/sync.
- Redis chỉ được phép ghi/xóa session, history, profile và idempotency thuộc sender/message eval; cleanup lỗi sẽ làm runner thất bại thay vì bị nuốt.
- Report ghi `run_id`, namespace, side-effect policy, dependency status, latency từng turn, runtime manifest và dataset manifest.
- Cùng nội dung nhưng khác Messenger message ID vẫn được xử lý hai lần; cùng message ID vẫn dùng idempotency cache.

## 4. Runtime manifest

Runtime manifest schema đã nâng lên v2. Nó fingerprint các thành phần pipeline, router, orchestrator, conversation store, idempotency, evidence, NLU, agronomy, AMIS adapters, legacy HTTP bridge và hai workflow chatbot.

Manifest còn chứa hash cho request v1, response v1, conversation state v5, Redis keys v1 và capability inventory v1. ID không còn thay đổi chỉ vì process khởi động ở thời điểm khác.

Runtime manifest ID của lần replay cuối: `sha256:f927061850ae694c6a8ad794a96389643fbb057d26119c1152a9617c53bd8891`.

## 5. Kết quả kiểm tra local

| Nhóm | Validation mode | Kết quả | Ý nghĩa |
|---|---|---:|---|
| Byte compile toàn bộ `chatbot/server` | `unit_static` | Pass | Không có lỗi cú pháp/import-time compile trong source đã quét |
| Phase 0 + các route liên quan | `pipeline_fixture` | 63/63 pass | Contract, manifest, replay isolation, Telegram/shadow/profile guard, idempotency, AMIS projection, order, loyalty và hot-cache đều đạt |
| Full `chatbot/server/tests` | `pipeline_fixture` | 247/247 pass | Toàn bộ test hiện có trong `chatbot/server/tests` xanh |
| 19 conversation replay | `redis_integration` | 11/19 case; 24/36 turn | Redis available, source coverage 100%; đây là baseline chất lượng hiện tại, không phải pass toàn bộ gold case |
| Redis cleanup | `redis_integration` | Confirmed | Session/history/profile và idempotency key eval được xóa; cleanup lỗi sẽ làm runner fail |
| Ollama local | `ollama_local` | Chưa benchmark riêng | Replay có quan sát timeout synthesis/agronomy nhưng không dùng nó làm benchmark model độc lập |
| Live canary | `live_canary` | Chưa chạy | Ngoài phạm vi Phase 0 và chưa được deploy |

Lệnh full suite:

```bash
LLM_NLU_MODE=off CHAT_CONVERSATION_MODE=off PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m unittest discover -s chatbot/server/tests -p 'test_*.py' -q
```

Replay cuối có `run_id=064efab7046b`, report ID `eval:df8e999faabb9ac38a5d7580`; memory 10/10, routing 8.33/10, grounding 8.15/10 và task completion 0.5 trên 2 turn có gắn cờ task.

## 6. Baseline gap hội thoại đã được ghi nhận

Tám case còn fail là đầu vào cho Phase 1–2, không bị che bằng cách nới expectation:

1. `zeo_contact_paraphrase`: paraphrase hotline bị rơi vào unanswered.
2. `cfc_product_to_dealer`: catalog route trả intent mới khác gold intent cũ.
3. `cfc_agronomy_to_purchase`: route dosage/review khác expected.
4. `cfc_dealer_location_memory`: capability boundary/location follow-up chưa khớp gold.
5. `cfc_inventory_phone_resume`: nội dung boundary tồn kho chưa khớp chuỗi bắt buộc.
6. `cfc_agronomy_expert_intake`: retrieval timeout nên thiếu fact/phrase kỳ vọng.
7. `cfc_order_and_loyalty_topic_switch`: local protected cache trả no-match thay cho unavailable và trace boundary chưa khớp.
8. `cfc_wholesale_policy_boundary`: ý nghĩa an toàn đúng nhưng câu chữ khác phrase gold.

Các gap này không làm Phase 0 thất bại vì mục tiêu Phase 0 là tạo baseline có thể lặp lại và khóa hệ thống cũ. Chúng chặn việc tuyên bố chatbot đạt toàn bộ gold set hoặc sẵn sàng canary.

## 7. AMIS projection gap đã xử lý thế nào

Lịch sử source cho thấy commit 27/08 đã cố ý yêu cầu customer có `order_sales > 0` hoặc `number_orders > 0`, đồng thời đổi reason code cho stale/not-invoiced. Test fixture cũ chưa theo contract này. Phase 0 giữ nguyên implementation an toàn, cập nhật fixture để có `number_orders=1`, khóa trường hợp zero-sales/no-orders bị loại và dùng đúng reason code hiện hành. Sau thay đổi, AMIS projection test xanh 8/8.

## 8. Kết luận phạm vi

Phase 0 là `LOCAL_COMPLETE`. Trạng thái này chỉ xác nhận baseline, compatibility và runner safety đã đạt. Nó chưa xác nhận 19/19 replay, Ollama benchmark, live traffic, deployment hoặc CRM write. Bước kế tiếp hợp lệ là Phase 1 reliability; tám replay gap vẫn phải được xử lý hoặc phân loại bằng bằng chứng, không được sửa gold tùy tiện.
