/**
 * core.js — Shared utilities, state, navigation, Lucide icons
 * CFC AI Admin Dashboard — Enterprise SaaS Edition
 */

'use strict';

// ── Global State ──────────────────────────────────
window.APP = {
  currentPage: 'dashboard',
  customerBrand: 'all',
  lqBrand: 'all',
  testBrand: 'zeo',
  testMode: 'pipeline',
  customerPage: 1,
  allCustomers: [],
  version: '2.3',
};

// ── Lucide Icon Auto-Refresh ──────────────────────
function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
window.refreshIcons = refreshIcons;

// ── Fetch Helper ──────────────────────────────────
async function fetchJSON(url, opts = {}) {
  const resp = await fetch(url, opts);
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

// ── Toast Notification ────────────────────────────
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  if (!el) return;
  const iconName = type === 'success' ? 'check-circle-2' : 'alert-circle';
  el.innerHTML = `<i data-lucide="${iconName}" style="width:16px;height:16px;flex-shrink:0"></i><span>${msg}</span>`;
  el.className = `show ${type}`;
  refreshIcons();
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => { el.className = ''; }, 3600);
}

// ── Password Toggle ───────────────────────────────
function togglePass(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.type = el.type === 'password' ? 'text' : 'password';
}

// ── Time Helpers ──────────────────────────────────
function setLastUpdated() {
  const el = document.getElementById('last-updated');
  if (el) el.textContent = 'Cập nhật: ' + new Date().toLocaleTimeString('vi-VN');
}

