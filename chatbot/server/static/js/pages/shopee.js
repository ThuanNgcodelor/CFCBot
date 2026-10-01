/** shopee.js — Shopee Catalog CRUD & Google Sheets Sync */
'use strict';

let _shopeeProducts = [];

async function loadShopee() {
  const tbody = document.getElementById('shopee-table');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:36px"><span class="spinner"></span><span style="color:var(--text-muted);margin-left:8px">Đang tải Shopee Catalog...</span></td></tr>`;
  try {
    const d = await fetchJSON('/admin/shopee/catalog');
    _shopeeProducts = d.products || [];
    const countEl = document.getElementById('shopee-count');
    if (countEl) countEl.textContent = `${d.total || 0} sản phẩm`;

    // Load last sync time
    loadShopeeLastSync();

    if (!_shopeeProducts.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-dim)">Chưa có sản phẩm trong Shopee Catalog. Bấm <b>"Thêm Sản Phẩm"</b> để tạo mới!</td></tr>`;
      refreshIcons();
      return;
    }
    tbody.innerHTML = _shopeeProducts.map((p, i) => `
      <tr>
        <td><span class="badge ${p.brand === 'ZEO' ? 'badge-green' : 'badge-blue'}">${p.brand}</span></td>
        <td style="font-weight:600;color:var(--text-main)">${p.name}</td>
        <td style="font-size:12px;color:var(--text-muted)">${p.variant || '—'}</td>
        <td style="font-weight:700;color:var(--success);font-family:'JetBrains Mono',monospace">${p.price || '—'}</td>
        <td style="font-size:12px;color:var(--warning)">${p.promotion || '—'}</td>
        <td>
          <a href="${p.shopee_url}" target="_blank" rel="noopener" class="btn btn-ghost btn-xs" style="text-decoration:none;display:inline-flex;gap:4px">
            <i data-lucide="external-link"></i>
            <span>Shopee</span>
          </a>
        </td>
        <td style="text-align:right">
          <div style="display:inline-flex;gap:4px;justify-content:flex-end">
            <button class="btn btn-ghost btn-xs" onclick="openEditShopeeModal(${p._idx !== undefined ? p._idx : i})">
              <i data-lucide="edit-3"></i>
            </button>
            <button class="btn btn-danger btn-xs" onclick="deleteShopeeProduct(${p._idx !== undefined ? p._idx : i})">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </td>
      </tr>`).join('');
    refreshIcons();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--danger);padding:24px;text-align:center">Lỗi tải Shopee catalog: ${e.message}</td></tr>`;
  }
}

async function loadShopeeLastSync() {
  const syncEl = document.getElementById('shopee-last-sync');
  if (!syncEl) return;
  try {
    const d = await fetchJSON('/admin/shopee/last-sync');
    if (d.last_sync) {
      syncEl.textContent = `Sync lần cuối: ${timeSince(d.last_sync)}`;
    } else {
      syncEl.textContent = '';
    }
  } catch (_) {}
}

function openAddShopeeModal() {
  document.getElementById('shopee-modal-title').innerHTML = `<i data-lucide="shopping-bag"></i><span>Thêm Sản Phẩm Shopee Mới</span>`;
  document.getElementById('shopee-edit-idx').value = '-1';
  document.getElementById('shopee-form-brand').value = 'ZEO';
  document.getElementById('shopee-form-name').value = '';
  document.getElementById('shopee-form-variant').value = '';
  document.getElementById('shopee-form-price').value = '';
  document.getElementById('shopee-form-promotion').value = '';
  document.getElementById('shopee-form-url').value = '';
  document.getElementById('shopee-form-keywords').value = '';
  document.getElementById('shopee-modal').classList.add('open');
  refreshIcons();
}

function openEditShopeeModal(idx) {
  const p = _shopeeProducts.find(item => (item._idx !== undefined ? item._idx : -1) === idx) || _shopeeProducts[idx];
  if (!p) return;

  document.getElementById('shopee-modal-title').innerHTML = `<i data-lucide="edit-3"></i><span>Chỉnh Sửa Sản Phẩm — ${p.name}</span>`;
  document.getElementById('shopee-edit-idx').value = idx;
  document.getElementById('shopee-form-brand').value = p.brand || 'ZEO';
  document.getElementById('shopee-form-name').value = p.name || '';
  document.getElementById('shopee-form-variant').value = p.variant || '';
  document.getElementById('shopee-form-price').value = p.price || '';
  document.getElementById('shopee-form-promotion').value = p.promotion || '';
  document.getElementById('shopee-form-url').value = p.shopee_url || '';
  document.getElementById('shopee-form-keywords').value = (p.keywords || []).join(', ');
  document.getElementById('shopee-modal').classList.add('open');
  refreshIcons();
}

function closeShopeeModal() {
  document.getElementById('shopee-modal')?.classList.remove('open');
}

