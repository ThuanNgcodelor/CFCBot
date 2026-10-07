# Phase 05 — Media ingest và OCR Product Assistant

Trạng thái: **SECURITY GATE IMPLEMENTED / OCR OFF**
Ưu tiên: **P1 Product**  
Ước lượng: 4–7 ngày  
Phụ thuộc: Phase 02 `DONE`; bộ ảnh test và retention policy đã được duyệt.  
Thay đổi production: Shadow trước, CFC canary sau.

## 1. Mục tiêu

- Nhận attachment descriptor đầy đủ từ Meta/n8n ingress.
- Tải và xử lý ảnh an toàn trước khi URL hết hạn.
- OCR chữ trên bao phân, đối chiếu catalog và trả candidate có evidence/confidence.
- Ảnh tham gia cùng text/location trong một conversation bundle.
- Không dùng ảnh để bịa giá, tồn kho hoặc kết luận hàng thật/giả.

## 2. Hiện trạng

- `ChatPipelineRequest` mới có `input_kind` và `attachment_type`.
- Chưa có URL/source ID/MIME/media metadata contract.
- Chưa có media worker, OCR engine, TTL storage hoặc image evaluation dataset.
- BGE-M3 và catalog retrieval đã có thể tái sử dụng sau OCR normalization.

## 3. Work packages

### WP05.1 — Media contract

Mở rộng `InboundEventV1`/bundle bằng:

```text
attachment_id, type, ephemeral_url, mime_hint
received_at, expires_at, source_platform
download_status, content_hash, media_ref
```

Không truyền raw binary qua chat pipeline JSON nếu có thể dùng media reference.

### WP05.2 — Secure downloader

- Allowlist hostname/scheme Meta được duyệt.
- Chặn localhost/private IP redirect để tránh SSRF.
- Kiểm tra MIME thật, magic bytes, pixel dimensions và max bytes.
- Timeout, redirect limit, decompression-bomb protection.
- Hash/dedup và TTL storage; không dùng filename khách gửi làm path.

### WP05.3 — Image preprocessing/OCR worker

- Xoay EXIF, normalize orientation, resize và contrast có giới hạn.
- PaddleOCR worker riêng, concurrency thấp lúc đầu.
- Timeout/circuit breaker; OCR lỗi không làm mất bundle.
- Lưu OCR text/boxes/confidence đã redact theo policy.

### WP05.4 — Catalog matching

- Normalize thương hiệu, công thức NPK, trọng lượng/quy cách.
- Exact token/regex trước, fuzzy/BGE-M3 sau.
- Candidate có product ID, evidence spans và confidence.
- Không match chắc chắn khi catalog không có.

### WP05.5 — Conversation policy

- High confidence: hỏi xác nhận ngắn trước hành động bán hàng.
- Medium/low: yêu cầu mặt trước rõ hơn/tên sản phẩm.
- Complaint/damage: route CSKH/QA.
- Không tự báo giá/tồn/hàng thật giả từ ảnh.

### WP05.6 — Evaluation/canary

- Bộ ảnh đại diện theo ánh sáng, góc, độ mờ và model điện thoại.
- Ground truth do owner sản phẩm duyệt.
- Shadow không phản hồi ảnh trước.
- Canary CFC sender bucket, chưa mở ZeO.

## 4. Cấu hình dự kiến

```dotenv
MEDIA_INGEST_ENABLED=false
MEDIA_MAX_BYTES=10485760
MEDIA_RETENTION_HOURS=24
MEDIA_DOWNLOAD_TIMEOUT_SECONDS=10
OCR_ENABLED=false
OCR_PROVIDER=paddleocr
OCR_WORKER_CONCURRENCY=1
OCR_SHADOW=true
```

Không commit URL ảnh, token hoặc media artifacts.

## 5. Test bắt buộc

1. Ảnh hợp lệ tải/OCR/match candidate.
2. URL hết hạn -> fallback hỏi lại, không crash.
3. Redirect private IP/localhost -> chặn.
4. MIME giả/decompression bomb/file quá lớn -> chặn.
5. EXIF rotation/ảnh dọc/ngang xử lý đúng.
6. OCR đúng nhưng catalog không có -> không bịa SKU.
7. Ảnh mờ -> confidence thấp + hỏi lại.
8. Text + ảnh lệch thứ tự vẫn cùng bundle.
9. Duplicate attachment hash không OCR lặp ngoài policy.
10. TTL xóa ảnh gốc đúng; audit không chứa PII ngoài policy.

## 6. KPI/gate

- Security downloader tests pass 100%.
- OCR/product candidate precision đạt ngưỡng do owner chốt; ưu tiên precision hơn recall.
- Không unsupported price/stock/authenticity claim.
- P95 OCR nằm trong worker SLO, không kéo API webhook timeout.
- Tỷ lệ hỏi lại và failure quan sát được.

## 7. Rollback

- Tắt `OCR_ENABLED`/`MEDIA_INGEST_ENABLED` độc lập.
- Bundle text vẫn xử lý bình thường.
- Không xóa media metadata cần điều tra trước TTL.
- Khi OCR lỗi diện rộng, chuyển attachment acknowledgment/fallback đã duyệt.

## 8. Đã triển khai

- `MediaInspectRequest/Response` và HTTPS/allowlist/private-host/size gate.
- Chặn loopback/private DNS, scheme không phải HTTPS và file vượt kích thước.
- `MEDIA_INGEST_ENABLED=false`, `OCR_ENABLED=false` production; chưa tải ảnh hoặc
  gọi OCR thật khi provider/dataset chưa được owner duyệt.

## 8. Exit gate

- Dataset/ground truth đủ đại diện.
- Secure ingest + retention review pass.
- Shadow/canary đạt precision và latency gate.
- Complaint route và low-confidence fallback pass.
- Rollback không ảnh hưởng queue/text chat.
