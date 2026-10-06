# Messaging data policy v1

- Không log request body, prompt, token, attachment URL hoặc lịch sử hội thoại đầy đủ.
- Trace ID là opaque UUID/ID do ingress cấp; không chứa sender ID hay số điện thoại.
- Redis inbound/bundle mặc định TTL ngắn; dedup key giữ 24 giờ.
- SQLite lưu response outbox, LeadDraft và sales outbox để restart không mất lead.
- Operations endpoint chứa PII phải dùng `CHAT_CONVERSATION_CONTROL_KEY`.
- Telegram chỉ gửi summary tối thiểu; không gửi full history hoặc raw media.
- `.env`, `runtime/data/*`, SQLite/WAL và mapping chat ID thật đều bị Git ignore.
- Khi có yêu cầu xóa dữ liệu, phải xóa theo `brand + sender_id` ở session, LeadDraft
  và outbox bằng tool quản trị có audit; không thao tác SQL tay trên production.
- Retention production cần owner chốt trước canary. Đề xuất: inbound 24 giờ,
  response outbox 30 ngày, LeadDraft theo chính sách CRM, dead-letter 14 ngày.
