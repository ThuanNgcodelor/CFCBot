/** customers.js — Customers CRUD, Session & Chat History Viewer, Filter Chips, Export CSV, Admin Notes & Tags */
'use strict';

let _filterHasPhone = 'all'; // 'all' | 'yes' | 'no'
let _filterStage = 'all';

async function loadCustomers() {
  APP.allCustomers = [];
  const tbody = document.getElementById('customers-table');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:36px"><span class="spinner"></span> <span style="color:var(--text-muted);margin-left:8px">Đang tải danh sách khách hàng...</span></td></tr>`;
  try {
    const d = await fetchJSON(`/admin/customers?brand=${APP.customerBrand}&page=1&page_size=500`);
    APP.allCustomers = d.customers || [];
    APP.customerPage = 1;
    renderCustomers();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:var(--danger);padding:24px;text-align:center">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
  }
}

function setCustomerBrand(brand, el) {
  APP.customerBrand = brand;
  document.querySelectorAll('#page-customers .filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  loadCustomers();
}

function setPhoneFilter(val, el) {
  _filterHasPhone = val;
  document.querySelectorAll('.filter-phone-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  APP.customerPage = 1;
  renderCustomers();
}

function setStageFilter(val) {
  _filterStage = val;
  APP.customerPage = 1;
  renderCustomers();
}

function filterCustomers() { APP.customerPage = 1; renderCustomers(); }

function renderCustomers() {
  const search = document.getElementById('customer-search')?.value.toLowerCase() || '';
  let filtered = APP.allCustomers.filter(c => {
    const matchSearch = !search ||
      c.phone?.includes(search) ||
      c.fb_name?.toLowerCase().includes(search) ||
      c.area?.toLowerCase().includes(search) ||
      c.sender_id?.includes(search) ||
      c.admin_notes?.toLowerCase().includes(search);

    const hasPhone = Boolean(c.phone && c.phone.trim() && c.phone !== '—');
    const matchPhone = _filterHasPhone === 'all' ||
      (_filterHasPhone === 'yes' && hasPhone) ||
      (_filterHasPhone === 'no' && !hasPhone);

    const matchStage = _filterStage === 'all' || c.lead_stage === _filterStage;

    return matchSearch && matchPhone && matchStage;
  });

  const pageSize = 25;
  const total = filtered.length;
  const start = (APP.customerPage - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize);
  const tbody = document.getElementById('customers-table');
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-dim)">Không tìm thấy khách hàng nào theo bộ lọc hiện tại</td></tr>`;
  } else {
    tbody.innerHTML = items.map(c => {
      const hasNotes = Boolean(c.admin_notes && c.admin_notes.trim());
      const tags = (c.admin_tags || []).map(t => `<span class="badge badge-purple" style="font-size:10px;padding:1px 6px;margin-right:3px">${t}</span>`).join('');

      return `
      <tr>
        <td><span class="badge ${c.brand === 'ZEO' ? 'badge-green' : 'badge-blue'}">${c.brand}</span></td>
        <td><code style="color:var(--text-dim);font-size:11px">${c.sender_id?.slice(-10)}</code></td>
        <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          <div style="font-weight:600;color:var(--text-main)">${c.fb_name || '<span style="color:var(--text-dim)">—</span>'}</div>
          ${tags ? `<div style="margin-top:3px">${tags}</div>` : ''}
        </td>
        <td style="font-weight:600;color:${c.phone ? 'var(--success)' : 'var(--text-dim)'}">
          ${c.phone ? `<code style="color:#34D399">${c.phone}</code>` : '—'}
        </td>
        <td style="font-size:12px;color:var(--text-muted);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.area || '—'}</td>
        <td>${stageBadge(c.lead_stage)}</td>
        <td style="font-size:11.5px;color:var(--text-dim);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${hasNotes ? `<span title="Ghi chú: ${c.admin_notes}" style="color:var(--warning)">● </span>` : ''}${c.last_intent || '—'}
        </td>
        <td style="text-align:right">
          <div style="display:inline-flex;gap:4px;justify-content:flex-end">
            <button class="btn btn-ghost btn-xs" title="Xem lịch sử chat" onclick="viewHistory('${c.brand.toLowerCase()}','${c.sender_id}')">
              <i data-lucide="message-square"></i>
              <span>Chat</span>
            </button>
            <button class="btn btn-icon btn-xs" title="Xem session raw" onclick="viewSession('${c.brand.toLowerCase()}','${c.sender_id}')">
              <i data-lucide="eye"></i>
            </button>
            <button class="btn btn-ghost btn-xs" title="Chỉnh sửa & Ghi chú" onclick="openEditCustomer('${c.brand.toLowerCase()}','${c.sender_id}')">
              <i data-lucide="edit-3"></i>
            </button>
            <button class="btn btn-danger btn-xs" title="Xóa hoàn toàn" onclick="deleteCustomer('${c.brand.toLowerCase()}','${c.sender_id}')">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  // Pagination
  const pages = Math.ceil(total / pageSize);
  const pagDiv = document.getElementById('customer-pagination');
  if (pagDiv) {
    if (pages <= 1) {
      pagDiv.innerHTML = `<span style="font-size:12px;color:var(--text-dim)">${total} khách hàng</span>`;
    } else {
      let html = `<span style="font-size:12px;color:var(--text-dim);margin-right:10px">${total} khách hàng</span>`;
      for (let i = 1; i <= Math.min(pages, 10); i++) {
        html += `<button class="btn ${i === APP.customerPage ? 'btn-primary' : 'btn-ghost'} btn-xs" style="margin-right:4px" onclick="goCustomerPage(${i})">${i}</button>`;
      }
      pagDiv.innerHTML = html;
    }
  }

  refreshIcons();
}

function goCustomerPage(p) { APP.customerPage = p; renderCustomers(); }

async function openEditCustomer(brand, senderId) {
  try {
    const d = await fetchJSON(`/admin/customers/${brand}/${senderId}/session`);
    const p = d.profile || {};
    document.getElementById('edit-cust-brand').value = brand;
    document.getElementById('edit-cust-sender-id').value = senderId;
    document.getElementById('edit-cust-name').value = p.fb_name || '';
    document.getElementById('edit-cust-phone').value = p.phone || p.customer_phone || '';
    document.getElementById('edit-cust-area').value = p.area || p.customer_location || '';
    document.getElementById('edit-cust-intent').value = p.last_intent || '';
    document.getElementById('edit-cust-stage').value = p.lead_stage || 'new';
    document.getElementById('edit-cust-notes').value = p.admin_notes || '';
    document.getElementById('edit-cust-tags').value = (p.admin_tags || []).join(', ');
    document.getElementById('edit-modal-title').innerHTML = `<i data-lucide="edit-3"></i><span>Sửa Thông Tin — ...${senderId.slice(-8)} (${brand.toUpperCase()})</span>`;
    document.getElementById('edit-customer-modal').classList.add('open');
    refreshIcons();
  } catch (e) { toast('Lỗi tải thông tin: ' + e.message, 'error'); }
}

async function saveEditCustomer() {
  const brand = document.getElementById('edit-cust-brand').value;
  const senderId = document.getElementById('edit-cust-sender-id').value;
  const tagsStr = document.getElementById('edit-cust-tags').value.trim();
  const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];

  const payload = {
    fb_name:     document.getElementById('edit-cust-name').value.trim(),
    phone:       document.getElementById('edit-cust-phone').value.trim(),
    area:        document.getElementById('edit-cust-area').value.trim(),
    lead_stage:  document.getElementById('edit-cust-stage').value,
    last_intent: document.getElementById('edit-cust-intent').value.trim(),
    admin_notes: document.getElementById('edit-cust-notes').value.trim(),
    admin_tags:  tags,
  };
  try {
    await fetchJSON(`/admin/customers/${brand}/${senderId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    toast('Đã cập nhật thông tin và ghi chú thành công!', 'success');
    closeEditModal();
    loadCustomers();
    loadStats();
  } catch (e) { toast('Lỗi lưu: ' + e.message, 'error'); }
}

async function deleteCustomer(brand, senderId) {
  if (!confirm(`Xác nhận xóa khách ${senderId} khỏi Redis?\nHành động này không thể hoàn tác.`)) return;
  try {
    await fetchJSON(`/admin/customers/${brand}/${senderId}`, { method: 'DELETE' });
    toast('Đã xóa khách hàng!', 'success');
    loadCustomers(); loadStats();
  } catch (e) { toast('Lỗi xóa: ' + e.message, 'error'); }
}

async function viewSession(brand, senderId) {
  try {
    const d = await fetchJSON(`/admin/customers/${brand}/${senderId}/session`);
    const p = d.profile || {};
    document.getElementById('modal-title').innerHTML = `<i data-lucide="user"></i><span>Session — ...${senderId.slice(-10)} (${brand.toUpperCase()})</span>`;
    document.getElementById('modal-content').innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;font-size:13px">
        <div style="display:grid;grid-template-columns:100px 1fr;gap:8px"><span style="color:var(--text-dim)">SĐT:</span><strong style="color:var(--text-main)">${p.phone || p.customer_phone || '—'}</strong></div>
        <div style="display:grid;grid-template-columns:100px 1fr;gap:8px"><span style="color:var(--text-dim)">Khu vực:</span><span>${p.area || p.customer_location || '—'}</span></div>
        <div style="display:grid;grid-template-columns:100px 1fr;gap:8px"><span style="color:var(--text-dim)">Lead Stage:</span><span>${stageBadge(p.lead_stage)}</span></div>
        <div style="display:grid;grid-template-columns:100px 1fr;gap:8px"><span style="color:var(--text-dim)">Intent cuối:</span><code>${p.last_intent || '—'}</code></div>
        <div style="display:grid;grid-template-columns:100px 1fr;gap:8px"><span style="color:var(--text-dim)">Ghi chú:</span><span>${p.admin_notes || '—'}</span></div>
        <div style="display:grid;grid-template-columns:100px 1fr;gap:8px"><span style="color:var(--text-dim)">Tags:</span><span>${(p.admin_tags || []).join(', ') || '—'}</span></div>
        <div style="margin-top:8px">
          <div style="color:var(--text-dim);margin-bottom:6px;font-weight:600">Raw Session JSON:</div>
          <pre style="background:#050811;padding:12px;border-radius:var(--r-sm);border:1px solid var(--border);color:#818CF8;font-size:11px;overflow-x:auto;max-height:220px">${JSON.stringify(d.session, null, 2)}</pre>
        </div>
      </div>
      <div style="margin-top:18px;display:flex;justify-content:flex-end">
        <button class="btn btn-danger btn-sm" onclick="resetSession('${brand}','${senderId}');closeModal()">
          <i data-lucide="rotate-ccw"></i>
          <span>Reset Session</span>
        </button>
      </div>
    `;
    document.getElementById('session-modal').classList.add('open');
    refreshIcons();
  } catch (e) { toast('Lỗi tải session: ' + e.message, 'error'); }
}

async function viewHistory(brand, senderId) {
  try {
    const d = await fetchJSON(`/admin/customers/${brand}/${senderId}/history`);
    const modal = document.getElementById('history-modal');
    document.getElementById('history-modal-title').innerHTML = `<i data-lucide="message-square"></i><span>Lịch Sử Chat — ...${senderId.slice(-10)} (${brand.toUpperCase()})</span>`;

    const msgs = d.messages || [];
    const container = document.getElementById('history-messages-container');

    if (!msgs.length) {
      container.innerHTML = `<div style="text-align:center;padding:36px 20px;color:var(--text-dim)"><p>Chưa có lịch sử tin nhắn lưu trong Redis cho khách này.</p></div>`;
    } else {
      container.innerHTML = msgs.map((m, i) => {
        const isUser = m.role === 'user' || m.sender === 'user' || m.from === 'user' || m.user_message;
        const text = m.text || m.content || m.user_message || m.bot_reply || m.raw || JSON.stringify(m);
        const time = m.timestamp ? new Date(m.timestamp).toLocaleTimeString('vi-VN') : '';
        const intent = m.intent ? `<span class="badge badge-purple" style="font-size:10px">${m.intent}</span>` : '';

        return `
          <div class="chat-bubble ${isUser ? 'user' : 'bot'}">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px;font-size:11px;opacity:0.8">
              <span>${isUser ? 'Khách Hàng' : 'CFC AI Bot'}</span>
              <div style="display:flex;align-items:center;gap:6px">
                ${intent}
                ${time ? `<span class="chat-time" style="margin-top:0">${time}</span>` : ''}
              </div>
            </div>
            <div style="font-size:13px;line-height:1.55;word-break:break-word">${text}</div>
          </div>
        `;
      }).join('');
    }

    modal.classList.add('open');
    refreshIcons();
  } catch (e) {
    toast('Lỗi tải lịch sử chat: ' + e.message, 'error');
  }
}

async function resetSession(brand, senderId) {
  if (!confirm(`Reset session của ${senderId}?`)) return;
  try {
    await fetchJSON(`/admin/customers/${brand}/${senderId}/session`, { method: 'DELETE' });
    toast('Đã reset session thành công!', 'success');
    loadCustomers();
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}

function exportCustomersCSV() {
  const brand = APP.customerBrand;
  const hasPhoneParam = _filterHasPhone === 'yes' ? '&has_phone=true' : _filterHasPhone === 'no' ? '&has_phone=false' : '';
  const stageParam = _filterStage !== 'all' ? `&lead_stage=${_filterStage}` : '';
  const url = `/admin/customers/export?brand=${brand}${hasPhoneParam}${stageParam}`;

  toast('Đang xuất file CSV...', 'success');
  window.open(url, '_blank');
}
