import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : CFC Co Bay Knowledge
// Nodes   : 9  |  Connections: 8
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// ReadCfcFaqRows                     googleSheets               [creds]
// NormalizeCfcKnowledge              code
// WriteCfcRedisCandidate             redis                      [creds]
// WriteCfcRedisSyncMetadata          redis                      [creds]
// RebuildCfcVectorIndex              httpRequest
// ValidateCfcSync                    code
// PromoteCfcRedisSnapshot            redis                      [creds]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → ReadCfcFaqRows
//      → NormalizeCfcKnowledge
//        → WriteCfcRedisCandidate
//          → RebuildCfcVectorIndex
//            → ValidateCfcSync
//              → PromoteCfcRedisSnapshot
//                → WriteCfcRedisSyncMetadata
// ScheduleTrigger
//    → ReadCfcFaqRows (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: '92I5floRW5MElgu5',
    name: 'CFC Co Bay Knowledge',
    active: false,
    description: 'a',
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1', binaryMode: 'separate', availableInMCP: true },
})
export class CfcCoBayKnowledgeWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'a40181a3-dcf8-458b-9801-3d217b3a1401',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: 'b1eea6aa-76bd-478f-88e5-25fa00303d1b',
        name: 'Schedule Trigger',
        type: 'n8n-nodes-base.scheduleTrigger',
        version: 1.3,
        position: [0, 352],
    })
    ScheduleTrigger = {
        rule: {
            interval: [
                {
                    field: 'minutes',
                },
            ],
        },
    };

    @node({
        id: 'e22c7c88-d49e-449f-ac52-d972805b6a33',
        name: 'Read CFC FAQ Rows',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [256, 256],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
    })
    ReadCfcFaqRows = {
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1EBiuH3TVVSwLQE1loQ2bYijlaJPHGGFB9rAXM3xP9Tw/edit?gid=0#gid=0',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 'gid=0',
            mode: 'list',
            cachedResultName: 'FAQ',
            cachedResultUrl:
                'https://docs.google.com/spreadsheets/d/1EBiuH3TVVSwLQE1loQ2bYijlaJPHGGFB9rAXM3xP9Tw/edit#gid=0',
        },
        options: {},
    };

    @node({
        id: '65ab22fd-b35a-4c9a-ae36-a920b8bc7728',
        name: 'Normalize CFC Knowledge',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 256],
    })
    NormalizeCfcKnowledge = {
        jsCode: `
function text(value) {
  return String(value || '').replace(/\\s+/g, ' ').trim();
}

function asBool(value) {
  if (typeof value === 'boolean') return value;
  return ['true', '1', 'yes', 'y'].includes(String(value || '').trim().toLowerCase());
}

function examples(value) {
  if (Array.isArray(value)) return value.map(text).filter(Boolean);
  return String(value || '').split(';').map(text).filter(Boolean);
}

function tags(value) {
  if (Array.isArray(value)) return value.map(text).filter(Boolean);
  return String(value || '').split(/[|;,]/).map(text).filter(Boolean);
}

function brandKey(value) {
  return text(value).toLowerCase().replace(/\\s*\\/\\s*/g, '/');
}

function fnv1a(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

const cfcBrandKeys = new Set(['cfc', 'co bay', 'cò bay', 'cfc/co bay', 'cfc/cò bay']);
const normalizedRows = $input.all()
  .map((item, index) => ({
    active: asBool(item.json.active ?? true),
    brand: text(item.json.brand || 'CFC'),
    category: text(item.json.category || 'faq'),
    intent: text(item.json.intent),
    question_examples: examples(item.json.question_examples),
    answer: text(item.json.answer),
    priority: Number(item.json.priority || 0),
    source_id: text(item.json.source_id || 'cfc_faq_google_sheet'),
    updated_at: text(item.json.updated_at || new Date().toISOString().slice(0, 10)),
    audience: text(item.json.audience || 'customer').toLowerCase(),
    answer_mode: text(item.json.answer_mode || 'direct').toLowerCase(),
    risk_level: text(item.json.risk_level || (['support', 'policy'].includes(text(item.json.category)) ? 'medium' : 'low')).toLowerCase(),
    learning_tags: tags(item.json.learning_tags),
    profile_slots: tags(item.json.profile_slots),
    escalation_policy: text(item.json.escalation_policy || ''),
    row_index: index + 1,
  }));
const knowledgeItems = normalizedRows
  .filter(item => item.active)
  .filter(item => cfcBrandKeys.has(brandKey(item.brand)))
  .filter(item => item.intent && item.answer)
  .filter(item => item.audience === 'customer');

const duplicateIntents = [...new Set(knowledgeItems.map(item => item.intent).filter((intent, index, all) => all.indexOf(intent) !== index))];
const invalidExampleRows = knowledgeItems.filter(item => item.question_examples.length < 1).map(item => item.row_index);
if (knowledgeItems.length < 5) {
  throw new Error('Từ chối ghi Redis: CFC chỉ còn ' + knowledgeItems.length + ' mục hợp lệ (tối thiểu 5). Snapshot cũ vẫn được giữ nguyên.');
}
if (duplicateIntents.length) {
  throw new Error('Từ chối ghi Redis: intent bị trùng: ' + duplicateIntents.join(', '));
}
if (invalidExampleRows.length) {
  throw new Error('Từ chối ghi Redis: thiếu question_examples tại dòng ' + invalidExampleRows.join(', '));
}

knowledgeItems.sort((a, b) => b.priority - a.priority || a.intent.localeCompare(b.intent));
const snapshotJson = JSON.stringify(knowledgeItems);
const excludedInternalCount = normalizedRows.filter(item => item.active && item.audience === 'internal').length;

return [{
  json: {
    snapshot_key: 'cfc:kb:basic:active',
    candidate_key: 'cfc:kb:basic:candidate',
    brand_scope: 'CFC/Co Bay',
    knowledge_count: knowledgeItems.length,
    updated_at: new Date().toISOString(),
    schema_version: 2,
    snapshot_hash: fnv1a(snapshotJson),
    excluded_internal_count: excludedInternalCount,
    snapshot_json: snapshotJson,
  },
}];
`,
    };

    @node({
        id: '0ecb9657-0883-4cb7-93bb-060e5680b3cb',
        name: 'Write CFC Redis Candidate',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [768, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteCfcRedisCandidate = {
        operation: 'set',
        key: 'cfc:kb:basic:candidate',
        value: '={{ JSON.stringify($json) }}',
    };

    @node({
        id: 'f6858707-11f8-4dfe-829d-2b41c1e2e183',
        name: 'Write CFC Redis Sync Metadata',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1792, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteCfcRedisSyncMetadata = {
        operation: 'set',
        key: 'cfc:sync:faq:basic:last-success',
        value: '={{ JSON.stringify({ snapshot_key: $("Normalize CFC Knowledge").first().json.snapshot_key, candidate_key: $("Normalize CFC Knowledge").first().json.candidate_key, knowledge_count: $("Normalize CFC Knowledge").first().json.knowledge_count, excluded_internal_count: $("Normalize CFC Knowledge").first().json.excluded_internal_count, updated_at: $("Normalize CFC Knowledge").first().json.updated_at, schema_version: $("Normalize CFC Knowledge").first().json.schema_version, snapshot_hash: $("Normalize CFC Knowledge").first().json.snapshot_hash, snapshot_validated: $("Validate CFC Sync").first().json.snapshot_validated, vector_rebuilt: $("Validate CFC Sync").first().json.vector_rebuilt, hot_cache_refreshed: $("Validate CFC Sync").first().json.hot_cache_refreshed, complete: $("Validate CFC Sync").first().json.complete }) }}',
    };

    @node({
        id: 'a23ad1aa-bb2e-4b2c-9b30-9017cfc00101',
        name: 'Rebuild CFC Vector Index',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1024, 256],
    })
    RebuildCfcVectorIndex = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/sync' }}",
        sendQuery: true,
        queryParameters: {
            parameters: [
                {
                    name: 'brand',
                    value: 'cfc',
                },
                {
                    name: 'snapshot_key',
                    value: 'cfc:kb:basic:candidate',
                },
            ],
        },
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: 'a23ad1aa-bb2e-4b2c-9b30-9017cfc00102',
        name: 'Validate CFC Sync',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1280, 256],
    })
    ValidateCfcSync = {
        jsCode: `
const result = $input.first().json || {};
const expectedKey = $('Normalize CFC Knowledge').first().json.candidate_key;
const missing = [
  ['complete', result.complete === true],
  ['snapshot_validated', result.snapshot_validated === true],
  ['vector_rebuilt', result.vector_rebuilt === true],
  ['hot_cache_refreshed', result.hot_cache_refreshed === true],
  ['snapshot_key', result.snapshot_key === expectedKey],
].filter(([, ok]) => !ok).map(([name]) => name);
if (missing.length) {
  throw new Error('KNOWLEDGE_SYNC_INCOMPLETE:' + missing.join(','));
}
return [{ json: result }];
`,
    };

    @node({
        id: 'a23ad1aa-bb2e-4b2c-9b30-9017cfc00103',
        name: 'Promote CFC Redis Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1536, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    PromoteCfcRedisSnapshot = {
        operation: 'set',
        key: 'cfc:kb:basic:active',
        value: '={{ JSON.stringify($("Normalize CFC Knowledge").first().json) }}',
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.ReadCfcFaqRows.in(0));
        this.ScheduleTrigger.out(0).to(this.ReadCfcFaqRows.in(0));
        this.ReadCfcFaqRows.out(0).to(this.NormalizeCfcKnowledge.in(0));
        this.NormalizeCfcKnowledge.out(0).to(this.WriteCfcRedisCandidate.in(0));
        this.WriteCfcRedisCandidate.out(0).to(this.RebuildCfcVectorIndex.in(0));
        this.RebuildCfcVectorIndex.out(0).to(this.ValidateCfcSync.in(0));
        this.ValidateCfcSync.out(0).to(this.PromoteCfcRedisSnapshot.in(0));
        this.PromoteCfcRedisSnapshot.out(0).to(this.WriteCfcRedisSyncMetadata.in(0));
    }
}
