# Plan di chuyển toàn bộ Chatbot ZeO/CFC khỏi Javis OS sang CFCBot

Ngày lập: 30/09/2026  
Nguồn: `/home/kali/Works/David-nguyen/javis-os`  
Đích đã xác minh: `/home/kali/Works/David-nguyen/CFCBot`  
Trạng thái: **PLAN ONLY — chưa copy, chưa xóa, chưa đổi workflow production.**

## 1. Mục tiêu và giả định

Mục tiêu là để `CFCBot` sở hữu trọn bộ hệ thống chatbot ZeO/CFC:

1. Tài liệu hệ thống và nguồn tri thức DOCX/XLSX.
2. Toàn bộ workflow/source/config mẫu liên quan n8n.
3. Backend chatbot cũ, dashboard, knowledge, test, plan và skill liên quan.
4. Runtime độc lập với Javis OS.
5. Quy trình deploy, backup, test, rollback và vận hành riêng.

Giả định đang dùng trong plan:

- `CFCBot` là tên đích chính thức dù hệ thống phục vụ cả CFC và ZeO.
- Không thực hiện `mv` trực tiếp. Luôn **copy → checksum/test → cutover → quan sát → retire nguồn**.
- Giữ nguyên hành vi production trong giai đoạn đầu; việc queue/OCR/Telegram Sales là chương trình nâng cấp tiếp theo sau migration.
- Redis, Ollama và n8n runtime có thể tiếp tục dùng chung trên cùng máy trong canary.
- Không đưa secret, token, cookie đăng nhập, cache khách hàng hoặc database n8n vào Git.

## 2. Hiện trạng đã xác minh

### 2.1 Thư mục đích

- `CFCBot` hiện trống, dung lượng 4 KB, chưa có file.
- `CFCBot` chưa phải Git repository.
- Không có thư mục thật tên `CFCChatbot`; tên đó trong IDE có thể là workspace label hoặc buffer cũ.

### 2.2 Nguồn chatbot

- `javis-os/chatbot`: khoảng 57 MB, 202 file sau khi loại cache Python khỏi thống kê.
- Thành phần lớn:
  - `chatbot/server`: khoảng 56 MB.
  - `chatbot/plan`: khoảng 440 KB.
  - `chatbot/skills`: khoảng 284 KB.
  - `chatbot/knowledge`: khoảng 8 KB.
- File lớn nhất là `chatbot/server/data/amis_real_crm_cache.json`, khoảng 54,6 MB.
- Pipeline chính `chat_pipeline.py` khoảng 348 KB và vẫn đang được Javis import trực tiếp.

### 2.3 Tài liệu cần chuyển trước

| File nguồn | Vai trò | SHA-256 |
|---|---|---|
| `chatbot/TAI_LIEU_HE_THONG_CFC_AI.docx` | Tài liệu hệ thống chatbot | `1fac1f827864ce783b20c56d568945aea282a822afcda82b4cc95f076094ab9f` |
| `chatbot/TAI_LIEU_HE_THONG_CFC_AI.md` | Bản Markdown để diff/search | `b3222002a432e032da14a672aa12864a70737a70d2dff42fc394d91c62596fa2` |
| `chatbot/Nhung cau hoi thuong gap o nha nong.docx` | Nguồn kiến thức nông nghiệp | `ea715e6a2a1ad54778c4def56253eb984598c356ae449d85c137a7640ec40559` |
| `chatbot/Bang_Danh_Gia_Chatbot_Facebook_AI.xlsx` | Bộ đánh giá Facebook AI | `f28c05b122b0bce4cb146604be3cad7966a06630ae08da14707929d619d79038` |

### 2.4 n8n hiện có

Có 7 workflow source:

1. `cfc_cobay_chatbot.workflow.ts` — Messenger CFC → API → Messenger reply.
2. `zeo_chatbot.workflow.ts` — Messenger ZeO → API → Messenger reply.
3. `cfc_knowledge_sync_basic.workflow.ts` — Google Sheets → Redis/vector CFC.
4. `zeo_knowledge_sync_basic.workflow.ts` — FAQ/Shopee/Web → Redis/vector ZeO.
5. `amis_crm_full_warm.workflow.ts` — AMIS full warm mỗi giờ.
6. `amis_crm_public_sync.workflow.ts` — public catalog sync; cần xác minh có còn active hay đã bị Full Warm thay thế.
7. `chatbot_operations_alert.workflow.ts` — cảnh báo vận hành qua Telegram có Redis dedup.

