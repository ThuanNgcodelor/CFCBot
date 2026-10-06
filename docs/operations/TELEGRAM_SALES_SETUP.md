# Setup Telegram Sales cho CFCBot (Phase 03)

Trạng thái mặc định là **shadow**: CFCBot tạo LeadDraft và quyết định tuyến nhưng
không gửi Telegram. Không dán bot token hoặc chat ID thật vào Git, issue hay chat.

## 1. Tạo bot và group

1. Mở Telegram, chat với `@BotFather`, chạy `/newbot` và lưu token vào password manager.
2. Tạo group nội bộ cho từng vùng (ví dụ `CFC Sale Cần Thơ`) và một group `CFC Lead Triage`.
3. Add bot vào từng group. Quyền tối thiểu chỉ cần gửi tin nhắn; không cấp admin nếu không cần.
4. Gửi một tin nhắn bất kỳ trong mỗi group để Telegram tạo update.

## 2. Lấy chat ID an toàn

Tạm dừng webhook Telegram của chính bot nếu bot đang dùng webhook, rồi gọi cục bộ:

```bash
curl -sS "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
```

Tìm `message.chat.id`. ID group/supergroup thường là số âm, ví dụ `-100...`.
Không lưu JSON trả về vì có thể chứa thông tin thành viên. Nếu bot đã có webhook,
ưu tiên dùng một bot riêng cho Sales hoặc công cụ quản trị Telegram đáng tin cậy.

## 3. Cấu hình runtime (không commit)

Sao chép mẫu mapping rồi sửa file runtime bị Git ignore:

```bash
cp config/sales_routes.example.json runtime/data/sales-routes.json
chmod 600 runtime/data/sales-routes.json
```

Điền trong `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=<token-from-password-manager>
TELEGRAM_SALES_TRIAGE_DESTINATION=triage
TELEGRAM_SALES_DESTINATIONS_JSON='{"triage":"-100...","sales_can_tho":"-100...","sales_hau_giang":"-100..."}'
SALES_HANDOFF_ENABLED=false
SALES_HANDOFF_SHADOW=true
```

`destination_key` trong `runtime/data/sales-routes.json` phải khớp key của
`TELEGRAM_SALES_DESTINATIONS_JSON`. Khu vực không chắc luôn vào `triage`.

## 4. Test shadow trước

```bash
CFCbot restart
curl -sS http://127.0.0.1:7777/api/messaging/status
```

Gửi synthetic event qua test stack/port 7778. Kiểm tra `lead_drafts` và
`sales_outbox` có trạng thái `shadow`; tuyệt đối chưa có tin trong group thật.

## 5. Pilot có kiểm soát

Chỉ sau khi kiểm tra mapping và template:

1. Dùng một bot/group test riêng.
2. Đặt `SALES_HANDOFF_ENABLED=true`, `SALES_HANDOFF_SHADOW=false`.
3. `CFCbot restart`, gửi đúng một synthetic lead, xác minh chỉ xuất hiện một lần.
4. Kiểm tra sai khu vực đi `triage`; timeout tạo `retry`, không mất lead.
5. Sau pilot mới thay chat ID group thật. Rollback tức thì bằng
   `SALES_HANDOFF_ENABLED=false` và `SALES_HANDOFF_SHADOW=true`.

Lưu ý: Phase 03 không tự ý kích hoạt production. Mapping vùng, PII được phép gửi
và SLA phản hồi phải được chủ hệ thống duyệt trước.
