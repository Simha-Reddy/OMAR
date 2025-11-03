// --- Workspace Loading Stages ---
// Note: Removed documents:initialLoaded auto-trigger. Full chart load is driven by the main orchestrator
// to avoid duplicate calls and race conditions.

// Workspace context flag and fetch de-duplication wrapper
(function(){
    try { window.__IS_WORKSPACE = true; } catch(_e){}
    if (!window.__WSFetchWrapped) {
        const originalFetch = window.fetch.bind(window);
        const inflight = new Map(); // key -> Promise<Response>
        const ttlCache = new Map(); // key -> { expires: number, response: Response }
        const TTL_MS = 1200;
        const isGet = (opts)=> !opts || !opts.method || String(opts.method).toUpperCase()==='GET';
        const isDedupCandidate = (url)=>{
            try{
                const u = (url instanceof URL) ? url : new URL(String(url), window.location.origin);
                const p = u.pathname || '';
                return p === '/get_patient' || p.startsWith('/fhir/orders') || p.startsWith('/quick/');
            }catch(_e){ return false; }
        };
        const keyFor = (url, opts)=>{
            try{
                const u = (url instanceof URL) ? url : new URL(String(url), window.location.origin);
                const dfn = (window.CURRENT_PATIENT_DFN || sessionStorage.getItem('CURRENT_PATIENT_DFN') || '') + '';
                // Normalize search ordering
                const sp = new URLSearchParams(u.search);
                u.search = sp.toString() ? ('?' + sp.toString()) : '';
                return `GET|${u.pathname}${u.search}|dfn=${dfn}`;
            }catch(_e){ return `GET|${String(url)}|dfn=${window.CURRENT_PATIENT_DFN||''}`; }
        };
        function cloneResponse(res){
            try { return res.clone(); } catch(_e){ return res; }
        }
        function putTTL(key, res){
            try { ttlCache.set(key, { expires: Date.now() + TTL_MS, response: cloneResponse(res) }); } catch(_e){}
        }
        function getTTL(key){
            try{
                const ent = ttlCache.get(key);
                if (!ent) return null;
                if (Date.now() > ent.expires) { ttlCache.delete(key); return null; }
                return cloneResponse(ent.response);
            }catch(_e){ return null; }
        }
        function clearCaches(){ try { inflight.clear(); }catch(_e){} try { ttlCache.clear(); }catch(_e){} }
        try { window.addEventListener('PATIENT_SWITCH_START', clearCaches); } catch(_e){}

        window.fetch = async function(url, opts){
            opts = opts || {};
            try{
                if (!isGet(opts)) return originalFetch(url, opts);
                if (!isDedupCandidate(url)) return originalFetch(url, opts);
                // Honor AbortSignal by opting out of dedupe if provided
                if (opts.signal) return originalFetch(url, opts);

                const key = keyFor(url, opts);
                const cached = getTTL(key);
                if (cached) return Promise.resolve(cached);

                if (inflight.has(key)) return inflight.get(key).then(cloneResponse);

                // Inject lightweight instrumentation headers
                const headers = new Headers(opts.headers || {});
                try { if (!headers.has('X-Workspace')) headers.set('X-Workspace','1'); } catch(_e){}
                try { if (!headers.has('X-Caller')) headers.set('X-Caller','workspace'); } catch(_e){}
                const nextOpts = Object.assign({}, opts, { headers });

                const p = originalFetch(url, nextOpts).then(res => { try { putTTL(key, res); }catch(_e){} return res; })
                                                      .finally(() => { try{ inflight.delete(key); }catch(_e){} });
                inflight.set(key, p);
                return p.then(cloneResponse);
            }catch(_e){ return originalFetch(url, opts); }
        };
        try { window.__WSFetchWrapped = true; } catch(_e){}
    }
})();

// PatientContext: single source of truth for patient meta using client-held DFN (no server bootstrap)
(function(){
    if (window.PatientContext) return;
    const state = { dfn: '', value: null, inflight: null, ts: 0 };
    function currentDfn(){ try { return window.CURRENT_PATIENT_DFN || sessionStorage.getItem('CURRENT_PATIENT_DFN') || ''; } catch(_e){ return ''; } }
    function sameDfn(){ return (state.dfn && state.dfn === currentDfn()); }
    function clear(){ state.value=null; state.inflight=null; state.ts=0; state.dfn=currentDfn(); }
    async function fetchMeta(){
        // Do not call legacy /get_patient; rely on client DFN presence
        const dfn = currentDfn();
        return dfn ? { dfn } : null;
    }
    async function get(){
        const dfn = currentDfn();
        if (!dfn) { clear(); return null; }
        if (sameDfn() && state.value && (Date.now()-state.ts) < 3000) return state.value;
        if (state.inflight && sameDfn()) return state.inflight;
        state.dfn = dfn;
        state.inflight = fetchMeta().then(j => { state.value=j; state.ts=Date.now(); return j; })
                                     .finally(()=> { state.inflight=null; });
        return state.inflight;
    }
    function peek(){ return sameDfn()? state.value : null; }
    try { window.PatientContext = { get, peek, clear }; } catch(_e){}
    try { window.addEventListener('PATIENT_SWITCH_START', () => clear()); } catch(_e){}
})();

// Top-level module registry and config
let loadedModules = new Map(); // Track loaded module scripts
const moduleConfig = {
    'Snapshot': 'snapshot.js',
    'To Do': 'todo.js',
    'Documents': 'documents.js',   
    'Hey OMAR': 'heyomar.js',
    'Note': 'note.js',
    'Labs': 'labs.js',
    'Meds': 'meds.js',
    'After Visit Summary': 'after_visit_summary.js',
};
// Helper to get current DFN consistently
function _getCurrentDfn(){
    try {
        // Prefer in-memory, fall back to sessionStorage in case the page was reloaded
        const w = window.CURRENT_PATIENT_DFN;
        if (w !== undefined && w !== null && String(w).trim() !== '') return String(w);
        try {
            const s = (sessionStorage && sessionStorage.getItem) ? sessionStorage.getItem('CURRENT_PATIENT_DFN') : '';
            if (s && String(s).trim() !== '') return String(s);
        } catch(_e){}
        return null;
    } catch(_e){ return null; }
}

// Is a patient selected?
function _isPatientSelected(){
    return !!_getCurrentDfn();
}
// Dynamic module loader (moved to top-level scope for orchestrator)
async function loadModule(moduleName) {
    if (loadedModules.has(moduleName)) {
        return loadedModules.get(moduleName);
    }
    const fileName = moduleConfig[moduleName];
    if (!fileName) {
        console.warn(`No module file configured for ${moduleName}`);
        return null;
    }
    try {
        // Load the module script
    const script = document.createElement('script');
    script.src = `/static/js/workspace/modules/${fileName}`;
        script.async = true;
        console.debug('[Workspace] Loading module script', { moduleName, src: script.src });
        const loadPromise = new Promise((resolve, reject) => {
            script.onload = () => {
                // Check if module registered itself globally
                const moduleInstance = window.WorkspaceModules?.[moduleName];
                if (moduleInstance) {
                    loadedModules.set(moduleName, moduleInstance);
                    console.debug('[Workspace] Module loaded and registered', { moduleName });
                    resolve(moduleInstance);
                } else {
                    reject(new Error(`Module ${moduleName} did not register properly`));
                }
            };
            script.onerror = (e) => {
                console.error('[Workspace] Module script failed to load', { moduleName, error: e });
                reject(e);
            };
        });
        document.head.appendChild(script);
        return await loadPromise;
    } catch(e) {
        console.error('[Workspace] Error loading module', moduleName, e);
        return null;
    }
}

// Helper: wait for a condition to become true
function waitForCondition(checkFn, timeoutMs = 7000, intervalMs = 50) {
    return new Promise(resolve => {
        const start = Date.now();
        const timer = setInterval(() => {
            try {
                if (checkFn()) { clearInterval(timer); resolve(true); return; }
            } catch(_e) { /* swallow */ }
            if (Date.now() - start >= timeoutMs) { clearInterval(timer); resolve(false); }
        }, intervalMs);
    });
}

