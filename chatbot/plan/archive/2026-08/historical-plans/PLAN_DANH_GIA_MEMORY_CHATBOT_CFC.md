# Kế hoạch đánh giá Memory Chatbot CFC theo phạm vi Knowledge hiện có

> **Lưu trữ (08/09/2026):** Kế hoạch lịch sử. Hiện trạng và bộ test hiện hành xem [plan/README.md](../../../README.md).

**Ngày cập nhật:** 26/08/2026  
**Phạm vi:** Chatbot CFC Cò Bay trên Facebook Messenger  
**Nguồn Knowledge chuẩn:** `google_upload/cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv`  
**Trạng thái:** P0 đã triển khai local; chưa deploy workflow/runtime production

## 1. Yêu cầu từ quản lý

> "Câu hỏi thì sếp gửi chị. Chị chỉ tách ra thành các kịch bản khác nhau để xem memory của chat box này ok không."

Mục tiêu đúng của đợt đánh giá này là kiểm tra chatbot có:

1. Nhớ thông tin khách đã cung cấp hay không.
2. Giữ đúng mục tiêu đang xử lý qua nhiều lượt hay không.
3. Tiếp tục tác vụ sau khi khách bổ sung phone, khu vực hoặc mã đơn hay không.
4. Không dùng state sai từ lượt trước để trả lời lượt sau.

Không được chấm chatbot sai chỉ vì nó không trả được tồn kho, điểm thưởng hoặc trạng thái đơn khi các dữ liệu đó không tồn tại trong Knowledge hay tool hiện tại.

Yêu cầu bắt buộc sau khi triển khai: CFC chạy **grounded-only**. Bot chỉ được:

- Trả fact có `source_id` từ Knowledge.
- Trả capability boundary cố định khi nguồn/tool không tồn tại.
- Dùng phong cách chuyên gia nông nghiệp để tiếp nhận và tóm tắt tình huống, nhưng không tự sinh công thức NPK hoặc liều lượng.

## 2. Phạm vi thật của Knowledge CFC

File Knowledge hiện có 19 intent FAQ, chia thành hai nhóm.

### K1 - Có thể trả lời trực tiếp từ CSV

- `opening_hours`
- `product_lines`
- `shipping_methods`
- `buy_online`
- `support_general`
- `address`
- `company_overview`
- `cfc_npk_product_info`
- `cfc_organic_fertilizer_info`
- `cfc_cross_brand_out_of_scope`
- `cfc_company_website`

Với nhóm K1, chatbot phải trả đúng nội dung có nguồn từ CSV. Trả sai intent hoặc thêm fact không có nguồn là FAIL.

### K2 - CSV chỉ hỗ trợ hướng dẫn an toàn hoặc handoff

- `wholesale_dealer`
- `cfc_price_unverified`
- `cfc_dealer_location_request`
- `cfc_order_request`
- `cfc_shipping_to_area`
- `cfc_dosage_usage_review`
- `cfc_crop_consultation_request`
- `cfc_status_check`

Với nhóm K2, chatbot không cần đưa kết quả nghiệp vụ cuối cùng. Chatbot được tính PASS khi:

- Nhận đúng nhu cầu.
- Nhớ và tái sử dụng thông tin khách đã cung cấp.
- Chỉ hỏi slot còn thiếu.
- Trả lời đúng giới hạn Knowledge.
- Không bịa giá, liều lượng, đại lý, trạng thái đơn hoặc chiết khấu.

### K3 - Hoàn toàn chưa có dữ liệu/tool

Knowledge hiện không có:

- Giá cụ thể của từng công thức NPK.
- Tồn kho theo SKU, kho hoặc khu vực.
- Trạng thái xe, trạng thái đơn hàng và dữ liệu ERP/CRM.
- Điểm thưởng, lịch sử mua hàng hoặc cấp đại lý đã xác minh.
- Bảng giá sỉ và mức chiết khấu theo quý.
- Danh bạ đại lý có tọa độ, vùng giao hàng và khoảng cách.
- Công thức NPK hoặc liều lượng riêng theo triệu chứng cây trồng.

Với nhóm K3, câu trả lời đúng phải là **capability boundary**: nói rõ chưa thể tra cứu từ hệ thống hiện tại, giữ lại đầy đủ context và chuyển đúng bộ phận. Đây vẫn là PASS cho memory và grounding.

## 3. Cách chấm mới

