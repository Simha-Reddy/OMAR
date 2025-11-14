(function(){
  if (window.UserSettingsClient) return;

  const API_BASE = '/api/user-settings';
  const DEFAULT_CACHE_TTL_MS = 2 * 60 * 1000; // 2 minutes

  function now(){ return Date.now(); }

  function buildFieldsParam(fields){
    if (!fields) return null;
    if (Array.isArray(fields)) {
      const cleaned = fields.map(f => String(f || '').trim()).filter(Boolean);
      return cleaned.length ? cleaned.join(',') : null;
    }
    return String(fields).trim() || null;
  }

  async function requestJson(path, options = {}){
    const opts = Object.assign({
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
      cache: 'no-store'
    }, options || {});
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData) && !opts.headers['Content-Type']) {
      opts.headers = Object.assign({}, opts.headers, { 'Content-Type': 'application/json' });
      opts.body = JSON.stringify(opts.body);
    }
    if (typeof opts.keepalive === 'boolean' && opts.keepalive) {
      opts.keepalive = true;
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
      const txt = await res.text().catch(() => '');
      const err = new Error(`Request failed (${res.status})` + (txt ? `: ${txt}` : ''));
      err.status = res.status;
      throw err;
    }
    const text = await res.text();
    return text ? JSON.parse(text) : {};
  }

  function makeCache(){
    return {
      data: null,
      ts: 0,
      key: null,
      pending: null,
    };
  }

  const promptsCache = makeCache();
  const layoutCache = makeCache();
  let pendingLayoutSave = null;
  let layoutSaveTimer = null;

  function cacheValid(cache, key){
    if (!cache || !cache.data) return false;
    if (cache.key !== key) return false;
    if ((now() - cache.ts) > DEFAULT_CACHE_TTL_MS) return false;
    return true;
  }

  function buildPromptsKey(opts){
    const includeDefaults = opts && opts.includeDefaults !== undefined ? !!opts.includeDefaults : true;
    const fieldsParam = buildFieldsParam(opts && opts.fields);
    return `${includeDefaults ? '1' : '0'}|${fieldsParam || ''}`;
  }

  async function fetchPrompts(opts = {}){
    const includeDefaults = opts.includeDefaults !== undefined ? !!opts.includeDefaults : true;
    const fieldsParam = buildFieldsParam(opts.fields);
    const key = buildPromptsKey(opts);

    if (!opts.forceRefresh && cacheValid(promptsCache, key)) {
      return promptsCache.data;
    }

    if (promptsCache.pending && promptsCache.key === key) {
      return promptsCache.pending;
    }

    const params = new URLSearchParams();
    if (fieldsParam) params.set('fields', fieldsParam);
    if (!includeDefaults) params.set('include_defaults', '0');
    const url = `${API_BASE}/prompts${params.toString() ? `?${params.toString()}` : ''}`;

    const pending = requestJson(url).then(data => {
      promptsCache.data = data;
      promptsCache.ts = now();
      promptsCache.key = key;
      promptsCache.pending = null;
      return data;
    }).catch(err => {
      promptsCache.pending = null;
      throw err;
    });

    promptsCache.pending = pending;
    promptsCache.key = key;
    return pending;
  }

  function invalidatePromptsCache(){
    promptsCache.data = null;
    promptsCache.key = null;
    promptsCache.ts = 0;
    promptsCache.pending = null;
  }

  async function savePrompts(updates){
    const data = await requestJson(`${API_BASE}/prompts`, {
      method: 'PATCH',
      body: updates || {},
    });
    invalidatePromptsCache();
    return data;
  }

  function buildLayoutKey(opts){
    const includeDefaults = opts && opts.includeDefaults !== undefined ? !!opts.includeDefaults : true;
    return includeDefaults ? 'withDefaults' : 'noDefaults';
  }

  async function fetchLayout(opts = {}){
    const includeDefaults = opts.includeDefaults !== undefined ? !!opts.includeDefaults : true;
    const key = buildLayoutKey(opts);

    if (!opts.forceRefresh && cacheValid(layoutCache, key)) {
      return layoutCache.data;
    }

    if (layoutCache.pending && layoutCache.key === key) {
      return layoutCache.pending;
    }

    const params = new URLSearchParams();
    if (!includeDefaults) params.set('include_defaults', '0');
    const url = `${API_BASE}/layout${params.toString() ? `?${params.toString()}` : ''}`;

    const pending = requestJson(url).then(data => {
      layoutCache.data = data;
      layoutCache.ts = now();
      layoutCache.key = key;
      layoutCache.pending = null;
      return data;
    }).catch(err => {
      layoutCache.pending = null;
      throw err;
    });

    layoutCache.pending = pending;
    layoutCache.key = key;
    return pending;
  }

  function invalidateLayoutCache(){
    layoutCache.data = null;
    layoutCache.key = null;
    layoutCache.ts = 0;
    layoutCache.pending = null;
  }

  async function saveLayout(layout, opts = {}){
    const keepalive = !!opts.keepalive;
    const payload = (layout === null || layout === undefined)
      ? { layout: null }
      : { layout: cloneLayout(layout) };
    const data = await requestJson(`${API_BASE}/layout`, {
      method: 'PUT',
      body: payload,
      keepalive,
    });
    invalidateLayoutCache();
    return data;
  }

  function cloneLayout(layout){
    if (layout === null || layout === undefined) return layout;
    try {
      return JSON.parse(JSON.stringify(layout));
    } catch(_e) {
      return layout;
    }
  }

  function queueLayoutSave(layout, opts = {}){
    try {
      pendingLayoutSave = cloneLayout(layout);
      const delay = typeof opts.delay === 'number' ? Math.max(50, opts.delay) : 400;
      if (layoutSaveTimer) {
        clearTimeout(layoutSaveTimer);
      }
      layoutSaveTimer = setTimeout(() => {
        layoutSaveTimer = null;
        if (pendingLayoutSave === undefined) {
          pendingLayoutSave = null;
          return;
        }
        const snapshot = pendingLayoutSave;
        pendingLayoutSave = null;
        saveLayout(snapshot).catch(err => {
          try { console.warn('UserSettingsClient: layout save failed', err); } catch(_e){}
        });
      }, delay);
    } catch(err) {
      try { console.warn('UserSettingsClient: queueLayoutSave error', err); } catch(_e){}
    }
  }

  async function flushLayoutSave(opts = {}){
    if (layoutSaveTimer) {
      clearTimeout(layoutSaveTimer);
      layoutSaveTimer = null;
    }
    if (pendingLayoutSave === null || pendingLayoutSave === undefined) {
      pendingLayoutSave = null;
      return null;
    }
    const snapshot = pendingLayoutSave;
    pendingLayoutSave = null;
    try {
      return await saveLayout(snapshot, opts);
    } catch(err) {
      try { console.warn('UserSettingsClient: flushLayoutSave failed', err); } catch(_e){}
      throw err;
    }
  }

  window.UserSettingsClient = {
    getPrompts: fetchPrompts,
    savePrompts,
    invalidatePromptsCache,
    getLayout: fetchLayout,
    saveLayout,
    invalidateLayoutCache,
    queueLayoutSave,
    flushLayoutSave,
  };
})();
