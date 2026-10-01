/** reports.js — AI Executive Reports */
'use strict';

async function loadReports() {
  const container = document.getElementById('report-container');
  try {
    const d = await fetchJSON('/admin/reports/latest');
    if (!d.has_report || !d.report) {
      container.innerHTML = `
        <div style="text-align:center;padding:48px 20px;color:var(--text-dim)">
          <i data-lucide="file-bar-chart" style="width:44px;height:44px;color:var(--primary);margin-bottom:12px;opacity:0.6"></i>
          <p style="font-size:14px;color:var(--text-main);font-weight:600">Chưa có báo cáo nào được tạo hôm nay</p>
          <p style="font-size:12px;margin-top:4px">Bấm nút <b>"Tạo Báo Cáo AI Hôm Nay"</b> để AI phân tích toàn bộ metrics!</p>
        </div>`;
      refreshIcons();
      return;
    }
    renderReport(d.report);
  } catch (e) {
    container.innerHTML = `<div style="color:var(--danger);padding:24px;text-align:center">Lỗi tải báo cáo: ${e.message}</div>`;
  }
}

function renderReport(r) {
  const container = document.getElementById('report-container');
  const m = r.metrics || {};
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;border-bottom:1px solid var(--border);padding-bottom:16px;flex-wrap:wrap;gap:12px">
      <div>
        <div style="font-size:16px;font-weight:800;color:var(--text-main)">Bản Tin Điều Hành Ngày ${m.date || r.date}</div>
        <div style="font-size:12px;color:var(--text-dim);margin-top:4px">
          Sinh bởi model: <span class="badge badge-purple" style="font-family:'JetBrains Mono',monospace">${r.ai_provider}</span>
          lúc ${new Date(r.generated_at).toLocaleTimeString('vi-VN')}
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <span class="badge badge-blue">${m.total_customers || 0} Khách Hàng</span>
        <span class="badge badge-green">${m.total_leads || 0} Leads SĐT</span>
        <span class="badge badge-yellow">${m.learning_queue_count || 0} Learning Queue</span>
      </div>
    </div>
    <div class="msg-content" style="font-size:14px;line-height:1.8;color:var(--text-main);background:var(--bg-app);padding:24px;border-radius:var(--r-md);border:1px solid var(--border)">
      ${typeof renderMarkdownSimple === 'function' ? renderMarkdownSimple(r.report_markdown) : r.report_markdown.replace(/\n/g, '<br>')}
    </div>
  `;
  refreshIcons();
}

async function generateReport(sendTelegram) {
  const btn = document.getElementById('btn-gen-report');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> <span>Đang phân tích dữ liệu...</span>';
  toast('AI đang quét dữ liệu Redis và viết báo cáo...', 'success');
  try {
    const d = await fetchJSON(`/admin/reports/generate?send_telegram=${sendTelegram}`, { method: 'POST' });
    if (d.success && d.report) {
      renderReport(d.report);
      toast(sendTelegram ? 'Đã tạo báo cáo & gửi qua Telegram!' : 'Đã tạo báo cáo thành công!', 'success');
    }
  } catch (e) { toast('Lỗi tạo báo cáo: ' + e.message, 'error'); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="sparkles"></i><span>Tạo Báo Cáo AI Hôm Nay</span>';
    refreshIcons();
  }
}