Không dùng một điểm tổng duy nhất. Báo cáo phải tách bốn chỉ số.

| Chỉ số | Câu hỏi cần trả lời | Có phụ thuộc Knowledge không? |
| --- | --- | --- |
| `memory_score` | Bot có nhớ goal, slot và follow-up không? | Không |
| `routing_score` | Bot có chọn đúng intent hoặc capability boundary không? | Một phần |
| `grounding_score` | Bot có chỉ nói điều nguồn cho phép không? | Có |
| `task_completion` | Bot có trả được kết quả nghiệp vụ cuối cùng không? | Có; chỉ chấm khi dữ liệu/tool tồn tại |

### Nguyên tắc chấm theo lớp Knowledge

| Lớp | Điều kiện PASS | Không được yêu cầu chatbot |
| --- | --- | --- |
| K1 | Trả đúng fact và source trong CSV. | Thêm thông tin ngoài CSV. |
| K2 | Trả đúng hướng dẫn/handoff, nhớ slot, không hỏi lại dữ liệu đã biết. | Tự báo giá, liều lượng hoặc đại lý cụ thể. |
| K3 | Nói rõ giới hạn, giữ context và tạo/đề nghị handoff đúng. | Tự đoán tồn kho, điểm, đơn hàng hoặc chiết khấu. |

Một clarification hoặc safe fallback được tính PASS nếu phù hợp với dữ liệu thực tế. Không dùng tiêu chí "phải trả lời được mọi câu".

## 4. Điểm baseline đã hiệu chỉnh

### 4.1 Điểm Memory

Memory được chấm riêng trên các lượt nhiều vòng, không chấm các câu độc lập chỉ kiểm tra routing.

| Tiêu chí | Điểm tối đa | Điểm hiện tại | Bằng chứng từ transcript |
| --- | ---: | ---: | --- |
| Giữ đúng slot khách đã nói | 2 | 0,50 | Có lưu phone; area bị lưu thành nguyên câu hỏi; product, quantity và crop không được tái sử dụng ổn định. |
| Giữ đúng active goal | 2 | 0,25 | Không giữ được dealer lookup, inventory check, order tracking hoặc loyalty lookup. |
| Giải quyết follow-up/rút gọn | 2 | 0,25 | Phone gửi riêng không resume tồn kho; "câu sầu riêng" không nối lại tư vấn trước. |
| Không hỏi lại slot đã biết | 2 | 0,25 | Bot tiếp tục hỏi phone, area, crop và stage đã có. |
| State sạch và đổi chủ đề đúng | 2 | 0,00 | Area bẩn tiếp tục lan sang các lượt sau. |
| **Tổng chính xác** | **10** | **1,25/10** | Baseline thủ công từ transcript thật. |

Để báo cáo quản lý dễ đọc có thể làm tròn theo bước 0,5: **Memory hiện tại 1,5/10**.

### 4.2 Độ phủ Knowledge đối với 13 lượt của sếp

| Loại khả năng trả lời | Số lượt | Tỷ lệ | Ý nghĩa |
| --- | ---: | ---: | --- |
| Có đủ dữ liệu để trả kết quả nghiệp vụ trực tiếp | 0/13 | 0% | Các câu của sếp đều sâu hơn FAQ trực tiếp hiện có. |
| Có FAQ để trả lời an toàn/handoff | 6/13 | 46,2% | Có thể xử lý đúng quy trình nhưng không được tự đưa kết quả cụ thể. |
| Cần thêm dữ liệu hoặc tool | 7/13 | 53,8% | Kho, đơn hàng, tích điểm, tọa độ đại lý hoặc chiết khấu. |

Kết quả 0/13 câu trả lời trực tiếp **không phải lỗi chatbot**. Đây là giới hạn phạm vi Hệ thống hiện tại.

### 4.3 Điểm hành vi theo Knowledge hiện có

Trong transcript hiện tại, chỉ khoảng 3/13 lượt có phản hồi gần đúng hướng an toàn ở mức một phần: hỏi đại lý, giao tận nơi và chính sách sỉ. Các lượt còn lại bị route sai, ghép FAQ không liên quan hoặc bỏ mất mục tiêu.

- Tỷ lệ chấp nhận một phần: `3/13 = 23,1%`.
- Điểm hành vi Knowledge-aware tạm tính: **2,3/10**.
- Điểm này đo routing + grounding, không phải khả năng task completion.

## 5. Đánh giá lại 13 lượt theo Knowledge

