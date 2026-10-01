# Audit live và kế hoạch nâng cấp chatbot ZeO / CFC

> **Lưu trữ (08/09/2026):** Tài liệu audit tại thời điểm 28/08/2026. Dùng để đối chiếu lịch sử; hiện trạng mới xem [plan/README.md](../../../README.md).

Ngày kiểm tra: 2026-08-28  
Phạm vi: Javis OS, FastAPI chatbot, n8n live, Redis, Google Sheet, dữ liệu local, AMIS CRM  
Nguyên tắc của đợt kiểm tra: chỉ đọc trạng thái live; không sửa logic chatbot, không push/sync/activate/deactivate workflow.

## 1. Kết luận điều hành

Chatbot hiện không thiếu dữ liệu theo nghĩa đơn giản. Redis, vector và hot-cache đều đang có dữ liệu mới. Vấn đề chính nằm ở tầng hiểu ý, chọn nguồn, kiểm chứng mệnh đề và ghi dấu vết provider/revision.

Các kết luận quan trọng nhất:

1. FastAPI live đang chạy từ working tree hiện tại, không phải một revision Git sạch có thể tái tạo chính xác.
2. Cả 7 workflow được n8n quản lý đều đang `active=true` trên n8n live, bao gồm đồng thời hai workflow AMIS có thể ghi đè cùng snapshot.
3. Redis FAQ, catalog và vector hiện đã đồng bộ về số lượng/hash; hot-cache thật sự trả được kết quả.
4. Tuy nhiên hot-cache đang chọn sai intent ở các câu rất cơ bản. Dữ liệu đúng nhưng ranking/intent sai vẫn làm chatbot trả lời sai.
5. Câu trả lời sầu riêng dài không được grounded từ FAQ hoặc CRM. Nó được sinh bởi nhánh AI nông học từ một prompt yêu cầu model tự xây quy trình và chính sách.
6. Trace lịch sử ghi `ollama:cfc_agronomy`, nhưng đây là nhãn hard-code. Provider/model thật không được lưu, nên không thể kết luận trung thực là Groq hay Ollama.
7. AMIS có credential nhưng direct audit đang timeout/500. Endpoint báo `LIVE_AMIS_API` không chứng minh mỗi câu đang gọi realtime, vì lookup hiện đọc local JSON cache.
8. Không thể “hô biến” chatbot thành trí tuệ tổng quát chỉ bằng đổi model. Muốn bot ổn định cần khóa nguồn dữ kiện, bộ nhớ tác vụ, claim ledger, verifier, realtime tools và eval/rollout có cổng chặn.

Mức rủi ro hiện tại: **đỏ đối với tư vấn nông học, chính sách thương mại, AMIS raw warm và khả năng truy xuất nguồn**.

## 2. Trả lời 7 câu hỏi audit live

### 2.1 Revision nào đang deploy thực tế?

Đã xác minh:

- FastAPI đang nghe cổng `7777` bằng Uvicorn `--reload`.
- Runtime bridge báo đang load trực tiếp:
  - `chatbot/server/chat_pipeline.py`
  - thông qua `server/legacy_javis_runtime.py`
- Git branch: `main`.
- Git HEAD: `18f0f9ea81dbbc9e2f144d2d045cea08f0e676c7`.
- Commit: `refactor: replace Ollama-specific calls with unified AI provider abstraction and dynamic model routing`.
- Worker hiện tại khởi động sau thời điểm sửa các file chatbot, nên đang load working tree bẩn hiện tại.

Fingerprint các file runtime chính tại thời điểm audit:

| File | SHA-256 |
|---|---|
| `server/main.py` | `542d24b518f474ea1447c6286590faeb58de02be040b8ddc9a07582ac5da2563` |
| `server/legacy_javis_runtime.py` | `bb29d32927a81a9fbd64aeddc50a7bb3f10154582063afa3acb6392ef8a12d76` |
| `chatbot/server/chat_pipeline.py` | `65587001bfd300af3fa3905343ff5850c5280fbbdfe9d2cebc3331a94e49e3fe` |
| `chatbot/server/ai_engine.py` | `004227b1c1a662b743362745509730a675ce22f188ede202543483b5e77b3c0e` |
| `chatbot/server/query_understanding.py` | `16d885bfc499aa339c8340b2ba636c045754c3d1d211c35eb24c3c103529df72` |

Kết luận: revision deploy thực tế là **HEAD `18f0f9e` cộng với các thay đổi chưa commit trong working tree**, không phải riêng commit `18f0f9e`. Hiện chưa có endpoint `runtime_revision` ghi đủ Git SHA, dirty flag và hash file, nên không thể tái tạo tuyệt đối một câu trả lời lịch sử.

