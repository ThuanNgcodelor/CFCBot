# Bộ phase triển khai nâng cấp chatbot ZeO / CFC

> **Lưu trữ (08/09/2026):** Chỉ dùng để xem lịch sử phase. Tài liệu hiện hành bắt đầu ở [plan/README.md](../../../README.md).

Ngày tạo: 2026-08-28  
Trạng thái chung: `PLANNED — CHƯA CODE, CHƯA DEPLOY`  
Nguồn hiện trạng tại thời điểm đó: [Audit live và kế hoạch tổng](../historical-plans/PLAN_AUDIT_LIVE_VA_NANG_CAP_CHATBOT_ZEO_CFC_2026-08-28.md)

## 1. Mục đích

Bộ tài liệu này chuyển kế hoạch tổng thành các gói thực thi có thể giao việc, kiểm thử, nghiệm thu và rollback độc lập. Mỗi phase đều nêu rõ:

- vấn đề đang giải quyết;
- phạm vi và phần không làm;
- work package, file dự kiến tác động và dependency;
- test bắt buộc;
- điều kiện bắt đầu, điều kiện kết thúc;
- rollout, rollback và quyết định cần chủ hệ thống duyệt.

Không phase nào được xem là hoàn thành chỉ vì code đã viết hoặc unit test xanh. Trạng thái chỉ chuyển sang `DONE` khi đạt exit gate bằng real pipeline hoặc nguồn live phù hợp với mức rủi ro.

## 2. Danh sách phase

| Phase | Tài liệu | Mục tiêu | Ước lượng | Trạng thái |
|---|---|---|---:|---|
| 0 | [Containment và grounding](PHASE_0_CONTAINMENT_GROUNDING.md) | Chặn ngay câu trả lời bịa và rủi ro AMIS/n8n | 1–2 ngày | Sẵn sàng review |
| 1 | [Runtime manifest và evidence trace](PHASE_1_RUNTIME_EVIDENCE_TRACE.md) | Truy ra code/model/prompt/snapshot/fact của mỗi answer | 3–5 ngày | Planned |
| 2 | [Conversation intelligence](PHASE_2_CONVERSATION_INTELLIGENCE.md) | Hiểu paraphrase, multi-intent, follow-up và phản vấn nguồn | 4–7 ngày | Planned |
| 3 | [AMIS realtime và bảo mật](PHASE_3_AMIS_REALTIME_SECURITY.md) | Phân tách public snapshot với lookup realtime có quyền | 5–10 ngày | Chờ quyết định nghiệp vụ |
| 4 | [Tri thức nông học được duyệt](PHASE_4_APPROVED_AGRONOMY_KNOWLEDGE.md) | Biến tư vấn cây trồng thành fact/protocol có phê duyệt | 5–10 ngày + thời gian duyệt | Chờ kỹ sư nghiệp vụ |
| 5 | [Evaluation, canary và vận hành](PHASE_5_EVALUATION_CANARY_OPERATIONS.md) | Chứng minh chất lượng trước khi rollout và giám sát sau rollout | 3–5 ngày nền tảng, sau đó liên tục | Planned |

## 3. Dependency và đường triển khai

```text
Phase 0: containment
    |
    v
Phase 1: runtime/evidence foundation
    |------------------------|
    v                        v
Phase 2: conversation     Phase 3: AMIS realtime
    |                        |
    |-----------|------------|
                v
       Phase 4: approved agronomy
                |
                v
       Phase 5: canary/rollout
```

Ghi chú:

- Harness eval của Phase 5 nên được dựng tối thiểu từ Phase 0 để tạo regression gate; phần rollout production vẫn nằm cuối.
- Chuẩn hóa dữ liệu Phase 4 có thể làm song song Phase 2–3, nhưng không được bật customer-facing trước khi Phase 1 có claim/evidence contract.
- Phase 3A public snapshot có thể làm trước Phase 2; Phase 3B order/stock/loyalty realtime cần identity và authorization contract.

## 4. Luật bất biến cho mọi phase

1. Sheet, catalog, approved protocol và tool nghiệp vụ là nguồn fact; LLM không phải nguồn.
2. Không bịa giá, link, stock, order status, loyalty, chiết khấu, công nợ, liều lượng, tác dụng hoặc chính sách.
3. Không dùng `ollama:*`, `groq:*` hoặc tên provider làm `source_id` nghiệp vụ.
4. Không flush/reset Redis để rollout.
5. Không đưa raw customer/order/financial data vào public Redis, prompt LLM hoặc n8n execution history.
6. Không force-push workflow đang conflict. Phải pull/resolve rõ hướng và có phê duyệt trước push/activate.
7. Không bật semantic/LLM primary trước shadow và canary gate.
8. Timeout, malformed JSON, cache miss hoặc tool lỗi phải rơi về safe fallback, không rơi về model world knowledge.
9. Mọi thay đổi customer-facing phải có test paraphrase family, không chỉ một câu exact-match.
10. Deployment production thuộc quyền quyết định của chủ hệ thống.

