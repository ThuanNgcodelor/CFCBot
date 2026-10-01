# Kế hoạch khách hàng mới/cũ, tạo đơn CRM và dọn dẹp có kiểm soát

**Ngày lập:** 31/08/2026  
**Phạm vi:** CFC trước, sau đó mới cân nhắc áp dụng cho ZeO  
**Trạng thái:** Chờ chủ hệ thống duyệt. Tài liệu này **không cho phép xoá file, unpublish workflow, tạo khách hay tạo đơn**.

**Kế hoạch tích hợp ngày 08/09/2026:** [CFC Agent và CRM trên Mac M4 16GB](plan/PLAN_CFC_AGENT_VA_CRM_2026-09-08.md) kết nối các Phase A–E và cleanup bên dưới với kiến trúc Agent, đánh giá Qwen 7B, xác minh khách cũ và chống tạo trùng CRM. Đây là đề xuất bổ sung; chưa mở quyền ghi hoặc triển khai live.

## 1. Mục tiêu nghiệp vụ

Khi khách nhắn trên Page CFC, chatbot cần phân biệt được ba việc khác nhau:

1. **Khách cũ:** nhận diện an toàn bằng số điện thoại, dùng dữ liệu CRM phù hợp để hỗ trợ tra đơn hoặc tiếp nhận nhu cầu mua.
2. **Khách mới:** thu thập thông tin tối thiểu để tạo một hồ sơ/lead CRM sau khi khách xác nhận.
3. **Nhu cầu mua hàng:** hiểu sản phẩm, quy cách, số lượng, khu vực; tạo **bản nháp yêu cầu/đơn CRM** sau khi khách xác nhận, rồi chuyển nhân viên kinh doanh xử lý.

Chatbot không tự báo giá, tồn kho, chiết khấu, công nợ, không tự chốt thanh toán và không tự cam kết giao hàng.

## 2. Hiện trạng đã xác minh

| Hạng mục | Trạng thái | Ý nghĩa thực tế |
|---|---|---|
| Danh mục sản phẩm CFC public | Đã có warm/projection | Có thể xác định tên sản phẩm/công thức; không dùng để báo giá hoặc tồn. |
| Tra đơn | Đã có protected cache, yêu cầu mã đơn + SĐT | Chỉ hoạt động khi Full Warm còn mới; cache quá hạn thì phải báo không thể xác minh tức thời, không được đoán. |
| Khách/hội viên | Có nhận diện hồ sơ theo SĐT đã bảo vệ | AMIS hiện không có điểm/hạng/ưu đãi đáng tin để trả khách; không phải lỗi của câu trả lời. |
| Full Warm AMIS | Đã có workflow chunk/stage/commit | Workflow phải được publish/active và chạy thành công theo giờ thì order cache mới không stale. |
| Tạo khách/contact/đơn | **Chưa triển khai** | Hiện hệ thống chỉ đọc/warm CRM, chưa có quyền ghi CRM customer-facing. |
| Nông học | Có RAG/fact/đầu mối Khuyến nông | Chưa có protocol liều lượng được kỹ sư duyệt cho mọi cây/ca; không được để AI tự kê liều. |

## 3. Trải nghiệm đích của khách hàng

```text
Khách hỏi/muốn mua
  -> nhận diện sản phẩm, quy cách, số lượng, khu vực
  -> có SĐT?
       -> chưa có: xin SĐT và tên liên hệ
       -> có: xác thực định dạng, tìm hồ sơ CRM theo kênh bảo vệ
  -> 0 hồ sơ: khách mới
       -> tóm tắt thông tin, xin đồng ý tạo hồ sơ + yêu cầu mua
       -> tạo Contact/Khách hàng hoặc Lead theo quyết định nghiệp vụ
  -> 1 hồ sơ: khách cũ
       -> chỉ dùng đúng hồ sơ, không lộ dữ liệu riêng
  -> nhiều hồ sơ: xin thêm tên/khu vực; không chọn bừa
  -> tóm tắt sản phẩm + số lượng + địa bàn
  -> khách xác nhận lần cuối
  -> tạo bản nháp CRM có idempotency/audit
  -> thông báo đã tiếp nhận, chuyển Trưởng phòng Kinh doanh/nhân viên phụ trách
```

