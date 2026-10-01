/**
 * n8n.js — n8n Control: Workflows, Executions per workflow, Deploy, File Watcher
 * Enterprise SaaS Edition with Lucide Icons
 */
'use strict';

// ─── State ───────────────────────────────────────────────────────
let _currentTab = 'workflows'; // 'workflows' | 'executions' | 'deploy-log'
let _selectedWorkflowId = null;
let _selectedWorkflowName = '';
let _execPage = 1;
let _execLimit = 20;
let _execStatusFilter = 'all';
let _ws = null;
let _workflows = [];
let _changedFiles = {}; // { workflow_id: true }

// ─── Init ─────────────────────────────────────────────────────────
function initN8nPage() {
  renderN8nTabs();
  loadN8nWorkflows();
  connectFileWatcher();

  // Auto-refresh workflows mỗi 30s
  setInterval(() => {
    if (_currentTab === 'workflows') loadN8nWorkflows(true);
  }, 30000);
}

// ─── Tab system ───────────────────────────────────────────────────
function renderN8nTabs() {
  const container = document.getElementById('n8n-page');
  if (!container) return;

  const tabDefs = [
    { key: 'workflows', label: 'Workflows', icon: 'git-branch' },
    { key: 'executions', label: 'Lịch Sử Executions', icon: 'activity' },
    { key: 'deploy-log', label: 'Deploy Audit Log', icon: 'history' }
  ];

  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:20px;flex-wrap:wrap">
      <div class="filter-tabs">
        ${tabDefs.map(t => `
          <button id="n8n-tab-${t.key}" class="filter-tab ${_currentTab === t.key ? 'active' : ''}" onclick="switchN8nTab('${t.key}')"
            style="display:inline-flex;align-items:center;gap:6px">
            <i data-lucide="${t.icon}" style="width:14px;height:14px"></i>
            <span>${t.label}</span>
          </button>`).join('')}
      </div>
      <div id="ws-status" style="display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text-dim);background:var(--bg-card);padding:5px 12px;border-radius:var(--r-full);border:1px solid var(--border)">
        <span class="sys-dot" style="background:var(--warning);box-shadow:none"></span>
        <span>Đang kết nối...</span>
      </div>
    </div>
    <div id="n8n-tab-content"></div>
  `;
  showN8nTab(_currentTab);
  refreshIcons();
}

function switchN8nTab(tab) {
  _currentTab = tab;
  renderN8nTabs();
  showN8nTab(tab);
}

function showN8nTab(tab) {
  const el = document.getElementById('n8n-tab-content');
  if (!el) return;
  if (tab === 'workflows')    { renderWorkflowsTab(); loadN8nWorkflows(); }
  if (tab === 'executions')   { renderExecutionsTab(); if (_selectedWorkflowId) loadWorkflowExecutions(); }
  if (tab === 'deploy-log')   { renderDeployLogTab(); loadDeployLog(); }
  refreshIcons();
}

// ─── WORKFLOWS TAB ────────────────────────────────────────────────
function renderWorkflowsTab() {
  const el = document.getElementById('n8n-tab-content');
  el.innerHTML = `
    <div class="section-header" style="margin-bottom:14px">
      <div class="section-title">
        <i data-lucide="layers"></i>
        <span>Danh Sách Workflows &amp; Trạng Thái Local</span>
      </div>
      <button class="btn btn-ghost btn-sm" onclick="loadN8nWorkflows()">
        <i data-lucide="refresh-cw"></i>
        <span>Tải lại</span>
      </button>
    </div>
    <div class="table-wrap">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Tên Workflow</th>
              <th>Workflow ID</th>
              <th>Trạng Thái</th>
              <th style="text-align:center">Executions</th>
              <th>Cập Nhật Lần Cuối</th>
              <th style="text-align:right">Hành Động</th>
            </tr>
          </thead>
          <tbody id="workflows-table">
            <tr><td colspan="6" style="text-align:center;padding:36px"><span class="spinner"></span></td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <div id="deploy-output" style="display:none;margin-top:16px;background:#050811;border-radius:var(--r-md);padding:16px;font-family:'JetBrains Mono',monospace;font-size:12px;max-height:260px;overflow-y:auto;border:1px solid var(--border)"></div>
  `;
  refreshIcons();
}

async function loadN8nWorkflows(silent = false) {
  const tbody = document.getElementById('workflows-table');
  if (!tbody) return;
  if (!silent) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:36px"><span class="spinner"></span></td></tr>`;

  try {
    const [wfData, fsData] = await Promise.all([
      fetchJSON('/admin/n8n/workflows'),
      fetchJSON('/admin/n8n/file-status').catch(() => ({ files: [] })),
    ]);

    if (wfData.error) {
      tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger);padding:24px;text-align:center">${wfData.error}</td></tr>`;
      return;
    }

    _workflows = wfData.workflows || [];

    const fileStatus = {};
    (fsData.files || []).forEach(f => { fileStatus[f.workflow_id] = f; });
    Object.keys(_changedFiles).forEach(id => { if (fileStatus[id]) fileStatus[id].has_changes = true; });

    tbody.innerHTML = _workflows.map(w => {
      const fs = fileStatus[w.id] || {};
      const hasChanges = fs.has_changes;
      const changeBadge = hasChanges
        ? `<span class="badge badge-yellow" style="margin-left:8px;font-size:10px" title="File .ts đã thay đổi sau lần cập nhật trên n8n">Chưa push</span>` : '';
      return `
        <tr>
          <td style="font-weight:600;color:var(--text-main)">
            <div style="display:flex;align-items:center">
              <span>${w.name}</span>
              ${changeBadge}
            </div>
          </td>
          <td>
            <code style="color:var(--text-dim);font-size:11px">${w.id}</code>
          </td>
          <td>
            <span class="badge ${w.active ? 'badge-green' : 'badge-gray'}">
              ${w.active ? 'Active' : 'Inactive'}
            </span>
          </td>
          <td style="text-align:center">
            <button class="btn btn-ghost btn-xs" onclick="openExecutions('${w.id}','${w.name.replace(/'/g,'')}')">
              <i data-lucide="bar-chart-2"></i>
              <span>Xem lịch sử</span>
            </button>
          </td>
          <td style="font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace">
            ${w.updatedAt ? new Date(w.updatedAt).toLocaleDateString('vi-VN') : '—'}
          </td>
          <td style="text-align:right">
            <div style="display:inline-flex;gap:6px;justify-content:flex-end">
              <button class="btn btn-ghost btn-sm" onclick="toggleWorkflow('${w.id}','${w.name.replace(/'/g,'')}',${w.active})">
                <i data-lucide="${w.active ? 'pause' : 'play'}"></i>
                <span>${w.active ? 'Tắt' : 'Bật'}</span>
              </button>
              <button class="btn ${hasChanges ? 'btn-primary' : 'btn-ghost'} btn-sm" onclick="deployWorkflow('${fs.filename || ''}')"
                ${fs.filename ? '' : 'disabled title="Không có file .ts tương ứng"'} style="${hasChanges ? '' : 'opacity:0.6'}">
                <i data-lucide="upload-cloud"></i>
                <span>Deploy</span>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('') || `<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:36px">Không tìm thấy workflow nào</td></tr>`;

    refreshIcons();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger);padding:24px;text-align:center">Lỗi kết nối n8n instance. Hãy kiểm tra API key trong Cài đặt.</td></tr>`;
  }
}

