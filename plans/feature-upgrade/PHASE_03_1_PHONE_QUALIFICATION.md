# Phase 03.1 — Phone qualification trước LeadDraft

Trạng thái: **IMPLEMENTED — queue path enabled**  
Ngày: 06/10/2026

## Quyết định nghiệp vụ

Commercial intent chưa có số điện thoại sẽ không tạo LeadDraft và không gửi Sales
outbox. CFCBot lưu pending contact ngắn hạn trong Redis, trả lời xin số, sau đó
merge lượt follow-up có số vào cùng conversation.

## Bằng chứng

- `LEAD_REQUIRE_PHONE=true` mặc định.
- Không có phone: response `lead_stage=collecting_contact`, LeadDraft = 0.
- Có phone ở lượt sau: LeadDraft được tạo và Sales outbox được giao.
- Side effect test dùng số giả; không dùng dữ liệu khách thật.

## Rollback

Đặt `LEAD_REQUIRE_PHONE=false` rồi restart nếu owner muốn quay lại policy cũ.