Ví dụ câu trả lời mong muốn sau khi xác nhận:

> Dạ em đã ghi nhận nhu cầu **10 bao NPK Cò Bay 20-20-15, nhận tại Ô Môn**. Nhân viên kinh doanh sẽ kiểm tra giá, hàng và thời gian giao rồi liên hệ lại qua số điện thoại anh/chị đã cung cấp ạ.

Không hiển thị raw CRM, mã nội bộ, giá chưa xác nhận hoặc kết luận “đơn đã tạo” nếu API ghi CRM chưa trả kết quả thành công.

## 4. Các phase đề xuất triển khai

### Phase A — ổn định nền vận hành trước khi thêm chức năng ghi

- Xác nhận **một** workflow AMIS Full Warm là writer chính, chạy lịch 1 giờ/lần và có alert khi fail/stale.
- Giữ snapshot last-known-good; nếu warm lỗi, không xoá dữ liệu tốt đang dùng.
- Đo cache age, record count, index count, tỷ lệ lỗi và latency tra đơn.
- Câu tra đơn cache quá hạn phải nói rõ chưa thể xác minh ngay, đồng thời chuyển đầu mối phù hợp; không báo sai “không tìm thấy đơn”.
- Hoàn tất manual test bằng sender CFC riêng trước khi bật ở Page.

**Tiêu chí xong:** Có ba lần warm liên tiếp thành công; tra đúng/sai mã + SĐT không lộ dữ liệu và không bị stale ngoài ý muốn.

### Phase B — nhận diện khách mới và khách cũ (read-only trước)

- Chuẩn hóa SĐT Việt Nam (`0...`, `+84...`, khoảng trắng/dấu chấm) trước khi lookup.
- Tạo `CustomerResolution` với 4 trạng thái: `not_found`, `one_match`, `ambiguous`, `unavailable`.
- Chỉ trả một xác nhận an toàn như “đã khớp hồ sơ” khi có đúng một match; không lộ tên, địa chỉ, lịch sử mua trước khi cần thiết.
- Lưu goal/slot hội thoại: tên liên hệ, SĐT, khu vực, sản phẩm, quy cách, số lượng. Không để câu “ok” làm mất goal mua hàng.
- Chốt câu hỏi tối thiểu cho khách mới: tên liên hệ, SĐT, tỉnh/huyện hoặc điểm nhận; không đòi dữ liệu không cần thiết.

**Tiêu chí xong:** 0/1/nhiều match và biến thể câu nói SĐT đều có hành vi đúng, không phụ thuộc vào đúng một câu mẫu.

### Phase C — tiếp nhận yêu cầu mua và giỏ hàng hội thoại

- Match sản phẩm theo catalog public; chỉ hiển thị tối đa 3–5 tên phù hợp, không hiển thị mã hàng nếu khách không hỏi.
- Chuẩn hóa bao/kg/tấn; giữ lại sản phẩm, quy cách, số lượng, khu vực qua nhiều lượt.
- Nếu khách hỏi số lượng lớn: tiếp nhận thông tin và hiển thị đầu mối Trưởng phòng Kinh doanh, không tự hứa chiết khấu/hợp đồng.
- Tóm tắt cho khách xác nhận trước bất kỳ thao tác ghi nào.
- Có nút/câu “sửa lại” và “huỷ yêu cầu”, tránh tạo yêu cầu trùng khi khách nhắn lặp.

**Tiêu chí xong:** 10 case paraphrase (mua 10 bao, 200 kg, 5 tấn, đổi sản phẩm, đổi địa bàn, “ok”, “không phải”) giữ đúng state.