// --- Strict Sequential Orchestrator ---
let __orchestratorInFlight = false;
let __orchestratorForDfn = null;
// NEW: short per-tab cooldown to avoid immediate duplicate refreshes
let __refreshCooldown = new Map();
// NEW: per-tab in-flight guard to prevent overlapping refreshes
let __refreshInflight = new Map();
// Perf toggle: enable via localStorage.setItem('ws_perf','1') or window.__WS_PERF = true
function __wsPerf(){ try{ return window.__WS_PERF || localStorage.getItem('ws_perf')==='1'; }catch(_e){ return false; } }
// NEW: track last orchestrated DFN/time to dedupe back-to-back runs
let __lastOrchestratedDfn = null;
let __lastOrchestratedAt = 0;
async function orchestrateWorkspaceSequential() {
    const currentDfn = _getCurrentDfn();
    if(__wsPerf()){ console.time && console.time(`WS:orchestrate DFN=${currentDfn}`); performance.mark && performance.mark('ws:orchestrate:start'); }
    console.info && console.info('[Workspace] Orchestrator enter', { dfn: currentDfn, ts: Date.now() });
    if (__orchestratorInFlight && __orchestratorForDfn === currentDfn) {
        console.debug('[Workspace] Orchestrator already running for DFN, skipping duplicate', currentDfn);
        return;
    }
    // Dedup: if we just orchestrated this same DFN very recently, skip this run
    try{
        if (__lastOrchestratedDfn === currentDfn && (Date.now() - __lastOrchestratedAt) < 2000) {
            console.debug('[Workspace] Skipping near-duplicate orchestrate for DFN', currentDfn);
            return;
        }
    }catch(_e){}
    __orchestratorInFlight = true;
    __orchestratorForDfn = currentDfn;
    try {
        // Clear old patient state and UI for a clean start only if we previously orchestrated a different DFN
        if (__lastOrchestratedDfn && __lastOrchestratedDfn !== currentDfn) {
            console.debug('[Workspace] Clearing workspace for new patient', { from: __lastOrchestratedDfn, to: currentDfn });
            clearWorkspaceForNewPatient();
        }

        // Warm-up: load key modules in parallel to remove script load latency
        Promise.all([
            loadModule('Note'),
            loadModule('Snapshot'),
            loadModule('Documents')
        ]).catch(()=>{});

        // Helper to find a tab by name across both panes
        const findTabByName = (name) => {
            const leftBar = document.getElementById('leftTabBar');
            const rightBar = document.getElementById('rightTabBar');
            const byName = (bar) => bar ? Array.from(bar.children || []).find(t => ((t.dataset.moduleName || t.dataset.tabName || '').trim() === name)) : null;
            return byName(leftBar) || byName(rightBar) || null;
        };

        // 1) Kick off Snapshot refresh as early as possible (non-blocking)
        const snapshotTab = findTabByName('Snapshot');
        if (snapshotTab) {
            try {
                if(__wsPerf()){ console.time && console.time('WS:Snapshot refresh'); }
                const pane = snapshotTab.closest('.workspace-pane');
                const contentArea = pane?.querySelector('.tab-content-area');
                const content = contentArea?.querySelector(`[data-tab-id="${snapshotTab.dataset.tabId}"]`);
                const alreadyLoaded = !!(content && content.dataset && content.dataset.moduleLoaded === 'true' && content.dataset.lastDfn === _getCurrentDfn());
                if (!alreadyLoaded) { refreshTab(snapshotTab).finally(()=>{ if(__wsPerf()){ console.timeEnd && console.timeEnd('WS:Snapshot refresh'); } }); }
            } catch(_e) {}
        }

        // 2) Render Note next, but do not block Snapshot
    const noteTab = findTabByName('Note');
    if (noteTab) { try { if(__wsPerf()){ console.time && console.time('WS:Note refresh'); } refreshTab(noteTab).finally(()=>{ if(__wsPerf()){ console.timeEnd && console.timeEnd('WS:Note refresh'); } }); } catch(_e) {} }

        // 3) Fire-and-forget Documents initial render (shows UI immediately)
        const documentsTab = findTabByName('Documents');
        if (documentsTab) { try { refreshTab(documentsTab); } catch(_e) {} }

        // 4) Background: Documents initial indexing once per DFN, then refresh and notify
        (async () => {
            // Wait until DocumentsTab API is present
            const hasInit = await waitForCondition(() => (window.DocumentsTab && typeof window.DocumentsTab.loadInitial === 'function'));
            if (!hasInit) return;
            if (_getCurrentDfn() !== currentDfn) return; // DFN changed
            try {
                window.__DocumentsPromises = window.__DocumentsPromises || { initialByDfn: new Map(), remainingByDfn: new Map() };
            } catch(_e) { window.__DocumentsPromises = { initialByDfn: new Map(), remainingByDfn: new Map() }; }
            const initialMap = window.__DocumentsPromises.initialByDfn;
            if (initialMap.get(currentDfn)) return; // already started for this DFN
            const p = (async () => {
                try { 
                  if (window.WorkspaceDocuments && typeof window.WorkspaceDocuments.loadInitial === 'function') {
                    await window.WorkspaceDocuments.loadInitial();
                  } else if (window.DocumentsTab && typeof window.DocumentsTab.loadInitial === 'function') {
                    await window.DocumentsTab.loadInitial();
                  }
                } catch(e){ console.warn('[Workspace] Documents initial load failed', e); }
                if (_getCurrentDfn() !== currentDfn) return; // DFN changed during load
                try { if (documentsTab) await refreshTab(documentsTab); } catch(_e) {}
                try { window.dispatchEvent(new CustomEvent('documents:initial-indexed', { detail: { dfn: currentDfn, ts: Date.now() } })); } catch(_e) {}
            })();
            initialMap.set(currentDfn, p);
            try { await p; } catch(_e) {}
        })();

        // 5) Queue Orders and other tabs without blocking UX; defer to idle when possible
        const scheduleNonCritical = (fn)=>{
            try{
                if (window.requestIdleCallback) return window.requestIdleCallback(fn, { timeout: 1000 });
            }catch(_e){}
            return setTimeout(fn, 400);
        };
        scheduleNonCritical(() => {
            if (_getCurrentDfn() !== currentDfn) return;
            try {
                // Refresh remaining tabs selectively (non-blocking)
                const leftBar = document.getElementById('leftTabBar');
                const rightBar = document.getElementById('rightTabBar');
                const names = [];
                if (leftBar) names.push(...Array.from(leftBar.children || []).map(t => (t.dataset.moduleName || t.dataset.tabName || '').trim()).filter(Boolean));
                if (rightBar) names.push(...Array.from(rightBar.children || []).map(t => (t.dataset.moduleName || t.dataset.tabName || '').trim()).filter(Boolean));
                const exclude = new Set(['Note','Snapshot','Documents']);
                const seen = new Set();
                const others = names.filter(n => !exclude.has(n) && !seen.has(n) && seen.add(n));
                // Heaviest modules: preload scripts only; render when the user activates
                const heavy = new Set(['Orders','Labs','To Do']);
                // Stagger remaining tab refreshes to idle time to avoid main-thread contention
                const queue = others.map(n => () => {
                    const t = findTabByName(n);
                    if (!t) return;
                    // Always preload script so activation is instant
                    try { loadModule(n); } catch(_e){}
                    // If heavy or not currently active, skip rendering for now
                    const isActive = t.classList && t.classList.contains('active');
                    if (heavy.has(n) || !isActive) return;
                    try { refreshTab(t); } catch(_e){}
                });
                const kick = ()=>{ const fn = queue.shift(); if(!fn) return; fn(); if(queue.length) scheduleNonCritical(kick); };
                scheduleNonCritical(kick);
            } catch(_e) {}

            // 6) Later: Documents remaining load with guard; refresh once done
            const startRemaining = async () => {
                if (_getCurrentDfn() !== currentDfn) return;
                const hasRemain = await waitForCondition(() => (window.DocumentsTab && typeof window.DocumentsTab.loadRemaining === 'function'));
                if (!hasRemain) return;
                if (_getCurrentDfn() !== currentDfn) return;
                try {
                    window.__DocumentsPromises = window.__DocumentsPromises || { initialByDfn: new Map(), remainingByDfn: new Map() };
                } catch(_e) { window.__DocumentsPromises = { initialByDfn: new Map(), remainingByDfn: new Map() }; }
                const remainMap = window.__DocumentsPromises.remainingByDfn;
                if (remainMap.get(currentDfn)) return;
                const p2 = (async () => {
                    try { 
                      if (window.WorkspaceDocuments && typeof window.WorkspaceDocuments.loadRemaining === 'function') {
                        await window.WorkspaceDocuments.loadRemaining();
                      } else if (window.DocumentsTab && typeof window.DocumentsTab.loadRemaining === 'function') {
                        await window.DocumentsTab.loadRemaining();
                      }
                    } catch(e){ console.warn('[Workspace] Documents remaining load failed', e); }
                    if (_getCurrentDfn() !== currentDfn) return;
                    try { if (documentsTab) refreshTab(documentsTab); } catch(_e) {}
                })();
                remainMap.set(currentDfn, p2);
                try { await p2; } catch(_e) {}
            };
            if (window.requestIdleCallback) {
                try { window.requestIdleCallback(() => { startRemaining(); }); } catch(_e) { setTimeout(() => startRemaining(), 600); }
            } else {
                setTimeout(() => startRemaining(), 600);
            }
        });
    } finally {
        __orchestratorInFlight = false;
        // record last orchestrate stamp/dfn
        try { __lastOrchestratedDfn = currentDfn; __lastOrchestratedAt = Date.now(); } catch(_e){}
        console.info && console.info('[Workspace] Orchestrator exit', { dfn: currentDfn, ts: Date.now() });
        if(__wsPerf()){ performance.mark && performance.mark('ws:orchestrate:end'); console.timeEnd && console.timeEnd(`WS:orchestrate DFN=${currentDfn}`); performance.measure && performance.measure('ws:orchestrate', 'ws:orchestrate:start', 'ws:orchestrate:end'); }
    }
}

