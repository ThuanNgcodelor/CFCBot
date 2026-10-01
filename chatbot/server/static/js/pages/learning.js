/** learning.js — Learning Queue Review & AI Auto-Suggest FAQ */
'use strict';

async function loadLearningQueue() {
  const container = document.getElementById('lq-container');
  if (!container) return;
  container.innerHTML = `<div style="text-align:center;padding:36px"><span class="spinner"></span><span style="color:var(--text-muted);margin-left:8px">Đang tải Learning Queue...</span></div>`;
  try {
    const d = await fetchJSON(`/admin/learning-queue?brand=${APP.lqBrand}`);
    if (!d.items?.length) {
      container.innerHTML = `
        <div style="text-align:center;padding:48px 20px;color:var(--text-dim)">
          <i data-lucide="check-circle-2" style="width:44px;height:44px;color:var(--success);margin-bottom:12px"></i>
          <p style="font-size:14px;color:var(--text-main);font-weight:600">Không có câu hỏi nào cần review</p>
          <p style="font-size:12px;margin-top:4px">Bot đang tự tin trả lời chính xác tất cả các intent!</p>
        </div>`;
      refreshIcons();
      return;
    }
    container.innerHTML = d.items.map((item, i) => `
      <div class="card" style="margin-bottom:14px;padding:20px" id="lq-item-${i}">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
          <div style="display:flex;align-items:center;gap:8px">
            <span class="badge ${item.brand === 'ZEO' ? 'badge-green' : 'badge-blue'}">${item.brand || 'ZEO'}</span>
            ${item.confidence ? `<span class="badge badge-yellow">Độ tin cậy: ${Math.round(item.confidence * 100)}%</span>` : ''}
          </div>
          ${item.timestamp ? `<span style="font-size:11.5px;color:var(--text-dim);font-family:'JetBrains Mono',monospace">${new Date(item.timestamp).toLocaleString('vi-VN')}</span>` : ''}
        </div>
        <div style="font-size:14px;font-weight:600;color:var(--text-main);background:var(--bg-app);padding:12px 16px;border-radius:var(--r-sm);border:1px solid var(--border);margin-bottom:12px">
          "${item.user_message || item.query || item.raw || JSON.stringify(item)}"
        </div>
        ${item.bot_reply ? `<div style="font-size:12.5px;color:var(--text-muted);margin-bottom:14px;line-height:1.5"><strong>Bot đã trả lời:</strong> ${item.bot_reply}</div>` : ''}
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn btn-primary btn-sm" onclick="approveLQ(${i}, '${item.brand?.toLowerCase() || 'zeo'}', this, '${encodeURIComponent(item.user_message || item.query || '')}')">
            <i data-lucide="plus-circle"></i>
            <span>Thêm vào FAQ</span>
          </button>
          <button class="btn btn-danger btn-sm" onclick="document.getElementById('lq-item-${i}').style.display='none'">
            <i data-lucide="trash-2"></i>
            <span>Bỏ qua</span>
          </button>
        </div>
      </div>`).join('');
    refreshIcons();
  } catch (e) {
    container.innerHTML = `
      <div style="text-align:center;padding:36px;color:var(--text-dim)">
        <i data-lucide="alert-circle" style="width:36px;height:36px;color:var(--warning);margin-bottom:10px"></i>
        <p>Chưa có dữ liệu learning queue trong Redis.</p>
      </div>`;
    refreshIcons();
  }
}