Rủi ro cấu hình:

- `chatbot/server/settings.json` đang tồn tại trong working tree nhưng được stage để xóa khỏi Git.
- Runtime vẫn đọc file này và file chứa cấu hình provider/credential.
- Nếu deploy/checkout theo trạng thái Git mà không có cơ chế secret riêng, runtime có thể đổi hành vi hoặc mất cấu hình.

Việc phải làm: tạo một `runtime_manifest` khi boot gồm Git SHA, dirty flag, hash các module/prompt, config version, workflow ID và thời điểm khởi động. Mỗi response/history phải lưu manifest ID.

### 2.2 Workflow nào active trên n8n live?

Nguồn kiểm tra: environment `local-n8n-2`, target `local-n8n-3`, host live `https://n8n.dinhduongcantho.io.vn`, project `Personal`.

Tất cả 7 workflow sau đang active trên live:

| Workflow | ID | Active live | Tình trạng đáng chú ý |
|---|---|---:|---|
| AMIS CRM Full Warm | `QLY0cLK5tqcx3KY6` | Có | Local drift; chạy mỗi giờ; xử lý raw CRM |
| AMIS CRM Public Catalog Sync | `zksntDfjt5rhhbOW` | Có | Chạy mỗi 30 phút |
| CFC Cò Bay chatbot | `uJOo6NQO2mJZhUAr` | Có | Không thấy drift tại lúc kiểm tra |
| CFC knowledge sync | `92I5floRW5MElgu5` | Có | Remote drift/conflict |
| Chatbot Operations Alert | `f2IjxVj9sW3KQRAw` | Có | Remote drift |
| ZeO chatbot | `d7fctbMhVUmhrNG0` | Có | Không thấy drift tại lúc kiểm tra |
| ZeO knowledge sync | `DhrLUsDsldhxtTdX` | Có | Remote drift/conflict |

Execution gần nhất cho thấy:

- CFC/ZeO knowledge sync vẫn chạy mỗi 5 phút và được n8n đánh dấu `success`.
- AMIS Public Sync vẫn chạy mỗi 30 phút.
- AMIS Full Warm vẫn chạy mỗi giờ.
- CFC chatbot có execution trùng thời điểm câu sầu riêng 17:33 giờ Việt Nam.

Lưu ý: `success` của n8n hiện không đồng nghĩa toàn bộ pipeline thành công. Nhiều HTTP node dùng cơ chế continue-on-error, metadata `last-success` còn được ghi trước khi vector/hot-cache refresh hoàn tất. CFC/ZeO chatbot cũng có thể gửi fallback chung dù FastAPI lỗi.

Việc phải làm:

- Chỉ công nhận sync thành công khi đủ ba checkpoint: `snapshot_written`, `vector_rebuilt`, `hot_cache_refreshed`.
- Error output phải đi nhánh cảnh báo, không đi chung nhánh gửi trả lời khách.
- Bổ sung guard duplicate/takeover cho CFC giống ZeO.
- Không để cả hai AMIS writer cùng active sau khi chọn kiến trúc chính thức.

### 2.3 Redis đang chứa snapshot/hash nào?

Redis live kết nối thành công, `PING=true`, tổng số key tại thời điểm kiểm tra là 135.

| Key/dataset | Số bản ghi | Snapshot hash | Cập nhật UTC | TTL |
|---|---:|---|---|---:|
| `zeo:kb:basic:active` | 66 | `b538190f` | 2026-08-28 16:05:20 | không hết hạn |
| `cfc:kb:basic:active` | 47 | `2f1f2e28` | 2026-08-28 16:06:01 | không hết hạn |
| ZeO Shopee catalog | 52 | khớp local sau chuẩn hóa | cùng đợt sync | không hết hạn |
| ZeO Web catalog | 20 | khớp local sau chuẩn hóa | cùng đợt sync | không hết hạn |
| `amis:public:products:active` | 932 | `51dce0d2a99e9ce55c9438c85824fed0c5fd7f19aff14093ae994ef11b9ee8d8` | 2026-08-28 16:02:05 | không hết hạn |
| `amis:public:sales-locations:active` | 276 | `709a81500900405650c486511040002bec396067d48d0c92094a92d2f1233070` | 2026-08-28 16:02:05 | không hết hạn |

Metadata Redis tương ứng khớp hash, record count và timestamp của snapshot active.

Timestamp AMIS Redis khớp chính xác thời điểm AMIS Full Warm kết thúc, không khớp thời điểm Public Sync kết thúc. Vì vậy snapshot AMIS đang phục vụ tại lúc audit có bằng chứng mạnh là do **Full Warm** ghi.