function clearWorkspaceForNewPatient() {
    // Clear tab content, reset loaded state, remove old data
    const allTabs = document.querySelectorAll('.tab-content-area [data-tab-id]');
    allTabs.forEach(tab => {
        console.debug('[Workspace] clearWorkspaceForNewPatient: clearing tab', { tabId: tab.dataset.tabId, lastDfn: tab.dataset.lastDfn });
        tab.innerHTML = '';
        tab.removeAttribute('data-module-loaded');
        tab.removeAttribute('data-last-dfn');
    });
    // Optionally clear any global state, caches, etc.
}
// NEW: refresh a tab's module (prefer module.refresh, else re-render)
async function refreshTab(tab){
    if(!tab) return;
    const perfOn = __wsPerf();
    const tabName = (tab.dataset.moduleName || tab.dataset.tabName || '');
    // Guard against overlapping refreshes for the same tab
    try {
        const tabIdGuard = tab.dataset.tabId;
        if (tabIdGuard && __refreshInflight.get(tabIdGuard)) {
            console.debug && console.debug('[Workspace] Skipping refresh (in-flight)', { tabId: tabIdGuard, tabName });
            return;
        }
        if (tabIdGuard) __refreshInflight.set(tabIdGuard, true);
    } catch(_e){}
    const tStart = (perfOn && performance && performance.now) ? performance.now() : 0;
    // Cooldown: skip if same tab was refreshed very recently
    try {
        const now = Date.now();
        const last = __refreshCooldown.get(tab.dataset.tabId) || 0;
        if (now - last < 600) { console.debug('[Workspace] Skipping refresh (cooldown)', { tabId: tab.dataset.tabId }); return; }
        __refreshCooldown.set(tab.dataset.tabId, now);
    } catch(_e){}
    const pane = tab.closest('.workspace-pane');
    const contentArea = pane?.querySelector('.tab-content-area');
    const tabId = tab.dataset.tabId;
    const content = contentArea?.querySelector(`[data-tab-id="${tabId}"]`);
    const body = content?.querySelector('.tab-content-body') || content;
    const moduleKey = tab.dataset.moduleName || tab.dataset.tabName;
    if(!content || !moduleKey) {
        console.warn('[Workspace] refreshTab: No content or moduleKey for tab', tab);
        return;
    }
    try{
        console.log('[Workspace] refreshTab called for:', moduleKey, { tabId, ts: Date.now(), alreadyLoaded: content.dataset.moduleLoaded, lastDfn: content.dataset.lastDfn });
        const module = await loadModule(moduleKey);
        if(!module){ 
            console.warn('[Workspace] refreshTab: No module loaded for', moduleKey);
            return; 
        }
        const currentDfn = _getCurrentDfn();
        const lastDfn = content.dataset.lastDfn || '';
        const alreadyLoaded = content.dataset.moduleLoaded === 'true';
        const canSoftRefresh = alreadyLoaded && lastDfn === currentDfn && (typeof module.refreshSoft === 'function' || typeof module.refresh === 'function');
        const prefersPreserve = !!module.preserveOnRefresh;
        if (canSoftRefresh && prefersPreserve) {
            console.debug('[Workspace] Soft refresh for module', { moduleKey, tabId });
            try {
                if (typeof module.refreshSoft === 'function') {
                    await module.refreshSoft();
                } else if (typeof module.refresh === 'function') {
                    await module.refresh();
                }
                content.dataset.moduleLoaded = 'true';
                content.dataset.lastDfn = currentDfn;
                return;
            } catch(e){ console.warn('[Workspace] Soft refresh failed, falling back to hard render', e); }
        }
        console.debug('[Workspace] Hard render path; clearing body', { moduleKey, tabId });
        body.innerHTML = `<div class="module-loading"><h3>${tab.dataset.tabName}</h3><p>Loading ${tab.dataset.tabName} module...</p>`;
        try { delete content.dataset.moduleLoaded; } catch(_e){ content.removeAttribute('data-module-loaded'); }
        // Require a patient for all modules except After Visit Summary
        if(!_isPatientSelected() && moduleKey !== 'After Visit Summary'){
            body.innerHTML = `<div class="module-loading"><h3>${tab.dataset.tabName}</h3><p>Select a patient to load this tab.</p>`;
            return;
        }
        let extraOptions = {};
        if (tab.dataset.moduleOptions) { try { extraOptions = JSON.parse(tab.dataset.moduleOptions); } catch(_e){} }
        const t0 = (perfOn && performance.now)? performance.now() : 0;
        await module.render(body, Object.assign({ pane: pane.id }, extraOptions));
        if(perfOn && performance.now){ const dt = (performance.now()-t0).toFixed(0); console.log(`WS:render ${moduleKey} took ${dt}ms`); }
        content.dataset.moduleLoaded = 'true';
        content.dataset.lastDfn = _getCurrentDfn();
    }catch(e){ console.warn('Refresh failed', e); }
    finally{
        // Clear in-flight guard
        try { const tabIdGuard = tab.dataset.tabId; if (tabIdGuard) __refreshInflight.delete(tabIdGuard); } catch(_e){}
        if (perfOn && performance && performance.now) {
            try { const dt = (performance.now() - tStart).toFixed(3); console.log(`WS:refresh ${tabName}: ${dt} ms`); } catch(_e){}
        }
    }
}
// Helper: Refresh tabs by name (used by orchestrator)
function refreshTabsByName(tabNames) {
    if (!Array.isArray(tabNames)) return;
    const leftBar = document.getElementById('leftTabBar');
    const rightBar = document.getElementById('rightTabBar');
    const allTabs = [];
    if (leftBar) allTabs.push(...Array.from(leftBar.children || []));
    if (rightBar) allTabs.push(...Array.from(rightBar.children || []));
    for (const tab of allTabs) {
        const nm = (tab.dataset.moduleName || tab.dataset.tabName || '').trim();
        if (tabNames.includes(nm)) {
            console.log('[Workspace] Refreshing tab:', nm, tab);
            refreshTab(tab);
        }
    }
}

// Removed staged patient loading entry points and full-chart scaffolding
try { window.loadFullChartForPatient = undefined; } catch(_e) {}

// Workspace pane resizing functionality
(function() {
    const container = document.querySelector('.workspace-container');
    const divider = document.getElementById('workspaceDivider');
    const leftPane = document.getElementById('leftPane');
    const rightPane = document.getElementById('rightPane');
    
    let isDragging = false;
    let startX = 0;
    let startLeftWidth = 0;

    divider.addEventListener('mousedown', function(e) {
        isDragging = true;
        startX = e.clientX;
        startLeftWidth = leftPane.offsetWidth;
        container.classList.add('dragging');
        
        // Prevent text selection
        e.preventDefault();
        
        // Add global mouse move and up listeners
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    });

    function handleMouseMove(e) {
        if (!isDragging) return;
        
        const deltaX = e.clientX - startX;
        const containerWidth = container.offsetWidth;
        const newLeftWidth = startLeftWidth + deltaX;
        
        // Calculate percentage and apply constraints
        let leftPercentage = (newLeftWidth / containerWidth) * 100;
        
        // Constrain between 20% and 80%
        leftPercentage = Math.max(20, Math.min(80, leftPercentage));
        
        // Apply the new widths
        leftPane.style.flex = `0 0 ${leftPercentage}%`;
        
        e.preventDefault();
    }

    function handleMouseUp() {
        if (isDragging) {
            isDragging = false;
            container.classList.remove('dragging');
            
            // Remove global listeners
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        }
    }

    // Handle touch events for mobile support
    divider.addEventListener('touchstart', function(e) {
        isDragging = true;
        startX = e.touches[0].clientX;
        startLeftWidth = leftPane.offsetWidth;
        container.classList.add('dragging');
        
        e.preventDefault();
        
        document.addEventListener('touchmove', handleTouchMove, { passive: false });
        document.addEventListener('touchend', handleTouchEnd);
    });

    function handleTouchMove(e) {
        if (!isDragging) return;
        
        const deltaX = e.touches[0].clientX - startX;
        const containerWidth = container.offsetWidth;
        const newLeftWidth = startLeftWidth + deltaX;
        
        let leftPercentage = (newLeftWidth / containerWidth) * 100;
        leftPercentage = Math.max(20, Math.min(80, leftPercentage));
        
        leftPane.style.flex = `0 0 ${leftPercentage}%`;
        
        e.preventDefault();
    }

    function handleTouchEnd() {
        if (isDragging) {
            isDragging = false;
            container.classList.remove('dragging');
            
            document.removeEventListener('touchmove', handleTouchMove);
            document.removeEventListener('touchend', handleTouchEnd);
        }
    }
})();

