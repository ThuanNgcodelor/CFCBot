import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : AMIS CRM Full Warm — Redis Sync Every 1h
// Nodes   : 8  |  Connections: 7
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// FetchAmisData                      code
// ValidateSourceCounts               code
// StageAmisWarmChunk                 httpRequest
// PrepareAmisWarmCommit              code
// CommitAmisWarmRun                  httpRequest
// ValidateSyncResult                 code
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → FetchAmisData
//      → ValidateSourceCounts
//        → StageAmisWarmChunk
//          → PrepareAmisWarmCommit
//            → CommitAmisWarmRun
//              → ValidateSyncResult
// ScheduleTrigger
//    → FetchAmisData (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'QLY0cLK5tqcx3KY6',
    name: 'AMIS CRM Full Warm — Redis Sync Every 1h',
    active: true,
    isArchived: false,
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1', binaryMode: 'separate', availableInMCP: true },
})
export class AmisCrmFullWarmRedisSyncEvery1hWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560001',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 144],
    })
    ManualTrigger = {};

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560002',
        name: 'Schedule Trigger',
        type: 'n8n-nodes-base.scheduleTrigger',
        version: 1.3,
        position: [0, 352],
    })
    ScheduleTrigger = {
        rule: {
            interval: [
                {
                    field: 'hours',
                },
            ],
        },
    };

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560003',
        name: 'Fetch AMIS Data',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [320, 240],
    })
    FetchAmisData = {
        jsCode: `
const BASE_URL = $env.AMIS_BASE_URL || "https://crmconnect.misa.vn/api/v2";
const CLIENT_ID = $env.AMIS_CLIENT_ID || "JavisCFCChatbot";
const CLIENT_SECRET = $env.AMIS_CLIENT_SECRET || "";
const MAX_TRANSIENT_RETRIES = 5;
const REQUEST_TIMEOUT_MS = 30000;
const PAGE_GAP_MS = 250;

if (!CLIENT_SECRET) {
  throw new Error(
    "[AMIS Warm] AMIS_CLIENT_SECRET is not set. " +
    "Add it in n8n Settings > Environment Variables."
  );
}

const helpers = this.helpers;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const errorText = (err) => String((err && err.message) || err || "unknown error");
const isRetryable = (message) => /ECONNRESET|ECONNREFUSED|ETIMEDOUT|ESOCKETTIMEDOUT|socket hang up|network|timeout|\\b429\\b|\\b5\\d\\d\\b/i.test(message);
const isUnauthorized = (message) => /\\b401\\b|unauthori[sz]ed|token.*expired/i.test(message);

async function requestWithRetry(label, request) {
  let lastError = null;
  for (let attempt = 0; attempt < MAX_TRANSIENT_RETRIES; attempt++) {
    try {
      return await request();
    } catch (err) {
      lastError = err;
      const message = errorText(err);
      if (!isRetryable(message) || attempt + 1 >= MAX_TRANSIENT_RETRIES) {
        throw new Error("[AMIS Warm] " + label + " failed after " + (attempt + 1) + " attempt(s): " + message);
      }
      const backoffMs = Math.min(15000, 1000 * Math.pow(2, attempt)) + Math.floor(Math.random() * 500);
      console.warn("[AMIS Warm] " + label + " transient failure; retry " + (attempt + 2) + "/" + MAX_TRANSIENT_RETRIES + " in " + backoffMs + "ms: " + message);
      await sleep(backoffMs);
    }
  }
  throw new Error("[AMIS Warm] " + label + " failed: " + errorText(lastError));
}

async function authenticate() {
  const tokenRaw = await requestWithRetry("Auth", () => helpers.httpRequest({
    method: "POST",
    url: BASE_URL + "/Account",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: CLIENT_ID, client_secret: CLIENT_SECRET }),
    timeout: REQUEST_TIMEOUT_MS,
  }));
  const tokenPayload = (typeof tokenRaw === "string") ? JSON.parse(tokenRaw) : tokenRaw;
  let token = "";
  if (typeof tokenPayload.data === "string") {
    token = tokenPayload.data;
  } else if (tokenPayload.data && typeof tokenPayload.data.access_token === "string") {
    token = tokenPayload.data.access_token;
  }
  if (!token) {
    throw new Error("[AMIS Warm] Empty token. AMIS response: " + JSON.stringify(tokenPayload).slice(0, 300));
  }
  return token;
}

let token = await authenticate();

const authHeaders = () => ({
  "Authorization": "Bearer " + token,
  "Clientid": CLIENT_ID,
  "Accept": "application/json",
  "Connection": "close",
});

async function fetchAllPages(resource, maxPages) {
  const all = [];
  const PAGE_SIZE = 100;
  const seen = new Set();
  maxPages = maxPages || 300;

  for (let page = 0; page < maxPages; page++) {
    const url = BASE_URL + "/" + resource +
      "?page=" + page + "&pageSize=" + PAGE_SIZE +
      "&orderBy=modified_date&isDescending=true";

    let raw = null;
    let refreshedToken = false;
    while (true) {
      try {
        raw = await requestWithRetry(resource + " page " + page, () => helpers.httpRequest({
          method: "GET",
          url: url,
          headers: authHeaders(),
          timeout: REQUEST_TIMEOUT_MS,
        }));
        break;
      } catch (err) {
        const message = errorText(err);
        if (!refreshedToken && isUnauthorized(message)) {
          token = await authenticate();
          refreshedToken = true;
          continue;
        }
        throw err;
      }
    }

    const payload = (typeof raw === "string") ? JSON.parse(raw) : raw;
    let records = null;
    if (Array.isArray(payload)) {
      records = payload;
    } else if (Array.isArray(payload.data)) {
      records = payload.data;
    } else if (payload.data && Array.isArray(payload.data.items)) {
      records = payload.data.items;
    } else if (Array.isArray(payload.items)) {
      records = payload.items;
    } else if (Array.isArray(payload.records)) {
      records = payload.records;
    }

    if (!records || records.length === 0) break;

    const fp = resource + ":p" + page + ":n" + records.length + ":" + JSON.stringify(records[0]).slice(0, 60);
    if (seen.has(fp)) {
      throw new Error("[AMIS Warm] AMIS repeated a page while fetching " + resource + "; refusing a partial snapshot.");
    }
    seen.add(fp);

    all.push.apply(all, records);

    const total = (
      payload.total !== undefined ? payload.total :
      payload.totalCount !== undefined ? payload.totalCount :
      (payload.data && payload.data.total !== undefined) ? payload.data.total : null
    );
    if (total !== null && typeof total === "number" && all.length >= total) break;
    if (records.length < PAGE_SIZE) break;

    // Deliberate gap reduces AMIS 429/socket-reset bursts without slowing the
    // customer-facing lookup, which reads Redis rather than this workflow.
    await sleep(PAGE_GAP_MS);
  }
  return all;
}

const allCustomers = await fetchAllPages("Customers", 50);
const customers = allCustomers.filter(function(c) {
  if (c.inactive === true) return false;
  if (!c.purchase_date_first) return false;
  var t = c.account_type;
  if (!t) return false;
  var types = Array.isArray(t) ? t : [t];
  return types.some(function(v) {
    var s = String(v);
    return s === "KH001" || s === "KH002" || s.indexOf("001") !== -1 || s.indexOf("002") !== -1;
  });
});

const products = await fetchAllPages("Products", 20);

const rawOrders = await fetchAllPages("SaleOrders", 300);
const saleOrders = rawOrders.filter(function(o) {
  var s = String(o.status || "").toLowerCase();
  // Keep non-cancelled orders for the private, customer-owned status lookup.
  // The FastAPI public dealer projection retains its own invoiced eligibility
  // rule, so this must not remove valid orders from the private cache.
  return s.indexOf("huy") === -1 && s.indexOf("tu choi") === -1 &&
    s.indexOf("cancel") === -1 && s.indexOf("reject") === -1;
});

// n8n serialises every item between nodes.  Emit bounded chunks immediately
// so neither the next Code node nor an HTTP expression receives all CRM rows.
const CHUNK_SIZE = 100;
const sourceCounts = {
  customers_raw: allCustomers.length,
  customers_eligible: customers.length,
  loyalty_customers: allCustomers.length,
  products: products.length,
  sale_orders_raw: rawOrders.length,
  sale_orders_eligible: saleOrders.length,
};
const runId = "amiswarm-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
// Public dealer projection keeps the stricter eligible subset. Loyalty uses
// the full customer feed but FastAPI reduces it to an HMAC-keyed safe index;
// raw customer rows remain only in short-lived staging keys.
const datasets = {
  customers: customers,
  loyalty_customers: allCustomers,
  products: products,
  sale_orders: saleOrders,
};
const expectedCounts = {};
const expectedChunks = {};
for (const [dataset, records] of Object.entries(datasets)) {
  expectedCounts[dataset] = records.length;
  expectedChunks[dataset] = Math.ceil(records.length / CHUNK_SIZE);
}

const output = [];
for (const [dataset, records] of Object.entries(datasets)) {
  for (let chunkIndex = 0; chunkIndex < expectedChunks[dataset]; chunkIndex++) {
    output.push({
      json: {
        run_id: runId,
        dataset: dataset,
        chunk_index: chunkIndex,
        records: records.slice(chunkIndex * CHUNK_SIZE, (chunkIndex + 1) * CHUNK_SIZE),
        expected_counts: expectedCounts,
        expected_chunks: expectedChunks,
        source_counts: sourceCounts,
      },
    });
  }
}
return output;
`,
    };

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560004',
        name: 'Validate Source Counts',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [624, 240],
    })
    ValidateSourceCounts = {
        jsCode: `
const chunks = $input.all();
if (!chunks.length) {
  throw new Error("[AMIS Warm] Fetch returned no chunks.");
}
const first = chunks[0].json || {};
const c = first.source_counts || {};

if (!c.customers_eligible || c.customers_eligible < 5) {
  throw new Error(
    "[AMIS Warm] Too few eligible customers: " + (c.customers_eligible || 0) +
    " (raw fetched: " + (c.customers_raw || 0) + "). " +
    "Check KH001/KH002 customers have purchase_date_first set in AMIS."
  );
}
if (!c.loyalty_customers || c.loyalty_customers < c.customers_eligible) {
  throw new Error(
    "[AMIS Warm] Loyalty customer feed is incomplete: " +
    String(c.loyalty_customers || 0) + " < eligible dealers " +
    String(c.customers_eligible || 0)
  );
}
if (!c.products || c.products < 1) {
  throw new Error("[AMIS Warm] No products fetched. Check AMIS Products API.");
}
if (!c.sale_orders_eligible || c.sale_orders_eligible < 1) {
  throw new Error(
    "[AMIS Warm] No eligible non-cancelled sale orders (raw=" + (c.sale_orders_raw || 0) + "). " +
    "Check AMIS SaleOrders API response and status values."
  );
}

const expectedChunks = first.expected_chunks || {};
const expectedTotal = Object.values(expectedChunks).reduce((sum, value) => sum + Number(value || 0), 0);
const received = new Set();
for (const item of chunks) {
  const chunk = item.json || {};
  if (chunk.run_id !== first.run_id || JSON.stringify(chunk.expected_chunks || {}) !== JSON.stringify(expectedChunks)) {
    throw new Error("[AMIS Warm] Inconsistent chunk metadata from Fetch AMIS Data.");
  }
  received.add(String(chunk.dataset) + ":" + String(chunk.chunk_index));
}
if (received.size !== expectedTotal) {
  throw new Error("[AMIS Warm] Fetch generated an incomplete chunk plan: expected " + expectedTotal + ", got " + received.size);
}

console.log("[AMIS Warm] Source OK; staging " + chunks.length + " chunks — customers=" +
  c.customers_eligible + " loyalty_customers=" + c.loyalty_customers +
  " products=" + c.products + " orders=" + c.sale_orders_eligible);

return chunks;
`,
    };

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560005',
        name: 'Stage AMIS Warm Chunk',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.4,
        position: [928, 240],
    })
    StageAmisWarmChunk = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/admin/amis/warm/stage' }}",
        sendHeaders: true,
        headerParameters: {
            parameters: [
                {
                    name: 'X-Internal-Token',
                    value: '={{ $env.AMIS_SYNC_INTERNAL_TOKEN }}',
                },
            ],
        },
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ $json }}',
        options: {
            timeout: 60000,
        },
    };

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560007',
        name: 'Prepare AMIS Warm Commit',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1232, 240],
    })
    PrepareAmisWarmCommit = {
        jsCode: `
const staged = $input.all().map((item) => item.json || {});
if (!staged.length) {
  throw new Error("[AMIS Warm] No staged chunks returned by FastAPI.");
}
const first = staged[0];
const runId = first.run_id;
const expected = first.expected_chunks || {};
if (!runId || first.status !== "staged") {
  throw new Error("[AMIS Warm] FastAPI did not acknowledge the first staged chunk.");
}

const expectedTotal = Object.values(expected).reduce((sum, value) => sum + Number(value || 0), 0);
const received = new Set();
for (const result of staged) {
  if (result.status !== "staged" || result.run_id !== runId) {
    throw new Error("[AMIS Warm] Inconsistent staging acknowledgement.");
  }
  received.add(String(result.dataset) + ":" + String(result.chunk_index));
}
if (received.size !== expectedTotal) {
  throw new Error("[AMIS Warm] Incomplete staging acknowledgement: expected " + expectedTotal + ", got " + received.size);
}

return [{ json: { run_id: runId } }];
`,
    };

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560008',
        name: 'Commit AMIS Warm Run',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.4,
        position: [1536, 240],
    })
    CommitAmisWarmRun = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/admin/amis/warm/commit' }}",
        sendHeaders: true,
        headerParameters: {
            parameters: [
                {
                    name: 'X-Internal-Token',
                    value: '={{ $env.AMIS_SYNC_INTERNAL_TOKEN }}',
                },
            ],
        },
        sendBody: true,
        specifyBody: 'json',
        jsonBody: '={{ $json }}',
        options: {
            timeout: 300000,
        },
    };

    @node({
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234560006',
        name: 'Validate Sync Result',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1840, 240],
    })
    ValidateSyncResult = {
        jsCode: `
const result = $input.first().json || {};

if (result.status !== "ok") {
  const reasons = (result.gate && result.gate.reasons)
    ? result.gate.reasons.join(", ")
    : "unknown gate failure";
  throw new Error(
    "[AMIS Warm] Sync blocked: " + reasons +
    ". Status=" + String(result.status || "unknown") +
    ". Ensure AMIS_PILOT_APPROVE_ALL=true on FastAPI and dealers have GPS."
  );
}
if (result.written !== true) {
  throw new Error("[AMIS Warm] Did not write to Redis. dry_run=" + String(result.dry_run));
}

const locationCount = (result.snapshots && result.snapshots.locations)
  ? (result.snapshots.locations.record_count || 0) : 0;
const productCount = (result.snapshots && result.snapshots.products)
  ? (result.snapshots.products.record_count || 0) : 0;
const withCoords = (result.metrics && result.metrics.locations)
  ? (result.metrics.locations.with_coordinates_count || 0) : 0;
const orderLookup = (result.snapshots && result.snapshots.order_lookup)
  ? result.snapshots.order_lookup : {};
const loyaltyLookup = (result.snapshots && result.snapshots.loyalty_lookup)
  ? result.snapshots.loyalty_lookup : {};

if (locationCount < 1) {
  throw new Error("[AMIS Warm] Zero locations in snapshot! " +
    "Set AMIS_PILOT_APPROVE_ALL=true and ensure dealers have GPS coordinates in AMIS.");
}
if (orderLookup.enabled !== true) {
  throw new Error(
    "[AMIS Warm] Private order cache was not safely refreshed. candidate=" +
    String(orderLookup.candidate_record_count || 0) +
    " published=" + String(orderLookup.record_count || 0) +
    " reason=" + String(orderLookup.reason || "unknown")
  );
}
if (loyaltyLookup.enabled !== true) {
  throw new Error(
    "[AMIS Warm] Protected loyalty cache was not safely refreshed. candidate=" +
    String(loyaltyLookup.candidate_record_count || 0) +
    " published=" + String(loyaltyLookup.record_count || 0) +
    " reason=" + String(loyaltyLookup.reason || "unknown")
  );
}

console.log("[AMIS Warm] SUCCESS — locations=" + locationCount +
  " gps=" + withCoords + " products=" + productCount +
  " orders=" + orderLookup.record_count +
  " loyalty=" + loyaltyLookup.record_count +
  " direct_loyalty=" + loyaltyLookup.direct_loyalty_count +
  " at=" + result.synced_at);

return [{
  json: {
    status: "ok",
    source: "amis_crm",
    synced_at: result.synced_at,
    location_count: locationCount,
    location_with_coordinates_count: withCoords,
    product_count: productCount,
    order_lookup_count: Number(orderLookup.record_count || 0),
    loyalty_lookup_count: Number(loyaltyLookup.record_count || 0),
    direct_loyalty_count: Number(loyaltyLookup.direct_loyalty_count || 0),
    locations_snapshot_hash: (result.snapshots && result.snapshots.locations)
      ? result.snapshots.locations.snapshot_hash : "",
    products_snapshot_hash: (result.snapshots && result.snapshots.products)
      ? result.snapshots.products.snapshot_hash : "",
  },
}];
`,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.FetchAmisData.in(0));
        this.ScheduleTrigger.out(0).to(this.FetchAmisData.in(0));
        this.FetchAmisData.out(0).to(this.ValidateSourceCounts.in(0));
        this.ValidateSourceCounts.out(0).to(this.StageAmisWarmChunk.in(0));
        this.StageAmisWarmChunk.out(0).to(this.PrepareAmisWarmCommit.in(0));
        this.PrepareAmisWarmCommit.out(0).to(this.CommitAmisWarmRun.in(0));
        this.CommitAmisWarmRun.out(0).to(this.ValidateSyncResult.in(0));
    }
}
