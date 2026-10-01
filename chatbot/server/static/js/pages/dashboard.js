/** dashboard.js — Dashboard: Status cards, Stat numbers, Intent charts, Weekly Trend Analytics (C3) */
'use strict';

async function loadStatus() {
  try {
    const s = await fetchJSON('/admin/status');
    const svc = s.services;
    setServiceStatus('redis', svc.redis);
    setServiceStatus('ollama', svc.ollama);
    setServiceStatus('n8n', svc.n8n);
  } catch (e) { console.error('loadStatus', e); }
}

function setServiceStatus(name, svc) {
  const dot = document.getElementById('dot-' + name);
  const detail = document.getElementById('detail-' + name);
  if (!dot || !detail) return;
  if (!svc) { dot.className = 'status-dot error'; detail.textContent = 'Lỗi'; return; }
  if (svc.status === 'ok') {
    dot.className = 'status-dot ok';
    if (name === 'redis')
      detail.textContent = `v${svc.version} · uptime ${Math.floor(svc.uptime_seconds / 3600)}h`;
    else if (name === 'ollama')
      detail.textContent = `${svc.models?.length || 0} models · bge-m3: ${svc.embed_ready ? '✅' : '⚠️'}`;
    else if (name === 'n8n')
      detail.textContent = `${svc.active_workflows}/${svc.total_workflows} active`;
  } else if (svc.status === 'no_api_key') {
    dot.className = 'status-dot warn';
    detail.textContent = 'Thiếu API key n8n';
  } else {
    dot.className = 'status-dot error';
    detail.textContent = svc.detail?.substring(0, 50) || 'Lỗi';
  }
}

async function loadStats() {
  try {
    const s = await fetchJSON('/admin/stats/today');
    document.getElementById('stat-total').textContent = s.total_customers;
    document.getElementById('stat-zeo').textContent = s.zeo?.customers || 0;
    document.getElementById('stat-cfc').textContent = s.cfc?.customers || 0;
    const lq = (s.zeo?.learning_queue_count || 0) + (s.cfc?.learning_queue_count || 0);
    document.getElementById('stat-lq').textContent = lq;
    const badge = document.getElementById('lq-badge');
    if (badge) { badge.textContent = lq; badge.className = lq > 0 ? 'nav-badge visible' : 'nav-badge'; }
    renderIntents('zeo', s.zeo?.top_intents || {});
    renderIntents('cfc', s.cfc?.top_intents || {});
    setLastUpdated();

    // Load Weekly Analytics
    loadWeeklyAnalytics();
  } catch (e) { console.error('loadStats', e); }
}

function renderIntents(brand, intents) {
  const tbody = document.getElementById('intents-' + brand);
  if (!tbody) return;
  const entries = Object.entries(intents).slice(0, 8);
  if (!entries.length) {
    tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--text3)">Chưa có dữ liệu</td></tr>`;
    return;
  }
  const max = entries[0]?.[1] || 1;
  tbody.innerHTML = entries.map(([intent, count]) => `
    <tr>
      <td>
        <div style="font-size:12px;font-weight:500;margin-bottom:3px">${intent}</div>
        <div style="height:3px;background:var(--border);border-radius:2px;overflow:hidden">
          <div style="height:100%;width:${Math.round(count / max * 100)}%;background:var(--accent);border-radius:2px;transition:width .4s"></div>
        </div>
      </td>
      <td style="font-weight:700;text-align:right;font-size:13px">${count}</td>
    </tr>`).join('');
}

// ─── Weekly Trend Analytics (C3) ───
async function loadWeeklyAnalytics() {
  const chartContainer = document.getElementById('weekly-chart-container');
  if (!chartContainer) return;

  try {
    const d = await fetchJSON('/admin/analytics/weekly');
    const labels = d.labels || [];
    const newCust = d.new_customers || [];
    const leads = d.leads_with_phone || [];
    const maxVal = Math.max(1, ...newCust, ...leads);

    let barsHtml = labels.map((lbl, i) => {
      const cVal = newCust[i] || 0;
      const lVal = leads[i] || 0;
      const cPct = Math.round((cVal / maxVal) * 100);
      const lPct = Math.round((lVal / maxVal) * 100);

      return `
        <div class="trend-col">
          <div class="trend-bars">
            <div class="trend-bar bar-cust" style="height:${Math.max(4, cPct)}%" title="Khách mới: ${cVal}"></div>
            <div class="trend-bar bar-lead" style="height:${Math.max(4, lPct)}%" title="Leads SĐT: ${lVal}"></div>
          </div>
          <div class="trend-label">${lbl}</div>
        </div>
      `;
    }).join('');

    chartContainer.innerHTML = `
      <div class="trend-wrapper">
        <div class="trend-legend">
          <span><span class="legend-dot dot-cust"></span> Khách mới</span>
          <span><span class="legend-dot dot-lead"></span> Leads SĐT</span>
        </div>
        <div class="trend-chart">${barsHtml}</div>
      </div>
    `;
  } catch (e) {
    chartContainer.innerHTML = `<div style="font-size:12px;color:var(--text3);padding:10px">Chưa có đủ dữ liệu lịch sử 7 ngày</div>`;
  }
}