async function toggleWorkflow(id, name, isActive) {
  if (!confirm(`${isActive ? 'Tắt' : 'Bật'} workflow "${name}"?`)) return;
  try {
    await fetchJSON(`/admin/n8n/workflows/${id}/toggle`, { method: 'POST' });
    toast(`${isActive ? 'Đã tắt' : 'Đã bật'} "${name}" thành công`, 'success');
    loadN8nWorkflows();
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}

async function deployWorkflow(filename) {
  if (!filename) { toast('Không tìm thấy file .ts tương ứng', 'error'); return; }
  if (!confirm(`Deploy "${filename}" lên n8n?\n\nNếu conflict sẽ tự động resolve bằng keep-current (giữ code local).`)) return;

  const output = document.getElementById('deploy-output');
  if (output) {
    output.style.display = 'block';
    output.innerHTML = `<div style="color:#818CF8;display:flex;align-items:center;gap:8px"><span class="spinner"></span><span>Đang deploy ${filename} qua n8nac CLI...</span></div>`;
  }

  try {
    const res = await fetchJSON('/admin/n8n/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_file: filename, auto_resolve_conflict: true }),
    });
    const logHtml = (res.logs || []).map(l => {
      const color = l.startsWith('✅') ? '#34D399' : l.startsWith('⚠️') ? '#FBBF24' : l.startsWith('❌') ? '#F87171' : 'var(--text-muted)';
      return `<div style="color:${color};margin-bottom:3px">${l}</div>`;
    }).join('');
    if (output) output.innerHTML = logHtml;
    toast(`Deploy "${filename}" thành công!`, 'success');
    const wfId = Object.keys(_changedFiles).find(id => _changedFiles[id]);
    if (wfId) delete _changedFiles[wfId];
    setTimeout(loadN8nWorkflows, 1000);
  } catch (e) {
    const detail = e.detail || e.message || String(e);
    const logs = typeof detail === 'object' ? detail.logs : [String(detail)];
    if (output) output.innerHTML = (logs || []).map(l =>
      `<div style="color:${l.startsWith('✅')?'#34D399':l.startsWith('⚠️')?'#FBBF24':'#F87171'};margin-bottom:3px">${l}</div>`
    ).join('');
    toast(`Deploy thất bại: ${typeof detail === 'string' ? detail.substring(0,80) : 'Xem log bên dưới'}`, 'error');
  }
}

