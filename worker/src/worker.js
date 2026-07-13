const FALLBACK_BASE = 'https://xiadasy.github.io/site-labor-assistant/';
const ALLOWED_ORIGINS = new Set([
  'https://xiadasy.github.io',
  'https://xiadasy.github.io/site-labor-assistant',
]);

function corsHeaders(request) {
  const origin = request.headers.get('Origin') || '*';
  return {
    'Access-Control-Allow-Origin': origin === 'null' ? '*' : origin,
    'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-File-Name',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function jsonResponse(request, obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      ...corsHeaders(request),
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

function textResponse(request, text, status = 200, type = 'text/plain; charset=utf-8') {
  return new Response(text, {
    status,
    headers: {
      ...corsHeaders(request),
      'Content-Type': type,
      'Cache-Control': 'no-store',
    },
  });
}

async function readState(env, key) {
  const row = await env.DB.prepare('SELECT value FROM state WHERE key = ?').bind(key).first();
  return row ? row.value : null;
}

async function writeState(env, key, value) {
  await env.DB.prepare(
    'INSERT INTO state(key,value,updated_at) VALUES(?,?,datetime(\'now\')) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime(\'now\')'
  ).bind(key, value).run();
}

async function audit(env, action, summary, request) {
  const ua = request.headers.get('User-Agent') || '';
  const ip = request.headers.get('CF-Connecting-IP') || '';
  await env.DB.prepare('INSERT INTO audit_log(action,summary,user_agent,ip,created_at) VALUES(?,?,?,?,datetime(\'now\'))')
    .bind(action, summary || '', ua.slice(0, 200), ip).run();
}

async function fallback(path) {
  return fetch(FALLBACK_BASE + path.replace(/^\//, ''), { cf: { cacheTtl: 0, cacheEverything: false } });
}

function bytesToBase64(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  let out = '';
  for (let i = 0; i < bytes.length; i += 8192) out += String.fromCharCode(...bytes.slice(i, i + 8192));
  return btoa(out);
}

function base64ToBytes(value) {
  const raw = atob(value);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function readCertFromD1(env, key) {
  const meta = await env.DB.prepare('SELECT content_type,size FROM cert_files WHERE key = ?').bind(key).first();
  if (!meta) return null;
  const rows = await env.DB.prepare('SELECT body_base64 FROM cert_file_chunks WHERE key = ? ORDER BY idx ASC').bind(key).all();
  const body = (rows.results || []).map(x => x.body_base64).join('');
  if (!body) return null;
  return { bytes: base64ToBytes(body), contentType: meta.content_type || 'application/octet-stream', size: meta.size };
}

async function writeCertToD1(env, key, bytes, contentType) {
  const body = bytesToBase64(bytes);
  const chunkSize = 60000;
  await env.DB.prepare('DELETE FROM cert_file_chunks WHERE key = ?').bind(key).run();
  await env.DB.prepare('INSERT INTO cert_files(key,content_type,size,created_at) VALUES(?,?,?,datetime(\'now\')) ON CONFLICT(key) DO UPDATE SET content_type=excluded.content_type,size=excluded.size,created_at=datetime(\'now\')')
    .bind(key, contentType || 'application/octet-stream', bytes.byteLength || bytes.length).run();
  for (let i = 0, idx = 0; i < body.length; i += chunkSize, idx++) {
    await env.DB.prepare('INSERT INTO cert_file_chunks(key,idx,body_base64) VALUES(?,?,?)').bind(key, idx, body.slice(i, i + chunkSize)).run();
  }
}

function requireAdmin(request, env) {
  const configured = env.ADMIN_TOKEN && env.ADMIN_TOKEN.length >= 24;
  if (!configured) return { ok: false, status: 500, message: 'ADMIN_TOKEN not configured' };
  const auth = request.headers.get('Authorization') || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (token !== env.ADMIN_TOKEN) return { ok: false, status: 401, message: 'Unauthorized' };
  return { ok: true };
}

function validEnvelope(x) {
  return x && x.version && x.iterations && x.salt && x.iv && x.ciphertext && typeof x.ciphertext === 'string';
}

function validSummary(x) {
  return x && typeof x.records === 'number' && Array.isArray(x.units);
}

async function handleState(request, env) {
  if (request.method === 'GET') {
    const stored = await readState(env, 'encrypted-data');
    if (stored) return textResponse(request, stored, 200, 'application/json; charset=utf-8');
    const r = await fallback('encrypted-data.json');
    return new Response(r.body, { status: r.status, headers: { ...corsHeaders(request), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });
  }
  if (request.method === 'POST') {
    const auth = requireAdmin(request, env);
    if (!auth.ok) return jsonResponse(request, { ok: false, error: auth.message }, auth.status);
    const body = await request.json();
    if (!validEnvelope(body.encryptedData)) return jsonResponse(request, { ok: false, error: 'invalid encryptedData' }, 400);
    if (!validSummary(body.widgetSummary)) return jsonResponse(request, { ok: false, error: 'invalid widgetSummary' }, 400);
    await writeState(env, 'encrypted-data', JSON.stringify(body.encryptedData));
    await writeState(env, 'widget-summary', JSON.stringify(body.widgetSummary));
    await audit(env, 'save-state', JSON.stringify(body.auditSummary || {}).slice(0, 1000), request);
    return jsonResponse(request, { ok: true, savedAt: new Date().toISOString() });
  }
  return jsonResponse(request, { ok: false, error: 'method not allowed' }, 405);
}

async function handleCompanyState(request, env) {
  if (request.method === 'GET') {
    const stored = await readState(env, 'company-encrypted-data');
    if (stored) return textResponse(request, stored, 200, 'application/json; charset=utf-8');
    const r = await fallback('company-encrypted-data.json');
    return new Response(r.body, { status: r.status, headers: { ...corsHeaders(request), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });
  }
  if (request.method === 'POST') {
    const auth = requireAdmin(request, env);
    if (!auth.ok) return jsonResponse(request, { ok: false, error: auth.message }, auth.status);
    const body = await request.json();
    if (!validEnvelope(body.encryptedData)) return jsonResponse(request, { ok: false, error: 'invalid encryptedData' }, 400);
    await writeState(env, 'company-encrypted-data', JSON.stringify(body.encryptedData));
    await audit(env, 'save-company-state', JSON.stringify(body.auditSummary || {}).slice(0, 1000), request);
    return jsonResponse(request, { ok: true, savedAt: new Date().toISOString() });
  }
  return jsonResponse(request, { ok: false, error: 'method not allowed' }, 405);
}

async function handleSummary(request, env) {
  const stored = await readState(env, 'widget-summary');
  if (stored) return textResponse(request, stored, 200, 'application/json; charset=utf-8');
  const r = await fallback('widget-summary.json');
  return new Response(r.body, { status: r.status, headers: { ...corsHeaders(request), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' } });
}

async function handleCert(request, env, path) {
  const name = decodeURIComponent(path.replace(/^\/api\/cert\//, '').replace(/^\/cert-files\//, ''));
  if (!/^[a-f0-9]{24,64}\.bin$/i.test(name)) return jsonResponse(request, { ok: false, error: 'invalid cert name' }, 400);
  const key = `cert-files/${name}`;
  if (request.method === 'GET') {
    if (env.CERT_BUCKET) {
      const obj = await env.CERT_BUCKET.get(key);
      if (obj) return new Response(obj.body, { headers: { ...corsHeaders(request), 'Content-Type': 'application/octet-stream', 'Cache-Control': 'private, max-age=60' } });
    }
    const stored = await readCertFromD1(env, key);
    if (stored) return new Response(stored.bytes, { headers: { ...corsHeaders(request), 'Content-Type': stored.contentType, 'Cache-Control': 'private, max-age=60' } });
    const r = await fallback(key);
    return new Response(r.body, { status: r.status, headers: { ...corsHeaders(request), 'Content-Type': 'application/octet-stream', 'Cache-Control': 'private, max-age=60' } });
  }
  if (request.method === 'PUT') {
    const auth = requireAdmin(request, env);
    if (!auth.ok) return jsonResponse(request, { ok: false, error: auth.message }, auth.status);
    const bytes = await request.arrayBuffer();
    if (bytes.byteLength < 64) return jsonResponse(request, { ok: false, error: 'file too small' }, 400);
    if (bytes.byteLength > 3 * 1024 * 1024 && !env.CERT_BUCKET) return jsonResponse(request, { ok: false, error: 'file too large for D1 fallback; enable R2' }, 400);
    if (env.CERT_BUCKET) await env.CERT_BUCKET.put(key, bytes, { httpMetadata: { contentType: 'application/octet-stream' } });
    else await writeCertToD1(env, key, bytes, 'application/octet-stream');
    await audit(env, 'upload-cert', key, request);
    return jsonResponse(request, { ok: true, path: key, size: bytes.byteLength, storage: env.CERT_BUCKET ? 'r2' : 'd1' });
  }
  return jsonResponse(request, { ok: false, error: 'method not allowed' }, 405);
}

async function handleAudit(request, env) {
  const auth = requireAdmin(request, env);
  if (!auth.ok) return jsonResponse(request, { ok: false, error: auth.message }, auth.status);
  const rows = await env.DB.prepare('SELECT id,action,summary,user_agent,created_at FROM audit_log ORDER BY id DESC LIMIT 100').all();
  return jsonResponse(request, { ok: true, rows: rows.results || [] });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders(request) });
    const url = new URL(request.url);
    const path = url.pathname;
    try {
      if (path === '/api/state' || path === '/encrypted-data.json') return handleState(request, env);
      if (path === '/api/company-state' || path === '/company-encrypted-data.json') return handleCompanyState(request, env);
      if (path === '/api/summary' || path === '/widget-summary.json') return handleSummary(request, env);
      if (path.startsWith('/api/cert/') || path.startsWith('/cert-files/')) return handleCert(request, env, path);
      if (path === '/api/audit') return handleAudit(request, env);
      if (path === '/api/health') return jsonResponse(request, { ok: true, service: 'labor-admin-worker', time: new Date().toISOString() });
      return jsonResponse(request, { ok: false, error: 'not found' }, 404);
    } catch (err) {
      return jsonResponse(request, { ok: false, error: String(err && err.message || err) }, 500);
    }
  }
};