function timeSince(isoStr) {
  if (!isoStr) return '—';
  const diff = Date.now() - new Date(isoStr).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return 'vừa xong';
  if (min < 60) return `${min} phút trước`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} giờ trước`;
  return Math.floor(hr / 24) + ' ngày trước';
}

// ── Render Helpers ────────────────────────────────
function stageBadge(stage) {
  const map = {
    new:                ['badge-gray',   'Mới'],
    collecting_contact: ['badge-yellow', 'Đang thu thập'],
    lead_ready:         ['badge-green',  'Lead sẵn'],
    qualified:          ['badge-blue',   'Qualified'],
    escalated:          ['badge-red',    'Chuyển admin'],
    resolved:           ['badge-gray',   'Đã xử lý'],
  };
  const [cls, label] = map[stage] || ['badge-gray', stage || '?'];
  return `<span class="badge ${cls}">${label}</span>`;
}

// ── Modal Helpers ─────────────────────────────────
function closeModal() {
  document.getElementById('session-modal')?.classList.remove('open');
}
function closeEditModal() {
  document.getElementById('edit-customer-modal')?.classList.remove('open');
}
function closeHistoryModal() {
  document.getElementById('history-modal')?.classList.remove('open');
}
function closeShopeeModal() {
  document.getElementById('shopee-modal')?.classList.remove('open');
}
function closeImportSheetModal() {
  document.getElementById('import-sheet-modal')?.classList.remove('open');
}

// ── Sidebar Footer Status ─────────────────────────
async function updateSidebarStatus() {
  try {
    const s = await fetchJSON('/admin/status');
    const allOk = s.services?.redis?.status === 'ok' && s.services?.ollama?.status === 'ok';
    const dot = document.getElementById('sidebar-sys-dot');
    const label = document.getElementById('sidebar-sys-label');
    if (dot) {
      dot.style.background = allOk ? 'var(--success)' : 'var(--warning)';
      dot.style.boxShadow = allOk ? '0 0 8px var(--success)' : '0 0 8px var(--warning)';
    }
    if (label) label.textContent = allOk ? 'Hệ thống ổn định' : 'Có cảnh báo hệ thống';
  } catch (_) {}
}

// ── Navigation & SPA Hash Routing ────────────────────────────────
function switchPage(page, el, updateHash = true) {
  const validPages = ['assistant', 'dashboard', 'reports', 'documents', 'n8n', 'customers', 'learning', 'test', 'settings'];
  if (!validPages.includes(page)) {
    page = 'dashboard';
  }

  // 1. Highlight Nav Item
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const targetNav = el || document.querySelector(`.nav-item[data-page="${page}"]`);
  if (targetNav) targetNav.classList.add('active');

  // 2. Hiện Trang tương ứng
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const pageEl = document.getElementById('page-' + page);
  if (pageEl) pageEl.classList.add('active');

  const titles = {
    assistant: 'Trợ Lý Điều Hành AI',
    dashboard: 'Dashboard',
    reports:   'Báo Cáo & AI Insights',
    documents: 'Nạp Tài Liệu & Tự Học',
    n8n:       'n8n Control',
    customers: 'Hội Thoại Lead',
    learning:  'Learning Queue',
    test:      'Test Bot',
    settings:  'Cài Đặt & API Keys',
  };

  // 3. Cập nhật Breadcrumb
  const crumb = document.getElementById('breadcrumb-current');
  if (crumb) crumb.textContent = titles[page] || page;

  // 4. Đồng bộ URL Hash lên thanh địa chỉ trình duyệt (#page)
  if (updateHash && window.location.hash !== '#' + page) {
    if (window.history && window.history.pushState) {
      window.history.pushState(null, '', '#' + page);
    } else {
      window.location.hash = '#' + page;
    }
  }

  APP.currentPage = page;
  loadPage(page);
  setTimeout(refreshIcons, 50);
}

// Lắng nghe sự kiện Back/Forward của trình duyệt để đổi trang mượt mà
window.addEventListener('popstate', () => {
  const hashPage = (window.location.hash || '').replace('#', '').trim();
  if (hashPage && hashPage !== APP.currentPage) {
    switchPage(hashPage, null, false);
  }
});
window.addEventListener('hashchange', () => {
  const hashPage = (window.location.hash || '').replace('#', '').trim();
  if (hashPage && hashPage !== APP.currentPage) {
    switchPage(hashPage, null, false);
  }
});

function loadPage(page) {
  switch (page) {
    case 'assistant': if (typeof initAssistantPage === 'function') initAssistantPage(); break;
    case 'dashboard': loadStatus(); loadStats(); break;
    case 'reports':   loadReports(); break;
    case 'documents': loadDocuments(); break;
    case 'n8n':       initN8nPage(); break;
    case 'customers': loadCustomers(); break;
    case 'learning':  loadLearningQueue(); break;
    case 'settings':  loadSettings(); break;
    case 'test':      refreshIcons(); break;
  }
  setTimeout(refreshIcons, 100);
}

function refreshCurrentPage() {
  loadPage(APP.currentPage);
  setLastUpdated();
  refreshIcons();
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
  html = html.replace(/^### (.*$)/gim, '<h4 style="font-size:14px;font-weight:700;margin:12px 0 6px;color:var(--text-main)">$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3 style="font-size:15px;font-weight:700;margin:14px 0 8px;color:var(--primary)">$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2 style="font-size:16.5px;font-weight:800;margin:16px 0 10px;color:var(--text-main)">$1</h2>');

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong style="font-weight:700;color:var(--text-main)">$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Code inline
  html = html.replace(/`(.*?)`/gim, '<code style="background:var(--bg-surface2);padding:2px 5px;border-radius:4px;font-family:\'JetBrains Mono\',monospace;font-size:11.5px;color:#A5B4FC">$1</code>');

  // Bullet points
  html = html.replace(/^\- (.*$)/gim, '<div style="display:flex;gap:8px;margin-bottom:4px"><span style="color:var(--primary)">•</span><span>$1</span></div>');
  html = html.replace(/^\* (.*$)/gim, '<div style="display:flex;gap:8px;margin-bottom:4px"><span style="color:var(--primary)">•</span><span>$1</span></div>');
  html = html.replace(/^\+ (.*$)/gim, '<div style="display:flex;gap:8px;margin-bottom:4px;padding-left:14px"><span style="color:var(--text-dim)">-</span><span>$1</span></div>');

  // Linebreaks
  html = html.replace(/\n/g, '<br>');

  return html;
}