| ID | Lớp | Kịch bản | Kết quả đúng được chấp nhận | Kết quả hiện tại |
| --- | --- | --- | --- | --- |
| CFC-M01 | K2 | Hỏi giá NPK 20-20-15 có lời chào | Route `cfc_price_unverified`; nhớ công thức; hỏi quy cách/khu vực/phone còn thiếu. Không báo giá. | Ghép địa chỉ và đặt hàng: FAIL routing. |
| CFC-M02 | K2 | Sầu riêng nuôi trái non hỏi công thức và liều lượng | Route crop/dosage review; ghi nhận crop và stage; không tự đưa công thức/liều lượng. | Ghép shipping và hỏi lại crop/stage: FAIL. |
| CFC-M03 | K2/K3 | Mua 10 bao gần chợ Ô Môn, hỏi đại lý gần nhất | Giữ quantity và area; dùng dealer handoff; hỏi phone hoặc làm rõ `NPK Oplus`. Không tự nêu đại lý. | Đúng nhóm dealer nhưng hỏi lại area: PARTIAL. |
| CFC-M04 | K3 | Gửi Live Location, hỏi chỗ bán gần nhất | Giữ `dealer_lookup`; nếu không đọc được tọa độ thì nói rõ giới hạn và hỏi phần còn thiếu. | Mất location và trả shipping chung: FAIL. |
| CFC-M05 | K2 | Định Môn, Thới Lai hỏi đại lý giao tận nhà | Ghi nhận area; kết hợp dealer + shipping handoff; chỉ hỏi phone. | Hỏi lại khu vực đã có: PARTIAL. |
| CFC-M06 | K3 | Đại lý Vĩnh Thạnh hỏi tiến độ đơn hôm qua | Giữ dealer context; nói chưa có công cụ tra đơn; hỏi mã đơn và xác minh phone. | Ghép địa chỉ và support chung: FAIL. |
| CFC-M07 | K3 | Gửi phone và hỏi tích điểm/chiết khấu | Lưu phone; giữ `loyalty_lookup`; nói chưa có nguồn tra điểm và chuyển đúng bộ phận. | Nuốt intent, dùng area bẩn và hứa liên hệ chung: FAIL. |
| CFC-M08 | K3 | Hỏi tồn kho NPK 16-16-8 TE 50kg, cần 5 tấn | Lưu product, package và quantity; nói chưa có tồn kho realtime; hỏi slot còn thiếu để handoff. | Trả shipping + bảng giá: FAIL. |
| CFC-M09 | K3/Memory | Khách gửi riêng phone sau câu tồn kho | Điền phone và resume `inventory_check`; không trả lead acknowledgement độc lập. | Không resume tác vụ: FAIL memory. |
| CFC-M10 | K3/Memory | Hỏi tiếp hàng NPK chuyên lúa đợt 2 | Giữ inventory goal; nói chưa thể xác minh tồn kho; không chuyển sang dosage. | Route thành liều lượng: FAIL. |
| CFC-M11 | K2/Memory | Bổ sung sầu riêng, 100 hecta, Định Môn - Thới Lai | Hợp nhất crop, acreage, area và phone đã có; dùng safe agronomy handoff; không hỏi lại. | Ghép order + wholesale và hỏi lại thông tin: FAIL. |
| CFC-M12 | K3 | Tra đơn `#DH-2026-889`, hỏi xe đã bốc xong chưa | Trích xuất order ID; nói chưa có tool tra trạng thái; xác minh phone và handoff. | Dùng `cfc_status_check` của lead thay cho trạng thái đơn: FAIL. |
| CFC-M13 | K2/K3/Memory | Xin bảng giá sỉ và chiết khấu quý cho đại lý cấp 1 | Dùng wholesale handoff; nhớ phone; xác minh cấp đại lý; không tự nêu mức chiết khấu. | Đúng hướng chung nhưng hỏi lại phone/crop: PARTIAL. |

## 6. Những kịch bản thực sự dùng để chấm Memory

Không nên coi cả 13 lượt là 13 bài memory độc lập. Nên gom thành các cuộc hội thoại sau:

1. **Dealer lookup flow:** CFC-M03 → CFC-M04 → CFC-M05.
2. **Order và đổi mục tiêu sang loyalty:** CFC-M06 → CFC-M07.
3. **Inventory slot-resume flow:** CFC-M08 → CFC-M09 → CFC-M10.
4. **Agronomy resume sau nhiều chủ đề:** CFC-M02 → CFC-M11.
5. **Dealer context và chính sách sỉ:** CFC-M06/CFC-M07 → CFC-M13.