// ─── EXECUTIONS TAB ───────────────────────────────────────────────
function openExecutions(id, name) {
  _selectedWorkflowId = id;
  _selectedWorkflowName = name;
  _execPage = 1;
  switchN8nTab('executions');
}

function renderExecutionsTab() {
  const el = document.getElementById('n8n-tab-content');
  el.innerHTML = `
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:18px;flex-wrap:wrap">
      <select id="exec-wf-select" class="form-input" onchange="onWorkflowSelectChange()" style="width:260px">
        <option value="">— Chọn workflow cần xem —</option>
        ${_workflows.map(w => `<option value="${w.id}" ${w.id===_selectedWorkflowId?'selected':''}>${w.name}</option>`).join('')}
      </select>
      <select id="exec-status-filter" class="form-input" onchange="onExecStatusChange()" style="width:160px">
        ${['all','success','error','running','waiting'].map(s =>
          `<option value="${s}" ${s===_execStatusFilter?'selected':''}>${{all:'Tất cả trạng thái',success:'Thành công',error:'Lỗi',running:'Đang chạy',waiting:'Đang chờ'}[s]}</option>`
        ).join('')}
      </select>
      <select id="exec-limit-select" class="form-input" onchange="onExecLimitChange()" style="width:130px">
        ${[20,50,100].map(n => `<option value="${n}" ${n===_execLimit?'selected':''}>${n} / trang</option>`).join('')}
      </select>
      <button class="btn btn-ghost btn-sm" onclick="loadWorkflowExecutions()">
        <i data-lucide="refresh-cw"></i>
        <span>Làm mới</span>
      </button>
    </div>

    <div id="exec-stats" style="display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap"></div>

    <div class="table-wrap">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Execution ID</th>
              <th>Trạng Thái</th>
              <th>Trigger Mode</th>
              <th>Thời Gian Bắt Đầu</th>
              <th>Thời Gian Kết Thúc</th>
              <th style="text-align:right">Duration</th>
            </tr>
          </thead>
          <tbody id="executions-table">
            <tr><td colspan="6" style="text-align:center;padding:36px;color:var(--text-dim)">Chọn workflow từ dropdown bên trên để xem chi tiết</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div id="exec-pagination" style="display:flex;justify-content:center;gap:8px;margin-top:18px;align-items:center"></div>
  `;

  if (_selectedWorkflowId) {
    document.getElementById('exec-wf-select').value = _selectedWorkflowId;
    loadWorkflowExecutions();
  }
  refreshIcons();
}

function onWorkflowSelectChange() {
  const sel = document.getElementById('exec-wf-select');
  _selectedWorkflowId = sel.value;
  _selectedWorkflowName = sel.options[sel.selectedIndex]?.text || '';
  _execPage = 1;
  loadWorkflowExecutions();
}

function onExecStatusChange() {
  _execStatusFilter = document.getElementById('exec-status-filter').value;
  _execPage = 1;
  loadWorkflowExecutions();
}

function onExecLimitChange() {
  _execLimit = parseInt(document.getElementById('exec-limit-select').value);
  _execPage = 1;
  loadWorkflowExecutions();
}