### Phase D — adapter ghi AMIS ở chế độ an toàn

- Tạo adapter ghi riêng, không tái dùng public projection hay credential đọc hiện tại.
- Credential scope tối thiểu; internal token/secret chỉ nằm trong secret store, không nằm trong workflow source/log/chat.
- Ban đầu chỉ chạy **dry-run**, ghi audit redacted và trả `draft_preview`; chưa tạo record thật.
- Sau khi duyệt: tạo Contact/Khách hàng/Lead và Sales Order Draft theo mapping AMIS chính thức.
- Idempotency key bắt buộc theo sender + message/draft; retry không được tạo trùng.
- Có endpoint/flow rollback do chủ hệ thống dùng; chatbot không có quyền tự huỷ record thật.

**Tiêu chí xong:** Chạy được sandbox/dry-run với đầy đủ audit; retry 3 lần chỉ cho một draft; PII không xuất hiện ở trace/log public.

### Phase E — handoff và vận hành thật

- Gán người phụ trách theo vùng hoặc mặc định Trưởng phòng Kinh doanh khi chưa có rule.
- Gửi Telegram/n8n nội bộ sau khi CRM write thành công, không gửi dữ liệu nhiều hơn cần thiết.
- Nhân viên nhận được: loại khách (mới/cũ), tên/SĐT đã có consent, nhu cầu sản phẩm/quy cách/số lượng/khu vực, CRM draft ID.
- Page chỉ bật canary cho luồng tiếp nhận, không đưa giá/tồn kho/công nợ/protocol nông học vào cùng đợt.
- Đo conversion: số yêu cầu tiếp nhận, được xác nhận, tạo draft, bị từ chối, lỗi/duplicate, thời gian phản hồi nhân viên.

**Tiêu chí xong:** Owner nghiệp vụ duyệt output, có rollback đã diễn tập và canary không tăng lỗi/duplicate.

## 5. Quyết định nghiệp vụ cần bạn chốt trước Phase D

| Cần chốt | Phương án khuyến nghị | Vì sao |
|---|---|---|
| Khách mới tạo gì trong AMIS? | Tạo **Lead/Contact trước**, chỉ tạo Khách hàng sau khi nhân viên duyệt | Tránh làm bẩn danh mục khách hàng chính thức bằng chat chưa xác minh. |
| Đơn tạo ở trạng thái nào? | Chỉ tạo **bản nháp/yêu cầu bán hàng** | Không biến ý định hỏi giá thành đơn chính thức. |
| Ai là owner mặc định? | Trưởng phòng Kinh doanh hoặc rule theo tỉnh sau này | Có trách nhiệm rõ, không gửi mơ hồ. |
| Trường bắt buộc | Tên liên hệ, SĐT, tỉnh/huyện, sản phẩm/nội dung nhu cầu | Đủ để gọi lại và phân tuyến, tối thiểu PII. |
| Thời điểm ghi CRM | Sau câu khách xác nhận rõ “đồng ý/tạo yêu cầu” | Cần consent và chống tạo nhầm. |
| Nhiều hồ sơ cùng SĐT | Không tự chọn; yêu cầu tên/khu vực | Tránh lộ/ghi nhầm hồ sơ. |

## 6. Bộ test bắt buộc trước khi deploy

