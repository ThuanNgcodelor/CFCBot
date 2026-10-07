import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : [TEST] Zeo Chatbot
// Nodes   : 5  |  Connections: 4
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// MessengerTrigger                   facebookTrigger            [creds]
// LocDauVao                          code
// GoiFastApiChatPipeline             httpRequest
// PrepareMessengerReply              code
// NhanKhachAuto                      httpRequest                [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// MessengerTrigger
//    → LocDauVao
//      → GoiFastApiChatPipeline
//        → PrepareMessengerReply
//          → NhanKhachAuto
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'stDI5UffKsus3OQd',
    name: '[TEST] Zeo Chatbot',
    active: false,
    description: 'b',
    isArchived: false,
    projectId: 'A5416cGJlo1X0rDa',
    settings: { executionOrder: 'v1', binaryMode: 'separate', availableInMCP: true },
})
export class TestZeoChatbotWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'a7608503-8321-4a24-ae34-761f0e60a1c8',
        webhookId: '86033447-f404-40f3-bc7b-5934b6c61737',
        name: 'Messenger Trigger',
        type: 'n8n-nodes-base.facebookTrigger',
        version: 1,
        position: [0, 304],
        credentials: { facebookGraphAppApi: { id: 'DPEr450xHI0lpcpn', name: 'ZeO' } },
    })
    MessengerTrigger = {
        appId: '701126356010152',
        object: 'page',
        fields: ['messages'],
        options: {},
    };

    @node({
        id: 'a1efe7a3-c9b5-4537-bf2b-92603ca52710',
        name: 'Loc Dau Vao',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [224, 304],
    })
    LocDauVao = {
        jsCode: `
const data = $input.first().json;
let text = '';
let senderId = '';
let messageId = '';
let hasAttachment = false;
let isEcho = false;

const messaging = data?.messaging?.[0]
  || (data?.message && data?.sender ? data : null)
  || data?.body?.entry?.[0]?.messaging?.[0]
  || data?.entry?.[0]?.messaging?.[0]
  || null;

if (messaging) {
  text = messaging.message?.text || messaging.message?.quick_reply?.payload || '';
  senderId = messaging.sender?.id || '';
  messageId = messaging.message?.mid || '';
  hasAttachment = Boolean(messaging.message?.attachments?.length);
  isEcho = Boolean(messaging.message?.is_echo);
}

const emptyInput = !text || !text.trim();

return [{ json: {
  text: text.trim(),
  senderId,
  messageId,
  emptyInput,
  inputKind: emptyInput ? (hasAttachment ? 'attachment' : 'empty') : 'text',
  isEcho,
} }];
`,
    };

    @node({
        id: 'e5c0285a-2e66-4d64-b60d-8e4634a00799',
        name: 'Goi Fast API Chat Pipeline',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [448, 304],
    })
    GoiFastApiChatPipeline = {
        method: 'POST',
        url: 'http://127.0.0.1:7777/api/chat-pipeline',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { brand: "zeo", sender_id: $json.senderId, text: $json.text, fb_name: $json.fb_name || "", message_id: $json.messageId || "" } }}',
        options: {
            timeout: 30000,
        },
    };

    @node({
        id: '3329094d-ec8b-4d03-a5b8-db4936743193',
        name: 'Prepare Messenger Reply',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [680, 304],
    })
    PrepareMessengerReply = {
        jsCode: `
const input = $('Loc Dau Vao').first().json;
let pipelineRes = {};
try {
  pipelineRes = $input.first().json || {};
} catch (e) {
  pipelineRes = {};
}
// Fail closed: error payload, duplicate/takeover, malformed JSON or empty answer
// must not be transformed into a customer-facing success message.
if (
  !pipelineRes
  || typeof pipelineRes !== 'object'
  || pipelineRes.error
  || pipelineRes.duplicate === true
  || pipelineRes.suppress_send === true
  || ['duplicate_in_flight', 'human_handoff_active'].includes(pipelineRes.intent)
) {
  return [];
}
const finalReply = typeof pipelineRes.answer === 'string' ? pipelineRes.answer.trim() : '';
if (!finalReply) {
  return [];
}

return [{
  json: {
    senderId: input.senderId,
    finalReply: finalReply,
  }
}];
`,
    };

    @node({
        id: 'ae193da2-9bad-4c5c-81f5-8ccfaee61b47',
        name: 'Nhan Khach Auto',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [900, 304],
        credentials: { facebookGraphApi: { id: 'JyJ5NRHHJdzjsL4R', name: 'ZeO' } },
    })
    NhanKhachAuto = {
        method: 'POST',
        url: 'https://graph.facebook.com/v17.0/me/messages',
        authentication: 'predefinedCredentialType',
        nodeCredentialType: 'facebookGraphApi',
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ { recipient: { id: $json.senderId }, message: { text: $json.finalReply } } }}',
        options: {},
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.MessengerTrigger.out(0).to(this.LocDauVao.in(0));
        this.LocDauVao.out(0).to(this.GoiFastApiChatPipeline.in(0));
        this.GoiFastApiChatPipeline.out(0).to(this.PrepareMessengerReply.in(0));
        this.PrepareMessengerReply.out(0).to(this.NhanKhachAuto.in(0));
    }
}
