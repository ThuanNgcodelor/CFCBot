# ZeO/CFC Customer Support Runtime

Runtime Python cho chatbot ZeO và CFC Cò Bay: deterministic routing, conversation state, Shopee matcher, FAQ/RAG, grounding và handoff.

## Kiến trúc

```text
Messenger → n8n → Javis :7777/api/chat-pipeline
                    → message idempotency + sender lease
                    → QueryPlan + ConversationState + Dialogue Router
                    → FAQ/RAG hoặc Shopee tool
                    → Grounding trace + Redis session/history
                    → Messenger reply hoặc human handoff pause
```

Nhánh Web chỉ được dùng khi khách hỏi trực tiếp; chưa nằm trong recommendation/ranking chủ động.

## Kiểm thử hiện hành

```bash
cd /Users/hyden/Documents/David-nguyen/javis-os
LLM_NLU_MODE=off .venv/bin/python -m unittest discover -s chatbot/server/tests -p 'test_*.py' -v
LLM_NLU_MODE=off CHAT_CONVERSATION_MODE=off \
  .venv/bin/python chatbot/server/conversation_replay_eval.py --validation-mode redis_integration
npx n8nac skills validate workflows/local-n8n/zeo_chatbot.workflow.ts
npx n8nac skills validate workflows/local-n8n/cfc_cobay_chatbot.workflow.ts
```

Replay dùng namespace `eval-replay:<run_id>:` riêng cho từng lần chạy, chỉ dọn đúng session test và chặn Telegram trong context evaluation. Report luôn ghi đúng dataset/runtime manifest và validation mode. NLU runtime vẫn có thể cấu hình `shadow`; lệnh baseline ở trên cố định cả hai planner ở `off` để kết quả có thể so sánh.

## Cài đặt

### Tích hợp AMIS CRM Phase 0-2

AMIS được dùng ở chế độ chỉ đọc để tạo hai snapshot công khai: danh mục sản phẩm không giá và danh bạ điểm bán đã được duyệt. Secret chỉ lấy từ environment.

```bash
export AMIS_CLIENT_ID=JavisCFCChatbot
read -s AMIS_CLIENT_SECRET
export AMIS_CLIENT_SECRET

.venv/bin/python chatbot/server/scripts/amis_crm_sync.py status
.venv/bin/python chatbot/server/scripts/amis_crm_sync.py audit
```

Xem checklist field AMIS, gate dữ liệu và lệnh sync tại `chatbot/plan/AMIS_CRM_PHASE_0_2_RUNBOOK.md`.

### Bước 1: Cấu hình Redis password

Mở file `settings.json` và điền password Redis:

```json
{
  "redis": {
    "password": "ĐIỀN_PASSWORD_TỪ_infra/redis/.env"
  }
}
```

### Bước 2: Tạo môi trường Python

```bash
cd /Users/hyden/Documents/David-nguyen/javis-os

# Tạo virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Cài packages
pip install -r requirements.txt
```

### Bước 3: Kéo model embedding về Ollama

Model `bge-m3` là mô hình embedding đa ngôn ngữ tốt nhất, hiểu tiếng Việt rất tốt kể cả không dấu.

```bash
ollama pull bge-m3
```

> **Nếu máy yếu RAM:** Dùng model nhẹ hơn `mxbai-embed-large`:
> ```bash
> ollama pull mxbai-embed-large
> ```
> Sau đó sửa `settings.json`: `"embed_model": "mxbai-embed-large"` và `"embed_dim": 1024`

### Bước 4: Chạy server

```bash
cd /Users/hyden/Documents/David-nguyen/javis-os
source .venv/bin/activate
./bin/start-all.sh
```

Javis bridge chạy tại `http://127.0.0.1:7777`. `/api/chat-pipeline` chỉ miễn đăng nhập cho request localhost.

### Bước 5: Đồng bộ dữ liệu FAQ vào Vector Index

```bash
# Đồng bộ cả ZeO và CFC
curl -X POST "http://localhost:8000/sync?brand=all"

# Hoặc từng brand
curl -X POST "http://localhost:8000/sync?brand=zeo"
curl -X POST "http://localhost:8000/sync?brand=cfc"
```

Quá trình này sẽ tạo embedding cho từng dòng FAQ và lưu vào Redis Vector Index. Chạy mỗi khi cập nhật FAQ mới từ Google Sheets.

---

## Kiểm tra

```bash
# Health check
curl http://localhost:8000/health

# Test tìm kiếm ZeO
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "co ship khong shop", "brand": "zeo"}'

# Test câu không dấu — đây là điểm mạnh chính
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "thom ko ship v", "brand": "zeo"}'

# Test CFC
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "co phan bon npk khong", "brand": "cfc"}'
```

---

## Tích hợp vào n8n

Thêm một node **HTTP Request** vào workflow n8n (sau node Dialogue Manager):

```
Method: POST
URL: http://127.0.0.1:8000/search
Body (JSON):
{
  "query": "{{ $('Loc Dau Vao').first().json.text }}",
  "brand": "zeo",
  "top_k": 5
}
```

Kết quả trả về:
```json
{
  "confidence": "high",
  "score": 0.92,
  "intent": "nationwide_shipping_no_cod",
  "answer": "Dạ ZeO có giao hàng toàn quốc...",
  "answer_mode": "rewrite"
}
```

Nếu `confidence == "high"` hoặc `"medium"` và `answer_mode == "rewrite"` → đẩy qua node `GoiOllamaLocal` để viết lại tự nhiên hơn.

---

## Tóm tắt thay đổi đã làm

### Giai đoạn 1 (đã sửa trong n8n):
- ✅ Fix regex số điện thoại trong `zeo_chatbot.workflow.ts`
- ✅ Fix regex số điện thoại trong `cfc_cobay_chatbot.workflow.ts`
- ✅ Nới lỏng nhận diện địa chỉ (không cần bắt buộc có từ khoá "tỉnh/tp")

### Giai đoạn 2 (Python service này):
- ✅ `embedder.py` — Tạo vector embeddings qua Ollama bge-m3
- ✅ `knowledge_sync.py` — Đọc Redis snapshot → embed → upsert vào Redis Vector Index
- ✅ `rag_search.py` — Semantic search với RediSearch KNN
- ✅ `main.py` — FastAPI với /health, /sync, /search, /rewrite
