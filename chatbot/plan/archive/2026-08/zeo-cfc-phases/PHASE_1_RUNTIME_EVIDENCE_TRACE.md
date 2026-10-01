# Phase 1 — Runtime manifest, provider trace và evidence contract

> **Lưu trữ (08/09/2026):** Phase lịch sử; xem [plan/README.md](../../../README.md) để định hướng tài liệu hiện hành.

Trạng thái: `BLOCKED — LOCAL IMPLEMENTATION COMPLETE; chờ canary/live evidence`
Ưu tiên: P1, nền tảng cho source challenge và rollout  
Ước lượng: 3–5 ngày  
Phụ thuộc: Phase 0 exit gate đạt phần server/grounding

> Cập nhật 2026-08-29, local working tree sau Phase 0. Đã sửa và kiểm thử ở local; **không** push/deploy/activate workflow, không đổi credential và không truy cập CRM live. Chưa được đánh dấu `DONE`: runtime đang deploy, Redis snapshot, vector index và credential/provider live vẫn phải được canary có owner phê duyệt xác nhận.

## Kết quả triển khai local

| Work package | Trạng thái local | Thay đổi đã thực hiện |
|---|---|---|
| WP1 runtime manifest | Hoàn thành | `runtime_manifest.py` tạo fingerprint immutable khi worker import: git SHA/dirty, hash source đang chạy, config đã redacted, version prompt/policy và Python version. `runtime_manifest_id` đi cùng response/history. |
| WP2 provider trace | Hoàn thành cho đường `generate_ai_text()` | Gemini, OpenRouter, Groq, Ollama ghi attempt/model thực tế, mode, status, latency, prompt ID/hash; không lưu prompt/raw upstream error/API key. CFC semantic planner đi qua adapter này. |
| WP3 evidence registry | Hoàn thành mức P1 | Mỗi answer có evidence bundle; `FAQ/catalog/public_tool/privileged_tool` là source type hợp lệ. Provider/model không bao giờ được biến thành evidence. |
| WP4 claim ledger tối thiểu | Hoàn thành mức P1 | Mỗi answer có opaque `answer_id`, claim đã redact PII, evidence IDs và quyết định grounding Phase 0 (`verified`, `unverified`, `blocked`). Đây là ledger để replay/audit, không phải engine tự suy nguồn mới. |
| WP5 persistence | Hoàn thành | Trace envelope được dual-write vào `last_trace` và history hiện hữu; session cũ tự nhận field mới khi có turn kế tiếp, không reset Redis. |
| WP6 diagnostics | Hoàn thành local | `GET /admin/runtime-evidence` nội bộ-only trả manifest, hot cache, lần sync hoàn tất trong worker, provider trace cuối và trạng thái AMIS đã redacted. Không refresh/call AI. |
| WP7 sync/cache observability | Hoàn thành local | Snapshot hash, hot-cache hash/count/time và checkpoint vector/hot-cache được ghi khi sync chỉ hoàn tất thành công; Redis có bản `*:knowledge:sync:last-complete` nếu writer hỗ trợ. |

### File thay đổi

- Mới: `chatbot/server/runtime_manifest.py`, `chatbot/server/evidence_trace.py`, `chatbot/server/tests/test_phase1_runtime_evidence.py`.
- Cập nhật: `ai_engine.py`, `cfc_semantic_planner.py`, `chat_pipeline.py`, `rag_search.py`, `knowledge_sync.py`, `server/legacy_javis_runtime.py`, `server/routes/javis_legacy.py`, `test_knowledge_sync.py`.
- Không đụng workflow n8n trong Phase 1 này.

### Bằng chứng kiểm thử local

| Kiểm tra | Kết quả |
|---|---|
| `py_compile` các module Phase 1 | OK |
| `git diff --check` | OK |
| Phase 1 + grounding/query/sync/CFC memory regressions | `61/61 OK` ngày 2026-08-29 |
| `test_conversation_orchestrator` đầy đủ | Chưa dùng làm exit gate: 7 test cũ patch API `plan_conversation_turn_with_ollama` đã không còn tồn tại từ trước Phase 1; không sửa/ép quay lại contract đó trong phase trace này. |

