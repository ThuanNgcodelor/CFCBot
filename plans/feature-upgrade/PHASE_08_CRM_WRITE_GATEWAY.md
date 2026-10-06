# Phase 08 — CRM write gateway có phê duyệt và reconciliation

Trạng thái: **PENDING**  
Ưu tiên: **P2 High Risk**  
Ước lượng: 4–8 ngày  
Phụ thuộc: Phase 03/04/07 `DONE`; có AMIS sandbox hoặc test scope.  
Thay đổi production: Approval mode trước, auto mode sau.

## 1. Mục tiêu

- Tạo/cập nhật lead/contact AMIS từ LeadDraft đã xác nhận mà không ghi trùng/sai.
- Mọi write có approval, idempotency, audit và reconciliation.
- CRM lỗi không làm mất lead trong CFCBot.

## 2. Hiện trạng tận dụng

- AMIS client, public catalog, order/loyalty cache và sync modules đã có.
- Hệ thống hiện chủ yếu read/cache; chưa có customer-facing write contract an toàn.
- LeadDraft/outbox/audit từ Phase 03 là nguồn đầu vào bắt buộc.

## 3. Scope MVP

- Create/update lead hoặc contact theo schema đã xác minh.
- Approval queue trong dashboard.
- CRM write outbox và retry có giới hạn.
- Idempotency key gắn lead/version/operation.
- Reconciliation job so local intent với CRM result.
- Manual resolution cho conflict/duplicate.

Không tạo Sale Order, invoice, inventory reservation hoặc thay đổi loyalty trong MVP.

## 4. Work packages

### WP08.1 — Contract/sandbox discovery

- Xác minh endpoint, required fields, permissions và error semantics.
- Dùng test record/sandbox; không thử trên khách thật tùy ý.
- Mapping local field -> AMIS field có version.

### WP08.2 — Approval policy

- Điều kiện đủ để đề xuất write.
- Người/role được approve/reject.
- Preview payload đã mask.
- Reject/retry/edit tạo audit, không sửa lịch sử.

### WP08.3 — Write gateway/outbox

- Không gọi AMIS trực tiếp trong chat request.
- Idempotency và dedup local/remote nếu API hỗ trợ.
- Retry chỉ cho transient errors.
- Permanent validation/conflict -> manual queue.

### WP08.4 — Reconciliation

- Đọc lại/verify record sau write.
- Trạng thái `pending|approved|sent|confirmed|conflict|failed`.
- Alert record không reconcile.
- Báo cáo daily unresolved conflicts.

## 5. Test bắt buộc

1. Cùng idempotency key retry không tạo duplicate CRM record.
2. Timeout sau remote success -> reconciliation xác định đúng.
3. Validation error không retry vô hạn.
4. Permission/token error tạo alert, không leak secret.
5. Mapping phone/name/area/product đúng Unicode/format.
6. Approval/reject/auth/audit đúng role.
7. CRM outage không mất local lead.
8. Test record cleanup/reconciliation theo policy.

## 6. KPI/gate

- Duplicate record do gateway = 0.
- 100% writes có approval/actor/idempotency/audit.
- 100% canary writes reconcile đúng.
- Conflict có owner và resolution path.
- Không ảnh hưởng latency/reliability chat path.

## 7. Rollout

1. Sandbox/test records.
2. Production dry-run payload preview.
3. Approval mode cho một owner/region.
4. Canary writes số lượng nhỏ có giám sát.
5. Auto mode chỉ cho low-risk operation sau observation.

## 8. Rollback

- Tắt CRM writer; giữ local LeadDraft/outbox.
- Không tự xóa CRM record production; reversal cần human approval.
- Dừng retry khi credential/permission lỗi diện rộng.
- Reconcile pending trước khi resume.

## 9. Exit gate

- Sandbox/canary và reconciliation 100% đúng trong mẫu được duyệt.
- Approval/security/audit review pass.
- Duplicate/conflict drills pass.
- Owner đồng ý phạm vi auto mode, nếu có.