// Tab Management System
(function() {    
    // Default tabs and order per request:
    // Left: Snapshot, Hey OMAR, Documents, Labs, Meds
    // Right: Note, After Visit Summary, To Do
    const initialTabs = [
        'Snapshot', 'Hey OMAR', 'Documents', 'Labs', 'Meds',
        'Note', 'After Visit Summary', 'To Do'
    ];

    let tabIdCounter = 0;
    let draggedTab = null;
    
    // Floating tabs functionality
    let floatingTabs = new Map(); // Track floating tab windows
    let isDraggingToFloat = false;
    let dragStartPos = { x: 0, y: 0 };
    let floatingTabCounter = 0;

    // =============================
    // Persistence: save/load layout
    // =============================
    function buildLayoutStorageKey(){
        let user = '';
        try { user = window.CURRENT_USER_ID || window.CURRENT_USERNAME || window.USERNAME || ''; } catch(_e){}
        const parts = ['workspaceLayout', user || 'anon'];
        return parts.join('::');
    }

    // New: stable userKey for server-side mirroring (matches server override semantics)
    function buildUserKey(){
        try {
            const u = window.CURRENT_USER_ID || window.CURRENT_USERNAME || window.USERNAME || '';
            return (u && String(u).trim()) ? String(u).trim() : 'anon';
        } catch(_e){ return 'anon'; }
    }

    function collectPane(paneSide){
        const tabBar = document.getElementById(paneSide + 'TabBar');
        if (!tabBar) return { tabs: [], activeIndex: 0 };
        const tabs = Array.from(tabBar.children);
        const activeIndex = Math.max(0, tabs.findIndex(t => t.classList.contains('active')));
        const outTabs = tabs.map(t => {
            let title = '';
            try { title = (t.querySelector('.tab-label')?.textContent || t.dataset.tabName || t.textContent || '').trim(); } catch(_e){ title = t.dataset.tabName || ''; }
            let options = null;
            try { options = t.dataset.moduleOptions ? JSON.parse(t.dataset.moduleOptions) : null; } catch(_e){ options = null; }
            return {
                title,
                module: t.dataset.moduleName || t.dataset.tabName || null,
                options,
                deletable: t.dataset.deletable === '1'
            };
        });
        return { tabs: outTabs, activeIndex: activeIndex < 0 ? 0 : activeIndex };
    }

    // Throttling policy: fetch server layout once per session; persist locally during session;
    // post to server only on session end (beforeunload) or explicit reset.
    let __serverLayoutFetched = false;
    async function _mirrorLayoutToServer(_state, _opts = {}){
        // Deprecated: no server layout mirroring; local-only persistence
        return;
    }

    function saveLayout(){
        try{
            const state = {
                left: collectPane('left'),
                right: collectPane('right'),
                floating: collectFloatingTabs(),
                ts: Date.now()
            };
            localStorage.setItem(buildLayoutStorageKey(), JSON.stringify(state));
            // Do not mirror to server on every change; we'll finalize on exit/reset
        }catch(e){ console.warn('Workspace saveLayout failed', e); }
    }

    function collectFloatingTabs(){
        const floating = [];
        floatingTabs.forEach((data, id) => {
            const window = data.window;
            if (window) {
                floating.push({
                    id: id,
                    title: data.tabData.name,
                    module: data.tabData.moduleKey,
                    options: data.tabData.moduleOptions,
                    deletable: data.tabData.deletable,
                    // persist original pane side to allow docking back to the same row
                    pane: data.tabData.originalPane || 'right',
                    position: {
                        left: window.offsetLeft,
                        top: window.offsetTop,
                        width: window.offsetWidth,
                        height: window.offsetHeight
                    }
                });
            }
        });
        return floating;
    }

    let _saveTimer = null;
    function scheduleSave(){
        try { if (_saveTimer) clearTimeout(_saveTimer); } catch(_e){}
        _saveTimer = setTimeout(saveLayout, 250);
    }

    function clearAllTabs(){
        const leftTabBar = document.getElementById('leftTabBar');
        const rightTabBar = document.getElementById('rightTabBar');
        const leftContent = document.getElementById('leftTabContent');
        const rightContent = document.getElementById('rightTabContent');
        if (leftTabBar) leftTabBar.innerHTML = '';
        if (rightTabBar) rightTabBar.innerHTML = '';
        if (leftContent) leftContent.innerHTML = '';
        if (rightContent) rightContent.innerHTML = '';
        
        // Clear floating tabs
        clearAllFloatingTabs();
    }

    function clearAllFloatingTabs() {
        floatingTabs.forEach((data, id) => {
            if (data.window) {
                data.window.remove();
            }
        });
        floatingTabs.clear();
        updateFloatingTabCount();
    }

    // Blank all tab contents for a new patient selection and reset module state
    function blankAllTabsForNewPatient(){
        try {
            // Hide any global overlays (e.g., documents viewer)
            try { const ov = document.getElementById('docViewerOverlay'); if (ov) ov.style.display = 'none'; } catch(_e){}

            // Clear floating tabs content but keep windows
            floatingTabs.forEach((data, id) => {
                const contentArea = data.window.querySelector('.floating-tab-content');
                if (contentArea) {
                    contentArea.innerHTML = '<div class="module-loading"><h3>' + data.tabData.name + '</h3><p>Select a patient to load this tab.</p></div>';
                }
            });

            const sides = ['left','right'];
            for(const side of sides){
                const tabBar = document.getElementById(side + 'TabBar');
                const contentArea = document.getElementById(side + 'TabContent');
                if (!contentArea) continue;
                const contents = Array.from(contentArea.querySelectorAll('.tab-content'));
                contents.forEach(content => {
                    const tabId = content.dataset.tabId;
                    // Attempt to call module.destroy() to cancel any in-flight work
                    try {
                        const tabEl = tabId ? (tabBar?.querySelector(`.tab[data-tab-id="${tabId}"]`) || document.querySelector(`.tab-bar .tab[data-tab-id="${tabId}"]`)) : null;
                        const moduleKey = tabEl ? (tabEl.dataset.moduleName || tabEl.dataset.tabName) : null;
                        if (moduleKey && loadedModules && loadedModules.has(moduleKey)) {
                            const mod = loadedModules.get(moduleKey);
                            if (mod && typeof mod.destroy === 'function') {
                                try { mod.destroy(); } catch(_d){}
                            }
                        }
                    } catch(_e){}

                    // Clear content and mark as not loaded so it will re-render on next activation
                    content.innerHTML = '';
                    try { delete content.dataset.moduleLoaded; } catch(_e){ content.removeAttribute('data-module-loaded'); }
                });
            }
            console.log('[Workspace] Blanked all tabs for new patient');
        } catch(e) {
            console.warn('Blanking tabs failed', e);
        }
    }

    async function _fetchServerLayout(){
        // Deprecated: never fetch layout from server; rely on localStorage only
        return null;
    }

    async function restoreLayoutFromStorage(){
        let raw = null, state = null;
        // Prefer server state if available
        const serverState = __serverLayoutFetched ? null : (await _fetchServerLayout());
        if (serverState && serverState.left && serverState.right) {
            state = serverState;
            __serverLayoutFetched = true;
        } else {
            try { raw = localStorage.getItem(buildLayoutStorageKey()); } catch(_e){ raw = null; }
            try { state = raw ? JSON.parse(raw) : null; } catch(_e){ state = null; }
        }
        if (!state || !state.left || !state.right) return false;

        clearAllTabs();

        function buildPane(side, paneState){
            const items = Array.isArray(paneState.tabs) ? paneState.tabs : [];
            const created = [];
            for (const t of items){
                const title = String(t.title || t.name || 'Untitled');
                const module = t.module || null;
                // Skip deprecated Feedback tab if present in saved layouts
                if ((module && module === 'Feedback') || title === 'Feedback') {
                    continue;
                }
                const options = t.options || null;
                const deletable = !!t.deletable;
                const newTab = createTab(title, side, module, options, deletable);
                created.push(newTab);
            }
            const idx = Math.max(0, Math.min(created.length - 1, Number(paneState.activeIndex || 0)));
            if (created[idx]) activateTab(created[idx]);
            return created.length > 0;
        }

        const leftOk = buildPane('left', state.left);
        const rightOk = buildPane('right', state.right);
        
        // Restore floating tabs
        if (state.floating && Array.isArray(state.floating)) {
            restoreFloatingTabs(state.floating);
        }

        // If both panes ended up empty, fall back to defaults
        if (!leftOk && !rightOk) return false;

        updateTabBarState(document.getElementById('leftTabBar'));
        updateTabBarState(document.getElementById('rightTabBar'));

        // Ensure a save to normalize schema in local storage
        scheduleSave();
        // No server push here; only finalize on exit/reset
        return true;
    }

    // Helper to rehydrate layout for current patient DFN
    async function _rehydrateForCurrentPatient(blankFirst){
        try{
            if (blankFirst) clearAllTabs();
            const ok = await restoreLayoutFromStorage();
            if (!ok && blankFirst) {
                initializeTabs();
            }
            // Ensure persisted under correct DFN
            scheduleSave();
        }catch(_e){}
    }

    // Helper used by event listeners to rehydrate without blanking
    function rehydrate(){
        if (__layoutRestored) _rehydrateForCurrentPatient(false);
    }

    // Expose minimal API
    window.WorkspaceTabs = window.WorkspaceTabs || {};
    window.WorkspaceTabs.saveLayout = saveLayout;
    window.WorkspaceTabs.restoreLayout = restoreLayoutFromStorage;
    // NEW: expose explicit blanking helper so orchestrator can clear modules safely before rehydrate
    window.WorkspaceTabs.blankForNewPatient = blankAllTabsForNewPatient;
    window.WorkspaceTabs.resetLayout = async function(){
        try{
            // Clear local
            try { localStorage.removeItem(buildLayoutStorageKey()); } catch(_e){}
            // No server mirror to clear
            // Reinitialize default tabs
            clearAllTabs();
            initializeTabs();
            // Finalize write of new default layout
            try {
                const state = {
                    left: collectPane('left'),
                    right: collectPane('right'),
                    floating: collectFloatingTabs(),
                    ts: Date.now()
                };
                localStorage.setItem(buildLayoutStorageKey(), JSON.stringify(state));
                await _mirrorLayoutToServer(state, { reason: 'finalize' });
            } catch(_e) {}
        }catch(e){ console.warn('Reset layout failed', e); }
    };

    // Initialize tabs
    function initializeTabs() {
        const leftTabBar = document.getElementById('leftTabBar');
        const rightTabBar = document.getElementById('rightTabBar');

        // Add first 5 tabs to left pane
        initialTabs.slice(0, 5).forEach(tabName => {
            createTab(tabName, 'left');
        });

        // Add remaining tabs to right pane
        initialTabs.slice(5).forEach(tabName => {
            createTab(tabName, 'right');
        });

        // Activate first tab in each pane
        if (leftTabBar.children.length > 0) {
            activateTab(leftTabBar.children[0]);
        }
        if (rightTabBar.children.length > 0) {
            activateTab(rightTabBar.children[0]);
        }
        // Persist the default layout the first time
        scheduleSave();
    }

    // Create a new tab (optionally with explicit module and options)
    function createTab(name, pane, moduleNameOverride = null, moduleOptions = null, deletable = false) {
        const tabId = `tab-${++tabIdCounter}`;
        const tab = document.createElement('div');
        tab.className = 'tab';
        tab.draggable = true;
        tab.dataset.tabId = tabId;
        tab.dataset.tabName = name;
        if (moduleNameOverride) tab.dataset.moduleName = moduleNameOverride;
        if (moduleOptions) {
            try { tab.dataset.moduleOptions = JSON.stringify(moduleOptions); } catch(_e) {}
        }
        if (deletable) tab.dataset.deletable = '1';

        // Label + optional close button
        if (deletable) {
            tab.innerHTML = `<span class="tab-label">${name}</span>
                             <button class="tab-close" title="Close" aria-label="Close">×</button>`;
            const closeBtn = tab.querySelector('.tab-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', (ev)=>{
                    ev.stopPropagation();
                    removeTab(tab);
                });
            }
        } else {
            tab.innerHTML = `<span class="tab-label">${name}</span>`;
        }

        // Add event listeners
        tab.addEventListener('click', () => activateTab(tab));
        tab.addEventListener('dragstart', handleTabDragStart);
        tab.addEventListener('dragend', handleTabDragEnd);
        
        // Add context menu for floating
        tab.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showTabContextMenu(e, tab);
        });

        // Add to appropriate pane
        const tabBar = document.getElementById(pane + 'TabBar');
        tabBar.appendChild(tab);

        // Create content area with body container (no in-tab refresh button)
        const contentArea = document.getElementById(pane + 'TabContent');
        const content = document.createElement('div');
        content.className = 'tab-content';
        content.dataset.tabId = tabId;
        content.innerHTML = `
            <div class="tab-content-body">
                <div class="module-loading">
                    <h3>${name}</h3>
                    <p>Loading ${name} module...</p>
                </div>
            </div>
        `;
        contentArea.appendChild(content);

        updateTabBarState(tabBar);
        // Persist any change
        scheduleSave();
        return tab;
    }

    // Remove a tab
    function removeTab(tab){
        if (!tab) return;
        const pane = tab.closest('.workspace-pane');
        const tabBar = pane?.querySelector('.tab-bar');
        const contentArea = pane?.querySelector('.tab-content-area');
        const tabId = tab.dataset.tabId;
        const content = contentArea?.querySelector(`[data-tab-id="${tabId}"]`);
        const isActive = tab.classList.contains('active');
        // Decide which tab to activate after removal
        let nextToActivate = null;
        if (isActive) {
            nextToActivate = tab.nextElementSibling || tab.previousElementSibling || null;
        }
        // Remove DOM
        if (content) content.remove();
        tab.remove();
        if (tabBar) updateTabBarState(tabBar);
        if (nextToActivate) activateTab(nextToActivate);
        // Persist
        scheduleSave();
    }

    // Activate a tab and load its module
    async function activateTab(tab) {
        const pane = tab.closest('.workspace-pane');
        const tabBar = pane.querySelector('.tab-bar');
        const contentArea = pane.querySelector('.tab-content-area');
        const tabId = tab.dataset.tabId;
        const displayName = tab.dataset.tabName;
        const moduleKey = tab.dataset.moduleName || displayName;
        console.debug('[Workspace] Activating tab', { tabId, displayName, moduleKey });

        // Deactivate all tabs in this pane
        tabBar.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        contentArea.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        // Activate clicked tab
        tab.classList.add('active');
        const content = contentArea.querySelector(`[data-tab-id="${tabId}"]`);
        const body = content?.querySelector('.tab-content-body') || content;
        if (content) {
            content.classList.add('active');

            // Load and render module if not already loaded
            if (!content.dataset.moduleLoaded) {
                const patientSelected = _isPatientSelected();
                if (!patientSelected && moduleKey !== 'After Visit Summary'){
                    const dfn = (function(){ try{ return window.CURRENT_PATIENT_DFN; }catch(_e){ return undefined; } })();
                    console.warn('[Workspace] Blocking module render because no patient selected', { moduleKey, dfn });
                    body.innerHTML = `
                        <h3>${displayName}</h3>
                        <p>Select a patient to load this tab.</p>
                    `;
                } else {
                    try {
                        console.debug('[Workspace] Loading module for render', { moduleKey, patientSelected: !!patientSelected });
                        const module = await loadModule(moduleKey);
                        if (module && typeof module.render === 'function') {
                            // Clear only the body, keep floating controls
                            body.innerHTML = '';
                            let extraOptions = {};
                            if (tab.dataset.moduleOptions) {
                                try { extraOptions = JSON.parse(tab.dataset.moduleOptions); } catch(_e) {}
                            }
                            await module.render(body, Object.assign({ pane: pane.id }, extraOptions));
                            content.dataset.moduleLoaded = 'true';
                            // NEW: record DFN to avoid immediate duplicate refresh
                            try { content.dataset.lastDfn = _getCurrentDfn(); } catch(_e){}
                            console.debug('[Workspace] Module render complete', { moduleKey });
                        } else {
                            // Fallback to placeholder content
                            console.error('[Workspace] Module missing or no render() function', { moduleKey });
                            body.innerHTML = `
                                <h3>${displayName}</h3>
                                <p>Content for ${displayName} module will be loaded here...</p>
                                <div class="module-placeholder">
                                    <p>Module file: <code>/static/js/workspace/modules/${moduleConfig[moduleKey] || 'unknown.js'}</code></p>
                                    <p>Expected interface:</p>
                                    <pre>window.WorkspaceModules = window.WorkspaceModules || {};
window.WorkspaceModules['${moduleKey}'] = {
    render: async function(container, options) {
        // Module rendering logic here
    },
    refresh: function() {
        // Optional refresh method
    }
};</pre>
                                </div>
                            `;
                        }
                    } catch (error) {
                        console.error(`Error loading module ${moduleKey}:`, error);
                        body.innerHTML = `
                            <h3>${displayName}</h3>
                            <div class="module-error">
                                <p>Error loading module: ${error.message}</p>
                                <p>Expected module file: <code>/static/workspace/modules/${moduleConfig[moduleKey]}</code></p>
                            </div>
                        `;
                    }
                }
            } else {
                console.debug('[Workspace] Module already loaded, showing existing content', { moduleKey });
            }
        }
        // Persist active selection
        scheduleSave();
    }

    // Handle tab drag start
    function handleTabDragStart(e) {
        draggedTab = e.target;
        e.target.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', e.target.outerHTML);
        
        // Track initial position for float detection
        dragStartPos.x = e.clientX;
        dragStartPos.y = e.clientY;
        isDraggingToFloat = false;
        
        // Add global drag tracking for floating detection
        document.addEventListener('dragover', handleGlobalDragOver);
    }

    // Global drag over handler to detect floating gesture
    function handleGlobalDragOver(e) {
        if (!draggedTab) return;
        
        const deltaX = Math.abs(e.clientX - dragStartPos.x);
        const deltaY = Math.abs(e.clientY - dragStartPos.y);
        const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
        
        // If dragged far enough (150px) from start position, prepare for floating
        if (distance > 150 && !isDraggingToFloat) {
            isDraggingToFloat = true;
            draggedTab.classList.add('floating-candidate');
            
            // Show floating indicator
            showFloatingIndicator(e.clientX, e.clientY);
        }
        
        if (isDraggingToFloat) {
            updateFloatingIndicator(e.clientX, e.clientY);
        }
    }

    // Handle tab drag end
    function handleTabDragEnd(e) {
        document.removeEventListener('dragover', handleGlobalDragOver);
        hideFloatingIndicator();
        
        e.target.classList.remove('dragging', 'floating-candidate');
        document.querySelectorAll('.tab.drop-target').forEach(tab => {
            tab.classList.remove('drop-target');
        });
        document.querySelectorAll('.tab-bar.drag-over').forEach(bar => {
            bar.classList.remove('drag-over');
        });
        
        // Check if should create floating tab
        if (isDraggingToFloat && draggedTab) {
            e.preventDefault();
            e.stopPropagation();
            createFloatingTab(draggedTab, e.clientX, e.clientY);
        }
        
        draggedTab = null;
        isDraggingToFloat = false;
    }

    // Setup drag and drop for tab bars
    function setupTabBarDragDrop(tabBar) {
        tabBar.addEventListener('dragover', handleTabBarDragOver);
        tabBar.addEventListener('drop', handleTabBarDrop);
        tabBar.addEventListener('dragenter', handleTabBarDragEnter);
        tabBar.addEventListener('dragleave', handleTabBarDragLeave);
    }

    function handleTabBarDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        const tabBar = e.currentTarget;
        const tabs = Array.from(tabBar.querySelectorAll('.tab:not(.dragging)'));
        const nextTab = tabs.find(tab => {
            const rect = tab.getBoundingClientRect();
            return e.clientX < rect.left + rect.width / 2;
        });

        // Clear previous drop targets
        tabs.forEach(tab => tab.classList.remove('drop-target'));

        if (nextTab) {
            nextTab.classList.add('drop-target');
        }
    }

    function handleTabBarDragEnter(e) {
        e.currentTarget.classList.add('drag-over');
    }

    function handleTabBarDragLeave(e) {
        if (!e.currentTarget.contains(e.relatedTarget)) {
            e.currentTarget.classList.remove('drag-over');
        }
    }

    function handleTabBarDrop(e) {
        e.preventDefault();
        const tabBar = e.currentTarget;
        tabBar.classList.remove('drag-over');

        if (!draggedTab) return;

        // Capture properties before removing
        const originalPane = draggedTab.closest('.workspace-pane');
        const originalContentArea = originalPane.querySelector('.tab-content-area');
        const oldTabId = draggedTab.dataset.tabId;
        const tabContent = originalContentArea.querySelector(`[data-tab-id="${oldTabId}"]`);
        const name = draggedTab.dataset.tabName;
        const moduleNameOverride = draggedTab.dataset.moduleName || null;
        let moduleOptions = null;
        try { moduleOptions = draggedTab.dataset.moduleOptions ? JSON.parse(draggedTab.dataset.moduleOptions) : null; } catch(_e) { moduleOptions = null; }
        const deletable = draggedTab.dataset.deletable === '1';

        // Remove original
        draggedTab.remove();

        // Find drop position
        const tabs = Array.from(tabBar.querySelectorAll('.tab:not(.dragging)'));
        const dropTarget = tabs.find(tab => tab.classList.contains('drop-target'));

        // Create new tab in new location
        const newPane = tabBar.closest('.workspace-pane');
        const paneId = newPane.id === 'leftPane' ? 'left' : 'right';
        const newTab = createTab(name, paneId, moduleNameOverride, moduleOptions, deletable);

        // Position the tab
        if (dropTarget) {
            tabBar.insertBefore(newTab, dropTarget);
        }

        // Move content
        if (tabContent) {
            const newContentArea = newPane.querySelector('.tab-content-area');
            tabContent.dataset.tabId = newTab.dataset.tabId;
            newContentArea.appendChild(tabContent);
            // No in-tab refresh control to rebind
        }

        // Update both panes
        updateTabBarState(document.getElementById('leftTabBar'));
        updateTabBarState(document.getElementById('rightTabBar'));

        // Activate the moved tab
        activateTab(newTab);
        // Persist after move
        scheduleSave();
    }

    // Update tab bar state (empty/non-empty)
    function updateTabBarState(tabBar) {
        if (tabBar.children.length === 0) {
            tabBar.classList.add('empty');
        } else {
            tabBar.classList.remove('empty');
        }
    }

    // Public API for floating tabs
    window.WorkspaceTabs = window.WorkspaceTabs || {};
    window.WorkspaceTabs.createFloatingTab = createFloatingTab;
    window.WorkspaceTabs.dockFloatingTab = dockFloatingTab;
    window.WorkspaceTabs.closeFloatingTab = closeFloatingTab;
    window.WorkspaceTabs.getFloatingTabs = function() {
        return Array.from(floatingTabs.keys());
    };

    // Initialize everything when DOM is ready
    let __layoutRestored = false;
    document.addEventListener('DOMContentLoaded', async function() {
        if (!__layoutRestored) {
            const restored = await restoreLayoutFromStorage();
            __layoutRestored = true;
            if (!restored) {
                initializeTabs();
            }
        }
        setupTabBarDragDrop(document.getElementById('leftTabBar'));
        setupTabBarDragDrop(document.getElementById('rightTabBar'));
        
        // Add keyboard shortcuts for floating tabs
        document.addEventListener('keydown', (e) => {
            // Ctrl+Shift+F to create floating tab from active tab
            if (e.ctrlKey && e.shiftKey && e.key === 'F') {
                e.preventDefault();
                const activeTab = document.querySelector('.tab.active');
                if (activeTab) {
                    const rect = activeTab.getBoundingClientRect();
                    createFloatingTab(activeTab, rect.left + rect.width/2, rect.top + rect.height/2);
                }
            }
            // Escape to dock all floating tabs back to the main tab row
            if (e.key === 'Escape' && floatingTabs.size > 0) {
                const keys = Array.from(floatingTabs.keys());
                keys.forEach(id => {
                    try { dockFloatingTab(id); } catch(_e) { try { closeFloatingTab(id, false); } catch(__e) {} }
                });
                scheduleSave();
            }
        });
        
        // Hook reset button if present
        try{
            const btn = document.getElementById('resetLayoutBtn');
            if(btn && !btn._bound){
                btn._bound = true;
                btn.addEventListener('click', async ()=>{
                    const ok = window.confirm ? window.confirm('Reset layout for this patient?') : true;
                    if(!ok) return;
                    await (window.WorkspaceTabs && window.WorkspaceTabs.resetLayout ? window.WorkspaceTabs.resetLayout() : Promise.resolve());
                    try { window.dispatchEvent(new CustomEvent('workspace:layoutChanged', { detail: { reason: 'reset' } })); } catch(_e){}
                });
            }
        }catch(_e){}

        // Single sequential orchestrator on patient load (no preload)
        // Removed extra rehydrate to avoid duplicate renders; orchestrator will clear and refresh appropriately
        window.addEventListener('patient:loaded',   async ()=>{ try{ await updateHeaderFromDemographics(); await orchestrateWorkspaceSequential(); }catch(_e){} });

        // If a patient is already selected on initial load, immediately update header and orchestrate
        try{
            const d = _getCurrentDfn();
            if (d){
                await updateHeaderFromDemographics(d);
                await orchestrateWorkspaceSequential();
            }
        }catch(_e){}
    });

    // Persist on custom layout change events and page unload
    try { window.addEventListener('workspace:layoutChanged', () => scheduleSave()); } catch(_e){}
    try { window.addEventListener('beforeunload', () => {
        try {
            saveLayout();
            const raw = localStorage.getItem(buildLayoutStorageKey());
            const state = raw ? JSON.parse(raw) : null;
            if (state) { _mirrorLayoutToServer(state, { reason: 'finalize', keepalive: true }); }
        } catch(_e){}
    }); } catch(_e){}
    // On patient switch: blank then rehydrate server-saved layout for new DFN (or defaults)
    // On patient switch/context change: blank then rehydrate layout from localStorage only (never refetch from server)
    try { window.addEventListener('workspace:patientSwitched', (e) => {
        if (!__layoutRestored) return;
        if (e && e.detail && e.detail.alreadyRehydrated) {
            console.debug('[Workspace] Skipping layout rehydrate (alreadyRehydrated flag)');
            return;
        }
        _rehydrateForCurrentPatient(true);
    }); } catch(_e){}

    // Floating tab indicator functions
    function showFloatingIndicator(x, y) {
        let indicator = document.getElementById('floating-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'floating-indicator';
            indicator.className = 'floating-indicator';
            indicator.innerHTML = '📌 Release to float';
            document.body.appendChild(indicator);
        }
        indicator.style.display = 'block';
        indicator.style.left = (x + 10) + 'px';
        indicator.style.top = (y - 10) + 'px';
    }

    function updateFloatingIndicator(x, y) {
        const indicator = document.getElementById('floating-indicator');
        if (indicator) {
            indicator.style.left = (x + 10) + 'px';
            indicator.style.top = (y - 10) + 'px';
        }
    }

    function hideFloatingIndicator() {
        const indicator = document.getElementById('floating-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    // Create floating tab window
    function createFloatingTab(tab, x, y) {
        const tabId = tab.dataset.tabId;
        const tabName = tab.dataset.tabName;
        const moduleKey = tab.dataset.moduleName || tabName;
        
        // Get content before removing tab
        const originalPane = tab.closest('.workspace-pane');
        const originalContentArea = originalPane.querySelector('.tab-content-area');
        const tabContent = originalContentArea.querySelector(`[data-tab-id="${tabId}"]`);
        // Determine original pane side for docking later
        const originalPaneSide = originalPane && originalPane.id === 'leftPane' ? 'left' : 'right';
        
        // Create floating window
        const floatingId = `floating-${++floatingTabCounter}`;
        const floatingWindow = document.createElement('div');
        floatingWindow.id = floatingId;
        floatingWindow.className = 'floating-tab-window';
        floatingWindow.innerHTML = `
            <div class="floating-tab-header">
                <span class="floating-tab-title">${tabName}</span>
                <div class="floating-tab-controls">
                    <button class="floating-tab-dock" title="Dock back to workspace">📋</button>
                    <button class="floating-tab-close" title="Close">×</button>
                </div>
            </div>
            <div class="floating-tab-content" id="${floatingId}-content">
                ${tabContent ? tabContent.innerHTML : '<div class="module-loading"><h3>' + tabName + '</h3><p>Loading...</p></div>'}
            </div>
            <div class="floating-tab-resize-handle"></div>
        `;
        
        // Position the window with smart auto-positioning
        const windowWidth = 600;
        const windowHeight = 400;
        const offset = floatingTabs.size * 30; // Cascade offset for multiple windows
        
        let posX = Math.max(0, x - windowWidth / 2) + offset;
        let posY = Math.max(0, y - 30) + offset;
        
        // Keep window within viewport bounds
        const maxX = window.innerWidth - windowWidth;
        const maxY = window.innerHeight - windowHeight;
        posX = Math.min(posX, maxX);
        posY = Math.min(posY, maxY);
        
        floatingWindow.style.left = posX + 'px';
        floatingWindow.style.top = posY + 'px';
        floatingWindow.style.width = windowWidth + 'px';
        floatingWindow.style.height = windowHeight + 'px';
        
        document.body.appendChild(floatingWindow);
        
        // Setup window controls
        setupFloatingTabControls(floatingWindow, tab, tabContent);
        
        // Remove original tab
        if (tabContent) tabContent.remove();
        tab.remove();
        
        // Update tab bar states
        updateTabBarState(document.getElementById('leftTabBar'));
        updateTabBarState(document.getElementById('rightTabBar'));
        
        // Track floating tab
        floatingTabs.set(floatingId, {
            window: floatingWindow,
            tabData: {
                name: tabName,
                moduleKey: moduleKey,
                moduleOptions: tab.dataset.moduleOptions || null,
                deletable: tab.dataset.deletable === '1',
                originalPane: originalPaneSide
            }
        });
        
        // Load module content if needed
        if (!tabContent || !tabContent.dataset.moduleLoaded) {
            loadFloatingTabModule(floatingId, moduleKey);
        }
        
        updateFloatingTabCount();
        scheduleSave();
    }

    // Setup controls for floating tab window
    function setupFloatingTabControls(floatingWindow, originalTab, originalContent) {
        const header = floatingWindow.querySelector('.floating-tab-header');
        const dockBtn = floatingWindow.querySelector('.floating-tab-dock');
        const closeBtn = floatingWindow.querySelector('.floating-tab-close');
        const resizeHandle = floatingWindow.querySelector('.floating-tab-resize-handle');
        
        // Bring window to front when clicked
        floatingWindow.addEventListener('mousedown', () => {
            bringFloatingWindowToFront(floatingWindow);
        });
        
        // Make draggable
        let isDragging = false;
        let dragOffset = { x: 0, y: 0 };
        
        header.addEventListener('mousedown', (e) => {
            if (e.target === dockBtn || e.target === closeBtn) return;
            isDragging = true;
            dragOffset.x = e.clientX - floatingWindow.offsetLeft;
            dragOffset.y = e.clientY - floatingWindow.offsetTop;
            floatingWindow.classList.add('dragging');
            bringFloatingWindowToFront(floatingWindow);
            
            const onMouseMove = (e) => {
                if (!isDragging) return;
                floatingWindow.style.left = (e.clientX - dragOffset.x) + 'px';
                floatingWindow.style.top = (e.clientY - dragOffset.y) + 'px';
            };
            
            const onMouseUp = () => {
                isDragging = false;
                floatingWindow.classList.remove('dragging');
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
        
        // Dock back functionality
        dockBtn.addEventListener('click', () => {
            dockFloatingTab(floatingWindow.id);
        });
        
        // Close functionality
        closeBtn.addEventListener('click', () => {
            // On close, dock the floating tab back to its original pane (or right pane if unknown)
            dockFloatingTab(floatingWindow.id);
        });
        
        // Resize functionality
        let isResizing = false;
        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            bringFloatingWindowToFront(floatingWindow);
            const startX = e.clientX;
            const startY = e.clientY;
            const startWidth = floatingWindow.offsetWidth;
            const startHeight = floatingWindow.offsetHeight;
            
            const onMouseMove = (e) => {
                if (!isResizing) return;
                const width = Math.max(300, startWidth + (e.clientX - startX));
                const height = Math.max(200, startHeight + (e.clientY - startY));
                floatingWindow.style.width = width + 'px';
                floatingWindow.style.height = height + 'px';
            };
            
            const onMouseUp = () => {
                isResizing = false;
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    }
    
    // Bring floating window to front
    function bringFloatingWindowToFront(targetWindow) {
        const allFloatingWindows = document.querySelectorAll('.floating-tab-window');
        let maxZIndex = 1000;
        
        // Find the highest z-index
        allFloatingWindows.forEach(window => {
            const zIndex = parseInt(window.style.zIndex) || 1000;
            maxZIndex = Math.max(maxZIndex, zIndex);
        });
        
        // Bring target window to front
        targetWindow.style.zIndex = maxZIndex + 1;
    }

    // Load module content for floating tab
    async function loadFloatingTabModule(floatingId, moduleKey) {
        const floatingData = floatingTabs.get(floatingId);
        if (!floatingData) return;
        
        const contentArea = document.getElementById(`${floatingId}-content`);
        if (!contentArea) return;
        
        try {
            const module = await loadModule(moduleKey);
            if (module && typeof module.render === 'function') {
                contentArea.innerHTML = '';
                await module.render(contentArea, { pane: 'floating', floatingId });
            }
        } catch (error) {
            console.error(`Error loading floating tab module ${moduleKey}:`, error);
            contentArea.innerHTML = `
                <div class="module-error">
                    <h3>${floatingData.tabData.name}</h3>
                    <p>Error loading module: ${error.message}</p>
                </div>
            `;
        }
    }

    // Dock floating tab back to workspace
    function dockFloatingTab(floatingId, targetPane = null) {
        const floatingData = floatingTabs.get(floatingId);
        if (!floatingData) return;
        
        const { window: floatingWindow, tabData } = floatingData;
        const contentElement = floatingWindow.querySelector('.floating-tab-content');
        
        // Prefer original pane side, fallback to provided target or 'right'
        const paneToUse = targetPane || tabData.originalPane || 'right';
        
        // Create new tab in workspace
        const newTab = createTab(tabData.name, paneToUse, tabData.moduleKey, 
                                 tabData.moduleOptions ? JSON.parse(tabData.moduleOptions) : null, 
                                 tabData.deletable);
        
        // Move content to new tab
        if (contentElement && contentElement.innerHTML.trim()) {
            const newContentArea = document.getElementById(paneToUse + 'TabContent');
            const newContent = newContentArea.querySelector(`[data-tab-id="${newTab.dataset.tabId}"]`);
            if (newContent) {
                const newBody = newContent.querySelector('.tab-content-body');
                if (newBody) {
                    newBody.innerHTML = contentElement.innerHTML;
                    newContent.dataset.moduleLoaded = 'true';
                }
            }
        }
        
        // Close floating window
        closeFloatingTab(floatingId, false);
        
        // Activate the newly docked tab
        activateTab(newTab);
        updateFloatingTabCount();
        scheduleSave();
    }

    // Update floating tab count display
    function updateFloatingTabCount() {
        let countDisplay = document.getElementById('floating-tab-count');
        const count = floatingTabs.size;
        
        if (count > 0) {
            if (!countDisplay) {
                countDisplay = document.createElement('div');
                countDisplay.id = 'floating-tab-count';
                countDisplay.className = 'floating-tab-count';
                document.body.appendChild(countDisplay);
            }
            countDisplay.textContent = `${count} floating tab${count === 1 ? '' : 's'}`;
            countDisplay.style.display = 'block';
        } else if (countDisplay) {
            countDisplay.style.display = 'none';
        }
    }

    // Close floating tab
    function closeFloatingTab(floatingId, updateLayout = true) {
        const floatingData = floatingTabs.get(floatingId);
        if (!floatingData) return;
        
        floatingData.window.remove();
        floatingTabs.delete(floatingId);
        
        updateFloatingTabCount();
        
        if (updateLayout) {
            scheduleSave();
        }
    }

    // Restore floating tabs from saved state
    function restoreFloatingTabs(floatingState) {
        floatingState.forEach(floatingData => {
            // Skip deprecated Feedback tabs if present in saved floating state
            try {
                const m = floatingData && (floatingData.module || floatingData.title);
                if (m === 'Feedback' || floatingData.title === 'Feedback') {
                    return;
                }
            } catch(_e) {}
            try {
                const floatingId = `floating-${++floatingTabCounter}`;
                const floatingWindow = document.createElement('div');
                floatingWindow.id = floatingId;
                floatingWindow.className = 'floating-tab-window';
                floatingWindow.innerHTML = `
                    <div class="floating-tab-header">
                        <span class="floating-tab-title">${floatingData.title}</span>
                        <div class="floating-tab-controls">
                            <button class="floating-tab-dock" title="Dock back to workspace">📋</button>
                            <button class="floating-tab-close" title="Close">×</button>
                        </div>
                    </div>
                    <div class="floating-tab-content" id="${floatingId}-content">
                        <div class="module-loading"><h3>${floatingData.title}</h3><p>Loading...</p></div>
                    </div>
                    <div class="floating-tab-resize-handle"></div>
                `;
                
                // Restore position and size
                if (floatingData.position) {
                    floatingWindow.style.left = floatingData.position.left + 'px';
                    floatingWindow.style.top = floatingData.position.top + 'px';
                    floatingWindow.style.width = floatingData.position.width + 'px';
                    floatingWindow.style.height = floatingData.position.height + 'px';
                } else {
                    // Default position
                    floatingWindow.style.left = '100px';
                    floatingWindow.style.top = '100px';
                    floatingWindow.style.width = '600px';
                    floatingWindow.style.height = '400px';
                }
                
                document.body.appendChild(floatingWindow);
                
                // Create fake tab element for setupFloatingTabControls
                const fakeTab = {
                    dataset: {
                        tabName: floatingData.title,
                        moduleName: floatingData.module,
                        moduleOptions: floatingData.options,
                        deletable: floatingData.deletable ? '1' : '0'
                    }
                };
                
                // Setup window controls
                setupFloatingTabControls(floatingWindow, fakeTab, null);
                
                // Track floating tab
                floatingTabs.set(floatingId, {
                    window: floatingWindow,
                    tabData: {
                        name: floatingData.title,
                        moduleKey: floatingData.module,
                        moduleOptions: floatingData.options,
                        deletable: floatingData.deletable,
                        originalPane: floatingData.pane || 'right'
                    }
                });
                
                // Load module content
                loadFloatingTabModule(floatingId, floatingData.module);
                
            } catch (e) {
                console.warn('Failed to restore floating tab:', floatingData, e);
            }
        });
        updateFloatingTabCount();
    }

    // Context menu for tabs
    function showTabContextMenu(e, tab) {
        // Remove any existing context menu
        const existingMenu = document.getElementById('tab-context-menu');
        if (existingMenu) existingMenu.remove();
        
        const contextMenu = document.createElement('div');
        contextMenu.id = 'tab-context-menu';
        contextMenu.className = 'tab-context-menu';
        contextMenu.innerHTML = `
            <div class="context-menu-item" data-action="float">📌 Float Tab</div>
            <div class="context-menu-item" data-action="duplicate">📋 Duplicate Tab</div>
            ${tab.dataset.deletable === '1' ? '<div class="context-menu-item" data-action="close">❌ Close Tab</div>' : ''}
        `;
        
        // Position the menu
        contextMenu.style.position = 'fixed';
        contextMenu.style.left = e.clientX + 'px';
        contextMenu.style.top = e.clientY + 'px';
        contextMenu.style.zIndex = '10000';
        
        document.body.appendChild(contextMenu);
        
        // Handle menu item clicks
        contextMenu.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            if (action === 'float') {
                const rect = tab.getBoundingClientRect();
                createFloatingTab(tab, e.clientX, e.clientY);
            } else if (action === 'duplicate') {
                const pane = tab.closest('.workspace-pane');
                const paneId = pane.id === 'leftPane' ? 'left' : 'right';
                const newTab = createTab(
                    tab.dataset.tabName + ' (Copy)',
                    paneId,
                    tab.dataset.moduleName,
                    tab.dataset.moduleOptions ? JSON.parse(tab.dataset.moduleOptions) : null,
                    true
                );
                activateTab(newTab);
            } else if (action === 'close') {
                removeTab(tab);
            }
            contextMenu.remove();
        });
        
        // Remove menu on click outside
        const removeMenu = (e) => {
            if (!contextMenu.contains(e.target)) {
                contextMenu.remove();
                document.removeEventListener('click', removeMenu);
            }
        };
        setTimeout(() => document.addEventListener('click', removeMenu), 0);
    }
})();

// Helper to compute age from DOB (supports ISO YYYY-MM-DD, and "MMM DD,YYYY" or "MMM DD, YYYY")
function computeAgeFromDob(dobInput){
    try{
        if (!dobInput) return '';
        let d = null;
        const s = String(dobInput).trim();
        if (/^\d{4}-\d{2}-\d{2}$/.test(s)){
            d = new Date(s + 'T00:00:00Z');
        } else {
            const m = s.toUpperCase().match(/^([A-Z]{3})\s+(\d{1,2}),\s*(\d{4})$/);
            if (m){
                const mons = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
                const mi = mons.indexOf(m[1]);
                if (mi >= 0){ d = new Date(Date.UTC(parseInt(m[3],10), mi, parseInt(m[2],10))); }
            } else {
                const t = new Date(s);
                if (!isNaN(t.getTime())) d = t;
            }
        }
        if (!d || isNaN(d.getTime())) return '';
        const today = new Date();
        let age = today.getFullYear() - (d.getUTCFullYear ? d.getUTCFullYear() : d.getFullYear());
        const mDelta = (today.getMonth()+1) - (((d.getUTCMonth? d.getUTCMonth() : d.getMonth())+1));
        const dayDelta = today.getDate() - ((d.getUTCDate? d.getUTCDate() : d.getDate()));
        if (mDelta < 0 || (mDelta === 0 && dayDelta < 0)) age--;
        return String(age);
    }catch(_e){ return ''; }
}

// Fetch quick demographics and update header span#patientLookupResults to "Name (Age)"
async function updateHeaderFromDemographics(dfnOverride){
    try{
        const dfn = dfnOverride || _getCurrentDfn();
        if (!dfn) return;
        // Use refactor quick demographics endpoint
        const url = `/api/patient/${encodeURIComponent(String(dfn))}/quick/demographics`;
        const r = await fetch(url, { headers: { 'Accept':'application/json', 'X-Workspace':'1', 'X-Caller':'workspace-header' }, cache:'no-store', credentials:'same-origin' });
        if (!r.ok) return;
        const demo = await r.json();
        const name = (demo.Name || demo.name || '').toString();
        const dobIso = (demo.DOB_ISO || demo.dob || '').toString();
        const dobTxt = (demo.DOB || '').toString();
        if (!name) return;
        const age = computeAgeFromDob(dobIso || dobTxt);
        const el = document.getElementById('patientLookupResults');
        if (!el) return;
        const display = age ? `${name} (${age})` : name;
        el.dataset.originalText = display; // store unmasked original
        if (window.demoMasking && window.demoMasking.enabled && typeof window.demoMasking.maskName === 'function'){
            const masked = window.demoMasking.maskName(name);
            el.textContent = age ? `${masked} (${age})` : masked;
        } else {
            el.textContent = display;
        }
    }catch(_e){ /* silent */ }
}