Môi trường n8n-as-code đang trỏ đến:

- URL: `https://n8n.dinhduongcantho.io.vn`
- Workflow path hiện tại: `javis-os/workflows/local-n8n`
- Trạng thái truy cập: `missing-api-key`

Vì thiếu API key, chưa thể coi file local là bản live mới nhất. Lệnh inventory chính thức hiện báo:

> Environment "Local n8n" needs a host and API key before this command can run.

Backup n8n hiện khoảng 31 GB, chủ yếu là `database.sqlite` khoảng 32,6 GB. Đây là dữ liệu runtime, không phải source code.

### 2.5 Phụ thuộc Javis cần tháo

Javis hiện cung cấp `/api/chat-pipeline` qua:

```text
server/routes/javis_legacy.py
  -> server/legacy_javis_runtime.py
    -> import trực tiếp chatbot/server/chat_pipeline.py
```

Hai workflow Messenger đang gọi:

```text
http://127.0.0.1:7777/api/chat-pipeline
```

Các phần ngoài `chatbot/` cần audit/chuyển hoặc thay thế:

- `server/legacy_javis_runtime.py`
- `server/routes/javis_legacy.py`
- `tests/python/test_legacy_javis_runtime.py`
- `docs/dev/2026-08-chatbot-context-intelligence-plan.md`
- `CFC_CHATBOT_AI_CONTEXT_HANDOFF_CODEX.md`
- `JAVIS_OS_AI_CHATBOT_SUMMARY.md`
- `infra/redis/docker-compose.yml`
- `infra/cloudflared/config.yml` và systemd override
- runtime n8n Compose tại `/home/kali/javis-runtime/n8n-compose.yml`
- systemd `javis.service`, hiện đang là process phục vụ API chatbot gián tiếp.

## 3. Nguyên tắc migration

1. **Không xóa nguồn trong lần copy đầu.**
2. **Không đổi code và đổi hạ tầng trong cùng một bước.**
3. **Document-first, n8n-source-second, chatbot-code-third** theo yêu cầu.
4. Thứ tự copy không phải thứ tự cutover: n8n chỉ đổi endpoint sau khi Chatbot API mới đã healthy.
5. Mỗi phase có manifest, checksum, test, người duyệt và rollback riêng.
6. Workflow production phải pull/đối chiếu live trước khi sửa.
7. Credential được reconnect hoặc nhập qua secret store; không copy plaintext.
8. Cache/data khách hàng được export có kiểm soát hoặc rebuild, không commit Git.
9. Javis giữ compatibility bridge cho đến khi CFC và ZeO đều qua canary.
10. Chỉ retire phần cũ sau ít nhất 7–14 ngày ổn định.

## 4. Cấu trúc đích đề xuất

Giai đoạn migration đầu giữ layout gần nguồn để giảm số thay đổi:

```text
CFCBot/
├── README.md
├── AGENTS.md
├── .gitignore
├── docs/
│   ├── source/
│   │   ├── docx/
│   │   └── xlsx/
│   ├── architecture/
│   ├── operations/
│   ├── plans/
│   └── migration/
├── chatbot/
│   ├── server/
│   ├── knowledge/
│   ├── skills/
│   └── plan/
├── workflows/
│   └── local-n8n/
├── infra/
│   ├── redis/
│   ├── n8n/
│   ├── cloudflared/
│   └── systemd/
├── deploy/
├── tests/
└── migration/
    ├── inventory.csv
    ├── checksums.sha256
    ├── credential-map.example.md
    └── cutover-runbook.md
```

Không flatten `chatbot/server` thành `src/cfcbot` trong migration đầu. Việc đổi package layout là refactor riêng sau khi test xanh và production ổn định.

## 5. Phase 0 — Khóa an toàn và tạo baseline

### Việc làm