CFC-M01, CFC-M02 lượt đầu, CFC-M08 lượt đầu và CFC-M12 chủ yếu kiểm tra routing/grounding, không đưa vào mẫu số memory nếu chạy độc lập.

## 7. Rubric Memory 10 điểm cho từng flow

| Tiêu chí | Điểm tối đa | Điều kiện đạt tối đa |
| --- | ---: | --- |
| Confirmed slots | 2 | Phone, area, product, quantity, crop, stage và order ID được lưu chính xác. |
| Active goal | 2 | Giữ đúng dealer, inventory, agronomy, order hoặc loyalty goal. |
| Follow-up resolution | 2 | Hiểu câu rút gọn và phone gửi riêng theo tác vụ đang chờ. |
| Known-slot reuse | 2 | Không hỏi lại slot đã xác nhận. |
| State hygiene/topic switch | 2 | Không lưu text bẩn; đóng/mở goal đúng khi khách đổi chủ đề. |

Điểm memory không bị trừ chỉ vì tool chưa thể tra kho hoặc đơn hàng.

## 8. Trạng thái cập nhật bộ replay

### Phase A - Gắn lớp Knowledge cho từng case - Đã triển khai

Mỗi replay cần có:

- `knowledge_class: K1 | K2 | K3`
- `expected_behavior: direct | safe_handoff | capability_boundary`
- `task_completion_applicable: true | false`
- `risk_level`

### Phase B - Mở rộng scorer kiểm tra memory - Đã triển khai phần P0

Mở rộng `server/conversation_replay_eval.py` để hỗ trợ:

- `active_goal`
- `confirmed_slots`
- `slot_absent`
- `pending_slots_exact`
- `capability_boundary_required`

`source_freshness_required` chưa bật vì CSV hiện chỉ có metadata cập nhật ở cấp FAQ, chưa có contract freshness cho tồn kho, giá, đơn hàng hoặc chính sách quý.

### Phase C - Xuất báo cáo bốn chỉ số - Đã triển khai

Mỗi lần chạy cần báo cáo riêng:

1. Memory score.
2. Routing score.
3. Grounding score.
4. Task completion trên các case có dữ liệu/tool.

Không gộp case K3 vào tỷ lệ task completion, vì hệ thống chưa có khả năng hoàn thành tác vụ đó.

### Phase D - Gate trước khi thử trên Page - Local đạt, live còn chờ

- Memory score tối thiểu 8/10.
- Known-slot repeat rate bằng 0%.
- Dirty-state contamination bằng 0.
- Active-goal resume đạt ít nhất 95%.
- K1 source correctness đạt 100%.
- K2 safe-handoff correctness đạt ít nhất 95%.
- K3 unsupported claim bằng 0.
- Clarification hợp lý được tính PASS WITH CONDITIONS.

## 9. Thứ tự cải tiến và trạng thái

### P0 - Có thể làm với Hệ thống hiện tại - Đã triển khai local

- Sửa cách nhớ goal và confirmed slots.
- Không hỏi lại phone/area/crop đã có.
- Chặn area bẩn.
- Route đúng K2 và K3.
- Thêm capability-boundary response cho kho, đơn hàng, loyalty và chiết khấu.
- Không yêu cầu chatbot trả dữ liệu chưa tồn tại.

### P1 - Muốn hoàn thành tác vụ nghiệp vụ - Chưa triển khai

Cần bổ sung nguồn riêng, không nhét dữ liệu biến động vào FAQ tĩnh:

- Inventory adapter cho tồn kho.
- Order/ERP adapter cho trạng thái đơn và xe.
- CRM/loyalty adapter cho tích điểm và cấp đại lý.
- Dealer directory có tọa độ và vùng giao hàng.
- Pricing/promotion source có ngày hiệu lực.

### P2 - Nâng chất lượng hiểu ngôn ngữ - Một phần

- Structured extraction cho công thức NPK, quy cách, quantity, crop, stage và order ID: đã triển khai deterministic.
- Ollama shadow/canary sau khi state contract và grounding gate ổn định.

## 10. File đã cập nhật trong đợt P0