async function loadWorkflowExecutions() {
  if (!_selectedWorkflowId) return;
  const tbody = document.getElementById('executions-table');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:36px"><span class="spinner"></span></td></tr>`;

  try {
    const url = `/admin/n8n/workflows/${_selectedWorkflowId}/executions?page=${_execPage}&limit=${_execLimit}&status=${_execStatusFilter}`;
    const d = await fetchJSON(url);

    if (d.error) {
      tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger);padding:24px;text-align:center">${d.error}</td></tr>`;
      return;
    }

    const statsEl = document.getElementById('exec-stats');
    if (statsEl && d.stats) {
      const s = d.stats;
      const total = d.total || 0;
      statsEl.innerHTML = `
        <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-sm);padding:8px 16px;font-size:12.5px">
          <span style="color:var(--text-dim)">Tổng số:</span> <strong style="color:var(--text-main)">${total}</strong>
        </div>
        ${s.success ? `<div style="background:var(--success-light);border:1px solid var(--success-border);border-radius:var(--r-sm);padding:8px 16px;font-size:12.5px;color:#34D399">Thành công: <strong>${s.success}</strong></div>` : ''}
        ${s.error ? `<div style="background:var(--danger-light);border:1px solid var(--danger-border);border-radius:var(--r-sm);padding:8px 16px;font-size:12.5px;color:#F87171">Lỗi: <strong>${s.error}</strong></div>` : ''}
        ${s.running ? `<div style="background:var(--info-light);border:1px solid var(--info-border);border-radius:var(--r-sm);padding:8px 16px;font-size:12.5px;color:#38BDF8">Đang chạy: <strong>${s.running}</strong></div>` : ''}
      `;
    }

    const statusMap = {
      success: 'badge-green', error: 'badge-red',
      running: 'badge-blue', waiting: 'badge-yellow',
    };

    tbody.innerHTML = d.executions.map(e => {
      const dur = e.durationMs != null
        ? (e.durationMs < 1000 ? `${e.durationMs}ms` : `${(e.durationMs/1000).toFixed(1)}s`)
        : '—';
      return `
        <tr>
          <td><code style="color:var(--text-dim);font-size:11px">${e.id}</code></td>
          <td><span class="badge ${statusMap[e.status] || 'badge-gray'}">${e.status}</span></td>
          <td style="font-size:12px;color:var(--text-muted)">${e.mode || '—'}</td>
          <td style="font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace">${e.startedAt ? new Date(e.startedAt).toLocaleString('vi-VN') : '—'}</td>
          <td style="font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace">${e.stoppedAt ? new Date(e.stoppedAt).toLocaleString('vi-VN') : '—'}</td>
          <td style="text-align:right;font-size:12px;font-family:'JetBrains Mono',monospace;font-weight:600;color:${e.durationMs>5000?'var(--danger)':e.durationMs>1000?'var(--warning)':'var(--success)'}">${dur}</td>
        </tr>`;
    }).join('') || `<tr><td colspan="6" style="text-align:center;color:var(--text-dim);padding:36px">Không có execution nào</td></tr>`;

    renderExecPagination(d.page, d.pages, d.total);
    refreshIcons();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger);padding:24px;text-align:center">Lỗi: ${e.message}</td></tr>`;
  }
}

function renderExecPagination(page, pages, total) {
  const el = document.getElementById('exec-pagination');
  if (!el || pages <= 1) { if (el) el.innerHTML = ''; return; }

  let html = `<span style="font-size:12px;color:var(--text-dim);margin-right:8px">Trang ${page}/${pages} (${total} bản ghi)</span>`;
  if (page > 1) html += `<button class="btn btn-ghost btn-xs" onclick="gotoExecPage(${page-1})">‹ Trước</button>`;

  const start = Math.max(1, page - 2);
  const end = Math.min(pages, start + 4);
  for (let p = start; p <= end; p++) {
    html += `<button class="btn ${p===page ? 'btn-primary' : 'btn-ghost'} btn-xs" onclick="gotoExecPage(${p})">${p}</button>`;
  }

  if (page < pages) html += `<button class="btn btn-ghost btn-xs" onclick="gotoExecPage(${page+1})">Sau ›</button>`;
  el.innerHTML = html;
}

function gotoExecPage(p) {
  _execPage = p;
  loadWorkflowExecutions();
}

// ─── DEPLOY LOG TAB ───────────────────────────────────────────────
function renderDeployLogTab() {
  const el = document.getElementById('n8n-tab-content');
  el.innerHTML = `
    <div class="section-header" style="margin-bottom:16px">
      <div class="section-title">
        <i data-lucide="history"></i>
        <span>Lịch Sử Audit Log 30 Lần Deploy Gần Nhất</span>
      </div>
      <button class="btn btn-ghost btn-sm" onclick="loadDeployLog()">
        <i data-lucide="refresh-cw"></i>
        <span>Làm mới</span>
      </button>
    </div>
    <div id="deploy-log-list">
      <div style="text-align:center;padding:36px"><span class="spinner"></span></div>
    </div>
  `;
  refreshIcons();
}

