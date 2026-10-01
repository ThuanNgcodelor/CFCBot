/**
 * assistant.js — Trợ Lý Điều Hành AI & Quản Lý Phiên Hội Thoại Đa Kênh
 * Hỗ trợ Groq LLaMA 3.3 70B, Tool Calling n8n/CRM, và Lịch sử Chat đa phiên (Sessions Manager)
 */
'use strict';

const STORAGE_KEY = 'cfc_ai_chat_sessions_v1';
let _sessions = [];
let _currentSessionId = null;
let _assistantBrand = 'all';
let _isAssistantSending = false;

// ─── Khởi tạo Trang Assistant ──────────────────────────────────────────────
function initAssistantPage() {
  loadSessionsFromStorage();
  loadAssistantQuickPrompts();

  if (_sessions.length === 0) {
    createNewAssistantSession(false);
  } else if (!_currentSessionId || !_sessions.find(s => s.id === _currentSessionId)) {
    _currentSessionId = _sessions[0].id;
  }

  renderSessionsList();
  renderCurrentSessionMessages();

  const inputEl = document.getElementById('assistant-input');
  if (inputEl && !inputEl.dataset.bound) {
    inputEl.dataset.bound = 'true';
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitAssistantChat();
      }
    });
  }
  refreshIcons();
}

// ─── Quản lý LocalStorage Sessions ─────────────────────────────────────────
function loadSessionsFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    _sessions = raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Error loading sessions:', e);
    _sessions = [];
  }
}

function saveSessionsToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(_sessions));
  } catch (e) {
    console.error('Error saving sessions:', e);
  }
}

function getCurrentSession() {
  return _sessions.find(s => s.id === _currentSessionId) || null;
}

// ─── Tạo, Đổi & Xóa Phiên Hội Thoại ───────────────────────────────────────
function createNewAssistantSession(render = true) {
  const newSession = {
    id: 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4),
    title: 'Hội thoại mới',
    brand: _assistantBrand,
    updatedAt: new Date().toISOString(),
    messages: []
  };

  _sessions.unshift(newSession);
  _currentSessionId = newSession.id;
  saveSessionsToStorage();

  if (render) {
    renderSessionsList();
    renderCurrentSessionMessages();
    const input = document.getElementById('assistant-input');
    if (input) input.focus();
  }
  refreshIcons();
}

function switchAssistantSession(id) {
  _currentSessionId = id;
  const sess = getCurrentSession();
  if (sess && sess.brand) {
    setAssistantBrand(sess.brand, null, false);
  }
  renderSessionsList();
  renderCurrentSessionMessages();
}

function deleteAssistantSession(id, event) {
  if (event) event.stopPropagation();
  _sessions = _sessions.filter(s => s.id !== id);

  if (_sessions.length === 0) {
    createNewAssistantSession(false);
  } else if (_currentSessionId === id) {
    _currentSessionId = _sessions[0].id;
  }

  saveSessionsToStorage();
  renderSessionsList();
  renderCurrentSessionMessages();
  toast('Đã xoá phiên hội thoại', 'success');
}

function filterAssistantSessions(keyword) {
  const kw = (keyword || '').toLowerCase().trim();
  const container = document.getElementById('assistant-sessions-list');
  if (!container) return;

  const items = container.querySelectorAll('.session-item');
  items.forEach(el => {
    const text = el.getAttribute('data-title') || '';
    if (!kw || text.toLowerCase().includes(kw)) {
      el.style.display = 'flex';
    } else {
      el.style.display = 'none';
    }
  });
}