### 2.4 Google Sheet có khớp file local không?

Kết quả:

| Dataset | Kết luận |
|---|---|
| CFC FAQ Google Sheet ↔ CSV local | Khớp tuyệt đối 47/47 sau chuẩn hóa |
| CFC FAQ Google Sheet ↔ Redis | Khớp tuyệt đối 47/47 |
| ZeO FAQ local ↔ Redis | Khớp 66/66 bản ghi dành cho khách; chỉ khác format ngày |
| ZeO Shopee local ↔ Redis | Khớp 52/52 sau bỏ timestamp sync |
| ZeO Web local ↔ Redis | Khớp 20/20 sau bỏ timestamp sync |

Giải thích con số ZeO:

- Workbook `ZeoN8n.xlsx` có 82 dòng FAQ thật.
- Workflow chỉ nhận các dòng active, đúng brand, có answer/examples và `audience=customer`.
- Sau lọc còn 66 dòng, đúng bằng Redis và vector index.

Mức độ xác minh:

- CFC Sheet export mở được trực tiếp và đã so sánh byte/data sau chuẩn hóa.
- ZeO FAQ và Shopee Sheet yêu cầu quyền, export trực tiếp trả 401. Vì vậy kết luận ZeO là xác minh gián tiếp rất mạnh: local normalized khớp Redis, Redis vừa được workflow live sync thành công. Muốn đóng hoàn toàn mục này cần cấp quyền read-only hoặc export bằng service account rồi so hash nguồn.

### 2.5 Vector và hot-cache đã refresh chưa?

Vector index live:

| Index | `num_docs` | Redis doc keys | Đã index | Failure |
|---|---:|---:|---:|---:|
| `zeo:vec:faq` | 66 | 66 | 100% | 0 |
| `cfc:vec:faq` | 47 | 47 | 100% | 0 |

Kết luận: **vector hiện đã khớp snapshot Redis**.

Hot-cache cũng đang phục vụ thật. Hai truy vấn read-only qua `/search` trả HTTP 200:

- CFC dùng `in_memory_lexical`.
- ZeO dùng `redis_vector_knn`.

Nhưng kết quả cho thấy một lỗi chất lượng nghiêm trọng:

- “Công ty CFC là công ty gì?” bị chọn intent `address`; intent đúng `company_overview` chỉ đứng thứ hai.
- “ZeO là thương hiệu gì?” bị chọn `brand_slogans`; `company_mission` và catalog đứng sau.

Kết luận đúng không phải “cache lỗi” mà là: **cache mới và chạy được, nhưng intent/reranking không đủ tốt**. Đây là bằng chứng cụ thể rằng tăng dữ liệu hoặc refresh vector một mình không làm bot thông minh hơn.

### 2.6 Câu lịch sử được Groq, Ollama hay revision khác sinh?

Đã tìm thấy bản ghi đúng trong Redis history:

- Thời điểm: `2026-08-28T10:33:44.477852+00:00`, tức 17:33:44 giờ Việt Nam.
- Intent cuối: `cfc_dosage_usage_review`.
- QueryPlan: `cfc_agronomy_review_request`.
- Semantic plan: `agronomy`.
- Conversation orchestrator: `agronomy_followup`.
- Trace source: `ollama:cfc_agronomy`.
- `ollama_powered=true`.
- `fallback_reason=AGRONOMY_REQUIRES_EXPERT_REVIEW`.
- History record có `revision=2`.

Điều có thể khẳng định:

- Câu trả lời do `consult_cfc_agronomy_with_ai()` sinh và được pipeline gửi thẳng cho khách.
- Nó không phải đáp án trực tiếp từ Redis CRM hoặc một FAQ row.
- CRM snapshot chỉ được dùng để lấy/tìm tên và mã sản phẩm; CRM không có phác đồ bón, liều kg/ha hoặc chính sách 5–10 ha.

Điều **không thể** khẳng định từ trace hiện tại:

- `ollama:cfc_agronomy` là chuỗi hard-code khi có bất kỳ AI answer nào, không phải provider thật.
- `generate_ai_text()` trả về provider nhưng `consult_cfc_agronomy_with_ai()` bỏ trường đó và chỉ trả text.
- `revision=2` là revision của session/history, không phải Git revision hoặc prompt revision.
- Không có persisted provider, model, prompt hash hoặc runtime manifest cho lượt đó.

Vì cấu hình ưu tiên Groq và code có fallback qua nhiều provider, câu này có thể do Groq, OpenRouter hoặc Ollama sinh tùy credential/lỗi tại đúng thời điểm. Không còn log bền vững để phân biệt. Kết luận trung thực là: **nhánh AI nông học sinh; provider/model cụ thể không thể chứng minh**.

