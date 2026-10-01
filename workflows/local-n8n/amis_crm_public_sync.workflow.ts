import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : AMIS CRM Public Catalog Sync
// Nodes   : 4  |  Connections: 3
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// ManualTrigger                      manualTrigger
// ScheduleTrigger                    scheduleTrigger
// RunAmisPublicSync                  httpRequest
// ValidateAmisSyncResult             code
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// ManualTrigger
//    → RunAmisPublicSync
//      → ValidateAmisSyncResult
// ScheduleTrigger
//    → RunAmisPublicSync (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'zksntDfjt5rhhbOW',
    name: 'AMIS CRM Public Catalog Sync',
    active: false,
    isArchived: false,
    projectId: 'A5416cGJlo1X0rDa',
    settings: { timezone: 'Asia/Ho_Chi_Minh', executionOrder: 'v1' },
})
export class AmisCrmPublicCatalogSyncWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'b7d7a490-59f2-4d25-9941-a0be07628d31',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 160],
    })
    ManualTrigger = {};

    @node({
        id: 'ce00ccab-49cf-431c-b46e-f99fcb8be028',
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
                    minutesInterval: 30,
                },
            ],
        },
    };

    @node({
        id: 'e86acf3c-a9e7-4548-b4ca-ee784a2851af',
        name: 'Run AMIS Public Sync',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.4,
        position: [288, 256],
    })
    RunAmisPublicSync = {
        method: 'POST',
        url: "={{ $env.CFCBOT_API_BASE_URL + '/admin/amis/sync' }}",
        sendHeaders: true,
        specifyHeaders: 'keypair',
        headerParameters: {
            parameters: [
                {
                    name: 'X-Internal-Token',
                    value: '={{ $env.AMIS_SYNC_INTERNAL_TOKEN }}',
                },
            ],
        },
        sendQuery: true,
        specifyQuery: 'keypair',
        queryParameters: {
            parameters: [
                {
                    name: 'dry_run',
                    value: 'false',
                },
            ],
        },
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: 'e7473246-d47d-4bc3-a3f9-8f81947cb428',
        name: 'Validate AMIS Sync Result',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [576, 256],
    })
    ValidateAmisSyncResult = {
        jsCode: `
const result = $input.first().json || {};
const productCount = Number(result.snapshots?.products?.record_count || 0);
const locationCount = Number(result.snapshots?.locations?.record_count || 0);

if (result.status !== 'ok' || result.written !== true) {
  throw new Error('AMIS sync did not publish a safe snapshot. Status=' + String(result.status || 'unknown'));
}
if (productCount < 1 || locationCount < 1) {
  throw new Error('AMIS sync returned an invalid public snapshot count. products=' + productCount + ', locations=' + locationCount);
}

return [{
  json: {
    status: 'ok',
    source: 'amis_crm',
    synced_at: result.synced_at,
    product_count: productCount,
    location_count: locationCount,
    location_with_coordinates_count: Number(result.metrics?.locations?.with_coordinates_count || 0),
    products_snapshot_hash: result.snapshots.products.snapshot_hash,
    locations_snapshot_hash: result.snapshots.locations.snapshot_hash,
  },
}];
`,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.ManualTrigger.out(0).to(this.RunAmisPublicSync.in(0));
        this.ScheduleTrigger.out(0).to(this.RunAmisPublicSync.in(0));
        this.RunAmisPublicSync.out(0).to(this.ValidateAmisSyncResult.in(0));
    }
}