1. Khách mới: “Tôi muốn 10 bao 20-20-15 ở Ô Môn” → xin phần còn thiếu → tóm tắt → xác nhận → dry-run đúng một bản ghi.
2. Khách cũ với SĐT `0976...`, `+84976...`, có dấu cách → cùng một kết quả an toàn.
3. SĐT khớp nhiều hồ sơ → hỏi xác nhận, không lộ tên/dữ liệu của cả hai.
4. Khách đổi “10 bao” thành “5 tấn” → chỉ quantity thay đổi, không mất sản phẩm/khu vực.
5. Khách nhắn “ok” sau câu hỏi làm rõ → tiếp tục goal hiện tại, không trả fallback chung.
6. Khách gửi lại cùng tin nhắn hoặc Meta retry → không có draft/lead/đơn trùng.
7. Warm lỗi/stale → tra đơn không trả false-not-found; có handoff phù hợp.
8. Giá/tồn kho/chiết khấu → không bịa, không tự tạo đơn; chỉ tiếp nhận và chuyển Kinh doanh.
9. Prompt injection/đòi dữ liệu khách khác → từ chối an toàn.
10. CRM timeout/403/5xx → không khẳng định đã tạo; audit có lỗi đã redaction.

## 7. Danh sách dọn dẹp — chỉ đề xuất, chờ duyệt

Không mục nào dưới đây được xoá hoặc unpublish trong đợt lập kế hoạch này.

| Mục | Hiện trạng | Đề xuất | Điều kiện bắt buộc trước khi làm | Khuyến nghị hiện tại |
|---|---|---|---|---|
| `workflows/local-n8n/amis_crm_public_sync.workflow.ts` | Workflow public sync cũ/riêng, lịch 30 phút; Full Warm hiện cũng làm sync | **Archive/unpublish trước**, chưa xoá file | Full Warm chạy ổn tối thiểu 3 chu kỳ, catalog/dealer không mất và có đường rollback | Chờ duyệt; không xoá ngay. |
| `chatbot/server/data/amis_real_crm_cache.json` | Cache legacy lớn, `live_crm.py` còn đọc | Chỉ retire sau migration | Audit toàn bộ caller, có nguồn thay thế và test regression | Không xoá. |
| `chatbot/server/domains/amis/live_crm.py` | Có phần legacy đọc file cache; còn được `routes.py`/test tham chiếu | Refactor/tách dần, không xoá trực tiếp | Xác nhận module mới thay thế mọi capability, test pass | Không xoá. |
| `chatbot/plan/archive/2026-08/zeo-cfc-phases/` | Tài liệu lịch sử/acceptance | Đã **archive**, không delete | Giữ nguyên nội dung để đối chiếu, trong khi summary/handoff mới là nguồn hiện hành | Đã hoàn tất archive; không xoá. |
| `chatbot/server/manual_tests/TEST_CFC_REAL_WORLD_PHASE_0_5.md` và `TEST_ZEO_REAL_WORLD_PHASE_0_5.md` | Regression test lịch sử | Giữ làm suite regression | Chỉ archive khi có suite thay thế đã chạy thực tế | Không xoá. |
| `chatbot/server/manual_tests/TEST_DEMO.md` | File đang có thay đổi chưa commit của bạn | Không đụng | Chủ file tự duyệt nội dung demo | Tuyệt đối không xoá/sửa trong cleanup. |

### Câu trả lời cần bạn duyệt trước cleanup

- Có unpublish/archive `AMIS CRM Public Catalog Sync` sau khi Full Warm đã chạy ổn 3 chu kỳ không?
- Có muốn chuyển các tài liệu Phase 0–5 sang `chatbot/plan/archive/` hay giữ nguyên cấu trúc hiện tại?
- Sau khi Phase D hoàn tất, có cho phép retire cache legacy `amis_real_crm_cache.json` và phần caller cũ không? Việc này sẽ cần một đợt migration/test riêng, không làm cùng lúc với triển khai tạo đơn.

## 8. Thứ tự làm khuyến nghị

1. Duyệt lựa chọn nghiệp vụ ở mục 5 và cleanup ở mục 7.
2. Hoàn tất Phase A (đặc biệt Full Warm active + monitoring) trước.
3. Làm Phase B và C, demo read-only/customer intake trên Page test.
4. Duyệt mapping CRM với người quản trị AMIS rồi mới làm Phase D dry-run.
5. Chạy bộ test mục 6; chỉ sau đó mới cho phép ghi CRM thật ở canary.
