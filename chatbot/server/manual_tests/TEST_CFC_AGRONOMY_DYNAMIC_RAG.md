# Test thật CFC — Nông học động, không hardcode TC12

## 1. Phạm vi đã đổi

- Crop/stage/symptom chỉ được nhận diện một lần bởi `QueryPlan`; conversation memory không còn danh sách cây riêng.
- Câu hỏi nông học rõ ràng tìm trực tiếp FAQ `category=agronomy` trong Knowledge CFC theo cả câu hiện tại và ngữ cảnh đã nhớ.
- Câu trả lời chỉ trích nội dung từ row có `source_id`, `audience=customer`; bỏ câu xin SĐT/kỹ sư lặp ở cuối nguồn và giới hạn vài câu chính.
- Không có nguồn phù hợp, nguồn mơ hồ, thiếu liều cụ thể hoặc rủi ro cao: không đoán; chuyển Khuyến nông Lê Thanh Đạm `0353 857 516` hoặc Cao Văn Được `0939 852 529`.

## 2. Chuẩn bị

Từ thư mục gốc dự án:

```bash
./bin/stop-all.sh
./bin/start-all.sh
```

Kiểm tra API:

```bash
curl -s http://127.0.0.1:7777/health | jq
```

Nếu vừa sửa Google Sheet/FAQ, chạy workflow sync CFC và xác nhận snapshot/vector/hot cache đều `complete=true` trước khi test.

## 3. Hàm test một cuộc hội thoại sạch

Đổi `sender_id` cho từng nhóm test, hoặc reset session cũ:

```bash
curl -s -X DELETE \
  http://127.0.0.1:7777/admin/customers/cfc/test-agronomy-01/session | jq
```

Gửi câu hỏi:

```bash
curl -s -X POST http://127.0.0.1:7777/api/chat-pipeline \
  -H 'Content-Type: application/json' \
  -d '{
    "brand": "cfc",
    "sender_id": "test-agronomy-01",
    "text": "Sầu riêng giai đoạn nuôi trái non bị rụng hạt chuỗi thì nên bón công thức NPK nào và liều lượng sao?"
  }' | jq '{answer,intent,confidence,fallback_reason,latency_ms}'
```

Xem source/trace thật:

```bash
curl -s \
  http://127.0.0.1:7777/admin/customers/cfc/test-agronomy-01/session \
  | jq '.session.last_trace | {
    source_id,
    agronomy_support_source_ids,
    agronomy_support_intents,
    agronomy_evidence_count,
    agronomy_requires_expert,
    protected_fast_path
  }'
```

## 4. Bộ câu hỏi bắt buộc

| Nhóm | Câu test | Kết quả đạt |
|---|---|---|
| TC12 | Sầu riêng nuôi trái non bị rụng hạt chuỗi, nên dùng công thức nào và liều ra sao? | Có hướng dinh dưỡng thật từ FAQ; không tự tạo kg/gốc; nếu nguồn chưa có liều cụ thể thì đưa hai số khuyến nông. |
| Cây khác | Cây ổi đang ra hoa hay rụng bông thì nên bón gì? | Nhận đúng `crop=ổi`; trả nguyên tắc ra hoa có nguồn; không nói thành sầu riêng. |
| Cây khác | Nhãn nuôi trái non bị méo trái thì dùng phân gì? | Nhận đúng `crop=nhãn`; tìm hướng nuôi trái non; không cần nhánh code riêng cho nhãn. |
| Cây khác | Xoài sau thu hoạch suy cây thì phục hồi sao? | Lấy FAQ phục hồi sau thu hoạch nếu đang có trong snapshot; không bịa thêm sản phẩm/liều ngoài nguồn. |
| Ca rủi ro | Cây mít vàng lá, thối rễ nặng, rễ đen thì xử lý thế nào? | Có thể nêu bước cơ bản có nguồn; vì `risk_level=high` phải kèm chuyên gia. |
| Không đủ nguồn | Cây mắc ca bị triệu chứng lạ, tôi pha ba loại thuốc chung được không? | Không ghép đại một FAQ cây khác; trả ngắn và đưa hai số chuyên gia. |
| Không phải nông học | Tôi muốn mua 5 tấn NPK cho vườn ổi | Chuyển purchase/B2B intake, không trả quy trình nông học. |
| Hỏi vặn | Ngay sau một câu có hướng dẫn: “Thông tin này dựa vào đâu, có thật không?” | Nói là FAQ/cẩm nang có ghi nguồn; không nêu key Redis, tên model hoặc tự rút lại câu có nguồn. |