Nguyên nhân câu trả lời bịa/chắp vá:

1. Prompt tự gọi model là “Kỹ sư Nông nghiệp” và yêu cầu phân tích sinh lý cây.
2. Prompt bắt buộc nêu giá xuất xưởng, xe tải, khảo sát đất cho diện tích từ 5/10/100 ha, dù nguồn không có chính sách này.
3. Danh sách công thức/công dụng được hard-code trong `ai_engine.py`; nếu CRM không match sản phẩm, code vẫn đưa mô tả hard-code vào “danh mục thực tế”.
4. Pipeline gắn một `source_id` không rỗng cho output LLM.
5. `grounding_policy.py` hiện coi bất kỳ `source_id` không rỗng nào là grounded.
6. `AGRONOMY_REQUIRES_EXPERT_REVIEW` chỉ là nhãn trace; nó không chặn việc gửi câu trả lời chưa duyệt.

Các chi tiết như liều `150/180/200/300 kg/ha`, giai đoạn `0–6/6–12/12–24 tháng`, “đồng hành thu hoạch”, “bảo hành chất lượng” không có trong CSV CFC hiện tại.

### 2.7 Credential/internal token và AMIS API live

Đã xác minh an toàn, không in giá trị secret:

- AMIS client ID: có cấu hình.
- AMIS client secret: có cấu hình.
- Bộ credential được endpoint đánh dấu configured.
- Internal token: **chưa cấu hình**.
- `pilot_approve_all=true`.
- Public allowlist count: `0`.
- Public snapshot hiện có 932 sản phẩm và 276 điểm bán.

Direct AMIS audit không đạt:

- `POST /admin/amis/audit` trả HTTP 500.
- CLI audit dừng vì `httpx.ReadTimeout` khi lấy customers.
- Route không bắt riêng lỗi timeout nên biến lỗi mạng/API thành 500 thô.

Endpoint `/admin/amis/live-status` báo `LIVE_AMIS_API`, nhưng cách tính mode chỉ dựa trên việc credential có tồn tại. Các lookup trong `live_crm.py` hiện đọc `data/amis_real_crm_cache.json` đã nạp vào RAM, không gọi AMIS realtime cho mỗi câu. Vì vậy tên trạng thái hiện gây hiểu nhầm.

Rủi ro bảo mật/vận hành:

- Full Warm đang active và có secret nhúng trong source workflow; secret cần revoke/rotate.
- Full Warm tải raw Customers/Products/SaleOrders, khiến PII và dữ liệu đơn hàng có thể nằm trong n8n execution history.
- Hai workflow AMIS cùng ghi các key public, có thể đè/race nhau.
- `pilot_approve_all=true` cộng allowlist rỗng làm 276 location được public theo điều kiện rộng, không phải duyệt từng điểm.
- Chưa có internal token. Nếu sau này bật token mà workflow không gửi header, sync sẽ 403; nếu không bật, thiếu lớp bảo vệ nội bộ.

## 3. Chatbot hiện có bao nhiêu ngữ cảnh?

“Bao nhiêu ngữ cảnh” cần tách thành bốn lớp:

| Lớp | Hiện trạng |
|---|---|
| Redis history | Tối đa 50 record/session, TTL 30 ngày |
| Conversation state | Chỉ giữ 6 lượt gần nhất; bot reply bị cắt 600 ký tự |
| Conversation orchestrator | Cấu hình dùng tối đa 6 lượt gần nhất, cộng summary/entities/tool results |
| CFC semantic planner | Chỉ dùng 2 lượt gần nhất |
| AI nông học | Không nhận lịch sử hội thoại; chỉ nhận câu hiện tại, crop/area/district và catalog động |

Ngoài raw turns, state còn có `active_goal`, `confirmed_slots`, `active_entities`, `last_products_shown`, `last_tool_results`, `pending_request`, `topic_stack` và summary ngắn.

Điểm cần hiểu: Redis lưu 30 ngày không có nghĩa model đọc 30 ngày. Mỗi tầng tự cắt context khác nhau. Lỗi hiện tại chủ yếu do **ngữ nghĩa giữa các tầng không đồng nhất** và **không có claim memory**, không phải thiếu context window của model.

## 4. CFC và ZeO hiện trả lời được gì?

### 4.1 CFC

CFC FAQ có 47 intent, 350 câu ví dụ, trong đó 18 intent nông học. Nó trả lời khá tốt khi câu hỏi map đúng một intent và answer đã được duyệt.

Phù hợp:

- thông tin công ty, địa chỉ, nhóm sản phẩm;
- FAQ sản phẩm/phân bón đã có answer;
- một số hướng dẫn nông học đã ghi trong handbook;
- thu thập SĐT/khu vực để chuyển người thật;
- giới hạn an toàn khi giá/tồn kho/đơn hàng chưa xác minh, nếu route đi đúng guard.

Chưa đủ:

- trạng thái đơn realtime;
- ATP/tồn kho số lượng lớn realtime;
- loyalty/điểm/hạng;
- giá/chiết khấu theo khách/đại lý;
- GPS/đại lý gần nhất có khoảng cách;
- công nợ hoặc dữ liệu bên thứ ba;
- phác đồ nông học claim-level có nguồn;
- phản vấn “nguồn đâu/dữ liệu có thật không”.

Bộ đánh giá cũ có 14 case, điểm trung bình 5.00/10, chỉ 2 PASS. Nếu chỉ xét FAQ tĩnh hiện tại, không case nào đủ toàn bộ expected output; khoảng 8 case có dữ liệu một phần. Cần chạy lại real pipeline sau khi khóa nguồn và sửa route, không được lấy semantic similarity làm bằng chứng đã pass nghiệp vụ.

### 4.2 ZeO

ZeO có 82 FAQ raw nhưng 66 FAQ customer đang active, 52 Shopee SKU và 20 Web SKU.

Phù hợp:

- danh mục ZeO/PANO/Oplus;
- giá/link theo snapshot Shopee;
- mua hàng, ship, sỉ và xin liên hệ;
- complaint/đổi trả/review xấu;
- thông tin thương hiệu/sản phẩm nếu intent xếp hạng đúng.

Không nên trả như realtime nếu chưa có tool:

- tồn kho Web/ATP;
- tình trạng đơn hàng;
- CRM khách cũ;
- điểm/chiết khấu cá nhân;
- đại lý gần nhất theo GPS.

## 5. Kiến trúc đích: thông minh nhưng không bịa

Mục tiêu không phải để LLM “nhớ mọi thứ”. Mục tiêu là mỗi câu hỏi đi qua một chuỗi có thể kiểm chứng:

```text
Tin nhắn + session identity
  -> Query understanding (intent, entities, constraints, reference)
  -> Policy router (quyền, freshness, risk)
  -> Source resolver (FAQ / catalog / approved protocol / realtime tool)
  -> Evidence bundle
  -> LLM composer chỉ diễn đạt trong evidence
  -> Claim validator
  -> Response + claim ledger + provider/runtime trace
  -> Redis memory có cấu trúc
```

Vai trò của LLM:

- được dùng để phân loại câu khó, tách nhiều ý, hiểu follow-up và diễn đạt tự nhiên;
- không được xem là nguồn fact;
- không tự tạo giá, link, stock, liều lượng, tác dụng, chính sách, order status hoặc ưu đãi;
- output phải bị validator từ chối nếu có mệnh đề không map được về evidence.

## 6. Mô hình dữ liệu nguồn cần nâng cấp

Một answer dài không đủ để chứng minh từng chi tiết. Mỗi fact quan trọng nên có:

```yaml
fact_id: cfc.agronomy.durian.fruit_stage.ca_bo.v1
brand: cfc
claim_type: agronomy_protocol
statement: "..."
crop: durian
crop_stage: fruit_development
symptom: "..."
product_codes: []
dosage:
  min: null
  max: null
  unit: null
source_type: approved_handbook
source_locator: "file/sheet/page/row"
source_excerpt: "..."
approved_by: "role-or-id"
approved_at: "..."
last_verified_at: "..."
valid_until: null
freshness_class: static | periodic | realtime_only
allowed_audience: public | authenticated_customer | dealer | internal
risk_level: low | medium | high
```

Mỗi response phải tạo claim ledger:

```json
{
  "answer_id": "...",
  "claims": [
    {
      "claim_id": "...",
      "text": "...",
      "fact_ids": ["..."],
      "verification_status": "verified"
    }
  ],
  "provider": "groq",
  "model": "...",
  "prompt_hash": "...",
  "runtime_manifest_id": "...",
  "snapshot_hashes": {"faq": "...", "catalog": "..."}
}
```

## 7. Cách trả lời khi khách hỏi vặn “Dữ liệu đó có thật không?”

Tạo intent riêng `verify_previous_claim` cho các cách hỏi:

- “Dữ liệu đó có thật không?”
- “Nguồn đâu?”
- “Dựa vào đâu mà nói vậy?”
- “Chắc không?”
- “Thông tin này cập nhật khi nào?”
- “Nếu sai thì sao?”

Luồng xử lý:

1. Lấy `answer_id` gần nhất trong session.
2. Đọc claim ledger, không gọi lại semantic RAG từ đầu.
3. Với từng claim, trả trạng thái verified/unverified/stale/realtime-required.
4. Nếu claim trước do LLM thêm và không có fact, bot phải nói rõ, xin lỗi và rút lại chi tiết đó.
5. Nếu nguồn có version/timestamp, nêu loại nguồn và lần cập nhật; không lộ dữ liệu nội bộ/PII.
6. Nếu khách yêu cầu chứng từ chi tiết, chuyển nhân viên hoặc gửi tài liệu public đã duyệt.

Ví dụ hành vi đúng sau câu sầu riêng sai:

> Dạ, tên một số dòng sản phẩm có thể đối chiếu trong danh mục CFC, nhưng các liều kg/ha và chính sách 5–10 ha mình vừa nêu chưa có nguồn được duyệt trong hệ thống. Mình xin rút lại các chi tiết đó. Với câu hỏi “có phân dùng cho sầu riêng không”, dữ liệu hiện có chỉ cho phép trả lời là có hướng dẫn theo giai đoạn; để tư vấn liều cần thêm tuổi cây, giai đoạn và xác nhận của kỹ sư.

## 8. Kế hoạch thực hiện theo mức ưu tiên

### P0 — Chặn rủi ro ngay, trước khi làm chatbot “hay hơn”

Thời gian dự kiến: 0.5–2 ngày sau khi được duyệt.

1. Tắt customer-facing free generation cho nhánh nông học CFC.
2. Không coi `ollama:*`, `groq:*` hoặc bất kỳ provider nào là `source_id` dữ kiện.
3. `AGRONOMY_REQUIRES_EXPERT_REVIEW` phải thực sự chặn claim kỹ thuật chưa duyệt, không chỉ ghi trace.
4. Khôi phục guard: CFC không có fact/catalog phù hợp thì hỏi rõ hoặc chuyển người thật; không gọi AI để lấp khoảng trống.
5. Khôi phục guard trong `reason_and_answer_cskh()`: không có `retrieved_facts` và không có catalog thì không sinh answer fact.
6. Sửa câu “Có phân bón cho cây X không?” thành product-fit/catalog lookup trước; chỉ hỏi giai đoạn khi khách muốn tư vấn kỹ thuật.
7. Chọn một AMIS writer. Khuyến nghị cô lập/deactivate Full Warm sau khi chủ hệ thống duyệt.
8. Revoke/rotate secret từng được nhúng trong workflow Full Warm.
9. Tắt `pilot_approve_all`; dùng allowlist duyệt rõ từng public location.
10. Cấu hình internal token và truyền bằng n8n credential/header an toàn.
11. Giảm/loại raw CRM payload khỏi n8n execution data; đặt retention phù hợp và xử lý execution cũ theo quy trình bảo mật.

Điều kiện thoát P0:

- 0 câu trả lời có liều/chính sách/giá/stock/order không có source.
- Câu sầu riêng cơ bản trả lời ngắn, đúng intent, không tự dựng phác đồ.
- AMIS chỉ còn một đường ghi public snapshot được kiểm soát.
- Secret cũ không còn hiệu lực.

### P1 — Nền tảng nguồn, trace và deploy có thể tái tạo

Thời gian dự kiến: 3–5 ngày.

1. Thêm `runtime_manifest_id` khi boot.
2. Lưu provider thật, model thật, prompt hash, latency và fallback chain cho từng lần gọi AI.
3. Tách `source_id` khỏi `generator_id`.
4. Tạo evidence bundle và claim ledger.
5. Nâng `grounding_policy.py` từ “có source string là grounded” thành kiểm tra source type, fact ID, freshness và audience.
6. Thêm endpoint admin read-only:
   - runtime revision/fingerprint;
   - active snapshot/hash;
   - vector doc count;
   - hot-cache loaded hash/count;
   - provider health không lộ key.
7. Sync chỉ publish `last_success` sau tất cả checkpoint.
8. Lưu `source_updated_at` riêng với `synced_at`.

Điều kiện thoát P1:

- Có thể trả lời chính xác “câu này do model nào, code nào, dữ liệu hash nào sinh”.
- Có thể chứng minh hot-cache đang dùng đúng snapshot mà không cần suy luận gián tiếp.

### P2 — Hiểu câu hỏi lắt léo và hội thoại nhiều lượt

Thời gian dự kiến: 4–7 ngày.