// ─── Render Cột Lịch Sử Phiên (Sidebar Sessions List) ─────────────────────
function renderSessionsList() {
  const container = document.getElementById('assistant-sessions-list');
  if (!container) return;

  if (_sessions.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:24px 10px;color:var(--text-dim);font-size:12px">
        Chưa có phiên chat nào.<br>Bấm "+ Hội thoại mới" để bắt đầu.
      </div>
    `;
    return;
  }

  // Phân nhóm Hôm nay / Hôm qua / Cũ hơn
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = yesterday.toDateString();

  const groups = { today: [], yesterday: [], older: [] };

  _sessions.forEach(s => {
    const d = new Date(s.updatedAt || Date.now());
    const dStr = d.toDateString();
    if (dStr === todayStr) {
      groups.today.push(s);
    } else if (dStr === yesterdayStr) {
      groups.yesterday.push(s);
    } else {
      groups.older.push(s);
    }
  });

  let html = '';

  const renderGroup = (label, list) => {
    if (list.length === 0) return '';
    let groupHtml = `<div style="font-size:10.5px;font-weight:700;color:var(--text-dim);padding:8px 8px 4px;text-transform:uppercase;letter-spacing:0.05em">${label}</div>`;
    list.forEach(s => {
      const isActive = s.id === _currentSessionId;
      const msgCount = (s.messages || []).length;
      const timeStr = new Date(s.updatedAt || Date.now()).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
      groupHtml += `
        <div class="session-item" data-title="${escapeHtml(s.title)}" onclick="switchAssistantSession('${s.id}')"
          style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            padding:9px 12px;
            margin-bottom:3px;
            border-radius:var(--r-sm);
            cursor:pointer;
            transition:all var(--t-fast);
            background:${isActive ? 'var(--bg-surface2)' : 'transparent'};
            border:1px solid ${isActive ? 'var(--primary)' : 'transparent'};
          ">
          <div style="overflow:hidden;flex:1;margin-right:6px">
            <div style="font-size:12.5px;font-weight:${isActive ? '600' : '400'};color:${isActive ? 'var(--primary)' : 'var(--text-main)'};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
              ${escapeHtml(s.title || 'Hội thoại mới')}
            </div>
            <div style="display:flex;align-items:center;gap:6px;font-size:10.5px;color:var(--text-dim);margin-top:2px">
              <span>${timeStr}</span>
              <span class="badge badge-gray" style="font-size:9.5px;padding:0 5px">groq</span>
              <span>${msgCount} tin</span>
            </div>
          </div>
          <button class="btn btn-ghost btn-icon" onclick="deleteAssistantSession('${s.id}', event)" title="Xoá phiên này"
            style="width:24px;height:24px;color:var(--text-dim);opacity:0.6;flex-shrink:0">
            <i data-lucide="trash" style="width:12px;height:12px"></i>
          </button>
        </div>
      `;
    });
    return groupHtml;
  };

  html += renderGroup('Hôm nay', groups.today);
  html += renderGroup('Hôm qua', groups.yesterday);
  html += renderGroup('Cũ hơn', groups.older);

  container.innerHTML = html;
  refreshIcons();
}

// ─── Render Tin Nhắn Phiên Hiện Tại ───────────────────────────────────────
function renderCurrentSessionMessages() {
  const container = document.getElementById('assistant-messages');
  const titleEl = document.getElementById('assistant-active-session-title');
  if (!container) return;

  const sess = getCurrentSession();
  if (!sess) return;

  if (titleEl) {
    titleEl.textContent = sess.title || 'Hội thoại mới';
  }

  const msgs = sess.messages || [];

  if (msgs.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:50px 20px;color:var(--text-dim)">
        <div style="width:48px;height:48px;border-radius:var(--r-full);background:var(--bg-surface2);display:inline-flex;align-items:center;justify-content:center;margin-bottom:12px">
          <i data-lucide="bot" style="width:24px;height:24px;color:var(--primary)"></i>
        </div>
        <h3 style="font-size:16px;color:var(--text-main);margin-bottom:6px">Xin chào! Tôi là CFC AI Assistant</h3>
        <p style="font-size:13px;max-width:480px;margin:0 auto;line-height:1.6">
          Bạn có thể nhắn tin hỏi bất cứ điều gì: hỏi chuyện, hỏi model, hỏi số liệu kinh doanh, tra cứu Shopee, hoặc yêu cầu <strong>bật/tắt các workflow n8n</strong> trực tiếp.
        </p>
      </div>
    `;
    refreshIcons();
    return;
  }

  container.innerHTML = '';
  msgs.forEach(m => {
    renderMessageBubble(m.role, m.content, m.actionCards, m.toolsUsed, m.provider, m.time);
  });

  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

// ─── Quick Prompts ────────────────────────────────────────────────────────
async function loadAssistantQuickPrompts() {
  const container = document.getElementById('assistant-quick-prompts');
  if (!container) return;
  try {
    const data = await fetchJSON('/admin/assistant/quick-prompts');
    const prompts = data.prompts || [];
    container.innerHTML = prompts.map(p => `
      <button class="btn btn-ghost btn-sm" style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-full);font-size:12px;padding:5px 12px;white-space:nowrap"
        onclick="sendAssistantQuickPrompt('${escapeHtml(p.query)}')">
        <span>${p.label}</span>
      </button>
    `).join('');
    refreshIcons();
  } catch (_) {
    container.innerHTML = `
      <button class="btn btn-ghost btn-sm" style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-full);font-size:12px;padding:5px 12px"
        onclick="sendAssistantQuickPrompt('Tổng hợp tình hình khách hàng và leads mới hôm nay')">
        <span>📊 Báo cáo hôm nay</span>
      </button>
      <button class="btn btn-ghost btn-sm" style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-full);font-size:12px;padding:5px 12px"
        onclick="sendAssistantQuickPrompt('Liệt kê danh sách các workflow n8n và trạng thái hoạt động')">
        <span>⚡ Workflows n8n</span>
      </button>
      <button class="btn btn-ghost btn-sm" style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-full);font-size:12px;padding:5px 12px"
        onclick="sendAssistantQuickPrompt('Kiểm tra xem có workflow n8n nào bị lỗi gần đây không?')">
        <span>⚠️ Kiểm tra lỗi n8n</span>
      </button>
    `;
  }
}

function sendAssistantQuickPrompt(text) {
  const input = document.getElementById('assistant-input');
  if (input) input.value = text;
  submitAssistantChat();
}

function setAssistantBrand(brand, el, save = true) {
  _assistantBrand = brand;
  document.querySelectorAll('#assistant-brand-tabs .filter-tab').forEach(t => t.classList.remove('active'));
  if (el) el.classList.add('active');
  else {
    const btn = document.querySelector(`#assistant-brand-tabs .filter-tab[onclick*="'${brand}'"]`);
    if (btn) btn.classList.add('active');
  }

  const sess = getCurrentSession();
  if (sess && save) {
    sess.brand = brand;
    saveSessionsToStorage();
  }
}

// ─── Gửi Tin Nhắn & Xử Lý AI Phản Hồi ─────────────────────────────────────
async function submitAssistantChat() {
  if (_isAssistantSending) return;
  const input = document.getElementById('assistant-input');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  _isAssistantSending = true;

  let sess = getCurrentSession();
  if (!sess) {
    createNewAssistantSession(false);
    sess = getCurrentSession();
  }

  const timeStr = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  // 1. Tự động đổi tên phiên chat theo tin nhắn đầu tiên
  if (sess.messages.length === 0) {
    sess.title = text.length > 28 ? text.slice(0, 28) + '...' : text;
    const titleEl = document.getElementById('assistant-active-session-title');
    if (titleEl) titleEl.textContent = sess.title;
  }

  // 2. Thêm tin nhắn user
  const userMsg = { role: 'user', content: text, time: timeStr };
  sess.messages.push(userMsg);
  sess.updatedAt = new Date().toISOString();
  saveSessionsToStorage();
  renderSessionsList();

  // 3. Render tin nhắn user lên UI
  renderMessageBubble('user', text, [], [], '', timeStr);

  // 4. Hiện typing
  showAssistantTyping();
  const sendBtn = document.getElementById('assistant-send-btn');
  if (sendBtn) sendBtn.disabled = true;

  // 5. Chuẩn bị lịch sử gửi API
  const historyForApi = sess.messages.slice(-8).map(m => ({
    role: m.role,
    content: m.content
  }));

  try {
    const res = await fetchJSON('/admin/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: historyForApi,
        brand: _assistantBrand,
      })
    });

    hideAssistantTyping();

    const ansTime = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const ansText = res.text || '⚠️ Không nhận được phản hồi từ AI.';
    const actionCards = res.action_cards || [];
    const toolsUsed = res.tools_used || [];
    const provider = res.provider || 'groq';

    const aiMsg = {
      role: 'assistant',
      content: ansText,
      actionCards: actionCards,
      toolsUsed: toolsUsed,
      provider: provider,
      time: ansTime
    };

    sess.messages.push(aiMsg);
    sess.updatedAt = new Date().toISOString();
    saveSessionsToStorage();
    renderSessionsList();

    renderMessageBubble('assistant', ansText, actionCards, toolsUsed, provider, ansTime);

  } catch (err) {
    hideAssistantTyping();
    const errMsg = `❌ Lỗi kết nối: ${err.message}`;
    renderMessageBubble('assistant', errMsg, [], [], 'error', timeStr);
  } finally {
    _isAssistantSending = false;
    if (sendBtn) sendBtn.disabled = false;
    const msgBox = document.getElementById('assistant-messages');
    if (msgBox) msgBox.scrollTop = msgBox.scrollHeight;
    refreshIcons();
  }
}

