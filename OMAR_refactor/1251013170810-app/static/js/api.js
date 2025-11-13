// ApiClient: centralizes DFN management and refactor API calls
// This file exposes a global window.Api object for non-module scripts.
// Usage:
//   const dfn = Api.getDFN(); await Api.quick('demographics');

function readDFN() {
  try {
    // priority: URL ?dfn -> sessionStorage -> window
    const u = new URL(window.location.href);
    const qp = u.searchParams.get('dfn');
    if (qp) return qp.trim();
    const ss = sessionStorage.getItem('CURRENT_PATIENT_DFN');
    if (ss) return ss.trim();
    // window global (legacy)
    const g = (window.CURRENT_PATIENT_DFN || '').toString();
    if (g) return g.trim();
  } catch {}
  return '';
}

function writeDFN(dfn) {
  const v = (dfn == null) ? '' : String(dfn).trim();
  try { window.CURRENT_PATIENT_DFN = v; } catch {}
  try { sessionStorage.setItem('CURRENT_PATIENT_DFN', v); } catch {}
  try {
    const url = new URL(window.location.href);
    // Keep ?dfn only on non-workspace pages; workspace manages its own state
    if (!window.__IS_WORKSPACE) {
      if (v) url.searchParams.set('dfn', v); else url.searchParams.delete('dfn');
      window.history.replaceState({}, '', url.toString());
    }
  } catch {}
}

function requireDFN() {
  const d = readDFN();
  if (!d) throw new Error('No patient DFN set');
  return d;
}

// Use global fetch; csrf_fetch.js patches fetch() to include CSRF header automatically.
async function csrfFetch(url, options = {}) { return fetch(url, options); }

function toQuery(params) {
  if (!params) return '';
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return;
    usp.set(k, String(v));
  });
  const s = usp.toString();
  return s ? ('?' + s) : '';
}

function unwrapResult(payload) {
  if (!payload || typeof payload !== 'object') return payload;
  if (Object.prototype.hasOwnProperty.call(payload, 'result') && Object.prototype.hasOwnProperty.call(payload, 'context')) {
    return payload.result;
  }
  return payload;
}

async function quick(domain, params) {
  const dfn = requireDFN();
  const q = toQuery(params);
  const res = await fetch(`/api/patient/${encodeURIComponent(dfn)}/quick/${encodeURIComponent(domain)}${q}`, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const payload = await res.json();
  return unwrapResult(payload);
}

async function list(domain, params) {
  const dfn = requireDFN();
  const q = toQuery(params);
  const res = await fetch(`/api/patient/${encodeURIComponent(dfn)}/list/${encodeURIComponent(domain)}${q}`, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const payload = await res.json();
  return unwrapResult(payload);
}

async function vpr(domain, params) {
  const dfn = requireDFN();
  const q = toQuery(params);
  const res = await fetch(`/api/patient/${encodeURIComponent(dfn)}/vpr/${encodeURIComponent(domain)}${q}`, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const payload = await res.json();
  return unwrapResult(payload);
}

async function ask(query, extra = {}) {
  const body = { query, ...extra };
  try { body.patient = Object.assign({}, body.patient || {}, { DFN: requireDFN() }); } catch {}
  const res = await csrfFetch('/api/query/ask', { method: 'POST', body: JSON.stringify(body) });
  const payload = await res.json();
  return unwrapResult(payload);
}

async function ragResults(query, extra = {}) {
  const body = { query, ...extra };
  try { body.patient = Object.assign({}, body.patient || {}, { DFN: requireDFN() }); } catch {}
  const res = await csrfFetch('/api/query/rag_results', { method: 'POST', body: JSON.stringify(body) });
  try {
    const payload = await res.json();
    return unwrapResult(payload);
  } catch { return { results: [] }; }
}

async function resetQueryHistory(extra = {}) {
  const body = { patient: { DFN: '' }, ...extra };
  try { body.patient = Object.assign({}, body.patient || {}, { DFN: requireDFN() }); } catch {}
  const res = await csrfFetch('/api/query/reset', { method: 'POST', body: JSON.stringify(body) });
  try {
    const payload = await res.json();
    return unwrapResult(payload);
  } catch { return { status: 'error' }; }
}

// Documents helpers
async function documentsSearch(params) {
  const dfn = requireDFN();
  const q = toQuery(params);
  const res = await fetch(`/api/patient/${encodeURIComponent(dfn)}/documents/search${q}`, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const payload = await res.json();
  return unwrapResult(payload);
}

async function documentsTextBatch(ids) {
  const dfn = requireDFN();
  const body = { ids: Array.isArray(ids) ? ids : [] };
  const res = await csrfFetch(`/api/patient/${encodeURIComponent(dfn)}/documents/text-batch`, { method: 'POST', body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const payload = await res.json();
  return unwrapResult(payload);
}

// RAG: embed a specific list of documents for the current patient
async function embedDocuments(ids) {
  // Backward-compat no-op: embedding is handled in-model now
  return { status: 'removed' };
}

const Api = {
  getDFN: readDFN,
  setDFN: writeDFN,
  requireDFN,
  quick,
  list,
  vpr,
  ask,
  ragResults,
  resetQueryHistory,
  csrfFetch,
  documentsSearch,
  documentsTextBatch,
  embedDocuments,
};

try { window.Api = Api; } catch {}