1. Chốt `CFCBot` có quản lý cả CFC và ZeO.
2. Chốt remote Git/private repository nhưng chưa push dữ liệu.
3. Tạo `.gitignore` trước mọi thao tác copy.
4. Tạo inventory gồm path, size, SHA-256, loại dữ liệu và owner.
5. Chụp baseline:
   - health local/public;
   - danh sách workflow live;
   - workflow active/inactive/version;
   - credential name/type, không lấy secret;
   - test chatbot;
   - Redis keyspace/schema/index;
   - systemd/Docker/Cloudflare state.
6. Backup phục hồi được cho n8n và Redis.
7. Cấu hình API key cho n8n-as-code bằng `n8nac env auth set ... --api-key-stdin`; không ghi key vào file/command history.

### Blocker bảo mật phải giải quyết trước Git mới

- `chatbot/server/.env` và `settings.json` đang ignored: chỉ chuyển secret bằng kênh riêng.
- `chatbot/server/scripts/shopee_auth.json` đang **tracked** và có khả năng chứa session/cookie: không copy; audit và rotate credential.
- `chatbot/server/data/amis_real_crm_cache.json` đang **tracked**, khoảng 54,6 MB và có khả năng chứa PII/CRM: không copy vào Git mới; đánh giá purge khỏi history nguồn bằng kế hoạch riêng.
- Không copy `n8n-backup/.n8n/config`, SQLite, WAL, token Cloudflare hoặc credential JSON vào Git.

### Gate

- Manifest hoàn chỉnh.
- Gitignore test không nhận secret/cache.
- Có backup + restore drill tối thiểu trên bản copy.
- Có n8n API key và pull/list được live workflows.

## 6. Phase 1 — Di chuyển DOCX và tài liệu hệ thống trước

### Nhóm 1: nguồn gốc không sửa

Copy theo checksum vào:

- `docs/source/docx/TAI_LIEU_HE_THONG_CFC_AI.docx`
- `docs/source/docx/Nhung cau hoi thuong gap o nha nong.docx`
- `docs/source/xlsx/Bang_Danh_Gia_Chatbot_Facebook_AI.xlsx`

### Nhóm 2: tài liệu Markdown đang hoạt động

Copy và chỉnh link/path sau khi checksum nguồn đã lưu:

- `TAI_LIEU_HE_THONG_CFC_AI.md`
- `README.md`
- `AGENTS.md`
- `Bao_Cao_Doi_Chieu_Khach_Hang.md`
- toàn bộ `chatbot/plan`, gồm plan queue/OCR/Telegram Sales;
- các tài liệu root/dev thật sự mô tả chatbot và bridge Javis.

### Việc sửa bắt buộc sau copy

- Thay path Mac cũ `/Users/hyden/...`.
- Thay mô tả “Javis là runtime chatbot” thành service độc lập + compatibility bridge.
- Đánh dấu rõ tài liệu lịch sử, tài liệu hiện hành và tài liệu nguồn.
- Sửa `generate_doc.py` để output tương đối trong CFCBot, không hardcode path.
- Tạo `docs/README.md` làm điểm vào duy nhất.

### Gate

- Checksum ba file binary đúng nguồn.
- Link nội bộ Markdown không gãy.
- DOCX mở được.
- Không có secret/cache trong commit staged.

## 7. Phase 2 — Di chuyển toàn bộ n8n

### 7.1 Chụp live trước khi copy

1. Dùng n8n-as-code list/pull từng workflow.
2. Đối chiếu file live với local bằng workflow ID/version/checksum.
3. Nếu có conflict, dừng và chọn rõ `keep-current` hoặc `keep-incoming`; không force-push.
4. Lập bảng credential dependency:
   - Meta/Facebook CFC;
   - Meta/Facebook ZeO;
   - Google Sheets;
   - Redis;
   - Telegram;
   - AMIS/HTTP auth nếu có.
5. Ghi active/inactive và lịch schedule thật.

### 7.2 Source được copy vào CFCBot

- 7 file `*.workflow.ts`.
- `tsconfig.json`.
- generated typing chỉ regenerate bằng tool nếu có thể; không coi `n8n-workflows.d.ts` cũ là nguồn chân lý.
- Compose/template cho n8n và Redis.
- Cloudflare config template không chứa tunnel credential/token.
- Runbook backup/restore, health check và startup.

