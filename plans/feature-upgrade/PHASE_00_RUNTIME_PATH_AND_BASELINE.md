# Phase 00 — Khôi phục lifecycle theo đường dẫn mới và khóa baseline

Trạng thái: **DONE — 06/10/2026**  
Ưu tiên: **Critical / P0**  
Ước lượng: 0,5–1 ngày  
Phụ thuộc: Không  
Thay đổi production: Có, nhưng chỉ trong cửa sổ cutover được duyệt.

## 1. Vì sao phải làm đầu tiên

Repo hiện ở `/home/kali/Works/CFC/CFCBot`, trong khi:

- Docker Compose labels vẫn ghi working directory/config file tại đường dẫn cũ.
- `cfcbot-api` bind mount `runtime/settings.json` từ đường dẫn cũ.
- `/home/kali/.local/bin/CFCbot` và `cfcbot` là symlink gãy về đường dẫn cũ.
- README vẫn hướng dẫn `cd` tới đường dẫn cũ.

Container đang chạy không chứng minh lần restart tiếp theo sẽ an toàn. Không triển khai
tính năng mới trước khi source path và lifecycle command thống nhất.

### Snapshot xác minh ngày 06/10/2026

- `docker`, `ollama`, `cloudflared`: active.
- `javis`: inactive và disabled.
- `cfcbot-api`: healthy; `cfcbot-redis`: healthy; `cfcbot-n8n`: running.
- API/n8n health nội bộ và qua Cloudflare đều trả thành công.
- Symlink `/home/kali/.local/bin/CFCbot` không resolve vì còn trỏ repo cũ.

Kết luận sau cutover: **lifecycle đã được rebind sang repo mới; API/Redis/n8n đã
recreate an toàn và local/public health đều đạt.**

## Bằng chứng hoàn thành

- `CFCbot doctor`, test stack `7778/6380`, chat smoke và production health: pass.
- 252 baseline tests pass trước khi thêm Phase 01–03.
- Docker labels/bind mount API và Redis trỏ `/home/kali/Works/CFC/CFCBot`.
- Redis volume legacy được khai báo `external`, không bị Compose xóa/recreate.
- Báo cáo: `docs/operations/PHASE_00_BASELINE_2026-10-06.md`.

## 2. Mục tiêu

- `CFCbot doctor|test-start|test-stop|status|start|restart|logs` chạy từ repo mới.
- Compose production được recreate từ repo mới mà giữ nguyên n8n data/Redis volume.
- Cloudflare public routes, API `7777`, n8n `5678` và Redis `6379` không đổi.
- Có snapshot thông tin rollback trước khi đụng container hiện hành.
- Ghi baseline kỹ thuật để so sánh các phase sau.

## 3. Không nằm trong phase

- Không sửa business logic chatbot.
- Không sửa/publish workflow n8n.
- Không thay token, model hoặc credential.
- Không xóa container/image/volume legacy.

## 4. Work packages

### WP00.1 — Inventory không lộ secret

- Ghi image digest, container IDs, restart policy, health và Compose labels.
- Ghi tên Redis volume và n8n bind directory; không sao chép nội dung credential.
- Xác nhận `.env` và `runtime/settings.json` tồn tại ở repo mới, chỉ kiểm tra quyền/file.
- Ghi trạng thái `docker`, `ollama`, `cloudflared`, `javis`.

### WP00.2 — Sửa source path

- Cập nhật mọi đường dẫn tài liệu/script hard-code còn trỏ repo cũ.
- Chạy `scripts/bootstrap-command.sh` để tạo lại symlink từ repo mới.
- Re-index CodeGraph hoặc loại index hỏng khỏi local workflow theo chính sách repo.
- Chạy `docker compose config --quiet` với `.env` mới mà không in secret.

### WP00.3 — Test cô lập

- `CFCbot doctor`.
- `CFCbot test-start` trên API `7778`, Redis `6380`.
- Health và chat smoke synthetic.
- `CFCbot test-stop`.

### WP00.4 — Production rebind

- Chọn maintenance window ngắn.
- Lưu image digest hiện tại làm rollback reference.
- Recreate CFCBot Compose project từ repo mới, không xóa volume.
- Xác nhận container labels/bind mounts đã trỏ repo mới.
- Xác nhận local/public health và một synthetic chat request.

### WP00.5 — Baseline

Ghi lại:

- P50/P95 latency chat mẫu.
- Health của API/n8n/Redis/Ollama/Cloudflare.
- Số test pass.
- Tỷ lệ lỗi/fallback trong sample được phép dùng.
- Runtime manifest/image digest/commit SHA.

## 5. File dự kiến tác động

- `README.md`
- `scripts/bootstrap-command.sh`
- Chỉ sửa `scripts/cfcbot` nếu phát hiện assumption đường dẫn không portable.
- `docs/operations/` cho runbook/baseline.
- Không commit `.env`, `runtime/settings.json` hoặc `.codegraph` local database.

## 6. Kiểm thử bắt buộc

1. Symlink `CFCbot` resolve về repo mới.
2. `CFCbot doctor` pass.
3. Test stack không đụng production ports/containers.
4. Production recreate giữ nguyên workflow/data/index Redis.
5. Local `/health` API/n8n trả 200.
6. Public API/n8n health trả 200 qua Cloudflare.
7. Chat pipeline synthetic trả `ok=true` và không error.
8. Reboot/restart rehearsal xác nhận `restart: unless-stopped` hoạt động.

## 7. Rollback

- Không xóa image/container/volume trước khi gate đạt.
- Nếu recreate lỗi, chạy lại image digest cũ với cùng volume/data directory.
- Nếu API lỗi nhưng n8n/Redis ổn, rollback riêng API image.
- Nếu public lỗi, giữ local services và rollback Cloudflare config/service riêng.
- Không phục hồi Javis trừ khi runbook và chủ hệ thống phê duyệt.

## 8. Exit gate

- Tất cả lifecycle command hoạt động từ repo mới.
- Không còn container label, bind mount hay symlink production trỏ repo cũ.
- Local/public health + chat smoke pass.
- Baseline report và rollback evidence đã lưu.
- Không mất n8n workflows, credentials hoặc Redis data.

## 9. Deliverables

- Path migration runbook.
- Baseline report ngày thực thi.
- Docker inventory đã redact.
- Test/restart evidence.
- Quyết định `GO` cho Phase 01.
