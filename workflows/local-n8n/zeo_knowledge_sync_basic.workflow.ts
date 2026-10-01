import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Zeo Knowledge
// Nodes   : 17  |  Connections: 18
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// ReadFaqRows                        googleSheets               [creds]
// NormalizeKnowledge                 code
// WriteRedisCandidate                redis                      [creds]
// WriteRedisSyncMetadata             redis                      [creds]
// RebuildZeoVectorIndex              httpRequest
// ValidateZeoSync                    code
// PromoteRedisSnapshot               redis                      [creds]
// ReadShopeeRows                     googleSheets               [creds]
// NormalizeShopeeCatalog             code
// WriteShopeeRedisSnapshot           redis                      [creds]
// NotifyFastapiShopeeCache           httpRequest                [onError→regular]
// ReadWebRows                        googleSheets               [creds]
// NormalizeWebCatalog                code
// WriteWebRedisSnapshot              redis                      [creds]
// NotifyFastapiWebCache              httpRequest                [onError→regular]
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → ReadFaqRows
//      → NormalizeKnowledge
//        → WriteRedisCandidate
//          → RebuildZeoVectorIndex
//            → ValidateZeoSync
//              → PromoteRedisSnapshot
//                → WriteRedisSyncMetadata
//    → ReadShopeeRows
//      → NormalizeShopeeCatalog
//        → WriteShopeeRedisSnapshot
//          → NotifyFastapiShopeeCache
//    → ReadWebRows
//      → NormalizeWebCatalog
//        → WriteWebRedisSnapshot
//          → NotifyFastapiWebCache
// ScheduleTrigger
//    → ReadFaqRows (↩ loop)
//    → ReadShopeeRows (↩ loop)
//    → ReadWebRows (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'DhrLUsDsldhxtTdX',
    name: 'Zeo Knowledge',
    active: false,
    description: 'b',
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1', binaryMode: 'separate', availableInMCP: true },
})
export class ZeoKnowledgeWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'dab3bcba-1599-4b04-9c28-1a1e9f472254',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: '348d7851-139b-4e44-baaf-6542a6fc9223',
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
        id: '7d2703ee-b76b-45ef-939c-0ba057aae77f',
        name: 'Read FAQ Rows',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [256, 256],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
    })
    ReadFaqRows = {
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1SkxtMEydeOgzUefNMUxQrTu9D9aYIsSvHW3xLHtxNmQ/edit?gid=654759924#gid=654759924',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 654759924,
            mode: 'list',
            cachedResultName: 'FAQ',
            cachedResultUrl:
                'https://docs.google.com/spreadsheets/d/1SkxtMEydeOgzUefNMUxQrTu9D9aYIsSvHW3xLHtxNmQ/edit#gid=654759924',
        },
        options: {},
    };

    @node({
        id: 'ca4ea85f-f852-4c5f-b010-8045d68be80a',
        name: 'Normalize Knowledge',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 256],
    })
    NormalizeKnowledge = {
        jsCode: `
function normalizeText(value) {
  return String(value || '').replace(/\\s+/g, ' ').trim();
}

function asBool(value) {
  if (typeof value === 'boolean') return value;
  return ['true', '1', 'yes', 'y'].includes(String(value || '').trim().toLowerCase());
}

function splitExamples(value) {
  if (Array.isArray(value)) return value.map(String).map(normalizeText).filter(Boolean);
  return String(value || '').split(';').map(normalizeText).filter(Boolean);
}

function splitTags(value) {
  if (Array.isArray(value)) return value.map(String).map(normalizeText).filter(Boolean);
  return String(value || '').split(/[|;,]/).map(normalizeText).filter(Boolean);
}

function normalizeBrand(value) {
  const brand = normalizeText(value || 'ZeO');
  return brand || 'ZeO';
}

function brandKey(value) {
  return normalizeBrand(value).toLowerCase().replace(/\\s*\\/\\s*/g, '/');
}

function normalizeRow(row, index) {
  const intent = normalizeText(row.intent || '');
  const category = normalizeText(row.category || 'faq');
  const answer = normalizeText(row.answer || '')
    .replace(/^Theo Brand Bible,[ ]*/i, '')
    .replace(/[ ]+Theo Brand Bible,[ ]*/gi, ' ')
    .replace(/^Theo tài liệu hiện tại,[ ]*/i, '')
    .replace(/[ ]+Theo tài liệu hiện tại,[ ]*/gi, ' ')
    .replace(/Slogan được ghi cho ZeO trong Brand Bible là/gi, 'Slogan của ZeO là')
    .replace(/[ ]+trong Brand Bible[ ]+/gi, ' ')
    .replace(/[ ]+/g, ' ')
    .trim();
  const internalIntents = new Set([
    'new_customer_welcome_template',
    'post_purchase_followup_template',
    'loyal_customer_thank_template',
    'promotion_announcement_template',
    'tone_of_voice_guidelines',
    'tone_of_voice_restrictions',
    'tiktok_reels_content_style',
    'ecommerce_product_description_style',
    'facebook_zalo_content_style',
    'email_zalo_business_style',
    'review_response_guidelines',
    'complaint_handling_principles',
    'complaint_severity_levels',
    'complaint_one_star_review',
    'pano_brand_colors',
    'brand_typography',
    'brand_key_selling_points',
    'product_recommendation_by_need',
  ]);
  const hasTemplatePlaceholder = /{{[^}]+}}|[[A-Z_]{2,}]|<[^>]+>/.test(answer);
  const explicitAudience = normalizeText(row.audience || '').toLowerCase();
  const audience = explicitAudience || (internalIntents.has(intent) || hasTemplatePlaceholder ? 'internal' : 'customer');
  const explicitMode = normalizeText(row.answer_mode || '').toLowerCase();
  const answerMode = explicitMode || 'direct';
  return {
    active: asBool(row.active ?? true),
    brand: normalizeBrand(row.brand),
    category,
    intent,
    question_examples: splitExamples(row.question_examples),
    answer,
    priority: Number(row.priority || 0),
    source_id: normalizeText(row.source_id || 'zeo_faq_google_sheet'),
    updated_at: normalizeText(row.updated_at || new Date().toISOString().slice(0, 10)),
    audience,
    answer_mode: answerMode,
    risk_level: normalizeText(row.risk_level || (['policy', 'support'].includes(category) ? 'medium' : 'low')).toLowerCase(),
    learning_tags: splitTags(row.learning_tags),
    profile_slots: splitTags(row.profile_slots),
    escalation_policy: normalizeText(row.escalation_policy || ''),
    row_index: index + 1,
  };
}

function fnv1a(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

const allowedBrands = new Set(['zeo', 'pano', 'oplus', 'zeo/oplus', 'zeo/pano', 'zeo/pano/oplus']);
const normalizedRows = $input.all().map((item, index) => normalizeRow(item.json, index));
const knowledgeItems = normalizedRows
  .filter(item => item.active)
  .filter(item => allowedBrands.has(brandKey(item.brand)))
  .filter(item => item.answer && item.intent)
  .filter(item => item.audience === 'customer');

const duplicateIntents = [...new Set(knowledgeItems.map(item => item.intent).filter((intent, index, all) => all.indexOf(intent) !== index))];
const invalidExampleRows = knowledgeItems.filter(item => item.question_examples.length < 1).map(item => item.row_index);
if (knowledgeItems.length < 10) {
  throw new Error('Từ chối ghi Redis: ZeO chỉ còn ' + knowledgeItems.length + ' mục hợp lệ (tối thiểu 10). Snapshot cũ vẫn được giữ nguyên.');
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
    snapshot_key: 'zeo:kb:basic:active',
    candidate_key: 'zeo:kb:basic:candidate',
    brand_scope: 'ZeO/PANO/Oplus',
    knowledge_count: knowledgeItems.length,
    updated_at: new Date().toISOString(),
    schema_version: 2,
    snapshot_hash: fnv1a(snapshotJson),
    excluded_internal_count: excludedInternalCount,
    snapshot_json: snapshotJson,
  }
}];
`,
    };

    @node({
        id: 'c325b9d5-28fc-4871-af86-d289c0cdbeac',
        name: 'Write Redis Candidate',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [768, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteRedisCandidate = {
        operation: 'set',
        key: 'zeo:kb:basic:candidate',
        value: '={{ JSON.stringify($json) }}',
    };

    @node({
        id: '0be28c5b-7d4d-4bd4-a9b2-1f761c08d3a8',
        name: 'Write Redis Sync Metadata',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1792, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteRedisSyncMetadata = {
        operation: 'set',
        key: 'zeo:sync:faq:basic:last-success',
        value: '={{ JSON.stringify({ snapshot_key: $("Normalize Knowledge").first().json.snapshot_key, candidate_key: $("Normalize Knowledge").first().json.candidate_key, knowledge_count: $("Normalize Knowledge").first().json.knowledge_count, excluded_internal_count: $("Normalize Knowledge").first().json.excluded_internal_count, updated_at: $("Normalize Knowledge").first().json.updated_at, schema_version: $("Normalize Knowledge").first().json.schema_version, snapshot_hash: $("Normalize Knowledge").first().json.snapshot_hash, snapshot_validated: $("Validate ZeO Sync").first().json.snapshot_validated, vector_rebuilt: $("Validate ZeO Sync").first().json.vector_rebuilt, hot_cache_refreshed: $("Validate ZeO Sync").first().json.hot_cache_refreshed, complete: $("Validate ZeO Sync").first().json.complete }) }}',
    };

    @node({
        id: 'a23ad1aa-bb2e-4b2c-9b30-9017e0010101',
        name: 'Rebuild ZeO Vector Index',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1024, 256],
    })
    RebuildZeoVectorIndex = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/sync' }}",
        sendQuery: true,
        queryParameters: {
            parameters: [
                {
                    name: 'brand',
                    value: 'zeo',
                },
                {
                    name: 'snapshot_key',
                    value: 'zeo:kb:basic:candidate',
                },
            ],
        },
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: 'a23ad1aa-bb2e-4b2c-9b30-9017e0010102',
        name: 'Validate ZeO Sync',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1280, 256],
    })
    ValidateZeoSync = {
        jsCode: `
const result = $input.first().json || {};
const expectedKey = $('Normalize Knowledge').first().json.candidate_key;
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
        id: 'a23ad1aa-bb2e-4b2c-9b30-9017e0010103',
        name: 'Promote Redis Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [1536, 256],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    PromoteRedisSnapshot = {
        operation: 'set',
        key: 'zeo:kb:basic:active',
        value: '={{ JSON.stringify($("Normalize Knowledge").first().json) }}',
    };

    @node({
        id: '2b000001-0000-0000-0000-000000000001',
        name: 'Read Shopee Rows',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [256, 480],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
    })
    ReadShopeeRows = {
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1SkxtMEydeOgzUefNMUxQrTu9D9aYIsSvHW3xLHtxNmQ/edit?gid=654759924#gid=654759924',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 944270019,
            mode: 'list',
            cachedResultName: 'Shopee',
            cachedResultUrl:
                'https://docs.google.com/spreadsheets/d/1SkxtMEydeOgzUefNMUxQrTu9D9aYIsSvHW3xLHtxNmQ/edit#gid=944270019',
        },
        options: {},
    };

    @node({
        id: '2b000001-0000-0000-0000-000000000002',
        name: 'Normalize Shopee Catalog',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 480],
    })
    NormalizeShopeeCatalog = {
        jsCode: `
function text(v) {
  return String(v || '').replace(/\\s+/g, ' ').trim();
}
function asBool(v) {
  if (typeof v === 'boolean') return v;
  return ['true', '1', 'yes', 'y'].includes(String(v || '').trim().toLowerCase());
}
function parseList(v) {
  if (Array.isArray(v)) return v.map(text).filter(Boolean);
  return String(v || '').split(/[;|,]/).map(text).filter(Boolean);
}
const rows = $input.all().map(item => item.json);
const products = [];
for (const r of rows) {
  const active = asBool(r.active ?? true);
  const name = text(r.name);
  const link = text(r.link_shopee || r.shopee_url || r.link);
  if (!active || !name || !link) continue;
  const inStock = asBool(r.in_stock ?? true);
  const priceNum = Number(String(r.price || 0).replace(/[^0-9]/g, ''));
  const origPriceNum = Number(String(r.original_price || priceNum).replace(/[^0-9]/g, ''));
  products.push({
    item_id: text(r.item_id || name),
    name, brand: text(r.brand || 'ZeO'),
    category: text(r.category || 'Tẩy rửa & Giặt giũ'),
    price: priceNum, original_price: origPriceNum,
    discount: text(r.discount || ''),
    specs: text(r.specs || name),
    keywords: parseList(r.keywords),
    variants: parseList(r.variants),
    link_shopee: link,
    in_stock: inStock,
    badge: text(r.badge || 'STANDARD'),
    updated_at: new Date().toISOString(),
  });
}
if (products.length < 1) throw new Error('Từ chối ghi Redis: Danh mục Shopee không có sản phẩm hợp lệ.');
const snapshotJson = JSON.stringify(products);
return [{ json: { snapshot_key: 'zeo:shopee:catalog:active', product_count: products.length, updated_at: new Date().toISOString(), snapshot_json: snapshotJson } }];
`,
    };

    @node({
        id: '2b000001-0000-0000-0000-000000000003',
        name: 'Write Shopee Redis Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [768, 480],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteShopeeRedisSnapshot = {
        operation: 'set',
        key: 'zeo:shopee:catalog:active',
        value: '={{ $json.snapshot_json }}',
    };

    @node({
        id: '2b000001-0000-0000-0000-000000000004',
        name: 'Notify FastAPI Shopee Cache',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1024, 480],
        onError: 'continueRegularOutput',
    })
    NotifyFastapiShopeeCache = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/api/shopee/refresh-cache' }}",
        options: {
            timeout: 10000,
        },
    };

    @node({
        id: '3c000001-0000-0000-0000-000000000001',
        name: 'Read Web Rows',
        type: 'n8n-nodes-base.googleSheets',
        version: 4.7,
        position: [256, 704],
        credentials: { googleSheetsOAuth2Api: { id: 'li88zysXKFUU5A0d', name: 'Google Sheets account' } },
    })
    ReadWebRows = {
        documentId: {
            __rl: true,
            value: 'https://docs.google.com/spreadsheets/d/1SkxtMEydeOgzUefNMUxQrTu9D9aYIsSvHW3xLHtxNmQ/edit?gid=170432919#gid=170432919',
            mode: 'url',
        },
        sheetName: {
            __rl: true,
            value: 170432919,
            mode: 'list',
            cachedResultName: 'Web',
            cachedResultUrl:
                'https://docs.google.com/spreadsheets/d/1SkxtMEydeOgzUefNMUxQrTu9D9aYIsSvHW3xLHtxNmQ/edit#gid=170432919',
        },
        options: {},
    };

    @node({
        id: '3c000001-0000-0000-0000-000000000002',
        name: 'Normalize Web Catalog',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [512, 704],
    })
    NormalizeWebCatalog = {
        jsCode: `
function text(v) {
  return String(v || '').replace(/\\s+/g, ' ').trim();
}
function asBool(v) {
  if (typeof v === 'boolean') return v;
  return ['true', '1', 'yes', 'y'].includes(String(v || '').trim().toLowerCase());
}
function parseList(v) {
  if (Array.isArray(v)) return v.map(text).filter(Boolean);
  return String(v || '').split(/[;|,]/).map(text).filter(Boolean);
}
const rows = $input.all().map(item => item.json);
const products = [];
for (const r of rows) {
  const active = asBool(r.active ?? true);
  const name = text(r.name);
  const link = text(r.link_web || r.web_url || r.link);
  if (!active || !name || !link) continue;
  const inStock = asBool(r.in_stock ?? true);
  const priceNum = Number(String(r.price || 0).replace(/[^0-9]/g, ''));
  const origPriceNum = Number(String(r.original_price || priceNum).replace(/[^0-9]/g, ''));
  products.push({
    item_id: text(r.item_id || name),
    name,
    brand: text(r.brand || 'ZeO'),
    category: text(r.category || 'Tẩy rửa & Giặt giũ'),
    price: priceNum,
    original_price: origPriceNum,
    link_web: link,
    in_stock: inStock,
    keywords: parseList(r.keywords),
    updated_at: new Date().toISOString(),
  });
}
if (products.length < 1) throw new Error('Từ chối ghi Redis: Danh mục Web không có sản phẩm hợp lệ.');
const snapshotJson = JSON.stringify(products);
return [{ json: { snapshot_key: 'zeo:web:catalog:active', product_count: products.length, updated_at: new Date().toISOString(), snapshot_json: snapshotJson } }];
`,
    };

    @node({
        id: '3c000001-0000-0000-0000-000000000003',
        name: 'Write Web Redis Snapshot',
        type: 'n8n-nodes-base.redis',
        version: 1,
        position: [768, 704],
        credentials: { redis: { id: 'DW6fQRCZ77RgdCqL', name: 'Zeo Redis (local)' } },
    })
    WriteWebRedisSnapshot = {
        operation: 'set',
        key: 'zeo:web:catalog:active',
        value: '={{ $json.snapshot_json }}',
    };

    @node({
        id: '3c000001-0000-0000-0000-000000000004',
        name: 'Notify FastAPI Web Cache',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1024, 704],
        onError: 'continueRegularOutput',
    })
    NotifyFastapiWebCache = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/api/web/refresh-cache' }}",
        options: {
            timeout: 10000,
        },
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.ReadFaqRows.in(0));
        this.ManualTrigger.out(0).to(this.ReadShopeeRows.in(0));
        this.ManualTrigger.out(0).to(this.ReadWebRows.in(0));
        this.ScheduleTrigger.out(0).to(this.ReadFaqRows.in(0));
        this.ScheduleTrigger.out(0).to(this.ReadShopeeRows.in(0));
        this.ScheduleTrigger.out(0).to(this.ReadWebRows.in(0));
        this.ReadFaqRows.out(0).to(this.NormalizeKnowledge.in(0));
        this.NormalizeKnowledge.out(0).to(this.WriteRedisCandidate.in(0));
        this.WriteRedisCandidate.out(0).to(this.RebuildZeoVectorIndex.in(0));
        this.RebuildZeoVectorIndex.out(0).to(this.ValidateZeoSync.in(0));
        this.ValidateZeoSync.out(0).to(this.PromoteRedisSnapshot.in(0));
        this.PromoteRedisSnapshot.out(0).to(this.WriteRedisSyncMetadata.in(0));
        this.ReadShopeeRows.out(0).to(this.NormalizeShopeeCatalog.in(0));
        this.NormalizeShopeeCatalog.out(0).to(this.WriteShopeeRedisSnapshot.in(0));
        this.WriteShopeeRedisSnapshot.out(0).to(this.NotifyFastapiShopeeCache.in(0));
        this.ReadWebRows.out(0).to(this.NormalizeWebCatalog.in(0));
        this.NormalizeWebCatalog.out(0).to(this.WriteWebRedisSnapshot.in(0));
        this.WriteWebRedisSnapshot.out(0).to(this.NotifyFastapiWebCache.in(0));
    }
}