### 7.3 Không copy thẳng

- `.n8n-state.json` và `.n8n-sync-events.jsonl`: tạo lại theo workspace mới bằng n8nac, không dùng metadata cũ làm nguồn chân lý.
- `n8nac-config.json`: tạo môi trường bằng lệnh n8nac, không tự viết tay.
- Database SQLite 31 GB: giữ tại runtime storage/backup ngoài repo.
- Credential store của n8n: không export plaintext vào dự án.
- Cloudflare token/cert/tunnel credential: giữ trong system secret path.

### 7.4 Phân loại workflow khi chuyển

| Workflow | Hành động ban đầu |
|---|---|
| CFC Co Bay Chatbot | Copy/pull, giữ inactive ở workspace đích cho đến khi API mới sẵn sàng |
| Zeo Chatbot | Copy/pull, giữ inactive ở workspace đích cho đến khi API mới sẵn sàng |
| CFC Co Bay Knowledge | Copy/pull, reconnect Sheets/Redis, test snapshot candidate |
| Zeo Knowledge | Copy/pull, reconnect Sheets/Redis, test ba nhánh FAQ/Shopee/Web |
| AMIS Full Warm | Copy/pull, dry-run/staging trước, không đụng active snapshot |
| AMIS Public Sync | Copy để không mất lịch sử; audit trùng chức năng trước khi publish |
| Chatbot Operations Alert | Copy/pull, thay chat ID bằng credential/config mới, test ở nhóm sandbox |

### 7.5 Endpoint contract

Trong source workflow không tiếp tục hardcode `127.0.0.1:7777` lâu dài. Tạo một biến/config chuẩn, ví dụ:

```text
CHATBOT_API_BASE_URL=http://127.0.0.1:7780
```

Tuy nhiên chỉ đổi workflow sau Phase 4. Trước đó workflow live tiếp tục gọi Javis compatibility endpoint.

### Gate

- Tất cả workflow có source ID/version và validation result.
- Chưa có workflow đích nào vô tình publish.
- Credential map hoàn chỉnh và secret không vào Git.
- Knowledge/AMIS chạy dry-run không làm mất snapshot hiện tại.

## 8. Phase 3 — Di chuyển toàn bộ chatbot cũ

### 8.1 Copy nguyên trạng trước

Copy:

- `chatbot/server/*.py`
- toàn bộ `chatbot/server/domains/`
- `chatbot/server/static/`
- `chatbot/server/tests/`
- `chatbot/server/manual_tests/`
- `chatbot/server/scripts/` sau khi loại secret/auth;
- `chatbot/knowledge/`
- `chatbot/skills/`
- `chatbot/plan/`
- `requirements.txt`, README và example config.

Không copy:

- `__pycache__`, `.pytest_cache`, `.venv`;
- `.env`, `settings.json`;
- `shopee_auth.json`;
- `amis_real_crm_cache.json`;
- file `.bak` chưa qua audit như `query_understanding.py.bak`;
- log, PID, SQLite/WAL và runtime cache.

### 8.2 Các file ngoài chatbot phải được port

- Chuyển logic API cần thiết từ `server/routes/javis_legacy.py` sang route độc lập trong CFCBot.
- Thay `server/legacy_javis_runtime.py` bằng:
  - service implementation ở CFCBot;
  - HTTP compatibility client nhỏ còn lại ở Javis trong thời gian canary.
- Chuyển/viết lại test bridge thành integration test HTTP, không còn import module bằng `sys.path`.
- Cập nhật `runtime_manifest.py` vì hiện hash cả file Javis và workflow ở root cũ.
- Cập nhật domain n8n vì hiện mặc định quét/push `workflows/local-n8n` theo root Javis.

### 8.3 Cấu hình

- Tạo `settings.example.json` và `.env.example` sạch.
- Secret runtime dùng systemd EnvironmentFile, Docker secret hoặc secret store; không commit.
- Absolute path phải được thay bằng path lấy từ project root/config.
- Redis URL, Ollama URL, n8n URL, public domain và media path phải là config.
- Giữ model hiện tại trong migration; không đổi model cùng lúc.

