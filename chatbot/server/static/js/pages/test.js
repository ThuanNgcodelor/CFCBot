/** test.js — Chat Pipeline Debug + Raw RAG Search */
'use strict';

APP.testMode = APP.testMode || 'pipeline';

function setTestBrand(brand, el) {
  APP.testBrand = brand;
  document.querySelectorAll('#test-brand-tabs .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

function setTestMode(mode, el) {
  APP.testMode = mode;
  document.querySelectorAll('#test-mode-tabs .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const sender = document.getElementById('test-sender-id');
  const resetBtn = document.getElementById('test-reset-btn');
  if (sender) sender.style.display = mode === 'pipeline' ? '' : 'none';
  if (resetBtn) resetBtn.style.display = mode === 'pipeline' ? '' : 'none';
}

function _jsonBlock(obj) {
  try {
    return JSON.stringify(obj || {}, null, 2);
  } catch (_) {
    return String(obj || '');
  }
}

function _setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || '—';
}

function _setHtml(id, value) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = value || '';
}

function _renderScore(score, label = 'Score') {
  const pct = Math.max(0, Math.min(100, Math.round((score || 0) * 100)));
  _setText('res-score-label', label);
  _setText('res-score', `${pct}%`);
  const bar = document.getElementById('res-bar');
  if (bar) {
    bar.style.width = pct + '%';
    bar.style.background = pct >= 78 ? 'var(--success)' : pct >= 55 ? 'var(--warning)' : 'var(--danger)';
  }
}

function _renderConfidence(confidence) {
  const confMap = {
    high: ['badge-green', 'High Confidence'],
    medium: ['badge-yellow', 'Medium Confidence'],
    low: ['badge-red', 'Low / Fallback'],
  };
  const [cls, lbl] = confMap[confidence] || ['badge-gray', confidence || 'Unknown'];
  const badge = document.getElementById('res-confidence-badge');
  if (badge) {
    badge.className = 'badge ' + cls;
    badge.textContent = lbl;
  }
}

function _renderTopResults(results) {
  if (!results || !results.length) {
    _setHtml('res-top5', '<div style="font-size:12px;color:var(--text-dim);padding:8px 0">Không có kết quả RAG top-k.</div>');
    return;
  }
  _setHtml('res-top5', results.map((r, i) => `
    <div style="display:flex;gap:12px;align-items:center;padding:10px 14px;background:${i === 0 ? 'var(--bg-surface2)' : 'var(--bg-card)'};border-radius:var(--r-sm);margin-bottom:6px;border:1px solid ${i === 0 ? 'var(--primary)' : 'var(--border)'}">
      <span style="font-size:11px;color:var(--text-dim);min-width:24px;font-family:'JetBrains Mono',monospace">#${i + 1}</span>
      <span style="flex:1;font-size:13px;font-weight:${i === 0 ? '600' : '400'};color:var(--text-main)">${escapeHtml(r.intent || r.source_id || 'unknown')}</span>
      <span style="font-size:12px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${(r.score || 0) >= 0.78 ? 'var(--success)' : (r.score || 0) >= 0.55 ? 'var(--warning)' : 'var(--text-dim)'}">${Math.round((r.score || 0) * 100)}%</span>
      <span class="badge badge-gray" style="font-size:10.5px">${escapeHtml(r.category || r.retrieval_method || '—')}</span>
    </div>`).join(''));
}

function _renderPipelineResult(d) {
  const res = d.response || {};
  const debug = d.debug || {};
  const rawRag = debug.raw_rag || {};

  _setText('res-intent', res.intent || '(không khớp intent nào)');
  _setText('res-answer', res.answer || '—');
  _setText('res-fallback', res.fallback_reason || '—');
  _setText('res-stage', res.lead_stage || '—');
  const shopee = res.shopee_url || '—';
  const shopeeEl = document.getElementById('res-shopee');
  if (shopeeEl) {
    shopeeEl.innerHTML = shopee && shopee !== '—'
      ? `<a href="${escapeHtml(shopee)}" target="_blank" rel="noopener" style="color:var(--primary)">${escapeHtml(shopee)}</a>`
      : '—';
  }
  _setText('res-latency', `${res.latency_ms || 0}ms / total ${d.latency_ms_total || 0}ms`);
  _renderScore(res.score || 0, 'Pipeline Score');
  _renderConfidence(res.confidence);
  _setText('res-top5-label', 'Raw RAG Top Results để đối chiếu:');
  _renderTopResults(rawRag.results || []);

  const debugPanel = document.getElementById('pipeline-debug-panel');
  if (debugPanel) debugPanel.style.display = 'block';
  _setText('res-query-plan', _jsonBlock(debug.query_plan));
  _setText('res-reference', _jsonBlock({
    reference_resolution: debug.reference_resolution,
    query_entities: debug.query_entities,
    conversation_state: debug.conversation_state,
  }));
  _setText('res-trace', _jsonBlock(debug.last_trace));
}

function _renderRagResult(d) {
  _setText('res-intent', d.intent || '(không khớp intent nào)');
  _setText('res-answer', d.answer || '—');
  _setText('res-fallback', d.fallback_reason || '—');
  _setText('res-stage', 'raw_rag');
  _setHtml('res-shopee', '—');
  _setText('res-latency', '—');
  _renderScore(d.score || 0, d.score_margin ? `Similarity (+${Math.round(d.score_margin * 100)}% margin)` : 'Similarity Score');
  _renderConfidence(d.confidence);
  _setText('res-top5-label', 'Top 5 Document Matching:');
  _renderTopResults(d.results || []);

  const debugPanel = document.getElementById('pipeline-debug-panel');
  if (debugPanel) debugPanel.style.display = 'none';
}

async function runTest() {
  const query = document.getElementById('test-query')?.value.trim();
  if (!query) { toast('Vui lòng nhập câu hỏi trước', 'error'); return; }
  const mode = APP.testMode || 'pipeline';
  const btn = document.getElementById('test-btn');
  const result = document.getElementById('test-result');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> <span>${mode === 'pipeline' ? 'Đang chạy full pipeline...' : 'Đang vector search...'}</span>`;
  }
  if (result) result.style.display = 'none';

  try {
    if (mode === 'rag') {
      const d = await fetchJSON(`/admin/test/query?query=${encodeURIComponent(query)}&brand=${APP.testBrand}`, { method: 'POST' });
      _renderRagResult(d);
    } else {
      const senderId = document.getElementById('test-sender-id')?.value.trim() || 'dashboard_debug_001';
      const d = await fetchJSON('/admin/test/chat-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand: APP.testBrand,
          sender_id: senderId,
          text: query,
          fb_name: 'Dashboard Debug',
          include_rag: true,
        }),
      });
      _renderPipelineResult(d);
    }
    if (result) result.style.display = 'block';
    refreshIcons();
  } catch (e) {
    toast('Lỗi test: ' + e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="play"></i><span>Chạy Debug</span>';
    }
    refreshIcons();
  }
}

async function resetTestSession() {
  const senderId = document.getElementById('test-sender-id')?.value.trim() || 'dashboard_debug_001';
  const brand = APP.testBrand || 'zeo';
  const btn = document.getElementById('test-reset-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> <span>Đang reset...</span>';
  }
  try {
    await fetchJSON(`/admin/customers/${brand}/${encodeURIComponent(senderId)}/session`, { method: 'DELETE' });
    toast(`Đã reset session test ${senderId}`, 'success');
  } catch (e) {
    toast('Lỗi reset session: ' + e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="rotate-ccw"></i><span>Reset Session</span>';
    }
    refreshIcons();
  }
}
