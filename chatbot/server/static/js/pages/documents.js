/** documents.js — Document list, Upload .md, Import Google Sheet, Sync, Extract FAQ */
'use strict';

async function loadDocuments() {
  const tbody = document.getElementById('documents-table');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:36px"><span class="spinner"></span><span style="color:var(--text-muted);margin-left:8px">Đang tải danh sách tài liệu...</span></td></tr>`;
  try {
    const d = await fetchJSON('/admin/documents');
    if (!d.documents?.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-dim)">Chưa có file tài liệu nào trong thư mục <code>knowledge/</code></td></tr>`;
      refreshIcons();
      return;
    }
    tbody.innerHTML = d.documents.map(doc => `
      <tr>
        <td style="font-weight:600;color:var(--text-main)">
          <div style="display:flex;align-items:center;gap:8px">
            <i data-lucide="file-text" style="width:16px;height:16px;color:#818CF8"></i>
            <span>${doc.name}</span>
          </div>
        </td>
        <td><span class="badge ${doc.brand === 'ZEO' ? 'badge-green' : 'badge-blue'}">${doc.brand}</span></td>
        <td style="font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace">${doc.size_kb} KB</td>
        <td style="font-size:12px;color:var(--text-dim);font-family:'JetBrains Mono',monospace">${doc.modified_at}</td>
        <td style="text-align:right">
          <button class="btn btn-primary btn-xs" onclick="extractFaqFromDoc('${doc.name}', '${doc.brand.toLowerCase()}')">
            <i data-lucide="sparkles"></i>
            <span>Trích xuất FAQ</span>
          </button>
        </td>
      </tr>`).join('');
    refreshIcons();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger);padding:24px;text-align:center">Lỗi tải danh sách tài liệu: ${e.message}</td></tr>`;
  }
}

async function uploadDocument(inputEl) {
  const file = inputEl.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  toast(`Đang tải lên & vector hóa "${file.name}"...`, 'success');
  try {
    const resp = await fetch('/admin/documents/upload', {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) throw new Error(await resp.text());
    const res = await resp.json();
    toast(`${res.message || 'Tải lên thành công!'}`, 'success');
    inputEl.value = '';
    loadDocuments();
  } catch (e) {
    toast('Lỗi tải lên: ' + e.message, 'error');
  }
}

function openImportSheetModal() {
  if (typeof openGoogleSheetHub === 'function') {
    openGoogleSheetHub('faq');
  } else {
    document.getElementById('google-sheet-hub-modal')?.classList.add('open');
    refreshIcons();
  }
}

function closeImportSheetModal() {
  document.getElementById('google-sheet-hub-modal')?.classList.remove('open');
}

async function submitImportSheet() {
  const sheetUrl = document.getElementById('sheet-import-url')?.value?.trim();
  const brand = document.getElementById('sheet-import-brand')?.value || 'zeo';

  if (!sheetUrl) {
    toast('Vui lòng nhập đường dẫn Google Sheets', 'error');
    return;
  }

  const btn = document.getElementById('btn-submit-import-sheet');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> <span>Đang nạp dữ liệu...</span>'; }

  toast('Đang tải và vector hóa dữ liệu từ Google Sheets...', 'success');
  try {
    const res = await fetchJSON('/admin/documents/import-sheet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet_url: sheetUrl, brand: brand }),
    });
    toast(`${res.message}`, 'success');
    closeImportSheetModal();
    loadDocuments();
  } catch (e) {
    toast('Lỗi import Google Sheets: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i data-lucide="download"></i><span>Tiến Hành Import</span>'; refreshIcons(); }
  }
}

async function syncDocuments() {
  toast('Đang đồng bộ và vector hóa toàn bộ tài liệu .md...', 'success');
  try {
    const d = await fetchJSON('/admin/documents/sync', { method: 'POST' });
    toast(`Đã đồng bộ ${d.result?.total_files || 0} tài liệu vào Vector Index!`, 'success');
    loadDocuments();
  } catch (e) { toast('Lỗi đồng bộ: ' + e.message, 'error'); }
}

async function extractFaqFromDoc(docName, brand) {
  toast(`AI đang đọc và trích xuất FAQ từ "${docName}"...`, 'success');
  try {
    const d = await fetchJSON('/admin/documents/extract-faq', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_name: docName, brand }),
    });
    if (d.faqs?.length) {
      alert(`AI đã trích xuất thành công ${d.faqs.length} cặp FAQ từ tài liệu!\n\nVí dụ:\n- Intent: ${d.faqs[0].intent}\n- Câu hỏi: ${d.faqs[0].question_examples}\n- Trả lời: ${d.faqs[0].answer}`);
    } else {
      toast('Không tìm thấy FAQ phù hợp trong tài liệu', 'error');
    }
  } catch (e) { toast('Lỗi trích xuất: ' + e.message, 'error'); }
}