## 5. Thứ tự ưu tiên nếu nguồn lực hạn chế

Nếu chỉ có thể làm trong một tuần, ưu tiên:

1. Hoàn thành toàn bộ Phase 0.
2. Làm phần tối thiểu của Phase 1: runtime manifest, provider/model trace và evidence status.
3. Dựng regression cho câu sầu riêng, empty-facts, source challenge và n8n HTTP error.

Chưa nên ưu tiên đổi model hoặc tăng context window. Hai việc đó không sửa được lỗi nguồn, trace, quyền truy cập và false-green đã xác minh.

## 6. Trạng thái và quy tắc cập nhật

Mỗi phase dùng một trong các trạng thái:

- `PLANNED`: đã mô tả, chưa bắt đầu code.
- `IN_PROGRESS`: đang code/test local; chưa production.
- `BLOCKED`: thiếu quyết định, credential, dữ liệu hoặc người duyệt.
- `READY_FOR_CANARY`: đạt local/replay gate, chưa rollout rộng.
- `DONE`: đạt exit gate và có bằng chứng production/canary.
- `ROLLED_BACK`: đã rút khỏi production; ghi rõ manifest/snapshot bị rollback.

Khi cập nhật trạng thái phải kèm:

- commit/runtime manifest;
- test command và kết quả;
- dữ liệu/snapshot hash liên quan;
- tỷ lệ rollout;
- lỗi còn mở;
- người duyệt và thời điểm duyệt.

## 7. Quan hệ với tài liệu conversation cũ

[PLAN_CONVERSATION_INTELLIGENCE_PHASED_ROLLOUT.md](../PLAN_CONVERSATION_INTELLIGENCE_PHASED_ROLLOUT.md) vẫn hữu ích cho GoalFrame, reference resolver và replay multi-turn. Tuy nhiên các nhãn “đã triển khai/hoàn thành” trong tài liệu đó là ghi nhận tại thời điểm cũ, không tự động vượt qua gate của bộ phase mới.

Audit live ngày 28/08 là nguồn hiện trạng ưu tiên khi có mâu thuẫn, đặc biệt đối với:

- nhánh AI nông học đang gửi output chưa kiểm chứng;
- provider trace bị hard-code;
- AMIS Full Warm và Public Sync cùng active;
- ranking hot-cache chọn sai intent;
- workflow continue-on-error tạo false-green.

## 8. Quy trình n8n khi đến phase có sửa workflow

Environment đã xác minh:

- environment: `local-n8n-2`;
- target: `local-n8n-3`;
- workflows path: `workflows/local-n8n`;
- instance: external n8n live.

Khi thực thi, không dựa vào thông tin trên như cấu hình vĩnh viễn. Luôn chạy lại `npx --yes n8nac env status --json`, sau đó:

1. `npx --yes n8nac list --json` để kiểm tra drift/active.
2. Pull workflow hiện hữu trước khi sửa.
3. Nếu conflict, dừng và chọn rõ `keep-current` hoặc `keep-incoming`; không force âm thầm.
4. Kiểm tra schema/node trước khi thay parameter.
5. Validate local, kiểm tra embedded Code-node JavaScript riêng.
6. Chỉ push/activate/test production khi người dùng phê duyệt thao tác live.
7. Sau thay đổi phải kiểm tra execution error path và trình bày workflow bằng URL do công cụ trả về.

## 9. Definition of Done toàn chương trình

Chương trình chỉ hoàn tất khi:

- unsupported critical claim bằng 0 trong bộ gate;
- khách hỏi “nguồn đâu/có thật không” nhận được trạng thái từng claim và bot biết rút lại claim không nguồn;
- mọi AI call có provider/model/prompt hash/runtime manifest;
- mỗi dynamic fact có freshness và authorization scope;
- order/stock/loyalty/price chỉ đi qua tool phù hợp, không qua public snapshot;
- không lộ PII/financial data bên thứ ba;
- paraphrase, follow-up, topic switch và tool failure đạt gate;
- n8n không còn false-green cho lỗi pipeline;
- rollout có canary, error budget và rollback đã thử.
