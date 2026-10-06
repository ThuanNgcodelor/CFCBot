# Phase 04 — Hoàn thiện human takeover, claim và SLA

Trạng thái: **PENDING**  
Ưu tiên: **P0 Business Safety**  
Ước lượng: 2–4 ngày  
Phụ thuộc: Phase 03 `DONE`  
Thay đổi production: Mở pilot cùng vùng Telegram Phase 03.

## 1. Không làm lại từ đầu

Source hiện đã có:

- Takeover state `pending`, `human`, `closed` trong conversation state.
- Pipeline suppress bot reply khi human takeover active.
- API claim/close được bảo vệ bằng conversation control key.
- Test cơ bản cho request human, admin claim/close và suppress reply.

Phase này hoàn thiện phần còn thiếu: actor identity, durable audit, Telegram/dashboard
claim, SLA, escalation và behavior khi dependency lỗi.

## 2. Mục tiêu

- Sale/CSKH claim một lead/conversation atomically.
- Bot không trả lời chồng nội dung đang được người thật xử lý.
- Có trạng thái, owner, SLA và audit đầy đủ.
- Conversation có thể release/close/resume an toàn.

## 3. State machine mục tiêu

```text
bot_active
  -> handoff_pending
  -> human_claimed
  -> contacted
  -> closed
  -> bot_resumed (khi policy cho phép)

handoff_pending/human_claimed
  -> expired/escalated
```

Transition phải có actor, timestamp, reason, previous/new state và idempotency key.

## 4. Work packages

### WP04.1 — Durable claim/audit

- Claim compare-and-set; hai sale không thể cùng claim.
- Persist owner/source/timestamps/SLA.
- Audit mọi transition.
- Reconcile conversation takeover state với LeadDraft state.

### WP04.2 — Auth và callback

- Không dùng endpoint public không xác thực.
- Telegram callback verify token/signature và map Telegram user -> sale identity.
- Dashboard dùng authenticated admin identity.
- Rate limit và replay protection.

### WP04.3 — Bot policy

- `pending`: gửi một acknowledgment đã duyệt rồi suppress sale-related replies.
- `human`: suppress hoàn toàn luồng liên quan.
- FAQ không liên quan chỉ bật nếu policy được duyệt.
- `closed`: bot resume với context summary, không lặp CTA cũ.

### WP04.4 — SLA/escalation

- `routed -> claimed` và `claimed -> contacted` timers.
- Reminder một lần theo policy.
- Escalation tới owner/triage khi quá hạn.
- Không spam reminder lặp.

### WP04.5 — Operator experience

- Telegram buttons hoặc dashboard actions: Nhận lead, Đã liên hệ, Đóng.
- Hiển thị owner/state/SLA còn lại.
- Manual release/reassign có audit.

## 5. Test bắt buộc

1. Hai sale claim đồng thời -> một người thắng.
2. Callback replay -> không tạo transition lặp.
3. `pending/human` suppress reply đúng.
4. Close/resume không mất conversation context.
5. Quá SLA tạo một reminder/escalation đúng owner.
6. Telegram callback lỗi -> dashboard/manual fallback dùng được.
7. Auth sai/thiếu -> từ chối, không lộ state.
8. Restart API/worker -> claim/audit còn nguyên.

## 6. KPI/gate

- Bot/sale overlap = 0 trong test/pilot.
- Duplicate claim = 0.
- 100% transition có actor/time/reason.
- SLA overdue quan sát được.
- Claim/contact rate và median time-to-claim đo được.

## 7. Rollback

- Tắt callback/button mới, giữ manual dashboard/control API.
- Giữ state/audit; không reset takeover hàng loạt.
- Nếu SLA worker lỗi, tắt reminder nhưng không tắt claim/suppress policy.
- Có runbook giải phóng conversation bị stuck sau khi owner xác nhận.

## 8. Exit gate

- Auth/callback security review pass.
- Claim/SLA/audit test và pilot pass.
- Không bot/sale overlap.
- Manual fallback và rollback diễn tập xong.
- Dữ liệu handoff sẵn sàng cho dashboard Phase 07.

