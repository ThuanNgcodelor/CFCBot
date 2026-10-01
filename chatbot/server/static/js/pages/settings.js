/** settings.js — Load and Save all Settings / API Keys */
'use strict';

async function loadSettings() {
  try {
    const cfg = await fetchJSON('/admin/settings');
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
    // n8n
    set('set-n8n-url', cfg.n8n?.url);
    set('set-n8n-api-key', cfg.n8n?.api_key);
    // Redis
    set('set-redis-host', cfg.redis?.host || '127.0.0.1');
    set('set-redis-port', cfg.redis?.port || 6379);
    set('set-redis-pass', cfg.redis?.password);
    // Ollama
    set('set-ollama-url', cfg.ollama?.base_url || 'http://127.0.0.1:11434');
    set('set-ollama-embed', cfg.ollama?.embed_model || 'bge-m3');
    set('set-ollama-fallback', cfg.ollama?.fallback_embed_model || 'qwen2.5:7b-instruct');
    // AI Providers
    set('set-gemini-key', cfg.ai_providers?.gemini?.api_key);
    set('set-openrouter-key', cfg.ai_providers?.openrouter?.api_key);
    set('set-groq-key', cfg.ai_providers?.groq?.api_key);
    // Telegram
    set('set-telegram-token', cfg.telegram?.bot_token);
    set('set-telegram-chatid', cfg.telegram?.chat_id);
    // RAG
    set('set-rag-high', cfg.rag?.high_confidence_threshold || 0.78);
    set('set-rag-med', cfg.rag?.medium_confidence_threshold || 0.55);
    set('set-rag-topk', cfg.rag?.top_k || 5);
  } catch (e) { toast('Lỗi tải cài đặt: ' + e.message, 'error'); }
}

async function saveSettings() {
  const get = (id) => document.getElementById(id)?.value?.trim() || '';
  const payload = {
    n8n: {
      url: get('set-n8n-url'),
      api_key: get('set-n8n-api-key'),
    },
    redis: {
      host: get('set-redis-host') || '127.0.0.1',
      port: parseInt(get('set-redis-port')) || 6379,
      password: get('set-redis-pass'),
    },
    ollama: {
      base_url: get('set-ollama-url') || 'http://127.0.0.1:11434',
      embed_model: get('set-ollama-embed') || 'bge-m3',
      fallback_embed_model: get('set-ollama-fallback') || 'qwen2.5:7b-instruct',
    },
    ai_providers: {
      preferred_provider: 'gemini',
      gemini: { api_key: get('set-gemini-key'), model: 'gemini-2.0-flash' },
      openrouter: { api_key: get('set-openrouter-key'), model: 'google/gemini-2.0-flash-exp:free' },
      groq: { api_key: get('set-groq-key'), model: 'llama-3.3-70b-versatile' },
    },
    telegram: {
      enabled: true,
      bot_token: get('set-telegram-token'),
      chat_id: get('set-telegram-chatid'),
    },
    rag: {
      high_confidence_threshold: parseFloat(get('set-rag-high')) || 0.78,
      medium_confidence_threshold: parseFloat(get('set-rag-med')) || 0.55,
      top_k: parseInt(get('set-rag-topk')) || 5,
    },
  };
  try {
    await fetchJSON('/admin/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    toast('✅ Đã lưu tất cả cài đặt & API Keys!', 'success');
    loadStatus();
  } catch (e) { toast('Lỗi lưu cài đặt: ' + e.message, 'error'); }
}

// ── Test connections ──────────────────────────────
async function testTelegram() {
  const token = document.getElementById('set-telegram-token')?.value?.trim();
  const chatid = document.getElementById('set-telegram-chatid')?.value?.trim();
  if (!token || !chatid) { toast('Vui lòng nhập Bot Token và Chat ID trước', 'error'); return; }
  toast('Đang gửi tin nhắn thử nghiệm qua Telegram...', 'success');
  try {
    const d = await fetchJSON('/admin/telegram/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: token, chat_id: chatid }),
    });
    d.success ? toast('✅ Đã nhận tin nhắn Telegram thành công!', 'success')
              : toast('❌ Lỗi Telegram: ' + (d.error || 'Sai Token/Chat ID'), 'error');
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}

async function testN8n() {
  toast('Đang thử kết nối n8n...', 'success');
  await saveSettings();
  try {
    const s = await fetchJSON('/admin/status');
    const n8n = s.services?.n8n;
    if (n8n?.status === 'ok') toast(`✅ Kết nối n8n thành công! (${n8n.total_workflows} workflows)`, 'success');
    else if (n8n?.status === 'no_api_key') toast('⚠️ Kết nối được nhưng thiếu API Key!', 'error');
    else toast('❌ Không thể kết nối n8n: ' + (n8n?.detail || 'Lỗi mạng'), 'error');
  } catch (e) { toast('Lỗi test n8n: ' + e.message, 'error'); }
}

async function testRedis() {
  toast('Đang kiểm tra Redis...', 'success');
  await saveSettings();
  try {
    const s = await fetchJSON('/admin/status');
    const redis = s.services?.redis;
    redis?.status === 'ok'
      ? toast(`✅ Kết nối Redis OK (v${redis.version})`, 'success')
      : toast('❌ Lỗi Redis: ' + (redis?.detail || 'Sai host/port/pass'), 'error');
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}

async function testOllama() {
  toast('Đang kiểm tra Ollama...', 'success');
  await saveSettings();
  try {
    const s = await fetchJSON('/admin/status');
    const ol = s.services?.ollama;
    ol?.status === 'ok'
      ? toast(`✅ Ollama OK! (${ol.models.length} models, bge-m3: ${ol.embed_ready ? 'Sẵn sàng' : 'Chưa có'})`, 'success')
      : toast('❌ Lỗi Ollama: ' + (ol?.detail || 'Chưa chạy ollama serve'), 'error');
  } catch (e) { toast('Lỗi: ' + e.message, 'error'); }
}
