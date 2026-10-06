# n8n source mapping — 2026-10-06

Local source hiện có:

| Chức năng | Source |
|---|---|
| CFC Messenger chatbot | `workflows/local-n8n/cfc_cobay_chatbot.workflow.ts` |
| ZeO Messenger chatbot | `workflows/local-n8n/zeo_chatbot.workflow.ts` |
| CFC knowledge sync | `workflows/local-n8n/cfc_knowledge_sync_basic.workflow.ts` |
| ZeO knowledge sync | `workflows/local-n8n/zeo_knowledge_sync_basic.workflow.ts` |
| AMIS public sync | `workflows/local-n8n/amis_crm_public_sync.workflow.ts` |
| AMIS full warm | `workflows/local-n8n/amis_crm_full_warm.workflow.ts` |
| Operations alert | `workflows/local-n8n/chatbot_operations_alert.workflow.ts` |

Live workflow ID, published status và drift: **chưa xác định**. Lệnh
`n8nac env status --json` trả `configured=false` vì workspace/API key chưa được
cấu hình. Theo read-before-write policy, không list/pull/push/publish workflow.

Khi owner cung cấp API key: chạy `n8nac env add`, xác nhận `env status --json`,
list và pull live trước; chỉ sau đó mới thiết kế n8n adapter gọi
`POST /api/messaging/enqueue` và delivery callback.