async function saveShopeeProduct() {
  const idx = parseInt(document.getElementById('shopee-edit-idx').value);
  const brand = document.getElementById('shopee-form-brand').value;
  const name = document.getElementById('shopee-form-name').value.trim();
  const variant = document.getElementById('shopee-form-variant').value.trim();
  const price = document.getElementById('shopee-form-price').value.trim();
  const promotion = document.getElementById('shopee-form-promotion').value.trim();
  const url = document.getElementById('shopee-form-url').value.trim();
  const keywordsStr = document.getElementById('shopee-form-keywords').value.trim();
  const keywords = keywordsStr ? keywordsStr.split(',').map(k => k.trim()).filter(Boolean) : [];

  if (!name || !url) {
    toast('Vui lòng nhập đầy đủ Tên sản phẩm và Link Shopee', 'error');
    return;
  }

  const payload = {
    brand,
    name,
    variant,
    price,
    promotion,
    shopee_url: url,
    keywords,
  };

  try {
    if (idx >= 0) {
      await fetchJSON(`/admin/shopee/products/${idx}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      toast(`Đã cập nhật sản phẩm "${name}"!`, 'success');
    } else {
      await fetchJSON('/admin/shopee/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      toast(`Đã thêm sản phẩm "${name}" vào Shopee Catalog!`, 'success');
    }
    closeShopeeModal();
    loadShopee();
  } catch (e) {
    toast('Lỗi lưu sản phẩm: ' + e.message, 'error');
  }
}

async function deleteShopeeProduct(idx) {
  const p = _shopeeProducts.find(item => (item._idx !== undefined ? item._idx : -1) === idx) || _shopeeProducts[idx];
  const name = p?.name || 'sản phẩm này';
  if (!confirm(`Xác nhận xóa sản phẩm "${name}" khỏi Shopee Catalog?`)) return;

  try {
    await fetchJSON(`/admin/shopee/products/${idx}`, { method: 'DELETE' });
    toast(`Đã xóa "${name}"!`, 'success');
    loadShopee();
  } catch (e) {
    toast('Lỗi xóa sản phẩm: ' + e.message, 'error');
  }
}

async function syncShopeeSheetNow() {
  openGoogleSheetHub('shopee');
}

function openGoogleSheetHub(target = 'shopee') {
  const modal = document.getElementById('google-sheet-hub-modal');
  if (!modal) return;
  const targetSelect = document.getElementById('hub-sheet-target');
  if (targetSelect) targetSelect.value = target;

  const urlInput = document.getElementById('hub-sheet-url');
  if (urlInput && !urlInput.value) {
    urlInput.value = '';
  }
  modal.classList.add('open');
  refreshIcons();
}

function closeGoogleSheetHub() {
  document.getElementById('google-sheet-hub-modal')?.classList.remove('open');
}

function switchHubMethod(method) {
  const btnUrl = document.getElementById('hub-tab-btn-url');
  const btnFile = document.getElementById('hub-tab-btn-file');
  const secUrl = document.getElementById('hub-method-url');
  const secFile = document.getElementById('hub-method-file');

  if (method === 'url') {
    btnUrl?.classList.add('active');
    btnFile?.classList.remove('active');
    if (secUrl) secUrl.style.display = 'block';
    if (secFile) secFile.style.display = 'none';
  } else {
    btnFile?.classList.add('active');
    btnUrl?.classList.remove('active');
    if (secFile) secFile.style.display = 'block';
    if (secUrl) secUrl.style.display = 'none';
  }
}

async function fetchSheetTabsList() {
  const url = document.getElementById('hub-sheet-url')?.value.trim();
  const apiKey = document.getElementById('hub-sheet-key')?.value.trim();
  const select = document.getElementById('hub-sheet-tab-select');
  const btn = document.getElementById('btn-fetch-tabs');

  if (!url) {
    toast('Vui lòng dán link Google Sheet trước', 'error');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> <span>Đang tải Tab...</span>';
  }

  try {
    const res = await fetchJSON('/admin/sheets/get-tabs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet_url: url, api_key: apiKey || null })
    });

    if (res.success && Array.isArray(res.tabs)) {
      if (select) {
        select.innerHTML = res.tabs.map(t => `<option value="${escapeHtml(t.title)}">${escapeHtml(t.title)}</option>`).join('');
      }
      toast(`Đã tải thành công ${res.total_tabs} Tab từ Google Sheet!`, 'success');
    } else {
      toast('Không tìm thấy tab: ' + (res.message || 'Lỗi không xác định'), 'error');
    }
  } catch (err) {
    toast('Lỗi tải danh sách tab: ' + err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="list"></i> <span>Tải Danh Sách Tab</span>';
      refreshIcons();
    }
  }
}

let _previewSheetRows = [];

async function previewGoogleSheet() {
  const url = document.getElementById('hub-sheet-url')?.value.trim();
  const apiKey = document.getElementById('hub-sheet-key')?.value.trim();
  const sheetName = document.getElementById('hub-sheet-tab-select')?.value || '';
  const previewWrap = document.getElementById('hub-preview-area');
  const previewTable = document.getElementById('hub-preview-table');
  const previewCount = document.getElementById('hub-preview-count');
  const btnSync = document.getElementById('btn-hub-sync');

  if (!url) {
    toast('Vui lòng nhập link Google Sheet', 'error');
    return;
  }

  if (previewWrap) previewWrap.style.display = 'block';
  if (previewTable) previewTable.innerHTML = '<tr><td style="padding:20px;text-align:center"><span class="spinner"></span> Đang nạp dữ liệu bảng tính...</td></tr>';

  try {
    const res = await fetchJSON('/admin/sheets/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet_url: url, sheet_name: sheetName || null, api_key: apiKey || null, max_rows: 30 })
    });

    if (res.success && res.columns && res.columns.length) {
      _previewSheetRows = res.rows || [];
      if (previewCount) previewCount.textContent = `Đã đọc thành công ${res.total_rows} dòng (${res.preview_count} dòng xem trước)`;
      
      let thead = `<tr>${res.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
      let tbody = _previewSheetRows.map(r => `
        <tr>${res.columns.map(c => `<td>${escapeHtml(r[c] || '')}</td>`).join('')}</tr>
      `).join('');

      if (previewTable) previewTable.innerHTML = `<table class="sheet-preview-table"><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
      if (btnSync) btnSync.disabled = false;
      toast(`Đã nạp ${res.total_rows} dòng dữ liệu từ Google Sheet!`, 'success');
    } else {
      if (previewTable) previewTable.innerHTML = `<tr><td style="padding:20px;color:var(--danger)">Không đọc được dữ liệu: ${res.message || 'File rỗng'}</td></tr>`;
    }
  } catch (err) {
    if (previewTable) previewTable.innerHTML = `<tr><td style="padding:20px;color:var(--danger);white-space:pre-wrap;line-height:1.6">${escapeHtml(err.message)}</td></tr>`;
    toast('Lỗi đọc Sheet: ' + err.message, 'error');
  }
}

async function syncGoogleSheetFromHub() {
  const url = document.getElementById('hub-sheet-url')?.value.trim();
  const apiKey = document.getElementById('hub-sheet-key')?.value.trim();
  const sheetName = document.getElementById('hub-sheet-tab-select')?.value || '';
  const target = document.getElementById('hub-sheet-target')?.value || 'shopee';
  const brand = document.getElementById('hub-sheet-brand')?.value || 'zeo';
  const btnSync = document.getElementById('btn-hub-sync');

  if (!url) {
    toast('Vui lòng nhập link Google Sheet', 'error');
    return;
  }

  if (btnSync) {
    btnSync.disabled = true;
    btnSync.innerHTML = '<span class="spinner"></span> Đang đồng bộ vào Redis...';
  }

  try {
    const res = await fetchJSON('/admin/sheets/sync-direct', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet_url: url, sheet_name: sheetName || null, target_type: target, brand, api_key: apiKey || null })
    });

    if (res.success) {
      toast(`Đồng bộ thành công ${res.synced_count || 0} mục vào Redis (${target.toUpperCase()})!`, 'success');
      closeGoogleSheetHub();
      if (target === 'shopee') loadShopee();
    } else {
      toast('Đồng bộ thất bại: ' + (res.message || 'Lỗi không xác định'), 'error');
    }
  } catch (err) {
    toast('Lỗi đồng bộ: ' + err.message, 'error');
  } finally {
    if (btnSync) {
      btnSync.disabled = false;
      btnSync.innerHTML = '<i data-lucide="zap"></i><span>Đồng Bộ Vào Redis Ngay</span>';
      refreshIcons();
    }
  }
}

async function uploadCsvDirectFromHub() {
  const fileInput = document.getElementById('hub-file-input');
  const target = document.getElementById('hub-sheet-target')?.value || 'shopee';
  const brand = document.getElementById('hub-sheet-brand')?.value || 'zeo';

  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    toast('Vui lòng chọn file CSV / Excel từ máy tính', 'error');
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);
  formData.append('target_type', target);
  formData.append('brand', brand);

  toast('Đang tải lên và đồng bộ vào Redis...', 'success');

  try {
    const resp = await fetch('/admin/sheets/upload-csv', {
      method: 'POST',
      body: formData,
    });
    const res = await resp.json();
    if (resp.ok && res.success) {
      toast(`Đã nạp thành công ${res.synced_count || 0} mục từ file "${file.name}" vào Redis!`, 'success');
      closeGoogleSheetHub();
      if (target === 'shopee') loadShopee();
    } else {
      toast('Lỗi upload: ' + (res.detail || res.message || 'Thất bại'), 'error');
    }
  } catch (err) {
    toast('Lỗi tải file: ' + err.message, 'error');
  }
}