### Gate

- Import/compile sạch trong virtualenv mới.
- Toàn bộ unit/replay test baseline chạy độc lập khỏi Javis.
- Không cần thêm `javis-os/server` vào `PYTHONPATH`.
- Runtime manifest chỉ tham chiếu file thuộc CFCBot hoặc dependency được khai báo.

## 9. Phase 4 — Dựng Chatbot API độc lập

### Đề xuất runtime

- Service: `cfcbot.service` hoặc `chatbot-api.service`.
- Port canary: `127.0.0.1:7780`.
- Health: `/health`.
- Contract giữ tương thích:
  - `POST /api/chat-pipeline`
  - admin/knowledge/AMIS routes cần thiết.
- Dependency ngoài service:
  - Redis tại `127.0.0.1:6379`;
  - Ollama tại `127.0.0.1:11434`;
  - n8n tại `127.0.0.1:5678`.

### Compatibility

- Javis `:7777/api/chat-pipeline` tạm proxy sang CFCBot `:7780`.
- n8n vẫn gọi `:7777` trong smoke/canary đầu.
- Sau khi CFCBot ổn, workflow draft đổi sang `:7780`.
- Cuối cùng xóa import trực tiếp `chatbot/server` khỏi Javis, nhưng chưa xóa proxy cho đến hết rollback window.

### Gate

- Tắt Javis nhưng gọi trực tiếp CFCBot vẫn xử lý được synthetic request.
- Restart CFCBot không ảnh hưởng Javis.
- Redis/Ollama lỗi có degraded behavior đúng policy.
- Log, PID, health và restart policy độc lập.

## 10. Phase 5 — Cutover không gián đoạn

Thứ tự cutover khuyến nghị:

1. Knowledge sync CFC ở draft/test.
2. CFC Messenger canary theo stable sender bucket.
3. CFC 100% sau khi metrics đạt gate.
4. Knowledge sync ZeO.
5. ZeO Messenger canary rồi 100%.
6. AMIS Full Warm sau dry-run/staging.
7. Operations Alert.
8. Audit `AMIS Public Sync`; chỉ publish nếu còn thật sự cần.

Mỗi bước:

- pull live mới nhất;
- sửa source trong CFCBot;
- validate;
- push draft;
- test production contract bằng payload an toàn;
- inspect execution;
- publish/canary;
- ghi thời điểm, revision và người duyệt.

Chỉ số theo dõi:

- webhook accepted;
- duplicate reply;
- pipeline error/timeout;
- P50/P95 latency;
- Redis/Ollama degraded rate;
- knowledge snapshot freshness;
- AMIS warm status;
- Messenger send failures;
- Telegram alert failures.

## 11. Rollback

Trong suốt 7–14 ngày đầu:

- Không xóa source `javis-os/chatbot`.
- Không unpublish workflow cũ trước khi workflow mới pass.
- Giữ Javis compatibility endpoint `:7777`.
- Giữ backup n8n/Redis trước cutover.
- Mỗi workflow có revision cũ đã ghi lại.

Rollback nhanh:

1. Đưa workflow về revision cũ gọi `:7777`.
2. Tắt route/canary flag của CFCBot.
3. Kiểm tra Javis/Redis/Ollama health.
4. Chạy synthetic message và một test Page sandbox.
5. Ghi incident; không tự retry cutover khi chưa rõ nguyên nhân.

## 12. Phase 6 — Retire phần cũ

Chỉ làm khi CFC và ZeO chạy ổn tối thiểu 7–14 ngày:

1. Ngừng Javis import `chatbot/server`.
2. Chuyển `legacy_javis_runtime.py` thành proxy mỏng hoặc xóa sau một release deprecation.
3. Xóa route compatibility sau khi mọi caller đã đổi.
4. Archive tài liệu Javis cũ, sửa link về CFCBot.
5. Xóa bản source chatbot trong Javis bằng commit riêng, có tag/backup.
6. Không xóa n8n backup 31 GB cho đến khi có retention policy và restore drill đạt.
7. Audit/purge secret và PII đã từng bị track trong Git history bằng kế hoạch bảo mật riêng.

## 13. Ma trận source → target