function setLQBrand(brand, el) {
  APP.lqBrand = brand;
  document.querySelectorAll('#page-learning .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  loadLearningQueue();
}

async function approveLQ(idx, brand, btn, rawQueryEncoded = '') {
  const defaultQuery = rawQueryEncoded ? decodeURIComponent(rawQueryEncoded) : '';
  const intent = prompt('Nhập intent name (ví dụ: wholesale_methods):', defaultQuery.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 30));
  if (!intent) return;
  const question = prompt('Câu hỏi mẫu (phân cách bằng ;):', defaultQuery) || defaultQuery;
  const answer = prompt('Nhập câu trả lời chuẩn:');
  if (!answer) return;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    await fetchJSON(`/admin/learning-queue/approve?brand=${brand}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, question_examples: question, answer, category: 'faq' }),
    });
    toast('Đã thêm vào FAQ và cập nhật Vector Index!', 'success');
    document.getElementById('lq-item-' + idx).style.display = 'none';
  } catch (e) {
    toast('Lỗi: ' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="plus-circle"></i><span>Thêm vào FAQ</span>';
    refreshIcons();
  }
}

// ─── AI Auto-Suggest FAQ from Learning Queue (C1) ───
async function triggerAISuggestFAQ() {
  const btn = document.getElementById('btn-ai-suggest-faq');
  const resultDiv = document.getElementById('ai-suggest-results');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> <span>AI đang phân tích...</span>'; }
  toast('AI đang quét và phân tích các câu hỏi chưa trả lời...', 'success');

  try {
    const d = await fetchJSON(`/admin/learning/ai-suggest?brand=${APP.lqBrand}`);
    if (!d.suggestions?.length) {
      toast(d.message || 'Không có đề xuất nào từ AI', 'info');
      return;
    }

    resultDiv.innerHTML = `
      <div class="card" style="margin-top:16px;margin-bottom:20px;padding:20px;border-color:var(--primary)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <div style="font-weight:700;font-size:14px;color:#A5B4FC;display:flex;align-items:center;gap:8px">
            <i data-lucide="sparkles"></i>
            <span>AI Đã Đề Xuất ${d.suggestions.length} Nhóm FAQ Mới</span>
          </div>
          <button class="btn btn-ghost btn-xs" onclick="document.getElementById('ai-suggest-results').innerHTML=''">✕ Đóng</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:14px">
          ${d.suggestions.map((s, idx) => `
            <div style="background:var(--bg-app);padding:16px;border-radius:var(--r-sm);border:1px solid var(--border)" id="sug-${idx}">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <span style="font-weight:700;color:var(--text-main);font-family:'JetBrains Mono',monospace">${s.intent}</span>
                <span class="badge ${s.brand === 'ZEO' ? 'badge-green' : 'badge-blue'}">${s.brand || 'ZEO'}</span>
              </div>
              <div style="font-size:12.5px;color:var(--text-dim);margin-bottom:8px">
                <strong style="color:var(--text-muted)">Câu hỏi mẫu:</strong> ${(s.sample_questions || []).join(' ; ') || s.intent}
              </div>
              <div style="font-size:13px;color:#34D399;background:var(--success-light);padding:10px 14px;border-radius:var(--r-sm);margin-bottom:12px;border:1px solid var(--success-border)">
                <strong>Câu trả lời đề xuất:</strong> ${s.suggested_answer}
              </div>
              <div style="display:flex;gap:8px">
                <button class="btn btn-success btn-sm" onclick="applySuggestion(${idx}, '${s.brand?.toLowerCase() || 'zeo'}', '${s.intent}', '${encodeURIComponent((s.sample_questions || []).join(';'))}', '${encodeURIComponent(s.suggested_answer)}')">
                  <i data-lucide="check"></i>
                  <span>Duyệt FAQ này</span>
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
    refreshIcons();
    toast(`AI đã gom nhóm và đề xuất ${d.suggestions.length} FAQ mới!`, 'success');
  } catch (e) {
    toast('Lỗi phân tích AI: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="sparkles"></i><span>AI Đề Xuất FAQ Tự Động</span>'; refreshIcons(); }
  }
}

async function applySuggestion(idx, brand, intent, qEncoded, aEncoded) {
  const question = decodeURIComponent(qEncoded);
  const answer = decodeURIComponent(aEncoded);
  try {
    await fetchJSON(`/admin/learning-queue/approve?brand=${brand}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, question_examples: question, answer, category: 'faq' }),
    });
    toast(`Đã thêm FAQ "${intent}" vào Knowledge Base!`, 'success');
    document.getElementById(`sug-${idx}`)?.remove();
    loadLearningQueue();
  } catch (e) {
    toast('Lỗi duyệt FAQ: ' + e.message, 'error');
  }
}