1. Chuẩn hóa một `QueryPlan` chung cho deterministic router, semantic planner và conversation orchestrator.
2. Semantic LLM chỉ đề xuất plan có schema; validator quyết định có chấp nhận hay không.
3. Thêm multi-intent decomposition: sản phẩm + giá + tồn kho + khu vực + số lượng.
4. Thêm reference resolver cho “cái đó”, “dữ liệu đó”, “loại vừa nói”, “đơn hồi nãy”.
5. Thêm `verify_previous_claim`, correction/retraction và topic-switch/return-to-topic.
6. Dùng GoalFrame/active goal và reference snapshots; không dựa riêng vào sáu raw turn.
7. Không thêm regex riêng cho từng paraphrase. Dùng entity ontology, plan schema, threshold và fallback.
8. Rerank phải có intent priors và negative evidence để tránh:
   - company question → address;
   - brand overview → slogan;
   - complaint → storage FAQ;
   - “có sản phẩm cho cây X không” → phác đồ liều lượng.

Điều kiện thoát P2:

- Paraphrase của cùng ý định cho cùng action/source family.
- Khi độ chắc thấp, bot hỏi một câu làm rõ thay vì đoán.
- Follow-up sau đổi chủ đề vẫn tham chiếu đúng kết quả trước.

### P3 — Tool realtime đúng nghĩa và phân quyền

Thời gian dự kiến: 5–10 ngày tùy AMIS API.

Phân loại nguồn:

| Câu hỏi | Nguồn bắt buộc |
|---|---|
| Công ty, thương hiệu, hướng dẫn đã duyệt | Sheet/handbook versioned |
| Tên/mã/đơn vị sản phẩm public | AMIS public snapshot |
| Giá hiện hành | privileged realtime/short-lived lookup |
| ATP/tồn kho | realtime inventory tool |
| Trạng thái đơn | realtime order tool + xác thực chủ sở hữu |
| Loyalty/điểm/hạng | realtime customer tool + xác thực |
| Chiết khấu/công nợ | role-based internal flow; không public |
| Đại lý gần nhất | approved location + geo index |
| Liều/phác đồ nông học | approved protocol, không lấy từ model world knowledge |

Các việc chính:

1. Sửa `live_crm.py` để không gọi local cache là live.
2. Adapter realtime phải trả `source_timestamp`, `request_id`, `freshness`, `authorization_scope`.
3. Catch timeout/rate-limit/auth error thành mã lỗi rõ, không trả 500 thô.
4. Có circuit breaker, timeout ngắn, retry có giới hạn và fallback không bịa.
5. Không lưu raw PII/order trong Redis public hoặc n8n execution.
6. Cache dữ liệu nhạy cảm phải short-lived, keyed theo identity và scope.

### P4 — Bộ tri thức nông học được duyệt

Thời gian dự kiến: 5–10 ngày, phụ thuộc kỹ sư/phòng kỹ thuật.

1. Tách mỗi cây/giai đoạn/triệu chứng/sản phẩm/liều thành fact có cấu trúc.
2. Mọi liều lượng, công dụng, thời điểm bón và cảnh báo phải có người duyệt.
3. Nếu thiếu tuổi cây, giai đoạn, diện tích, đất/nước/tình trạng vườn thì hỏi slot trước.
4. Model chỉ ghép câu từ fact; không dùng kiến thức nông học nền để bổ sung số liệu.
5. Câu hỏi “có hay không” chỉ trả eligibility ngắn, không tự mở rộng sang phác đồ.
6. High-risk answer phải chuyển kỹ sư hoặc yêu cầu duyệt trước khi gửi.

### P5 — Evals, canary và vận hành

Thời gian dự kiến: 3–5 ngày để dựng nền, sau đó chạy liên tục.

Mở rộng 14 case cũ thành các family:

- 10–20 paraphrase/case, có typo và tiếng địa phương;
- multi-intent;
- follow-up;
- hỏi vặn nguồn;
- đổi chủ đề rồi quay lại;
- câu có PII/third-party;
- lỗi/timeout/stale source;
- câu ngoài dữ liệu;
- prompt injection và yêu cầu model bỏ qua nguồn.

Chỉ số cổng chặn:

| Chỉ số | Mục tiêu trước rollout 100% |
|---|---:|
| Unsupported critical claim | 0% |
| Lộ PII/financial data bên thứ ba | 0% |
| Source challenge trả đúng verified/unverified | 100% bộ test |
| Correct tool/source family | ≥ 95% |
| Correct intent family | ≥ 90%, sau đó nâng dần |
| Clarification đúng khi thiếu slot | ≥ 95% |
| Workflow false-green | 0 case đã biết |
| Provider/runtime trace đầy đủ | 100% AI calls |

Rollout:

1. Static/unit tests.
2. Replay offline trên history đã ẩn danh.
3. Shadow mode, không ảnh hưởng câu trả lời.
4. Canary 5% sender ổn định theo hash.
5. 25% nếu không vượt error budget.
6. 100% sau duyệt nghiệp vụ.
7. Rollback theo runtime manifest và snapshot hash, không rollback mơ hồ theo “bản mới/bản cũ”.