async function loadDeployLog() {
  const el = document.getElementById('deploy-log-list');
  if (!el) return;
  try {
    const d = await fetchJSON('/admin/n8n/deploy-log');
    if (!d.logs?.length) {
      el.innerHTML = `<div style="text-align:center;color:var(--text-dim);padding:48px 20px"><i data-lucide="clock" style="width:36px;height:36px;margin-bottom:10px;opacity:0.3"></i><p>Chưa có lịch sử deploy nào trong Redis</p></div>`;
      refreshIcons();
      return;
    }
    el.innerHTML = d.logs.map(l => `
      <div class="card" style="margin-bottom:14px;padding:18px 20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div style="display:flex;align-items:center;gap:10px">
            <span style="font-weight:700;font-size:14px;color:var(--text-main)">${l.filename}</span>
            <span class="badge ${l.success ? 'badge-green' : 'badge-red'}">
              ${l.success ? 'Thành công' : 'Thất bại'}
            </span>
          </div>
          <span style="font-size:11.5px;color:var(--text-dim);font-family:'JetBrains Mono',monospace">
            ${l.deployed_at ? new Date(l.deployed_at).toLocaleString('vi-VN') : '—'}
          </span>
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.65;background:#050811;padding:12px 14px;border-radius:var(--r-sm);border:1px solid var(--border)">
          ${(l.logs || []).map(line =>
            `<div style="color:${line.startsWith('✅')?'#34D399':line.startsWith('⚠️')?'#FBBF24':line.startsWith('❌')?'#F87171':'var(--text-muted)'}">${line}</div>`
          ).join('')}
        </div>
        ${l.error ? `<div style="color:var(--danger);font-size:11.5px;margin-top:8px;font-family:'JetBrains Mono',monospace">Lỗi: ${l.error.substring(0,250)}</div>` : ''}
      </div>`).join('');
    refreshIcons();
  } catch (e) {
    el.innerHTML = `<div style="color:var(--danger);padding:24px;text-align:center">Lỗi tải deploy audit log: ${e.message}</div>`;
  }
}

// ─── KB SYNC ─────────────────────────────────────────────────────
async function triggerSync(brand) {
  toast(`Đang đồng bộ Knowledge Base (${brand})...`, 'success');
  try {
    const r = await fetchJSON(`/admin/n8n/sync-knowledge?brand=${brand}`, { method: 'POST' });
    const synced = brand === 'all'
      ? `ZeO: ${r.zeo?.synced || 0}, CFC: ${r.cfc?.synced || 0}`
      : `${r.synced} items`;
    toast(`Đồng bộ xong! ${synced} FAQ đã vector hóa`, 'success');
  } catch (e) { toast('Lỗi sync: ' + e.message, 'error'); }
}

// ─── WEBSOCKET FILE WATCHER ───────────────────────────────────────
function connectFileWatcher() {
  const statusEl = document.getElementById('ws-status');
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/admin/n8n/ws/file-watch`;

  function setStatus(ok, msg) {
    if (statusEl) {
      statusEl.innerHTML = `<span class="sys-dot" style="background:${ok ? 'var(--success)' : 'var(--danger)'};box-shadow:${ok ? '0 0 8px var(--success)' : 'none'}"></span><span>${msg}</span>`;
      statusEl.style.borderColor = ok ? 'var(--success-border)' : 'var(--danger-border)';
    }
  }

  function connect() {
    try {
      _ws = new WebSocket(wsUrl);

      _ws.onopen = () => setStatus(true, 'File watcher đang hoạt động');

      _ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'file_changed' && msg.changed?.length) {
            msg.changed.forEach(f => {
              _changedFiles[f.workflow_id] = true;
              toast(`File "${f.filename}" vừa thay đổi — Nhớ deploy lên n8n!`, 'success');
            });
            if (_currentTab === 'workflows') loadN8nWorkflows(true);
          }
          if (msg.type === 'deploy_success') {
            toast(`Đã deploy "${msg.filename}" thành công!`, 'success');
            delete _changedFiles[msg.wf_id];
          }
        } catch (_) {}
      };

      _ws.onclose = () => {
        setStatus(false, 'Đã ngắt kết nối watcher');
        setTimeout(connect, 5000);
      };

      _ws.onerror = () => setStatus(false, 'Lỗi kết nối watcher');
    } catch (e) {
      setStatus(false, 'Không hỗ trợ WebSocket');
    }
  }

  connect();
}
