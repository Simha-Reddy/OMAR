// filepath: static/csrf_fetch.js
// Global fetch patch to automatically attach CSRF header and same-origin credentials
// Applies to mutating same-origin requests (POST/PUT/PATCH/DELETE)
(function(){
  try {
    if (window.__csrfFetchPatched) return;
    const origFetch = window.fetch;
    const METHODS = new Set(['POST','PUT','PATCH','DELETE']);    function getCsrf(){
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
      try {
        const isReq = (resource && typeof Request !== 'undefined' && resource instanceof Request);
        const url = isReq ? resource.url : String(resource);
        const method = ((init && init.method) || (isReq ? resource.method : 'GET') || 'GET').toUpperCase();
        if (METHODS.has(method) && isSameOrigin(url)){
          const csrf = getCsrf();
          // Build headers, preserving existing
          const existing = isReq ? resource.headers : (init && init.headers);
          const hdrs = toHeaders(existing);
          if (csrf && !hdrs.has('X-CSRF-Token')) hdrs.set('X-CSRF-Token', csrf);
          // Merge back into init to avoid reconstructing Request bodies
          init = init || {};
          init.headers = hdrs;
          if (!('credentials' in (init||{}))){ init.credentials = 'same-origin'; }
          if (!('cache' in (init||{}))){ init.cache = 'no-store'; }
          if (!('referrerPolicy' in (init||{}))){ init.referrerPolicy = 'no-referrer'; }
        }
      } catch(_e) { /* non-fatal */ }
      return origFetch.call(this, resource, init);
    };

    window.__csrfFetchPatched = true;
    try { console.info('[CSRF] fetch() patched for automatic tokens'); } catch(_e){}
  } catch(_e) {
    // If anything goes wrong, keep original fetch
  }
})();
