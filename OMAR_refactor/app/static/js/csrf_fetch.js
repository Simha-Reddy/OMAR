// filepath: static/csrf_fetch.js
// Global fetch patch to automatically attach CSRF header and per-tab session metadata
// Applies to all same-origin requests; mutation methods also receive CSRF protection.
(function(){
  try {
    if (window.__csrfFetchPatched) return;
    const origFetch = window.fetch;
    const METHODS = new Set(['POST','PUT','PATCH','DELETE']);
    const TAB_ID_KEY = 'omar:session:client-id';
    const TAB_ORDER_KEY = 'omar:session:order';
    const ORDER_COUNTER_KEY = 'omar:session:order-counter';

    function randomId(){
      try {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
          return window.crypto.randomUUID();
        }
      } catch(_e){}
      return 'tab-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    }

    function ensureTabSessionMeta(){
      const cached = window.__omarSessionMeta;
      if (cached && typeof cached === 'object') return cached;
      let clientId = null;
      try {
        clientId = sessionStorage.getItem(TAB_ID_KEY);
        if (!clientId) {
          clientId = randomId();
          sessionStorage.setItem(TAB_ID_KEY, clientId);
        }
      } catch(_e) {
        clientId = randomId();
      }

      let order = null;
      try {
        const stored = sessionStorage.getItem(TAB_ORDER_KEY);
        const parsed = stored ? parseInt(stored, 10) : NaN;
        if (Number.isFinite(parsed) && parsed > 0) {
          order = parsed;
        }
      } catch(_e){}

      if (order === null) {
        try {
          const counterRaw = localStorage.getItem(ORDER_COUNTER_KEY);
          let counter = counterRaw ? parseInt(counterRaw, 10) : 0;
          if (!Number.isFinite(counter) || counter < 0) counter = 0;
          counter += 1;
          localStorage.setItem(ORDER_COUNTER_KEY, String(counter));
          order = counter;
        } catch(_e) {
          order = Math.max(1, Math.floor(Date.now() % 1_000_000));
        }
        try { sessionStorage.setItem(TAB_ORDER_KEY, String(order)); } catch(_e){}
      }

      const meta = { clientId, order };
      window.__omarSessionMeta = meta;
      return meta;
    }

    function getCsrf(){
      try {
        // Prefer cookie value since it's set by server and matches session
        const cookieValue = document.cookie.split('; ')
            .find(row => row.startsWith('csrf_token='))
            ?.split('=')[1];
        if (cookieValue) return cookieValue;
        
        // Fallback to meta tag
        const el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
      } catch { return ''; }
    }
    function isSameOrigin(url){
      try {
        // If relative URL, treat as same-origin
        if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(url)) return true;
        const u = new URL(url, window.location.href);
        return u.origin === window.location.origin;
      } catch { return false; }
    }
    function toHeaders(obj){
      const h = new Headers();
      if (!obj) return h;
      if (obj instanceof Headers) { obj.forEach((v,k)=>h.append(k,v)); return h; }
      const entries = Array.isArray(obj) ? obj : Object.entries(obj);
      for (const [k,v] of entries) { if (k) h.append(k, v); }
      return h;
    }

    window.fetch = function(resource, init){
      let patchedInit = init;
      try {
        const isReq = (resource && typeof Request !== 'undefined' && resource instanceof Request);
        const url = isReq ? resource.url : String(resource);
        const method = ((init && init.method) || (isReq ? resource.method : 'GET') || 'GET').toUpperCase();
        const sameOrigin = isSameOrigin(url);
        const existing = isReq ? resource.headers : (init && init.headers);
        let headersToSend = null;

        if (sameOrigin){
          const meta = ensureTabSessionMeta();
          if (meta && (meta.clientId || meta.order)){
            headersToSend = toHeaders(existing);
            if (meta.clientId && !headersToSend.has('X-OMAR-Session-Id')) {
              headersToSend.set('X-OMAR-Session-Id', meta.clientId);
            }
            if (meta.order && !headersToSend.has('X-OMAR-Session-Order')) {
              headersToSend.set('X-OMAR-Session-Order', String(meta.order));
            }
          }
        }

        if (sameOrigin && METHODS.has(method)){
          if (!headersToSend) headersToSend = toHeaders(existing);
          const csrf = getCsrf();
          if (csrf && !headersToSend.has('X-CSRF-Token')) headersToSend.set('X-CSRF-Token', csrf);
          patchedInit = init || {};
          patchedInit.headers = headersToSend;
          if (!('credentials' in (patchedInit||{}))){ patchedInit.credentials = 'same-origin'; }
          if (!('cache' in (patchedInit||{}))){ patchedInit.cache = 'no-store'; }
          if (!('referrerPolicy' in (patchedInit||{}))){ patchedInit.referrerPolicy = 'no-referrer'; }
        } else if (headersToSend) {
          patchedInit = init || {};
          patchedInit.headers = headersToSend;
        }
      } catch(_e) { patchedInit = init; }
      return origFetch.call(this, resource, patchedInit);
    };

    window.__csrfFetchPatched = true;
    try { console.info('[CSRF] fetch() patched with automatic tokens and session metadata'); } catch(_e){}
  } catch(_e) {
    // If anything goes wrong, keep original fetch
  }
})();