## 9. File/module dự kiến cần cập nhật khi bắt đầu code

Không thực hiện trong đợt audit này. Danh sách để review scope:

| Khu vực | File chính | Mục tiêu |
|---|---|---|
| Pipeline | `chatbot/server/chat_pipeline.py` | route, evidence bundle, guard, claim ledger |
| AI provider | `chatbot/server/ai_engine.py` | trả provider/model thật; bỏ fact generation tự do |
| Grounding | `chatbot/server/grounding_policy.py` | claim-level validation |
| Query plan | `chatbot/server/query_understanding.py` | source challenge, multi-intent, reference |
| Conversation | `chatbot/server/conversation_orchestrator.py` | GoalFrame/reference/evidence memory |
| CFC planner | `chatbot/server/cfc_semantic_planner.py` | schema/threshold; không ghi đè deterministic tùy tiện |
| RAG | `chatbot/server/rag_search.py` | rerank, negative evidence, cache status |
| Sync | `chatbot/server/knowledge_sync.py` | transactional checkpoint/status |
| AMIS | `chatbot/server/domains/amis/*` | realtime adapter, auth, projection, timeout |
| Runtime bridge | `server/legacy_javis_runtime.py`, `server/routes/javis_legacy.py` | status/manifest/health |
| n8n chatbot | `workflows/local-n8n/zeo_chatbot.workflow.ts`, `cfc_cobay_chatbot.workflow.ts` | error route, duplicate/takeover |
| n8n knowledge | hai workflow knowledge sync | success contract và cache refresh |
| n8n AMIS | hai workflow AMIS | một writer, token, credential, không raw PII |
| Eval | `Bang_Danh_Gia_Chatbot_Facebook_AI.xlsx` và test suite server | replay real pipeline + trace |

## 10. Thứ tự triển khai khuyến nghị

Không nên làm tất cả một lần. Thứ tự an toàn:

1. Duyệt và thực hiện P0.
2. Chốt runtime manifest + provider trace + claim ledger tối thiểu.
3. Sửa hai lỗi ranking đã chứng minh bằng `/search`.
4. Thêm `verify_previous_claim` và retraction.
5. Tách AMIS warm/realtime đúng ranh giới.
6. Nâng data nông học có phê duyệt.
7. Chạy lại 14 case bằng real pipeline, không chấm similarity đơn lẻ.
8. Mới mở semantic/LLM canary theo tỷ lệ.

Nếu chỉ có thời gian làm ba việc đầu tiên, hãy chọn:

1. Chặn LLM tạo fact nông học/chính sách.
2. Ghi provider/runtime/evidence thật cho mỗi answer.
3. Chỉ giữ một AMIS public writer và rotate secret.

## 11. Các quyết định cần chủ hệ thống duyệt trước khi code/deploy

- Có cho phép tạm dừng AMIS Full Warm live không?
- Secret nhúng trong workflow sẽ được rotate bởi ai và khi nào?
- Danh sách location nào được phép public?
- Ai là người duyệt fact nông học và SLA duyệt bao lâu?
- Kênh realtime nào được cấp cho order, stock, price và loyalty?
- Retention n8n execution chứa raw CRM sẽ đặt bao lâu?
- Model/provider nào được phép nhận dữ liệu thuộc từng data class?
- Ngưỡng canary và người có quyền rollback?

## 12. Definition of Done

Chatbot chỉ được xem là “ổn định và thông minh hơn” khi:

- câu trả lời đúng nguồn dù khách đổi cách hỏi;
- biết hỏi lại khi thiếu dữ kiện;
- không lấy LLM làm nguồn fact;
- có thể tự kiểm tra/rút lại câu trước khi khách hỏi vặn;
- phân biệt static snapshot với realtime;
- không lộ PII/financial data;
- mỗi câu trả lời truy được code revision, provider/model, prompt, snapshot và fact IDs;
- lỗi tool hiện rõ trong vận hành, không bị workflow che bằng fallback xanh;
- toàn bộ family eval đạt cổng chặn trước rollout.

## 13. Những thay đổi được thực hiện trong đợt audit

- Không sửa logic chatbot.
- Không push, pull workflow, activate/deactivate hoặc ghi Redis/AMIS.
- Chỉ tạo tài liệu kế hoạch này.
- Công cụ n8n bắt buộc chạy `n8nac update-ai`, nên các file hướng dẫn/context sinh tự động của n8n-as-code có thể có thay đổi metadata. Cần review riêng, không coi đó là thay đổi workflow nghiệp vụ.
