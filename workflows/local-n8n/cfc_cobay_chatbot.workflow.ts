import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CFC Co Bay Chatbot
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
    id: 'uJOo6NQO2mJZhUAr',
    name: 'CFC Co Bay Chatbot',
    active: false,
    description: 'a',
    isArchived: false,
    settings: { executionOrder: 'v1', binaryMode: 'separate', availableInMCP: true },
})
export class CfcCoBayChatbotWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'e91ecffd-fd90-42de-ad11-6bc8ce3f7d00',
        webhookId: '98ef5c46-bab4-4f70-b110-63007639e882',
        name: 'Messenger Trigger',
        type: 'n8n-nodes-base.facebookTrigger',
        version: 1,
        position: [0, 304],
        credentials: { facebookGraphAppApi: { id: 'H7jFvG3kDaEFuBjD', name: 'CFC Cò Bay' } },
    })
    MessengerTrigger = {
        appId: '946909570780806',
        object: 'page',
        fields: ['messages'],
        options: {},
    };

    @node({
        id: '78996a74-05e4-470e-8a9d-e65f082773f0',
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
let attachmentType = '';
let latitude = null;
let longitude = null;

const messaging = data?.messaging?.[0]
  || (data?.message && data?.sender ? data : null)
  || data?.body?.entry?.[0]?.messaging?.[0]
  || data?.entry?.[0]?.messaging?.[0]
  || null;

if (messaging) {
  text = messaging?.message?.text || messaging?.message?.quick_reply?.payload || '';
  senderId = messaging?.sender?.id || '';
  messageId = messaging?.message?.mid || '';
  const attachments = messaging?.message?.attachments || [];
  hasAttachment = Boolean(attachments.length);
  isEcho = Boolean(messaging?.message?.is_echo);
  const locationAttachment = attachments.find((item) => (
    item?.type === 'location' || item?.payload?.coordinates
  ));
  const payload = locationAttachment?.payload || {};
  const coordinates = payload?.coordinates || payload?.location || {};
  const rawLatitude = coordinates?.lat ?? coordinates?.latitude;
  const rawLongitude = coordinates?.long ?? coordinates?.lng ?? coordinates?.longitude;
  if (rawLatitude !== undefined && rawLongitude !== undefined) {
    const parsedLatitude = Number(rawLatitude);
    const parsedLongitude = Number(rawLongitude);
    if (Number.isFinite(parsedLatitude) && Number.isFinite(parsedLongitude)) {
      latitude = parsedLatitude;
      longitude = parsedLongitude;
      attachmentType = 'location';
    }
  }
}

const emptyInput = !text || !text.trim();
const inputKind = attachmentType === 'location'
  ? 'location'
  : (emptyInput ? (hasAttachment ? 'attachment' : 'empty') : 'text');

// Echo, malformed sender and truly empty events must never reach the chatbot.
if (isEcho || !senderId || (emptyInput && !hasAttachment)) {
  return [];
}

return [{ json: {
  text: text.trim(),
  senderId,
  messageId,
  emptyInput,
  inputKind,
  attachmentType,
  latitude,
  longitude,
  isEcho,
} }];
`,
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000001',
        name: 'Goi Fast API Chat Pipeline',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [448, 304],
    })
    GoiFastApiChatPipeline = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/api/chat-pipeline' }}",
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ { brand: "cfc", sender_id: $json.senderId, text: $json.text, fb_name: $json.fb_name || "", message_id: $json.messageId || "", input_kind: $json.inputKind, attachment_type: $json.attachmentType || "", latitude: $json.latitude, longitude: $json.longitude } }}',
        options: {
            timeout: 30000,
        },
    };

    @node({
        id: 'f3000001-0000-0000-0000-000000000002',
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
        id: '965d18a8-f64f-458d-adb9-3c1538209a80',
        name: 'Nhan Khach Auto',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.1,
        position: [900, 304],
        credentials: { facebookGraphApi: { id: 'cKx1OHWWIdDjOUuM', name: 'Cò bay' } },
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
