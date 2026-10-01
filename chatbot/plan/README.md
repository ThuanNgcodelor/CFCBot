# Plan & context index

Tài liệu này là điểm vào cho người hoặc AI cần hiểu và vận hành chatbot CFC/ZeO.

## Tài liệu hiện hành — đọc theo thứ tự

1. [AGENTS.md](../AGENTS.md) — quy tắc làm việc, kiến trúc và các bất biến an toàn.
2. [Master plan cập nhật CFCBot: queue, OCR và Telegram Sales](PLAN_DINH_HUONG_CAP_NHAT_CFCBOT_QUEUE_OCR_TELEGRAM_2026-10-01.md) — nguồn quyết định hiện hành sau cutover: baseline, kiến trúc đích, contract, phase/gate, test, rollout và rollback.
3. [Master plan CFC AI Agent: hiện tại và tương lai](MASTER_PLAN_CFC_AI_AGENT_HIEN_TAI_VA_TUONG_LAI_2026-09-09.md) — nền tảng chức năng và roadmap AI/CRM trước cutover.
4. [Plan triển khai Chatbot độc lập, queue, OCR và Telegram Sales — bản gốc 29/09](PLAN_TRIEN_KHAI_CHATBOT_QUEUE_OCR_TELEGRAM_SALES_2026-09-29.md) — bản lịch sử đã được plan ngày 01/10 thay thế; chỉ dùng đối chiếu quyết định ban đầu.
5. [Phase roadmap nâng cấp không làm mất hệ thống cũ](PHASE_ROADMAP_CFC_AI_AGENT_NANG_CAP_KHONG_MAT_HE_THONG_CU_2026-09-09.md) — thứ tự thực thi, dependency, file tác động, test, rollout và rollback cho từng phase.
6. [Báo cáo triển khai Phase 0](PHASE_0_BASELINE_REPORT_2026-09-09.md) — contract đã khóa, dataset/runtime manifest, hàng rào replay và kết quả test thật.
7. [Tài liệu hệ thống CFC AI](../TAI_LIEU_HE_THONG_CFC_AI.md) — mô tả hệ thống và các luồng nghiệp vụ.
8. [Tổng hợp hiện trạng và bộ test Conversation Intelligence CFC](TONG_HOP_HIEN_TRANG_VA_BO_TEST_CONVERSATION_INTELLIGENCE_CFC.md) — hiện trạng kỹ thuật, giới hạn và bộ test đang dùng.
9. [Plan khách hàng mới/cũ, tạo đơn CRM và dọn dẹp](../PLAN_KHACH_HANG_MOI_CU_TAO_DON_CRM_VA_DON_DEP_2026-08-31.md) — backlog nghiệp vụ đang chờ chủ hệ thống duyệt.
10. [Rà soát toàn bộ `chatbot/server` cho CFC Agent](AUDIT_SERVER_CHO_CFC_AGENT_2026-09-09.md) — bằng chứng source, phần đã có, khoảng trống và giới hạn chưa được xác minh live.
11. [Plan CFC Agent và CRM trên Mac M4 16GB](PLAN_CFC_AGENT_VA_CRM_2026-09-08.md) — plan kỹ thuật đã chỉnh sau source audit; chưa triển khai.
12. [Plan Hybrid Agent: hiểu ngôn ngữ tự nhiên mà không bịa dữ liệu](PLAN_HYBRID_AGENT_CFC_HIEU_NGUON_NGU_TU_NHIEN_2026-09-17.md) — lộ trình chuyển từ route cứng sang model-driven decision + tool có kiểm soát.

## Lịch sử

Các audit, plan và phase đã hoàn thành hoặc đã được thay thế được giữ nguyên tại [archive/2026-08](archive/2026-08/). Chúng chỉ để đối chiếu lịch sử; không dùng làm nguồn quyết định deployment hiện tại nếu mâu thuẫn với các tài liệu ở trên.