- `server/eval_conversation_replays.jsonl`: thêm gold conversations và Knowledge class.
- `server/conversation_replay_eval.py`: mở rộng state assertions và cách tính điểm.
- `server/tests/test_conversation_replay_eval.py`: regression cho scorer.
- `server/query_understanding.py`: entity/intent CFC.
- `server/dialogue_router.py`: active goal và capability route.
- `server/chat_pipeline.py`: slot resume và state hygiene.
- `server/grounding_policy.py`: chặn claim K3 thiếu nguồn.
- `workflows/local-n8n/cfc_cobay_chatbot.workflow.ts`: giữ payload Live Location.

Ngoài danh sách trên đã thêm `server/tests/test_cfc_grounded_memory.py` để khóa các lỗi từ transcript thật.

## 11. Mẫu báo cáo ngắn gửi quản lý

> Knowledge CFC hiện có 19 intent FAQ, chủ yếu trả thông tin chung và hướng dẫn chuyển nhân viên. Baseline trước sửa của transcript sếp là Memory 1,25/10 vì bot không giữ goal/slot và để area bẩn. P0 local đã bổ sung confirmed slots, active goal, capability boundary và chế độ grounded-only. Bộ replay hiện có 16 flow/31 lượt và đạt 31/31 ở chế độ degraded-local; Redis live chưa được xác minh trong môi trường chạy này. Bot không tự báo tồn kho, trạng thái đơn, điểm, chiết khấu, đại lý cụ thể hoặc liều lượng khi chưa có nguồn/tool.

## 12. Quyết định còn cần duyệt

1. Duyệt bộ câu trả lời capability boundary trước khi thử trên Page.
2. Duyệt tài liệu kỹ thuật nông nghiệp nào được phép làm nguồn cho công thức/liều lượng.
3. Duyệt adapter nghiệp vụ nào làm trước: inventory, order, CRM/loyalty, dealer directory hay pricing.
4. Chạy replay với Redis/Ollama/runtime thật trước khi deploy production.
5. Deploy workflow CFC vẫn do chủ dự án thực hiện sau khi duyệt kết quả live.

## 13. Kết quả triển khai P0 ngày 26/08/2026

### Grounded-only và chống bịa

- CFC không dùng LLM multi-intent để ghép hai FAQ độc lập.
- CFC không dùng LLM assist để thay đổi response path.
- CFC không dùng `synthesize_cskh_answer` để viết lại câu RAG.
- CFC không gọi `reason_and_answer_cskh` khi RAG thiếu nguồn.
- RAG CFC chỉ được trả khi có `source_id`; nếu không có, bot trả `cfc_grounded_fallback` và nói rõ không tự suy đoán.
- Các intent kho, đơn hàng, loyalty và chính sách sỉ trả safe fallback với `fallback_reason` cụ thể.

### Memory và hiểu ngữ cảnh

- State schema v3 có `confirmed_slots`, `active_goal`, `pending_request` và `last_capability_boundary`.
- Area chỉ lưu cụm địa bàn ngắn; không lưu nguyên câu hỏi.
- Phone gửi riêng resume goal đang chờ thay vì rơi vào acknowledgement chung.
- Topic switch giữa order, loyalty, inventory và agronomy đổi active goal nhưng giữ slot đã xác nhận.
- Agronomy intake nhắc lại crop, stage, symptom, acreage và area; chỉ hỏi slot còn thiếu.

### Live Location

- Workflow CFC đọc `payload.coordinates.lat/long` từ Messenger.
- FastAPI nhận `input_kind`, `attachment_type`, `latitude`, `longitude`.
- Bot xác nhận đã nhận location nhưng không tự nêu đại lý gần nhất khi chưa có dealer directory.

### Kiểm thử

- Unit test: **78/78 PASS** với `LLM_NLU_MODE=off`.
- Embedded JavaScript trong workflow: **2/2 block parse thành công**.
- Conversation replay: **16/16 flow, 31/31 turn PASS**, source coverage **100%**.
- Điểm replay local: Memory **10/10** (16 lượt có state assertion), Routing **10/10** (31 lượt), Grounding **10/10** (25 lượt), Task completion **100%** trên 2 lượt K1 có dữ liệu trực tiếp.
- Replay được gắn đúng nhãn `degraded_local_pipeline_replay` vì Redis `127.0.0.1:6379` bị sandbox chặn; đây chưa phải bằng chứng live production.
- TypeScript `tsc` chưa xác minh được vì package không có trong local npm cache; không tự tải dependency hoặc deploy.
