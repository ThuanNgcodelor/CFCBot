# Tổng kết triển khai ZeO/CFC — Phase 0 → 5

> **Lưu trữ (08/09/2026):** Bản tổng kết lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Ngày cập nhật: 2026-08-29  
Phạm vi: local code/test; **chưa push Git, chưa bật canary, chưa tự deploy n8n production**.

## Trạng thái

| Phase | Đã có ở local | Chưa hoàn tất |
|---|---|---|
| 0 — Containment & grounding | Guard giá/tồn/chính sách/nông học, source challenge an toàn, không bịa | Live evidence đầy đủ cho mọi capability |
| 1 — Runtime evidence | Trace request/source/claim/fallback, runtime manifest, freshness | Đối chiếu mọi provider/live revision |
| 2 — Conversation intelligence | QueryPlan/GoalFrame/reference, topic switch, correction, shadow planner | Đánh giá đủ traffic thật và multi-intent |
| 3 — AMIS security | Protected warm order lookup mã + SĐT, HMAC, allowlist; CFC catalog projection | Realtime privileged adapter, OTP, secret/live 401-403 test |
| 4 — Agronomy | Validator fact có source/approval/expiry; eligibility sầu riêng; không cho Ollama tự kê liều | Kỹ sư duyệt protocol structured cho từng cây/giai đoạn |
| 5 — Evaluation/canary | Replay manifest/scorer, shadow v2 redacted, stable canary primitive, manual suites | Baseline live, dashboard/alert n8n, approval và rollout |

## Thay đổi customer-facing

1. **Đơn hàng:** mã đơn + SĐT khớp protected snapshot mới trả; allowlist gồm mã đơn, tình trạng đơn, giao hàng, ngày đặt, hạn giao và “Cập nhật gần nhất” nghiệp vụ. Không hiện `synced_at`, địa chỉ, tiền, dòng hàng hoặc khách khác. Sai/mismatch nói không tìm thấy khớp, không nói “chưa kết nối CRM”.
2. **Giá/tồn kho:** policy hiện tại không trả giá/tồn kho. Public snapshot không có trường giá/tồn; các câu này chuyển đầu mối kiểm tra, không đoán.
3. **Danh mục CFC:** snapshot AMIS có 932 dòng và lẫn hàng không phải phân bón. Runtime lọc allowlist, loại áo/quà/bột giặt/máy móc và chỉ hiện 3–5 tên/mã. Công thức `20-20-10` chỉ trả khi khớp chính xác; không đổi thành `20-10-10` gần giống.
4. **Nông học:** “có phân cho sầu riêng không” trả nhóm NPK/hữu cơ và hỏi giai đoạn. Xin liều/công thức/chẩn đoán phải qua fact/protocol đã duyệt; thiếu thì chuyển Khuyến nông. Ollama chỉ hỗ trợ hiểu câu/soạn nháp nội bộ, không tự phát hành liều customer-facing.
5. **Mua số lượng lớn:** từ 200kg đến nhiều tấn nhận diện B2B, không báo giá/chiết khấu/giao hàng. Đầu mối: Trưởng phòng Kinh doanh `0981 205 448`.
6. **Khuyến nông:** Lê Thanh Đạm `0353 585 7516`; Cao Văn Được `0939 385 2529`. Đây là đầu mối chuyển tiếp, không phải bằng chứng đã có protocol.
7. **Khiếu nại:** xin lỗi, xin ảnh hiện trạng + mã lô/bao bì + liên hệ/khu vực, chuyển CSKH/Kỹ thuật; không hứa tạo ticket hay đổi trả.
8. **Hội thoại:** cùng phiên có reference sản phẩm, GoalFrame, correction và topic switch; “à ok” không mặc định là yêu cầu dịch vụ. Không dùng context sender khác.
9. **Website/source challenge:** cụm “chính thức không?” không còn bị bắt nhầm thành “thực không?”; câu hỏi website đi thẳng FAQ và source-challenge thật sự bỏ qua AI planner để giảm latency.

## Test tự động local

- `chatbot/server/tests/test_cfc_public_catalog.py`: lọc hàng lẫn, formula exact, projection không có price/stock, B2B contact.
- Regression Phase 0–5 nằm trong `chatbot/server/tests/`.

```bash
cd /Users/hyden/Documents/David-nguyen/javis-os
LLM_NLU_MODE=off CHAT_CONVERSATION_MODE=off \
  .venv/bin/python -m unittest discover -s chatbot/server/tests -p 'test*.py' -v
```

## Test thật trên page

1. Dùng sender test riêng CFC; chạy `chatbot/server/manual_tests/TEST_CFC_REAL_WORLD_PHASE_0_5.md`, ưu tiên CFC-03/06/10/14/16/32/33/34/42/43/49/50/51/54/56.
2. Đổi sender hoặc reset session rồi chạy `chatbot/server/manual_tests/TEST_ZEO_REAL_WORLD_PHASE_0_5.md`, ưu tiên ZEO-01/02/03/11/15/16/17/21/23/25/27/28/30/31/32/38.
3. CRM dùng fixture mã + SĐT được phép; không dùng khách thật trong file/log.
4. Ghi response JSON và trace đã redaction. PASS theo route/source/fallback/claim cấm, không cần giống từng chữ.
5. Case fail phải lưu `intent`, `fallback_reason`, `source_id`, `runtime_manifest_id`, latency, snapshot time; không sửa expected để che lỗi.

## Checklist trước khi gọi “đạt”

- [ ] CFC/ZeO manual pass nhóm high-risk và paraphrase.
- [ ] Không output nội bộ (`B2B`, `Knowledge CFC`, Redis key, “snapshot sync”) với khách.
- [ ] Không có provider fallback làm mất route deterministic.
- [ ] Order warm cache có fixture khớp/mismatch; output có cập nhật nghiệp vụ.
- [ ] Catalog không lẫn hàng ngoài phân bón; formula mismatch không thay thế.
- [ ] Agronomy protocol được kỹ sư duyệt và version hóa trước khi bật liều.
- [ ] N8n live đã reconcile/pull, error contract/alert không false-green.
- [ ] Người sở hữu production duyệt canary và giữ rollback.

## Việc vận hành tiếp theo

1. Chạy test tự động local và test page theo hai file trên.
2. Tôi chưa tự restart vì có thể ảnh hưởng n8n/page đang test; nếu bạn muốn, dừng/bật `bin/start-all.sh` theo quy trình local của bạn rồi báo lại.
3. Gửi các case fail kèm JSON response/trace đã che PII để sửa đúng nhánh.
4. Sau khi local pass, bạn tự publish workflow; chỉ audit production/canary khi có live revision, workflow ID và credential được duyệt.