### Điều kiện canary trước khi `DONE`

1. Gọi `/admin/runtime-evidence` từ internal network/token, đối chiếu `runtime_manifest_id` với checkout/revision thực đang chạy.
2. Chạy một FAQ/catalog có source, một safe fallback và một request có provider; xác nhận history có `answer_id`, evidence/claim, attempt/model đúng thực tế và không có PII/secret.
3. Chạy sync ZeO + CFC được phê duyệt, đối chiếu source snapshot hash, vector checkpoint và hot-cache hash.
4. Xác minh diagnostics AMIS chỉ là trạng thái cấu hình/cache; không được suy diễn thành realtime nếu chưa có adapter Phase 3.

## 1. Mục tiêu

Cho phép trả lời chính xác năm câu hỏi cho mọi answer:

1. Code/runtime nào đã chạy?
2. Provider và model nào thực sự được gọi?
3. Prompt/policy version nào được dùng?
4. Snapshot/tool/fact nào cung cấp dữ kiện?
5. Claim nào verified, unverified, stale hoặc bị block?

Phase này không làm chatbot “nói hay hơn”. Nó tạo nền để biết bot đúng/sai vì đâu và rollback đúng revision.

## 2. Vấn đề hiện tại

- Runtime là HEAD cộng working-tree dirty nhưng response không lưu fingerprint.
- History `revision` là session revision, dễ bị hiểu nhầm thành code revision.
- `consult_cfc_agronomy_with_ai()` bỏ `provider` và chỉ trả text.
- Các `call_*` chủ yếu trả string; fallback chain/model attempt không được persist thống nhất.
- Trace dùng source hard-code như `ollama:cfc_agronomy`.
- Một answer có thể trộn FAQ/catalog/tool/LLM nhưng chỉ có một `last_source_id`.
- Hot-cache status không công khai loaded snapshot hash/count.
- Sync metadata không đủ chứng minh vector/cache đã refresh.

## 3. Ngoài phạm vi

- Chưa làm multi-intent/reference/source-challenge UX đầy đủ — Phase 2.
- Chưa làm AMIS realtime tool — Phase 3.
- Chưa xây toàn bộ agronomy fact authoring — Phase 4.
- Không lưu raw prompt chứa PII nếu chưa redaction.
- Không đưa secret/config values vào manifest hoặc endpoint.

## 4. Contracts mục tiêu

### Runtime manifest

Tạo một manifest immutable khi worker boot/reload:

```json
{
  "runtime_manifest_id": "sha256:...",
  "started_at": "...",
  "git_sha": "...",
  "git_dirty": true,
  "files": {
    "chat_pipeline.py": "sha256:...",
    "ai_engine.py": "sha256:...",
    "query_understanding.py": "sha256:...",
    "grounding_policy.py": "sha256:..."
  },
  "config_version": "sha256:redacted-config-shape",
  "policy_versions": {},
  "prompt_versions": {},
  "python_version": "..."
}
```

Không hash/ghi giá trị secret. Config fingerprint chỉ dùng keys/policy non-secret hoặc redacted canonical structure.

### AI invocation result

```json
{
  "success": true,
  "text": "...",
  "generator": {
    "provider": "groq",
    "model": "...",
    "execution_mode": "cloud",
    "attempts": [
      {"provider": "groq", "model": "...", "status": "ok", "latency_ms": 120}
    ],
    "prompt_id": "cfc.agronomy-draft.v2",
    "prompt_hash": "sha256:..."
  }
}
```

Error chỉ lưu class/code/latency, không lưu key hoặc raw upstream body nhạy cảm.

### Evidence bundle và claim ledger

```json
{
  "answer_id": "opaque-id",
  "runtime_manifest_id": "sha256:...",
  "query_plan_id": "...",
  "evidence": [
    {
      "evidence_id": "...",
      "source_type": "faq|catalog|approved_protocol|public_tool|privileged_tool",
      "source_id": "...",
      "source_version": "...",
      "snapshot_hash": "...",
      "source_timestamp": "...",
      "expires_at": null,
      "allowed_audience": "public"
    }
  ],
  "claims": [
    {
      "claim_id": "...",
      "text": "...",
      "evidence_ids": ["..."],
      "status": "verified|unverified|stale|blocked"
    }
  ],
  "generator": {},
  "decision": {}
}
```