// ─── Render Message Bubble ────────────────────────────────────────────────
function renderMessageBubble(role, content, actionCards = [], toolsUsed = [], provider = '', time = '') {
  const container = document.getElementById('assistant-messages');
  if (!container) return;

  // Remove empty welcome placeholder if present
  const placeholder = container.querySelector('div[style*="text-align:center"]');
  if (placeholder) placeholder.remove();

  const timeStr = time || new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  const isUser = role === 'user';

  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = `chat-msg-row ${isUser ? 'user-row' : 'assistant-row'}`;
  bubbleDiv.style.cssText = `
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    align-items: flex-start;
    ${isUser ? 'flex-direction: row-reverse;' : ''}
  `;

  const avatar = isUser
    ? `<div style="width:34px;height:34px;border-radius:var(--r-full);background:var(--primary);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:12px;flex-shrink:0;box-shadow:0 0 10px rgba(99,102,241,0.4)">Admin</div>`
    : `<div style="width:34px;height:34px;border-radius:var(--r-full);background:linear-gradient(135deg,#6366F1,#10B981);display:flex;align-items:center;justify-content:center;color:#fff;flex-shrink:0;box-shadow:0 0 12px rgba(16,185,129,0.3)"><i data-lucide="bot" style="width:17px;height:17px"></i></div>`;

  let toolsBadgeHtml = '';
  if (toolsUsed && toolsUsed.length > 0) {
    toolsBadgeHtml = `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap">
        <span style="font-size:11px;color:var(--text-dim)">Công cụ:</span>
        ${toolsUsed.map(t => {
          let icon = 'wrench';
          let badgeClass = 'badge-blue';
          if (t === 'execute_system_command') { icon = 'terminal'; badgeClass = 'badge-emerald'; }
          else if (t === 'trigger_n8n_webhook') { icon = 'send'; badgeClass = 'badge-amber'; }
          else if (t === 'get_system_status') { icon = 'activity'; badgeClass = 'badge-purple'; }
          return `<span class="badge ${badgeClass}" style="font-size:10px;padding:2px 7px;font-family:'JetBrains Mono',monospace"><i data-lucide="${icon}" style="width:9px;height:9px;display:inline-block;vertical-align:-1px"></i> ${t}</span>`;
        }).join('')}
      </div>
    `;
  }

  let actionCardsHtml = '';
  if (actionCards && actionCards.length > 0) {
    actionCardsHtml = actionCards.map(c => renderActionCard(c)).join('');
  }

  const formattedContent = renderMarkdownSimple(content);

  bubbleDiv.innerHTML = `
    ${avatar}
    <div style="max-width: 82%; min-width: 140px;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;${isUser ? 'justify-content:flex-end;' : ''}">
        <span style="font-size:12px;font-weight:600;color:var(--text-main)">${isUser ? 'Bạn' : 'CFC AI Assistant'}</span>
        ${provider && !isUser ? `<span class="badge badge-gray" style="font-size:9.5px;padding:1px 5px">${provider}</span>` : ''}
        <span style="font-size:11px;color:var(--text-dim)">${timeStr}</span>
      </div>
      <div style="
        background: ${isUser ? 'var(--primary)' : 'var(--bg-card)'};
        color: ${isUser ? '#ffffff' : 'var(--text-main)'};
        padding: 13px 16px;
        border-radius: ${isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px'};
        border: 1px solid ${isUser ? 'transparent' : 'var(--border)'};
        box-shadow: var(--shadow-sm);
        line-height: 1.65;
        font-size: 13.5px;
      ">
        ${toolsBadgeHtml}
        <div class="msg-content">${formattedContent}</div>
        ${actionCardsHtml ? `<div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border)">${actionCardsHtml}</div>` : ''}
      </div>
    </div>
  `;

  container.appendChild(bubbleDiv);
  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

function renderActionCard(card) {
  const tool = card.tool;
  const res = card.result || {};

  // 1. Business Stats / Leads CRM Card
  if (tool === 'get_business_stats' && res.total_customers !== undefined) {
    const details = res.details || {};
    return `
      <div class="action-card-box">
        <div class="action-card-header">
          <div style="display:flex;align-items:center;gap:6px;font-weight:700;font-size:13px;color:var(--text-main)">
            <i data-lucide="bar-chart-2" style="width:16px;height:16px;color:var(--primary)"></i>
            <span>Báo Cáo Tổng Hợp Khách Hàng &amp; Leads</span>
          </div>
          <span class="badge badge-emerald" style="font-size:10px">${res.timestamp || 'Realtime'}</span>
        </div>
        <div class="stat-metric-grid">
          <div class="stat-metric-cell">
            <span class="stat-metric-num">${res.total_customers || 0}</span>
            <span class="stat-metric-title">Tổng Khách Hàng</span>
          </div>
          <div class="stat-metric-cell" style="border-color:rgba(16,185,129,0.3)">
            <span class="stat-metric-num" style="color:var(--success)">${res.total_leads_with_phone || 0}</span>
            <span class="stat-metric-title">Leads Có SĐT</span>
          </div>
          <div class="stat-metric-cell">
            <span class="stat-metric-num" style="color:var(--warning)">${res.total_learning_queue_pending || 0}</span>
            <span class="stat-metric-title">Chờ Duyệt FAQ</span>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:8px;padding-top:8px;border-top:1px solid var(--border-subtle)">
          <div style="font-size:11.5px;color:var(--text-dim)">
            ZeO: <strong>${details.zeo?.leads_with_phone || 0} SĐT</strong> · CFC: <strong>${details.cfc?.leads_with_phone || 0} SĐT</strong>
          </div>
          <button class="btn btn-ghost btn-xs" onclick="switchPage('customers', document.querySelector('.nav-item[data-page=customers]'))" style="font-size:11px">
            <span>Mở CRM Lead</span>
            <i data-lucide="arrow-right" style="width:12px;height:12px"></i>
          </button>
        </div>
      </div>
    `;
  }

  // 2. Shopee Catalog Products Card
  if (tool === 'get_shopee_catalog_summary' && (res.sample_products || res.products)) {
    const prods = res.products || res.sample_products || [];
    return `
      <div class="action-card-box">
        <div class="action-card-header">
          <div style="display:flex;align-items:center;gap:6px;font-weight:700;font-size:13px;color:var(--text-main)">
            <i data-lucide="shopping-bag" style="width:16px;height:16px;color:var(--primary)"></i>
            <span>Sản Phẩm Khuyên Dùng (${res.total_products !== undefined ? res.total_products + ' sản phẩm' : prods.length + ' sản phẩm'})</span>
          </div>
        </div>
        <div class="shopee-product-grid">
          ${prods.slice(0, 4).map(p => `
            <div class="shopee-product-card">
              <div>
                <div class="shopee-prod-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</div>
                ${p.variant ? `<div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">${escapeHtml(p.variant)}</div>` : ''}
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;margin-top:8px">
                <span class="shopee-prod-price">${escapeHtml(p.price || '')}</span>
                ${p.link ? `<a href="${p.link}" target="_blank" rel="noopener" class="btn btn-primary btn-xs" style="text-decoration:none;padding:2px 8px;font-size:10.5px">Xem Mall</a>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // 3. n8n Workflows List Card
  if (tool === 'list_n8n_workflows' && Array.isArray(res.workflows)) {
    return `
      <div class="action-card-box">
        <div class="action-card-header">
          <div style="display:flex;align-items:center;gap:6px;font-weight:700;font-size:13px;color:var(--text-main)">
            <i data-lucide="git-branch" style="width:16px;height:16px;color:var(--primary)"></i>
            <span>Trạng Thái Workflows n8n (${res.total || res.workflows.length})</span>
          </div>
          <span class="badge badge-blue" style="font-size:10px">${res.active_count || 0} Đang Chạy</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">
          ${res.workflows.slice(0, 5).map(wf => `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:var(--bg-surface2);border-radius:var(--r-sm);border:1px solid var(--border)">
              <div style="display:flex;align-items:center;gap:8px;overflow:hidden">
                <span class="sys-dot" style="background:${wf.active ? 'var(--success)' : 'var(--danger)'}"></span>
                <span style="font-weight:600;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(wf.name)}</span>
              </div>
              <button class="btn btn-sm ${wf.active ? 'btn-ghost' : 'btn-primary'}" onclick="assistantToggleWorkflow('${wf.id}', this)" style="font-size:10.5px;padding:2px 8px">
                <i data-lucide="${wf.active ? 'power-off' : 'power'}" style="width:10px;height:10px"></i>
                <span>${wf.active ? 'Tắt' : 'Bật'}</span>
              </button>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // 4. Learning Queue Card
  if (tool === 'get_learning_queue_summary' && Array.isArray(res.items)) {
    return `
      <div class="action-card-box">
        <div class="action-card-header">
          <div style="display:flex;align-items:center;gap:6px;font-weight:700;font-size:13px;color:var(--text-main)">
            <i data-lucide="brain" style="width:16px;height:16px;color:var(--warning)"></i>
            <span>Hàng Đợi Học &amp; Duyệt FAQ (${res.total_retrieved || res.items.length} câu)</span>
          </div>
          <button class="btn btn-ghost btn-xs" onclick="switchPage('learning', document.querySelector('.nav-item[data-page=learning]'))" style="font-size:11px">
            <span>Duyệt ngay</span>
            <i data-lucide="arrow-right" style="width:11px;height:11px"></i>
          </button>
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;margin-top:6px">
          ${res.items.slice(0, 3).map(it => `
            <div style="padding:6px 10px;background:var(--bg-surface2);border-radius:var(--r-sm);font-size:12px;border:1px solid var(--border)">
              <div style="font-weight:600;color:var(--text-main)">"${escapeHtml(it.user_message || it.query || '')}"</div>
              <div style="font-size:11px;color:var(--text-dim);margin-top:2px">Lý do: ${escapeHtml(it.fallback_reason || 'Chưa chắc chắn')}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // 5. Toggle Workflow Success Card
  if (tool === 'toggle_n8n_workflow' && res.success) {
    const isNowActive = res.new_state;
    return `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:9px 12px;background:var(--bg-surface2);border-radius:var(--r-sm);border:1px solid var(--border);margin-top:6px">
        <div style="display:flex;align-items:center;gap:8px">
          <span class="sys-dot" style="background:${isNowActive ? 'var(--success)' : 'var(--danger)'}"></span>
          <div>
            <div style="font-weight:600;font-size:12.5px">${escapeHtml(res.workflow_name || 'Workflow')}</div>
            <div style="font-size:10.5px;color:var(--text-dim);font-family:'JetBrains Mono',monospace">ID: ${res.workflow_id}</div>
          </div>
        </div>
        <button class="btn btn-sm ${isNowActive ? 'btn-ghost' : 'btn-primary'}" onclick="assistantToggleWorkflow('${res.workflow_id}', this)"
          style="font-size:11px;padding:3px 10px">
          <i data-lucide="${isNowActive ? 'power-off' : 'power'}" style="width:11px;height:11px"></i>
          <span>${isNowActive ? 'Tắt workflow' : 'Bật workflow'}</span>
        </button>
      </div>
    `;
  }

  // 6. System Status Card
  if (tool === 'get_system_status' && res.redis) {
    return `
      <div style="display:flex;align-items:center;gap:12px;font-size:11.5px;color:var(--text-dim);margin-top:6px;flex-wrap:wrap">
        <span>💾 Redis RAM: <strong style="color:var(--success)">${res.redis.used_memory_ram || '?'}</strong></span>
        <span>•</span>
        <span>🔑 Keys: <strong style="color:var(--text-main)">${res.redis.total_keys || 0}</strong></span>
        <span>•</span>
        <span>⚡ n8n: <strong style="color:var(--primary)">${res.n8n ? res.n8n.active_workflows : 0} online</strong></span>
      </div>
    `;
  }
  return '';
}

async function assistantToggleWorkflow(wfId, btn) {
  if (btn) btn.disabled = true;
  try {
    const res = await fetchJSON(`/admin/n8n/workflows/${wfId}/toggle`, { method: 'POST' });
    toast(`Đã ${res.active ? 'bật' : 'tắt'} workflow thành công!`, 'success');
    submitAssistantChatWithText(`Kiểm tra lại trạng thái workflow ${res.name || wfId}`);
  } catch (e) {
    toast(`Lỗi: ${e.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function submitAssistantChatWithText(text) {
  const input = document.getElementById('assistant-input');
  if (input) input.value = text;
  submitAssistantChat();
}

function showAssistantTyping() {
  const container = document.getElementById('assistant-messages');
  if (!container) return;

  const typingDiv = document.createElement('div');
  typingDiv.id = 'assistant-typing-indicator';
  typingDiv.className = 'chat-msg-row assistant-row';
  typingDiv.style.cssText = 'display:flex;gap:12px;margin-bottom:16px;align-items:center;';
  typingDiv.innerHTML = `
    <div style="width:34px;height:34px;border-radius:var(--r-full);background:linear-gradient(135deg,#6366F1,#10B981);display:flex;align-items:center;justify-content:center;color:#fff;flex-shrink:0;">
      <i data-lucide="bot" style="width:17px;height:17px"></i>
    </div>
    <div style="background:var(--bg-card);padding:9px 14px;border-radius:14px;border:1px solid var(--border);display:flex;align-items:center;gap:6px">
      <span class="spinner" style="width:13px;height:13px;border-width:2px"></span>
      <span style="font-size:12px;color:var(--text-dim)">AI đang xử lý...</span>
    </div>
  `;
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

function hideAssistantTyping() {
  const el = document.getElementById('assistant-typing-indicator');
  if (el) el.remove();
}

function clearAssistantMessages() {
  const sess = getCurrentSession();
  if (sess) {
    sess.messages = [];
    sess.title = 'Hội thoại mới';
    sess.updatedAt = new Date().toISOString();
    saveSessionsToStorage();
    renderSessionsList();
    renderCurrentSessionMessages();
    toast('Đã làm mới tin nhắn phiên này', 'success');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, function(m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
  });
}

function renderMarkdownSimple(md) {
  if (!md) return '';
  let html = escapeHtml(md);

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h4 style="font-size:13.5px;font-weight:700;margin:8px 0 4px;color:var(--text-main)">$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3 style="font-size:14.5px;font-weight:700;margin:10px 0 5px;color:var(--text-main)">$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2 style="font-size:15.5px;font-weight:700;margin:12px 0 6px;color:var(--text-main)">$1</h2>');

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong style="font-weight:600;color:var(--text-main)">$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Code inline
  html = html.replace(/`(.*?)`/gim, '<code style="background:var(--bg-surface2);padding:2px 5px;border-radius:4px;font-family:\'JetBrains Mono\',monospace;font-size:11.5px;color:#A5B4FC">$1</code>');

  // Bullet points
  html = html.replace(/^\- (.*$)/gim, '<div style="display:flex;gap:8px;margin-bottom:3px"><span style="color:var(--primary)">•</span><span>$1</span></div>');
  html = html.replace(/^\* (.*$)/gim, '<div style="display:flex;gap:8px;margin-bottom:3px"><span style="color:var(--primary)">•</span><span>$1</span></div>');
  html = html.replace(/^\+ (.*$)/gim, '<div style="display:flex;gap:8px;margin-bottom:3px;padding-left:14px"><span style="color:var(--text-dim)">-</span><span>$1</span></div>');

  // Linebreaks
  html = html.replace(/\n/g, '<br>');

  return html;
}