| Nguồn | Đích | Cách xử lý |
|---|---|---|
| `chatbot/*.docx` | `docs/source/docx/` | Copy binary + checksum |
| `chatbot/*.xlsx` | `docs/source/xlsx/` | Copy binary + checksum |
| `chatbot/*.md`, `chatbot/plan` | `docs/`, `chatbot/plan` | Copy rồi sửa link/path |
| `workflows/local-n8n/*.workflow.ts` | `workflows/local-n8n/` | Pull live trước, copy source, validate |
| n8n metadata local | Regenerate | Không copy mù |
| n8n SQLite 31 GB | Runtime backup ngoài Git | Không đưa vào repo |
| `chatbot/server` | `chatbot/server` | Copy nguyên trạng trước, refactor sau |
| `chatbot/knowledge` | `chatbot/knowledge` | Copy + checksum |
| `chatbot/skills` | `chatbot/skills` | Audit Javis-specific skill trước |
| Redis Compose | `infra/redis` | Copy template, không copy env |
| Cloudflare config | `infra/cloudflared` | Template hóa, secret ở hệ thống |
| Javis bridge | CFCBot API + Javis HTTP proxy | Tách theo Phase 4 |
| AMIS cache | Runtime rebuild/import kiểm soát | Không commit |
| Shopee auth | Secret store/re-auth | Không copy, rotate |

## 14. Bộ test nghiệm thu tối thiểu

1. DOCX/XLSX checksum đúng.
2. Markdown link và path không còn trỏ Mac cũ.
3. Workflow source khớp live revision đã duyệt.
4. Hai Messenger workflow giữ duplicate suppression và human takeover.
5. Location attachment CFC vẫn đúng.
6. Google Sheets reconnect và knowledge snapshot promote nguyên tử.
7. Full Warm không publish khi source count/commit lỗi.
8. Order/loyalty/product/dealer/agronomy regression pass.
9. Message ID retry không gửi trả lời hai lần.
10. CFCBot restart không mất session quan trọng.
11. Javis tắt không làm CFCBot trực tiếp chết.
12. Rollback workflow về `:7777` hoạt động.
13. Không có secret/PII trong `git diff --cached`.
14. Restore n8n và Redis từ backup test thành công.
15. Public n8n/Cloudflare health và Meta webhook vẫn hợp lệ.

## 15. Các quyết định cần chốt trước khi triển khai

1. `CFCBot` có chính thức chứa cả ZeO lẫn CFC không?
2. CFCBot sẽ có Git remote private nào?
3. Tiếp tục dùng cùng n8n instance/database hay tạo instance mới cho CFCBot?
4. Giữ domain `n8n.dinhduongcantho.io.vn` hay tạo domain riêng?
5. Cho phép mang cache AMIS sang runtime mới hay bắt buộc rebuild từ AMIS?
6. Có giữ toàn bộ plan/archive lịch sử hay chỉ tài liệu hiện hành?
7. Port chính thức sau canary là 7780 hay một port khác?
8. Ai cung cấp/duyệt lại Meta, Google Sheets, Telegram, Redis và AMIS credential?
9. Workflow `AMIS CRM Public Catalog Sync` còn active hay được Full Warm thay thế?
10. Thời gian canary/rollback window: 7 hay 14 ngày?

## 16. Thứ tự triển khai ngắn gọn

```text
0. Security + inventory + backup
1. DOCX/XLSX/Markdown
2. n8n source + credential map + runtime templates
3. Chatbot code + tests + knowledge
4. CFCBot API :7780 + Javis compatibility proxy
5. CFC canary -> CFC 100%
6. ZeO canary -> ZeO 100%
7. AMIS/alerts
8. Quan sát 7–14 ngày
9. Retire phần chatbot khỏi Javis bằng commit riêng
```

## 17. Việc tuyệt đối chưa làm trong giai đoạn plan

- Không copy/xóa code.
- Không init Git hoặc push remote.
- Không sửa/publish workflow.
- Không đổi endpoint production.
- Không di chuyển SQLite/Redis data.
- Không copy credential/token/cookie.
- Không tắt Javis/n8n/Redis/Ollama/Cloudflare.
- Không purge Git history khi chưa có backup và quyết định riêng.