## 5. Test nhớ ngữ cảnh nhiều lượt

Dùng cùng một `sender_id`:

1. `Nhãn đang nuôi trái non bị rụng, nên bón gì?`
2. `Vườn 6 năm, khoảng 2 ha ở Cần Thơ.`
3. `Vậy liều mỗi gốc bao nhiêu?`
4. `Thông tin này lấy từ đâu?`

Đạt khi:

- Lượt 2 và 3 vẫn giữ `crop=nhãn`, giai đoạn và triệu chứng trước đó.
- Không hỏi lại dữ kiện đã có.
- RAG được tìm bằng cả câu mới và ngữ cảnh đã nhớ.
- Nếu nguồn chưa quy định liều theo tuổi cây/hiện trạng, bot không tự sinh con số và đưa hai đầu mối khuyến nông.
- Lượt 4 mô tả đúng nguồn của câu vừa trả lời; không chuyển sang website mua hàng hoặc FAQ của chủ đề khác.

Các cách hỏi tương đương cũng phải đi cùng một route, không cần nhánh riêng theo từng cây:

- `Liều bao nhiêu một gốc?`
- `Mỗi gốc bón mấy ký?`
- `Bón bao nhiêu mỗi gốc?`
- `Nội dung ở trên tham khảo từ đâu?`

## 6. Kiểm tra độ dài và độ trễ

```bash
curl -s -o /tmp/cfc-agronomy-response.json \
  -w 'HTTP=%{http_code} TOTAL=%{time_total}s\n' \
  -X POST http://127.0.0.1:7777/api/chat-pipeline \
  -H 'Content-Type: application/json' \
  -d '{"brand":"cfc","sender_id":"test-agronomy-speed","text":"Cây ổi ra hoa rụng bông nên bón gì?"}'

jq -r '.answer, "latency_ms=\(.latency_ms)"' /tmp/cfc-agronomy-response.json
```

Mốc đánh giá thực tế:

- Câu lexical nông học khớp từ mức vừa trở lên: kỳ vọng dưới khoảng `1 giây` trên máy local đã warm; route vẫn qua bộ lọc category/source/crop trước khi gửi.
- Câu phải tạo embedding bằng Ollama: có thể khoảng `1–3,5 giây`; quá `3,5 giây` hệ thống chuyển chuyên gia thay vì bắt khách chờ vô hạn. Trace phải cho thấy RAG source, không phải LLM chat tự tạo facts.
- Câu trả lời thông thường nên khoảng `2–4 câu`, ưu tiên dưới `650 ký tự`; ca chuyển chuyên gia có thể dài hơn một dòng vì có hai đầu mối.

## 7. Chạy regression tự động

```bash
.venv/bin/python -m unittest \
  chatbot/server/tests/test_agronomy_dynamic_guidance.py \
  chatbot/server/tests/test_cfc_grounded_memory.py \
  chatbot/server/tests/test_query_understanding.py \
  chatbot/server/tests/test_dialogue_router.py \
  chatbot/server/tests/test_conversation_replay_eval.py
```

Pass khi không có câu trả lời sales lọt vào route agronomy, không dùng source không có `source_id`, không dùng hướng sầu riêng cho ổi/nhãn, và toàn bộ replay/state assertions đều đạt.