## 5. Work packages

### P1-WP1 — Runtime manifest service

Việc làm:

1. Tính manifest một lần khi worker boot/import hoàn tất.
2. Hash đúng source đang load, không chỉ Git HEAD.
3. Ghi `git_dirty` và optional diff fingerprint, không ghi full diff vào Redis/log.
4. Version prompt/policy bằng ID ổn định và hash canonical text.
5. Expose read-only status đã redacted.
6. Mỗi response/history lưu `runtime_manifest_id`.

File dự kiến:

- module mới trong `chatbot/server/` cho runtime manifest
- `server/legacy_javis_runtime.py`
- `server/routes/javis_legacy.py`
- `chatbot/server/chat_pipeline.py`
- tests manifest/redaction/stability

### P1-WP2 — Provider/model attempt tracing

Việc làm:

1. Chuẩn hóa `call_groq`, `call_openrouter`, `call_gemini`, `call_ollama` trả typed result thay vì string.
2. Ghi đúng model đã thành công, không chỉ model mặc định đầu tiên.
3. `generate_ai_text()` giữ attempt chain và reason code.
4. Caller không được bỏ generator metadata.
5. Tách `generator_id`/`provider` khỏi `source_id`.
6. Redact API error/body và prompt PII trước log.

File dự kiến:

- `chatbot/server/ai_engine.py`
- các caller: pipeline, semantic planner, reporter/document ingestor/learning nếu dùng contract chung
- tests provider fallback/timeout/redaction

Migration cần cẩn thận vì `generate_ai_text()` có nhiều caller. Không đổi tất cả bằng search-replace thiếu test; tạo adapter tương thích tạm thời nếu cần.

### P1-WP3 — Source/evidence registry

Việc làm:

1. Định nghĩa source types và required fields.
2. FAQ evidence mang intent/source_id/source version/row locator/snapshot hash.
3. Catalog evidence mang item ID/source/snapshot/freshness.
4. Tool evidence mang result ID/request ID/timestamp/authorization.
5. Provider output không được đăng ký làm evidence.
6. Evidence audience/freshness phải được policy kiểm tra trước composition.

File dự kiến:

- module evidence/claims mới trong `chatbot/server/`
- `chatbot/server/rag_search.py`
- `chatbot/server/shopee_matcher.py`
- `chatbot/server/chat_pipeline.py`
- AMIS/tool adapters khi Phase 3 triển khai

### P1-WP4 — Claim extraction/validation tối thiểu

P1 không cần một semantic theorem prover. Bản đầu:

1. Deterministic formatter tạo claim mapping trực tiếp từ fact fields.
2. Với LLM composer, yêu cầu structured output chứa claim IDs rồi validate allowlist.
3. Số, đơn vị, giá, mã, link, phone, policy term phải exact-match evidence hoặc bị block.
4. Nếu không parse/validate được, dùng deterministic answer/safe fallback.
5. Lưu claim ledger cùng answer history.

### P1-WP5 — Conversation/history persistence

Việc làm:

1. Mỗi history record có `answer_id`, manifest ID, plan ID, evidence summary, claims, generator.
2. Session giữ pointer tới answer/evidence gần nhất để source challenge dùng.
3. Không đưa full raw evidence nhạy cảm vào public/session state; privileged result chỉ lưu sanitized pointer/TTL.
4. History schema version mới có backward-compatible reader.
5. Không reset existing Redis sessions; migrate lazily khi đọc/ghi.

File dự kiến:

- `chatbot/server/conversation_store.py`
- `chatbot/server/chat_pipeline.py`
- conversation state schema/tests

### P1-WP6 — Read-only diagnostics

Đề xuất endpoint admin, tên cuối cần review route conventions:

- runtime manifest/status;
- active FAQ/catalog snapshot hash/count/timestamp;
- vector index doc count/indexing/failure;
- hot-cache loaded hash/count/loaded_at;
- provider health/configured boolean không lộ key;
- AMIS snapshot/cache/realtime mode tách biệt.

Endpoint phải:

- auth phù hợp;
- redacted;
- không tạo AI call hoặc refresh side effect;
- có schema/test;
- trả `unknown` trung thực nếu không chứng minh được.

File dự kiến:

- `server/routes/javis_legacy.py`
- `server/legacy_javis_runtime.py`
- `chatbot/server/rag_search.py`
- `chatbot/server/knowledge_sync.py`
- status tests

### P1-WP7 — Sync/cache observability

Việc làm:

1. Persist trạng thái từng checkpoint và hash input/output.
2. Hot-cache ghi loaded snapshot hash/count.
3. Vector status ghi source snapshot hash thay vì chỉ doc count.
4. Nếu Redis snapshot đổi nhưng vector/cache cũ, health báo degraded.
5. n8n metadata chỉ tham chiếu server-confirmed complete status.

## 6. Test matrix bắt buộc

### Manifest

- clean vs dirty tree;
- một file đổi tạo manifest ID mới;
- secret đổi không xuất hiện trong manifest/output;
- worker reload tạo manifest mới;
- response/history giữ đúng ID.

### Provider

- preferred provider success;
- provider thứ nhất timeout, fallback thứ hai success;
- exact model fallback trong cùng provider;
- all providers fail;
- execution mode local/cloud/auto;
- trace không gọi Groq thành Ollama hoặc ngược lại;
- error/redaction không lộ API key/raw PII.

### Evidence/claims

- một FAQ answer;
- một catalog result;
- mixed FAQ + catalog;
- model-only text;
- stale/expired evidence;
- audience mismatch;
- số/liều/link/phone không evidence;
- deterministic fallback khi claim validation fail.

### Persistence/status

- old session lazy upgrade;
- cross-brand/sender isolation;
- evidence pointer TTL;
- cache hash match/mismatch;
- vector count match nhưng source hash mismatch;
- endpoint unauthorized/redacted/no side effect.

## 7. Entry gate

- Phase 0 không còn unsupported customer-facing generator.
- Trace/history hiện tại được snapshot để đối chiếu backward compatibility.
- Có schema/version naming convention.
- Có quyết định retention cho claim/evidence metadata.

## 8. Exit gate

- 100% AI calls trong target pipeline có actual provider/model/prompt hash/attempt status.
- 100% customer answers có runtime manifest ID.
- Dynamic/static fact có evidence type/version/freshness phù hợp.
- Model/provider không bao giờ xuất hiện như fact source.
- Critical claim thiếu evidence bị block.
- Có thể tái hiện câu trả lời bằng manifest + snapshot/fact IDs trong phạm vi dữ liệu còn retention.
- Diagnostics chứng minh snapshot/vector/hot-cache alignment.
- Không lộ secret/PII qua trace/status/log.

## 9. Rollout và rollback

Rollout:

1. dual-write trace mới và trace cũ;
2. shadow claim ledger, không block answer;
3. so sánh missing/false mapping;
4. bật block cho critical claim trước;
5. mở dần low-risk claim validation;
6. chuyển source challenge sang ledger sau Phase 2.

Rollback:

- reader hỗ trợ schema cũ/mới;
- tắt enforcement nhưng vẫn giữ safe guards Phase 0;
- không xóa history/evidence;
- manifest/status module có thể disable độc lập;
- không rollback về provider hard-code source.

## 10. Checklist nghiệm thu

- [ ] Runtime manifest ổn định, redacted và đổi khi source đổi.
- [ ] Provider/model thực tế được lưu.
- [ ] Prompt/policy có ID/hash.
- [ ] Source registry phân biệt generator/evidence.
- [ ] Claim ledger dual-write hoạt động.
- [ ] Old session đọc được, không reset Redis.
- [ ] Diagnostics snapshot/vector/cache đầy đủ.
- [ ] Secret/PII redaction suite xanh.
- [ ] Critical claim enforcement xanh.
- [ ] Rollback schema/enforcement được thử.
