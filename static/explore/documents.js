import { on, openDocument, EVENTS } from './state.js';

// Explore Documents panel wiring
// Initializes a Tabulator table for FHIR DocumentReferences and wires control buttons.

(function(){
  try { console.log('[Documents] module loaded'); } catch(_e){}
  let table = null;
  // All rows loaded from server, and progressive append state
  let allRows = [];
  let loadedCount = 0;
  const CHUNK_SIZE = 50; // number of rows to append per scroll step
  // Added: generation token to invalidate stale async work after resets/re-inits
  let generation = 0;
  // Track last selected/clicked row for keyboard open
  let lastRowSelected = null;
  // New: ResizeObserver to sync table height with wrapper
  let wrapResizeObserver = null;
  // New: debounce for saving wrapper height
  let saveHeightDebounce = null;

  // Helper: current DFN for cache-busted requests
  function currentDfn(){ try { return window.CURRENT_PATIENT_DFN || null; } catch(_e){ return null; } }

  // Track active fetches for cancellation on reset/reload
  const activeControllers = new Set();
  function withAbortableFetch(input, init){
    const controller = new AbortController();
    activeControllers.add(controller);
    const opts = Object.assign({ cache: 'no-store' }, init || {}, { signal: controller.signal });
    const p = fetch(input, opts).finally(() => { activeControllers.delete(controller); });
    return { fetchPromise: p, controller };
  }
  function cancelAllFetches(){
    try {
      for(const c of Array.from(activeControllers)){
        try { c.abort(); } catch(_e){}
      }
    } finally { activeControllers.clear(); }
  }

  // Note text cache and load state tracking (for viewer/prefetch only)
  const noteCache = new Map(); // doc_id -> { lines: string[], fetchedAt: number }
  const loadState = new Map(); // doc_id -> 'Queued'|'Loading'|'Ready'|'Error' (note text prefetch state)

  // Indexing state (shown in table column)
  const indexState = new Map(); // doc_id -> 'Queued'|'Indexing'|'Indexed'|'Error'
  let indexedCount = 0; // number of docs marked Indexed
  let autoIndexPaused = true; // default: OFF

  // Runner state
  let indexRunnerActive = false;
  let indexRunnerDebounce = null;

  // For note prefetcher
  let prefetchRunning = false;
  let prefetchDebounce = null;

  // New: composed filters state
  let currentKeyword = '';
  // New: multiple keywords for viewer highlighting
  let currentKeywords = [];
  let indexedOnlyFilterOn = false;
  // New: remember last opened doc for re-highlighting on filter/keyword changes
  let lastOpenedDocId = null;
  // New: allow hiding the viewer until a note is opened again
  let viewerClosed = false;
  // ---- Keyword inverted-index state ----
  let readyVersion = 0;               // increments when any doc becomes Ready
  let kwQuery = '';
  let kwDebounce = null;
  let kwHeaderInputDebounce = null;
  let kwSortActive = false;
  let prevSortBeforeKw = null;

  // Helper: enable/disable auto-sort by keyword hits while preserving previous sort
  function ensureKwSort(active){
    if(!table) return;
    try{
      if(active){
        if(!kwSortActive){
          if(typeof table.getSorters === 'function'){
            try { prevSortBeforeKw = table.getSorters(); } catch(_e){ prevSortBeforeKw = null; }
          }
        }
        kwSortActive = true;
        table.setSort([{ column: 'kwHits', dir: 'desc' }]);
      } else {
        kwSortActive = false;
        if(prevSortBeforeKw && Array.isArray(prevSortBeforeKw) && prevSortBeforeKw.length){
          table.setSort(prevSortBeforeKw);
        } else {
          table.setSort([{ column: 'date', dir: 'desc' }]);
        }
        prevSortBeforeKw = null;
      }
    } catch(_e){}
  }

  // === Overlay helpers for in-table viewer ===
  function _overlayRefs(){
    const overlay = document.getElementById('docViewerOverlay');
    const wrap = document.getElementById('documentsTableWrap');
    const container = document.getElementById('documentsTable');
    const header = container ? container.querySelector('.tabulator-header') : null;
    return { overlay, wrap, container, header };
  }
  function positionDocOverlay(){
    const { overlay, header, wrap } = _overlayRefs();
    if(!overlay || !wrap) return;
    const h = header && header.getBoundingClientRect ? Math.round(header.getBoundingClientRect().height) : 0;
    overlay.style.top = (h || 0) + 'px';
  }
  function showDocOverlay(){ const { overlay } = _overlayRefs(); if(overlay){ overlay.style.display=''; positionDocOverlay(); viewerClosed = false; } }
  function hideDocOverlay(){ const { overlay } = _overlayRefs(); if(overlay){ overlay.style.display='none'; viewerClosed = true; } }
  // Recalc overlay on window resize
  try { window.addEventListener('resize', ()=> positionDocOverlay()); } catch(_e){}

  // --- Tabs helpers (Prev/Current/Next) ---
  function _tableActiveRows(){
    if(!table) return [];
    try{ const rows = table.getRows('active'); if(Array.isArray(rows) && rows.length) return rows; }catch(_e){}
    try{ const rows = table.getRows(); if(Array.isArray(rows) && rows.length) return rows; }catch(_e){}
    return [];
  }
  function _currentIndexInActive(){
    const rows = _tableActiveRows();
    if(!rows.length) return { rows: [], index: -1 };
    if(lastOpenedDocId){
      const idx = rows.findIndex(r => (r.getData && r.getData().doc_id) === lastOpenedDocId);
      if(idx >= 0) return { rows, index: idx };
    }
    try{
      const sel = table ? table.getSelectedRows() : [];
      if(sel && sel.length){
        const sid = sel[0].getData && sel[0].getData().doc_id;
        const idx = rows.findIndex(r => (r.getData && r.getData().doc_id) === sid);
        if(idx >= 0) return { rows, index: idx };
      }
    }catch(_e){}
    return { rows, index: rows.length ? 0 : -1 };
  }
  function _fmtLabel(d){
    if(!d) return '';
    const date = _fmtShortDate(d.date);
    const title = (d.title || d.encounter || d.doc_id || '').toString();
    const parts = [];
    if(date) parts.push(date);
    if(title) parts.push(title);
    return parts.join(' — ');
  }
  function _fmtShortDate(input){
    if(!input) return '';
    const s = String(input).trim();
    // Try Date.parse
    let t = Date.parse(s);
    if(!isNaN(t)){
      const d = new Date(t);
      const mm = d.getMonth()+1;
      const dd = d.getDate();
      const yy = String(d.getFullYear()).slice(-2);
      return `${mm}/${dd}/${yy}`;
    }
    // Try to parse YYYY-MM-DD or M/D/YYYY etc.
    let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if(m){
      const mm = Number(m[2]);
      const dd = Number(m[3]);
      const yy = String(Number(m[1])).slice(-2);
      return `${mm}/${dd}/${yy}`;
    }
    m = s.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/);
    if(m){
      const mm = Number(m[1]);
      const dd = Number(m[2]);
      const yyFull = String(m[3]);
      const yy = yyFull.length === 2 ? yyFull : yyFull.slice(-2);
      return `${mm}/${dd}/${yy}`;
    }
    return s; // fallback
  }
  // New: normalize many date strings to a timestamp for sorting/filtering
  function _parseDateMs(val){
    if(val == null) return NaN;
    // numeric timestamp already
    if(typeof val === 'number') return Number.isFinite(val) ? val : NaN;
    // Date object
    if(val instanceof Date) return val.getTime();
    const s = String(val).trim();
    if(!s) return NaN;
    // Fast path: Date.parse
    let t = Date.parse(s);
    if(!Number.isNaN(t)) return t;
    // YYYY-MM-DD[ HH:mm[:ss]]
    let m = s.match(/^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$/);
    if(m){
      const yyyy = Number(m[1]); const mm = Number(m[2])-1; const dd = Number(m[3]);
      const hh = Number(m[4]||0); const mi = Number(m[5]||0); const ss = Number(m[6]||0);
      return new Date(yyyy, mm, dd, hh, mi, ss).getTime();
    }
    // M/D/YYYY or M-D-YYYY [HH:mm]
    m = s.match(/^\s*(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$/);
    if(m){
      let yyyy = String(m[3]); if(yyyy.length===2){ yyyy = '20'+yyyy; }
      const MM = Number(m[1])-1; const DD = Number(m[2]);
      const hh = Number(m[4]||0); const mi = Number(m[5]||0); const ss = Number(m[6]||0);
      return new Date(Number(yyyy), MM, DD, hh, mi, ss).getTime();
    }
    // Year only
    m = s.match(/^\s*(\d{4})\s*$/);
    if(m){ return new Date(Number(m[1]), 0, 1).getTime(); }
    // Fallback NaN
    return NaN;
  }
  function _setTabDisabled(tabEl, disabled){
    if(!tabEl) return;
    if(disabled){ tabEl.setAttribute('data-state','disabled'); }
    else { tabEl.removeAttribute('data-state'); }
  }
  function updateDocTabs(){
    try{
      const prevTab = document.getElementById('docTabPrev');
      const currTab = document.getElementById('docTabCurr');
      const nextTab = document.getElementById('docTabNext');
      const prevLabel = document.getElementById('docTabPrevLabel');
      const currLabel = document.getElementById('docTabCurrLabel');
      const nextLabel = document.getElementById('docTabNextLabel');
      if(!prevTab || !currTab || !nextTab) return; // not on this page
      const { rows, index } = _currentIndexInActive();
      const prevRow = (index > 0) ? rows[index-1] : null;
      const currRow = (index >= 0 && rows[index]) ? rows[index] : null;
      const nextRow = (index >= 0 && index < rows.length-1) ? rows[index+1] : null;
      const prevData = prevRow && prevRow.getData ? prevRow.getData() : null;
      const currData = currRow && currRow.getData ? currRow.getData() : null;
      const nextData = nextRow && nextRow.getData ? nextRow.getData() : null;
      // Labels and dataset doc ids
      if(prevLabel){
        prevLabel.textContent = prevData ? _fmtLabel(prevData) : 'Prev';
        if(prevLabel.dataset) prevLabel.dataset.docId = prevData && prevData.doc_id ? String(prevData.doc_id) : '';
      }
      if(currLabel){
        currLabel.textContent = currData ? _fmtLabel(currData) : 'Current';
        if(currLabel.dataset) currLabel.dataset.docId = currData && currData.doc_id ? String(currData.doc_id) : '';
      }
      if(nextLabel){
        nextLabel.textContent = nextData ? _fmtLabel(nextData) : 'Next';
        if(nextLabel.dataset) nextLabel.dataset.docId = nextData && nextData.doc_id ? String(nextData.doc_id) : '';
      }
      // Enable/disable tabs
      _setTabDisabled(prevTab, !prevData);
      _setTabDisabled(currTab, !currData);
      _setTabDisabled(nextTab, !nextData);
    } catch(_e){
      try { console.warn('[Documents] updateDocTabs error', _e); } catch(__){}
    }
  }

  function _unhideViewerIfClosed(){
    const { overlay } = _overlayRefs();
    if(overlay && viewerClosed){ overlay.style.display=''; viewerClosed = false; }
  }

  // Helper: pick a usable date string from various possible FHIR fields
  function pickDate(dr){
    try{
      const norm = (v)=>{
        if(v == null) return '';
        if(typeof v === 'number'){ return new Date(v).toISOString(); }
        if(typeof v === 'object'){
          // common nested shapes
          if(v.start) return String(v.start);
          if(v.value) return String(v.value);
          if(v.dateTime) return String(v.dateTime);
        }
        return String(v);
      };
      const cand = [];
      // flat fields commonly seen on DocumentReference-like objects
      cand.push(dr.date, dr.created, dr.authored, dr.authoredOn, dr.indexed, dr.lastUpdated, dr.serviceDate, dr.serviceStart, dr.issued, dr.effectiveDateTime, dr.effective);
      // nested fields
      if(dr && dr.period){ cand.push(dr.period.start, dr.period.dateTime); }
      if(dr && dr.meta){ cand.push(dr.meta.lastUpdated); }
      for(const v of cand){ const s = norm(v); if(s) return s; }
    }catch(_e){}
    return '';
  }

  async function fetchFromFhir(){
    const dfn = currentDfn();
    const url = dfn ? `/document_references?dfn=${encodeURIComponent(dfn)}` : '/document_references';
    const { fetchPromise } = withAbortableFetch(url);
    const res = await fetchPromise;
    if(!res.ok) throw new Error('Failed to load FHIR DocumentReferences');
    const data = await res.json();
    const docs = Array.isArray(data.documents) ? data.documents : [];
    if(!docs.length) return [];
    // Map to table shape
    const rows = docs.map(dr=>({
      date: pickDate(dr) || '',
      title: dr.title || dr.type || '',
      author: dr.author || '',
      encounter: dr.encounter || '',
      doc_id: dr.doc_id || '',
      indexed: indexState.get(dr.doc_id || '') || '',
      kwHits: null
    }));
    return rows;
  }

  function updateStatusShowing(){
    const status = document.getElementById('docsStatus');
    if(!status) return;
    const total = allRows.length;
    const showStr = total ? `Showing ${Math.min(loadedCount, total)} of ${total} note(s).` : 'No documents found.';
    const idxStr = total ? `Indexed ${indexedCount}/${total}` : '';
    // Added: keyword-ready count (how many notes have text loaded and are searchable client-side)
    let kwReadyStr = '';
    try{
      if(total){
        let readyCount = 0;
        for(const r of allRows){ const id = r && r.doc_id; if(id && loadState.get(id) === 'Ready') readyCount++; }
        kwReadyStr = `Keyword-ready ${readyCount}/${total}`;
      }
    }catch(_e){}
    // Added: selection count
    let selStr = '';
    try { if(table){ const n = (table.getSelectedRows()||[]).length; if(n>0) selStr = `Selected ${n}`; } } catch(_e){}
    status.textContent = [idxStr, kwReadyStr, showStr, selStr].filter(Boolean).join(' — ');
  }

  function resetIndexedUI(){
    try { indexState.clear(); } catch(_e){}
    indexedCount = 0;
    // Clear per-row UI column
    if(table){
      try{
        const rows = table.getRows();
        for(const r of rows){ r.update({ indexed: '' }); }
      } catch(_e){}
    }
    updateStatusShowing();
  }

  async function seedIndexStateFromServer(){
    // Call GET /explore/index_status to seed indexState and counter
    try{
      const { fetchPromise } = withAbortableFetch('/explore/index_status');
      const res = await fetchPromise;
      if(!res.ok) return;
      const j = await res.json();
      const ids = Array.isArray(j.indexed_ids) ? j.indexed_ids.map(String) : [];
      indexState.clear();
      for(const id of ids){ indexState.set(String(id), 'Indexed'); }
      indexedCount = ids.length;
      // Reflect in current rows if loaded
      if(table){
        const rows = table.getRows();
        for(const r of rows){
          const d = r.getData();
          if(d && d.doc_id && indexState.get(d.doc_id) === 'Indexed'){
            try { r.update({ indexed: 'Indexed' }); } catch(_e){}
          }
        }
      }
      updateStatusShowing();
    } catch(e){ /* ignore seed errors */ }
  }

  function applyIndexStateToRows(rows){
    rows.forEach(r=>{
      const st = indexState.get(r.doc_id || '') || '';
      if(st){ r.indexed = st; }
    });
  }

  function loadMoreIfNeeded(){
    if(!table) return;
    if(loadedCount >= allRows.length) return;
    const next = allRows.slice(loadedCount, loadedCount + CHUNK_SIZE);
    if(next.length){
      applyIndexStateToRows(next);
      table.addData(next);
      loadedCount += next.length;
      updateStatusShowing();
      // Immediately kick off indexing for this newly loaded batch
      try { indexDocsBatchNow(next); } catch(_e){}
    }
  }

  function attachInfiniteScroll(container){
    // Tabulator creates an internal scroll container with class .tabulator-tableholder
    const holder = container.querySelector('.tabulator-tableholder');
    if(!holder) return;
    // Remove previous listener if any
    if(holder._lazyScrollHandler){ holder.removeEventListener('scroll', holder._lazyScrollHandler); }
    holder._lazyScrollHandler = function(){
      const nearBottom = holder.scrollTop + holder.clientHeight >= holder.scrollHeight - 60;
      if(nearBottom){ loadMoreIfNeeded(); }
    };
    holder.addEventListener('scroll', holder._lazyScrollHandler);
  }

  async function fetchDocuments(){
    // Ensure any previous loads are cancelled before starting
    cancelAllFetches();
    const gen = ++generation; // bump generation and capture
    const status = document.getElementById('docsStatus');
    try{
      if(status) status.textContent = 'Loading FHIR documents...';
      const rows = await fetchFromFhir();
      if(gen !== generation) return; // stale
      allRows = rows || [];
      loadedCount = 0;
      if(gen !== generation) return; // stale
      if(table){ table.clearData(); }
      // Initial chunk
      const init = allRows.slice(0, CHUNK_SIZE);
      if(gen !== generation) return; // stale
      if(table && init.length){
        table.setData(init);
        loadedCount = init.length;
        // Immediately start indexing the initial batch so search is usable early
        try { indexDocsBatchNow(init); } catch(_e){}
      }
      if(status){
        if(allRows.length){ updateStatusShowing(); }
        else status.textContent = 'No documents found.';
      }
      if(gen !== generation) return; // stale
      // Kick off background prefetch after initial render
      schedulePrefetch(150);
      // Start/refresh index runner (will no-op while paused)
      scheduleIndexRunner(300);
      try { console.log('[Documents] fetched', allRows.length, 'records'); } catch(_e){}
    }catch(err){
      if(err && err.name === 'AbortError'){ if(status) status.textContent = 'Cancelled.'; return; }
      if(status) status.textContent = 'Error loading FHIR documents'; console.warn('Documents load failed', err);
    }
  }

  function selectAll(){ if(!table) return; table.getRows().forEach(r=>r.select()); }
  function clearSelection(){ if(!table) return; table.getSelectedRows().forEach(r=>r.deselect()); }

  // Estimate total size by sampling a subset of notes
  async function estimateTotalSize(){
    const status = document.getElementById('docsStatus');
    const estEl = document.getElementById('docsSizeEstimate');
    const total = allRows.length || 0;
    if(!total){ if(estEl) estEl.textContent = ''; return; }
    try {
      if(status) status.textContent = 'Estimating size…';
      if(estEl) estEl.textContent = '';
      // Pick a deterministic spread of up to N samples across the list
      const SAMPLE_TARGET = 20; // keep lightweight
      const sampleCount = Math.min(SAMPLE_TARGET, total);
      if(sampleCount === 0){ if(status) updateStatusShowing(); return; }
      const idxs = new Set();
      if(total <= SAMPLE_TARGET){
        for(let i=0;i<total;i++) idxs.add(i);
      } else {
        const step = total / sampleCount;
        for(let i=0;i<sampleCount;i++) idxs.add(Math.floor(i*step));
      }
      const ids = Array.from(idxs).map(i => (allRows[i]||{}).doc_id).filter(Boolean);
      // Mark as loading in UI (non-intrusive)
      ids.forEach(id=> setLoadState(id, loadState.get(id) || 'Queued'));
      // Fetch via batch in chunks to minimize calls
      const CHUNK = 12;
      let totalBytes = 0;
      for(let i=0; i<ids.length; i+=CHUNK){
        const part = ids.slice(i,i+CHUNK);
        try {
          const results = await fetchNotesBatch(part);
          for(const r of results){ if(r && Array.isArray(r.text)){ totalBytes += r.text.join('\n').length; } }
        } catch(e){ /* ignore sample errors */ }
      }
      // Extrapolate
      const avgBytes = totalBytes / sampleCount;
      const estTotalBytes = Math.round(avgBytes * total);
      function fmtBytes(n){
        if(n < 1024) return `${n} B`;
        if(n < 1024*1024) return `${(n/1024).toFixed(1)} KB`;
        if(n < 1024*1024*1024) return `${(n/1024/1024).toFixed(1)} MB`;
        return `${(n/1024/1024/1024).toFixed(2)} GB`;
      }
      const msg = `~${fmtBytes(estTotalBytes)} across ${total.toLocaleString()} notes (sampled ${sampleCount})`;
      if(estEl) estEl.textContent = msg;
      updateStatusShowing();
      // If large, add a gentle warning
      if(estTotalBytes > 50*1024*1024){
        try { console.warn('[Documents] Large dataset likely (', fmtBytes(estTotalBytes), ') — consider tighter filters or paging.'); } catch(_e){}
      }
    } finally {
      // Restore normal status line
      updateStatusShowing();
    }
  }

  async function fetchNoteText(docId){
    if(!docId) throw new Error('No doc id');
    const cached = noteCache.get(docId);
    if(cached && Array.isArray(cached.lines)) return cached.lines;
    const dfn = currentDfn();
    const url = `/last_primary_care_progress_note?doc_id=${encodeURIComponent(docId)}${dfn ? `&dfn=${encodeURIComponent(dfn)}` : ''}`;
    const { fetchPromise } = withAbortableFetch(url);
    const r = await fetchPromise;
    if(!r.ok) throw new Error('fetch failed');
    const j = await r.json();
    const lines = Array.isArray(j.text) ? j.text : [];
    noteCache.set(docId, { lines, fetchedAt: Date.now() });
    return lines;
  }

  async function fetchNotesBatch(docIds){
    const gen = generation; // capture
    const ids = (docIds || []).filter(Boolean);
    if(!ids.length) return [];
    const dfn = currentDfn();
    const url = dfn ? `/documents_text_batch?dfn=${encodeURIComponent(dfn)}` : '/documents_text_batch';
    const { fetchPromise } = withAbortableFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_ids: ids })
    });
    const resp = await fetchPromise;
    if(!resp.ok) throw new Error('batch fetch failed');
    const data = await resp.json();
    if(gen !== generation) return [];
    const arr = Array.isArray(data.notes) ? data.notes : [];
    // Cache successes
    for(const item of arr){
      if(item && item.doc_id && Array.isArray(item.text)){
        noteCache.set(item.doc_id, { lines: item.text, fetchedAt: Date.now() });
      }
    }
    return arr;
  }

  function findRowByDocId(docId){
    if(!table) return null;
    const rows = table.getRows();
    for(const row of rows){
      const d = row.getData();
      if(d && d.doc_id === docId) return row;
    }
    return null;
  }

  async function openDocById(docId){
    // Backward-compat wrapper: route to centralized event
    if(!docId) return;
    try { openDocument({ docId }); } catch(_e){}
  }

  // Visible in table: index state
  function setIndexState(docId, state){
    if(!docId) return;
    const prev = indexState.get(docId);
    indexState.set(docId, state);
    if(prev !== 'Indexed' && state === 'Indexed') { indexedCount += 1; }
    if(prev === 'Indexed' && state !== 'Indexed') { indexedCount = Math.max(0, indexedCount - 1); }
    const row = findRowByDocId(docId);
    if(row){ try{ row.update({ indexed: state }); } catch(_e){} }
    // If Indexed-only filter is active, re-evaluate row visibility
    try { if(indexedOnlyFilterOn && table){ table.refreshFilter(); } } catch(_e){}
    updateStatusShowing();
  }

  function setLoadState(docId, state){
    if(!docId) return;
    const prev = loadState.get(docId);
    loadState.set(docId, state);
    if(prev !== 'Ready' && state === 'Ready'){
      readyVersion++;
      scheduleKwAutoRefresh(200);
    }
    const row = findRowByDocId(docId);
    if(row){
      try{ row.update({ /* no-op for visible fields */ }); } catch(_e){}
    }
    // Update status so user sees Keyword-ready counts change in real time
    try{ updateStatusShowing(); }catch(_e){}
  }

  function renderDocView(meta){
    const titleEl = document.getElementById('docViewTitle');
    const statusEl = document.getElementById('docViewStatus');
    const textEl = document.getElementById('docViewText');
    // Proceed even if titleEl is missing (it was removed from the layout)
    if(statusEl){ statusEl.textContent = meta && meta.date ? meta.date : ''; }
    if(titleEl){
      titleEl.textContent = meta && meta.title ? meta.title : (meta && meta.doc_id ? meta.doc_id : '');
      if(meta && meta.author){ titleEl.textContent += titleEl.textContent ? ` — ${meta.author}` : meta.author; }
    }
    if(!textEl) return;
    const cached = meta && meta.doc_id ? noteCache.get(meta.doc_id) : null;
    if(cached && Array.isArray(cached.lines)){
      const joined = (cached.lines || []).join('\n');
      try { console.debug('[Documents] renderDocView lines', cached.lines.length, 'preview:', joined.slice(0, 80)); } catch(_e){}
      textEl.textContent = joined;
      textEl.innerText = joined;
      try { textEl.scrollTop = 0; } catch(_e){}
    } else {
      textEl.textContent = '';
      textEl.innerText = '';
    }
  }

  async function onRowClick(e, row){
    try{ console.log('[Documents]rowClick'); }catch(_e){}
    const data = row && row.getData ? row.getData() : null;
    if(!data || !data.doc_id) return;
    lastRowSelected = row; // remember for keyboard open
    // Centralized open via event bus
    try { openDocument({ docId: data.doc_id }); } catch(_e){}
  }

  function buildPrefetchQueue(){
    if(!table) return [];
    // 1) Current view order (respects current sort/filter, e.g., Author)
    const currentOrder = (table.getData() || []).map(r=>r.doc_id).filter(Boolean);
    // 2) Recency fallback (date desc). allRows already mapped from server; use that order
    const recencyOrder = (allRows || []).map(r=>r.doc_id).filter(Boolean);
    const seen = new Set();
    const combined = [];
    function pushList(list){
      for(const id of list){
        if(!id) continue;
        if(seen.has(id)) continue;
        // Skip items already loaded or loading (note text prefetch)
        const st = loadState.get(id) || '';
        if(st === 'Ready' || st === 'Loading') { seen.add(id); continue; }
        combined.push(id);
        seen.add(id);
      }
    }
    pushList(currentOrder);
    pushList(recencyOrder);
    return combined;
  }

  async function runPrefetch(){
    if(prefetchRunning) return;
    prefetchRunning = true;
    try{
      const gen = generation; // capture
      const queue = buildPrefetchQueue();
      if(!queue.length) return;
      // Mark queued first so UI reflects upcoming work
      queue.forEach(id=>{ if(!loadState.get(id)) setLoadState(id,'Queued'); });
      // Prefer batched requests in groups to reduce socket churn
      const BATCH_SIZE = 12;
      for(let i = 0; i < queue.length; i += BATCH_SIZE){
        if(gen !== generation) return; // stale
        const batch = queue.slice(i, i + BATCH_SIZE);
        batch.forEach(id=> setLoadState(id, 'Loading'));
        try{
          const results = await fetchNotesBatch(batch);
          if(gen !== generation) return; // stale
          const okSet = new Set();
          for(const r of results){
            if(r && r.doc_id){
              setLoadState(r.doc_id, 'Ready');
              okSet.add(r.doc_id);
            }
          }
          // If server skipped some ids, fallback fetch individually
          for(const id of batch){
            if(gen !== generation) return; // stale
            if(!okSet.has(id)){
              try{ const _ = await fetchNoteText(id); setLoadState(id, 'Ready'); } catch(e){ setLoadState(id, 'Error'); }
            }
          }
        } catch(err){
          // On batch failure, fall back to serial fetching for this batch
          for(const id of batch){
            if(gen !== generation) return; // stale
            try{ const _ = await fetchNoteText(id); setLoadState(id, 'Ready'); }
            catch(e){ setLoadState(id, 'Error'); }
          }
        }
      }
    } finally {
      prefetchRunning = false;
    }
  }

  function schedulePrefetch(delayMs){
    if(prefetchDebounce){ clearTimeout(prefetchDebounce); }
    prefetchDebounce = setTimeout(runPrefetch, typeof delayMs==='number'? delayMs : 0);
  }

  // ---- Simple auto-index runner + helpers ----
  function _collectIdsFromItems(items){
    const ids = [];
    if(Array.isArray(items)){
      for(const it of items){
        if(!it) continue;
        if(typeof it === 'string'){ ids.push(it); continue; }
        if(typeof it === 'object'){
          const id = it.doc_id || it.id || (it.getData && it.getData().doc_id);
          if(id) ids.push(id);
        }
      }
    }
    // de-dup, keep order
    const seen = new Set();
    return ids.filter(id => (seen.has(id) ? false : (seen.add(id), true)));
  }
  function _getIndexableIds(batchSize){
    const MAX = typeof batchSize === 'number' && batchSize > 0 ? batchSize : 12;
    const out = [];
    const seen = new Set();
    function push(id){ if(!id) return; if(seen.has(id)) return; const st = indexState.get(id) || ''; if(st === 'Indexed' || st === 'Indexing') return; out.push(id); seen.add(id); }
    // 1) Visible/active rows first
    try{
      if(table){
        const rows = (table.getRows && table.getRows('active')) || (table.getRows && table.getRows()) || [];
        for(const r of rows){ if(out.length >= MAX) break; const d = r && r.getData && r.getData(); if(d && d.doc_id) push(String(d.doc_id)); }
      }
    }catch(_e){}
    // 2) Loaded data in memory (initial chunks)
    try{
      if(out.length < MAX){
        const data = (table && table.getData && table.getData()) || [];
        for(const d of data){ if(out.length >= MAX) break; push(String(d && d.doc_id)); }
      }
    }catch(_e){}
    // 3) Fallback to allRows order
    if(out.length < MAX){
      for(const r of allRows){ if(out.length >= MAX) break; push(String(r && r.doc_id)); }
    }
    return out.slice(0, MAX);
  }

  async function indexDocsBatchNow(items){
    try{
      const ids = items && items.length ? _collectIdsFromItems(items) : _getIndexableIds(12);
      if(!ids || !ids.length) return;
      // Mark UI state
      ids.forEach(id => setIndexState(String(id), 'Indexing'));
      const { fetchPromise } = withAbortableFetch('/explore/index_notes', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ doc_ids: ids, append: true, skip_if_indexed: true })
      });
      const res = await fetchPromise;
      let j = {};
      try{ j = await res.json(); }catch(_e){}
      const results = Array.isArray(j.results) ? j.results : [];
      // Update states based on response
      if(results.length){
        for(const r of results){
          const id = String(r && r.doc_id || ''); if(!id) continue;
          const st = String(r && r.status || '');
          if(st === 'Indexed' || st === 'Skipped') setIndexState(id, 'Indexed');
          else if(st === 'Error') setIndexState(id, 'Error');
          else setIndexState(id, 'Indexed');
        }
      } else {
        // If server gave no per-id details, assume success
        ids.forEach(id => setIndexState(String(id), 'Indexed'));
      }
    } catch(err){
      // On error, mark as Error
      try{ const ids = items && items.length ? _collectIdsFromItems(items) : []; ids.forEach(id => setIndexState(String(id), 'Error')); }catch(_e){}
      try { console.warn('[Documents] index batch error', err); } catch(_e){}
    } finally {
      updateStatusShowing();
    }
  }

  async function _runIndexRunnerOnce(){
    if(autoIndexPaused) return;
    if(indexRunnerActive) return;
    // Peek queue
    const ids = _getIndexableIds(12);
    if(!ids.length) return;
    indexRunnerActive = true;
    try{
      await indexDocsBatchNow(ids);
    } finally {
      indexRunnerActive = false;
      // If more work remains and still not paused, schedule another pass
      try{
        if(!autoIndexPaused){
          const more = _getIndexableIds(1); // cheap check
          if(more && more.length){ scheduleIndexRunner(400); }
        }
      }catch(_e){}
    }
  }
  function scheduleIndexRunner(delayMs){
    try{ if(indexRunnerDebounce) clearTimeout(indexRunnerDebounce); }catch(_e){}
    indexRunnerDebounce = setTimeout(()=>{ _runIndexRunnerOnce(); }, typeof delayMs==='number' ? delayMs : 0);
  }

  // ---- Simple inverted index (keyword hits across full notes) ----
  function parseKwQuery(val){
    return _parseKeywords(val);
  }
  function computeDocHits(fullText, tokens){
    if(!fullText || !Array.isArray(tokens) || !tokens.length) return 0;
    let hits = 0;
    for(const raw of tokens){
      const t = String(raw || '').trim();
      if(!t) continue;
      // Escape regex and allow flexible whitespace inside phrases; count all occurrences
      const pattern = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
      if(!pattern) continue;
      const re = new RegExp(pattern, 'gi');
      let m;
      while((m = re.exec(fullText))){
        hits++;
        if(re.lastIndex === m.index) re.lastIndex++; // safety for zero-width
      }
    }
    return hits;
  }
  async function updateKwIndexForHeader(value){
    const tokens = parseKwQuery(value);
    const status = document.getElementById('docsStatus');
    if(!tokens.length){
      // Clear hits
      kwQuery = '';
      for(const r of allRows){ r.kwHits = null; }
      if(table){
        try{ table.getRows().forEach(row=>{ try{ row.update({ kwHits: null }); }catch(_e){} }); table.refreshFilter(); }catch(_e){}
      }
      if(status) status.textContent = 'Keyword filter cleared.';
      ensureKwSort(false);
      return;
    }
    kwQuery = value;
    // Make sure we have some Ready notes; if none, trigger prefetch and wait for auto-refresh
    const readyIds = [];
    for(const r of allRows){
      const id = r.doc_id; if(!id) continue;
      const st = loadState.get(id) || '';
      if(st === 'Ready') readyIds.push(id);
    }
    if(!readyIds.length){
      if(status) status.textContent = 'Loading notes for keyword filter...';
      try{ schedulePrefetch(0); }catch(_e){}
      return;
    }
    // Compute hits only for rows we have text for; leave others as unknown (null)
    const hitsMap = new Map();
    for(const r of allRows){
      const id = r.doc_id; if(!id) continue;
      const cache = noteCache.get(id);
      if(cache && Array.isArray(cache.lines)){
        const full = cache.lines.join('\n');
        const n = computeDocHits(full, tokens);
        hitsMap.set(id, n);
      }
    }
    // Apply to model and table
    for(const r of allRows){
      const id = r.doc_id; if(!id) continue;
      if(hitsMap.has(id)) r.kwHits = hitsMap.get(id);
      // else leave r.kwHits as-is (prefer null for unknown)
    }
    if(table){
      try{
        table.getRows().forEach(row=>{
          try{
            const d = row.getData && row.getData();
            if(d && d.doc_id && hitsMap.has(d.doc_id)){
              const n = hitsMap.get(d.doc_id);
              row.update({ kwHits: n });
            }
          }catch(_e){}
        });
        table.refreshFilter();
      }catch(_e){}
    }
    // Enable auto-sort by hit count
    ensureKwSort(true);
  }
  function scheduleKwAutoRefresh(delay){
    if(kwDebounce) clearTimeout(kwDebounce);
    kwDebounce = setTimeout(()=>{
      try{
        if(!table || !table.getHeaderFilters) return;
        const filters = table.getHeaderFilters()||[];
        const f = filters.find(x => String(x.field||'') === 'kwHits');
        const val = f ? f.value : '';
        if(val){ updateKwIndexForHeader(val); }
      }catch(_e){}
    }, delay||300);
  }

  async function combineAndLoad(){
    if(!table) return;
    const selected = table.getSelectedData();
    if(!selected.length){ alert('Select at least one item.'); return; }
    const btn = document.getElementById('combineDocsBtn');
    const status = document.getElementById('docsStatus');
    try{
      if(btn){ btn.disabled = true; btn.dataset._orig = btn.textContent; btn.textContent = 'Combining...'; }
      if(status) status.textContent = 'Combining selection...';
      const ids = selected.map(d=>d.doc_id).filter(Boolean);
      const parts = [];
      for(let i=0;i<ids.length;i++){
        const id = ids[i];
        try{
          // Use cache if available; else fetch now
          let lines = (noteCache.get(id) || {}).lines;
          if(!lines){
            setLoadState(id, 'Loading');
            lines = await fetchNoteText(id);
            setLoadState(id, 'Ready');
          }
          const title = (selected[i] && (selected[i].title || selected[i].encounter)) || id;
          parts.push(`=== Document ${i+1} / ${ids.length}: ${title} (${id}) ===\n${(lines||[]).join('\n')}\n\nPage ${i+1} of ${ids.length}\n\n`);
        }catch(e){ console.warn('Note fetch failed', id, e); setLoadState(id,'Error'); }
      }
      const text = parts.join('').trim();
      const ta = document.getElementById('chunkText');
      if(ta){ ta.value = text; ta.scrollTop = 0; }
      if(status) status.textContent = `Loaded ${selected.length} note(s) into Chart Data. Click "Prepare Data" next.`;
      if(ta) ta.focus();
    }catch(err){ console.warn('Combine error', err); if(status) status.textContent = 'Error combining selection.'; }
    finally{ if(btn){ btn.textContent = btn.dataset._orig || 'Combine & Load Into Chart Data'; btn.disabled = false; } }
  }

  async function handleOpenClick(ev){
    // Handle open-note-link and excerpt-citation
    const a = ev.target && ev.target.closest ? ev.target.closest('.open-note-link, .excerpt-citation') : null;
    if(a && a.dataset && a.dataset.docId){
      ev.preventDefault();
      const docId = a.dataset.docId;
      // If excerpt specified, derive text for robust highlighting and pass through event payload
      const excerptNum = a.dataset.excerpt;
      let excerptText;
      if(excerptNum){
        const matches = Array.isArray(window.lastNotesQAMatches) ? window.lastNotesQAMatches : [];
        const chunk = matches.find(m => String(m.page) === String(excerptNum) && m.note_id === docId);
        if(chunk && chunk.text){ excerptText = chunk.text; }
      }
      try { openDocument({ docId, excerptText, excerptIndex: excerptNum }); } catch(_e){}
      // Close any citation popover once a note is opened
      try { if(typeof closeCitePopover === 'function') closeCitePopover(); } catch(_e){}
    }
  }

  // === Citation hover popover ===
  let _citePopover = null;
  let _citeAnchor = null;
  let _citeHideTimer = null;

  function closeCitePopover(){
    try{ if(_citeHideTimer){ clearTimeout(_citeHideTimer); _citeHideTimer = null; } }catch(_e){}
    try{ if(_citePopover){ _citePopover.remove(); } }catch(_e){}
    _citePopover = null; _citeAnchor = null;
    try{ document.removeEventListener('click', _onDocClickCloseCite, true); }catch(_e){}
  }
  function _onDocClickCloseCite(ev){
    if(!_citePopover) return;
    const el = ev.target;
    if(_citePopover.contains(el) || (_citeAnchor && _citeAnchor.contains(el))) return;
    closeCitePopover();
  }
  function _getExcerptForAnchor(a){
    if(!a) return '';
    const ds = a.dataset || {};
    if(ds.excerptText){ return String(ds.excerptText); }
    const idx = ds.excerpt || ds.page;
    const docId = ds.docId || ds.noteId || ds.note_id;
    const arr = Array.isArray(window.lastNotesQAMatches) ? window.lastNotesQAMatches : [];
    if(!arr.length) return '';
    let best = null;
    if(idx != null){ best = arr.find(m => String(m.page) === String(idx) && (!docId || String(m.note_id) === String(docId))); }
    if(!best && idx != null){ best = arr.find(m => String(m.page) === String(idx)); }
    if(!best && docId){ best = arr.find(m => String(m.note_id) === String(docId)); }
    return best && best.text ? String(best.text) : '';
  }
  function showCitePopover(anchor, text){
    if(!anchor) return;
    if(_citeAnchor === anchor && _citePopover){ return; }
    closeCitePopover();
    const pop = document.createElement('div');
    pop.className = 'qa-cite-popover';
    pop.textContent = String(text || '').trim();
    Object.assign(pop.style, {
      position: 'absolute', maxWidth: '460px', whiteSpace: 'pre-wrap', background: '#fff', color: '#222',
      border: '1px solid #d1d5db', padding: '8px 10px', borderRadius: '6px',
      boxShadow: '0 8px 24px rgba(0,0,0,0.15)', zIndex: '9999', fontSize: '12px', lineHeight: '1.4'
    });
    document.body.appendChild(pop);
    const r = anchor.getBoundingClientRect();
    let top = window.scrollY + r.bottom + 6;
    let left = window.scrollX + r.left;
    const pr = pop.getBoundingClientRect();
    const pad = 8, vw = window.innerWidth, vh = window.innerHeight;
    if(left + pr.width > window.scrollX + vw - pad){ left = window.scrollX + vw - pad - pr.width; }
    if(left < window.scrollX + pad){ left = window.scrollX + pad; }
    if(top + pr.height > window.scrollY + vh - pad){ top = window.scrollY + r.top - pr.height - 6; if(top < window.scrollY + pad) top = window.scrollY + pad; }
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
    _citePopover = pop; _citeAnchor = anchor;
    try { document.addEventListener('click', _onDocClickCloseCite, true); } catch(_e){}
    pop.addEventListener('mouseenter', ()=>{ if(_citeHideTimer){ clearTimeout(_citeHideTimer); _citeHideTimer = null; } });
    pop.addEventListener('mouseleave', ()=>{ _citeHideTimer = setTimeout(()=> closeCitePopover(), 120); });
  }
  function handleCiteHover(ev){
    const a = ev.target && ev.target.closest ? ev.target.closest('a.excerpt-citation') : null;
    if(!a) return;
    const text = _getExcerptForAnchor(a);
    if(!text) return;
    showCitePopover(a, text);
  }
  function handleCiteOut(ev){
    const a = ev.target && ev.target.closest ? ev.target.closest('a.excerpt-citation') : null;
    if(!a) return;
    if(_citeHideTimer){ clearTimeout(_citeHideTimer); }
    _citeHideTimer = setTimeout(()=>{ closeCitePopover(); }, 150);
  }

  // Helper: escape HTML safely for highlighting
  function _escapeHtml(s){
    return String(s ?? '')
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;')
      .replace(/'/g,'&#39;');
  }

  // Parse keywords from a free-text string, supporting quoted phrases
  function _parseKeywords(str){
    const s = String(str || '').trim();
    if(!s) return [];
    const out = [];
    const re = /"([^"]+)"|'([^']+)'|(\S+)/g;
    let m;
    while((m = re.exec(s))){
      const tok = (m[1] || m[2] || m[3] || '').trim();
      if(!tok) continue;
      if(tok.length < 2) continue; // drop very short tokens
      out.push(tok.toLowerCase());
    }
    // De-duplicate, keep order
    const seen = new Set();
    return out.filter(t => (seen.has(t) ? false : (seen.add(t), true)));
  }

  // Compose currentKeywords from keyword input and header filters
  function recomputeCurrentKeywords(){
    try{
      const kws = [];
      // From docsKeywordInput
      const kwInput = document.getElementById('docsKeywordInput');
      if(kwInput && kwInput.value){ kws.push(..._parseKeywords(kwInput.value)); }
      // From header filters (Title, Author, Encounter, and Keywords)
      if(table && typeof table.getHeaderFilters === 'function'){
        const filters = table.getHeaderFilters() || [];
        for(const f of filters){
          const field = (f && f.field) || (f && f.column && f.column.getField && f.column.getField());
          const val = f && (f.value ?? f.term ?? f.params?.value);
          if(!field || typeof val !== 'string' || !val.trim()) continue;
          if(field === 'kwHits'){
            // User typed free-text keywords in the Keywords header
            kws.push(..._parseKeywords(val));
          } else if(field === 'title' || field === 'author' || field === 'encounter'){
            kws.push(..._parseKeywords(val));
          }
        }
      }
      // Fallback DOM read if needed
      if(!table || typeof table.getHeaderFilters !== 'function'){
        try{
          const container = document.getElementById('documentsTable');
          if(container){
            const inputs = container.querySelectorAll('.tabulator-col input');
            inputs.forEach(inp=>{ try{ const v = (inp && inp.value) ? String(inp.value).trim() : ''; if(v){ kws.push(..._parseKeywords(v)); } }catch(_e){} });
          }
        }catch(_e){}
      }
      // Dedup and assign
      const seen = new Set();
      currentKeywords = kws.filter(t => (seen.has(t) ? false : (seen.add(t), true)));
    }catch(_e){ currentKeywords = []; }
  }

  // Build highlighted HTML for the note text using currentKeywords and optional excerpt needle
  function buildHighlightedHTML(fullText, keywords, excerptNeedle){
    const MAX_CHARS = 1_000_000; // ~1MB safety cap
    if(!fullText) return { html: '', skipped: false };
    if(fullText.length > MAX_CHARS){
      // Skip heavy processing
      return { html: _escapeHtml(fullText), skipped: true };
    }
    const lower = fullText.toLowerCase();
    const ranges = [];
    // Excerpt range
    if(excerptNeedle){
      const needle = String(excerptNeedle).trim().toLowerCase();
      if(needle){
        const idx = lower.indexOf(needle);
        if(idx >= 0){ ranges.push({ start: idx, end: idx + needle.length, type: 'excerpt' }); }
      }
    }
    // Keyword ranges
    const toks = Array.isArray(keywords) ? keywords.slice() : [];
    // Sort longer first to reduce fragmentation
    toks.sort((a,b)=> b.length - a.length);
    for(const t of toks){
      if(!t) continue;
      // Build regex tolerant to whitespace in phrases
      const pattern = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
      if(!pattern) continue;
      const re = new RegExp(pattern, 'gi');
      let m;
      while((m = re.exec(fullText))){
        const start = m.index;
        const end = m.index + m[0].length;
        if(end === start) { re.lastIndex++; continue; }
        ranges.push({ start, end, type: 'kw' });
        // Prevent infinite loops on zero-width
        if(re.lastIndex === m.index) re.lastIndex++;
      }
    }
    if(!ranges.length){
      return { html: _escapeHtml(fullText), skipped: false };
    }
    // Build boundary map
    const boundaries = new Set([0, fullText.length]);
    for(const r of ranges){
      boundaries.add(Math.max(0, Math.min(fullText.length, r.start)));
      boundaries.add(Math.max(0, Math.min(fullText.length, r.end)));
    }
    const points = Array.from(boundaries).sort((a,b)=> a-b);
    // Helper to know if inside a type at position
    function active(pos, type){ return ranges.some(r => r.type===type && r.start <= pos && pos < r.end); }
    let html = '';
    for(let i=0;i<points.length-1;i++){
      const a = points[i], b = points[i+1];
      if(b <= a) continue;
      const seg = fullText.slice(a,b);
      const inExcerpt = active(a,'excerpt');
      const inKw = active(a,'kw');
      let chunk = _escapeHtml(seg);
      if(inKw){ chunk = `<mark class="doc-keyword-highlight">${chunk}</mark>`; }
      if(inExcerpt){ chunk = `<span class="excerpt-highlight" style="background:yellow;">${chunk}</span>`; }
      html += chunk;
    }
    return { html, skipped: false };
  }

  // Re-apply highlight to current open viewer without refetching
  function refreshViewerHighlights(opts){
    const options = opts || {};
    const viewer = document.getElementById('docViewText');
    const statusEl = document.getElementById('docViewStatus');
    if(!viewer || !lastOpenedDocId) return;
    try{
      const cache = window._documentsNoteCache ? window._documentsNoteCache.get(lastOpenedDocId) : null;
      const full = cache && Array.isArray(cache.lines) ? cache.lines.join('\n') : (viewer.textContent || viewer.innerText || '');
      const { html, skipped } = buildHighlightedHTML(full, currentKeywords, null);
      if(html){ viewer.innerHTML = html; }
      if(statusEl && skipped){
        const prev = statusEl.textContent || '';
        if(!/Highlights skipped/i.test(prev)) statusEl.textContent = `${prev} • Highlights skipped`;
      }
      if(options.scrollToFirst){
        const span = viewer.querySelector('.excerpt-highlight, .doc-keyword-highlight');
        if(span && span.scrollIntoView){ span.scrollIntoView({behavior:'smooth', block:'center'}); }
      }
    }catch(_e){}
  }

  // Safe no-op for table keyword filter pipeline used by Clear button
  function applyAllFilters(){ /* future: implement table-wide filters keyed by docsKeywordInput */ }

  // --- FHIR [[...]] token resolution for Notes Ask ---
  async function _getPatientMetaOnce(){
    try{ const r = await fetch('/get_patient', { cache:'no-store' }); if(!r.ok) return null; const j = await r.json(); if(j && j.dfn) return j; }catch(_e){}
    return null;
  }
  function _fmtMedsList(meds){
    try{
      if(!Array.isArray(meds) || meds.length===0) return 'None';
      const lines = meds.map(m=>{
        const name = m && m.name ? String(m.name) : '';
        const chunks = [];
        if(m && m.dose) chunks.push(String(m.dose));
        if(m && m.route) chunks.push(String(m.route));
        if(m && m.frequency) chunks.push(String(m.frequency));
        const tail = chunks.length ? ' — ' + chunks.join(' ') : '';
        return `- ${name}${tail}`;
      });
      return lines.join('\n');
    }catch(_e){ return ''; }
  }
  function _fmtProblemsList(problems){
    try{
      if(!Array.isArray(problems) || problems.length===0) return 'None';
      const lines = problems.map(p=>{
        const name = p && p.name ? String(p.name) : '';
        const act = (p && p.active) ? 'active' : 'inactive';
        return `- ${name} (${act})`;
      });
      return lines.join('\n');
    }catch(_e){ return ''; }
  }
  async function _resolveFhirToken(tok){
    const t = String(tok||'').trim().toLowerCase();
    if(t === 'meds/active' || t === 'medications/active'){
      try{ const r = await fetch('/fhir/medications?status=active', { cache:'no-store' }); if(!r.ok) return null; const j = await r.json(); return _fmtMedsList((j && j.medications) || []); }catch(_e){ return null; }
    }
    if(t === 'meds' || t === 'medications'){
      try{ const r = await fetch('/fhir/medications', { cache:'no-store' }); if(!r.ok) return null; const j = await r.json(); return _fmtMedsList((j && j.medications) || []); }catch(_e){ return null; }
    }
    if(t === 'problems' || t === 'problems/active'){
      const url = (t === 'problems/active') ? '/fhir/problems?status=active' : '/fhir/problems';
      try{ const r = await fetch(url, { cache:'no-store' }); if(!r.ok) return null; const j = await r.json(); return _fmtProblemsList((j && j.problems) || []); }catch(_e){ return null; }
    }
    return null; // unknown
  }
  async function _replaceFhirPlaceholdersInQuery(text){
    try{
      const s = String(text ?? '');
      if(!s.includes('[[')) return s;
      const meta = await _getPatientMetaOnce();
      if(!meta || !meta.dfn) return s; // leave alone if no patient
      const re = /\[\[\s*([^\]\[]+?)\s*\]\]/g;
      const tokens = new Map();
      let m;
      while((m = re.exec(s))){ const raw = m[0]; const tok = m[1]; if(!tokens.has(raw)) tokens.set(raw, tok); }
      if(tokens.size === 0) return s;
      const resolved = await Promise.all(Array.from(tokens.entries()).map(async ([raw, tok])=>{
        const val = await _resolveFhirToken(tok);
        return [raw, val];
      }));
      let out = s;
      for(const [raw, val] of resolved){ if(typeof val === 'string' && val.length){ out = out.split(raw).join(val); } }
      return out;
    }catch(_e){ return String(text ?? ''); }
  }

  async function runNotesAsk(qOverride){
    if(window._notesAskBusy){ return; }
    const askEl = document.getElementById('notesAskInput');
    const q = (qOverride != null ? String(qOverride) : (askEl && askEl.value || '')).trim();
    if(!q) return;
    const status = document.getElementById('docsStatus');
    const box = document.getElementById('notesAnswerBox');
    const btn = document.getElementById('notesAskBtn');
    const prevBtnText = btn ? btn.textContent : '';
    try{
      window._notesAskBusy = true;
      if(btn){ btn.disabled = true; btn.textContent = 'Asking…'; }
      if(status) status.textContent = 'Asking LLM over notes...';
      if(box){ box.style.display=''; box.innerHTML=''; box.setAttribute('aria-busy','true'); }      // NEW: resolve [[...]] tokens using FHIR endpoints before sending
      const qResolved = await _replaceFhirPlaceholdersInQuery(q);
      
      // Check if demo mode is enabled
      const demoMode = window.demoMasking && window.demoMasking.enabled;
      
      const res = await fetch('/explore/notes_qa', { 
        method:'POST', 
        headers:{'Content-Type':'application/json'}, 
        body: JSON.stringify({ 
          query: qResolved, 
          top_k: 8,
          demo_mode: demoMode 
        }) 
      });
      let j = {};
      try { j = await res.json(); } catch(_e) { j = {}; }
      if(!res.ok || j.error){
        const msg = (j && j.error) || `Request failed (${res.status})`;
        throw new Error(msg);
      }
      try { console.log('[Notes QA Response]', j); } catch(_e){}
      const ans = j.answer || '';
      const matches = j.matches || [];
      try { window.lastNotesQAMatches = matches; } catch(_e) {}
      const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c] || ''));
      // Answer text -> Markdown (keep same container/background)
      let answerHtml = (window.marked && typeof window.marked.parse === 'function') ? window.marked.parse(String(ans)) : esc(ans).replace(/\n/g,'<br>');

      // Build map: page/index -> { docId, text, date, section }
      const pageMap = new Map();
      if(Array.isArray(matches)){
        for(let i=0;i<matches.length;i++){
          const m = matches[i] || {};
          const nid = String(m.note_id || '');
          const page = (typeof m.page === 'number' && m.page>0) ? m.page : (i+1);
          if(nid){ pageMap.set(String(page), { docId: nid, text: m.text || '', date: m.date || '', section: m.section || '' }); }
        }
      }

      // Linkify inline citations like (Excerpt 1) and (Excerpts 2,7)
      if(pageMap.size){
        answerHtml = answerHtml.replace(/\((Excerpts?)\s+([0-9,\s\-]+)\)/gi, (full, label, nums) => {
          // Expand numbers and ranges (e.g., 2-4)
          const outNums = [];
          String(nums).split(',').forEach(tok => {
            const t = String(tok).trim(); if(!t) return;
            const m = t.match(/^(\d+)\s*-\s*(\d+)$/);
            if(m){
              let a = parseInt(m[1],10), b = parseInt(m[2],10);
              if(Number.isFinite(a) && Number.isFinite(b)){
                if(a <= b){ for(let n=a;n<=b;n++) outNums.push(n); }
                else { for(let n=a;n>=b;n--) outNums.push(n); }
              }
            } else {
              const n = parseInt(t,10);
              if(Number.isFinite(n)) outNums.push(n);
            }
          });
          if(!outNums.length) return full; // nothing to do
          const linked = outNums.map(n => {
            const meta = pageMap.get(String(n));
            if(!meta) return String(n);
            const titleBits = [];
            if(meta.date) titleBits.push(String(meta.date));
            if(meta.section) titleBits.push(String(meta.section));
            const title = esc(titleBits.join(' — '));
            return `<a href="#" class="excerpt-citation" data-doc-id="${esc(meta.docId)}" data-excerpt="${esc(n)}" title="${title}">${esc(n)}</a>`;
          }).join(', ');
          return `(${label} ${linked})`;
        });
        // Also linkify citations like: (Excerpt 1, Excerpt 2)
        answerHtml = answerHtml.replace(/\(\s*(?:Excerpt\s+\d+(?:\s*-\s*\d+)?\s*)(?:,\s*Excerpt\s+\d+(?:\s*-\s*\d+)?\s*)+\)/gi, (full) => {
          const nums = [];
          const rx = /Excerpt\s+(\d+)(?:\s*-\s*(\d+))?/gi;
          let m;
          while((m = rx.exec(full))){
            const a = parseInt(m[1],10);
            const b = m[2] ? parseInt(m[2],10) : null;
            if(Number.isFinite(a) && Number.isFinite(b)){
              if(a <= b){ for(let n=a;n<=b;n++) nums.push(n); }
              else { for(let n=a;n>=b;n--) nums.push(n); }
            } else if(Number.isFinite(a)) {
              nums.push(a);
            }
          }
          if(!nums.length) return full;
          // Deduplicate while preserving order
          const seen = new Set();
          const linked = nums.filter(n => { if(seen.has(n)) return false; seen.add(n); return true; })
            .map(n => {
              const meta = pageMap.get(String(n));
              if(!meta) return String(n);
              const title = esc([meta.date, meta.section].filter(Boolean).join(' — '));
              return `<a href="#" class="excerpt-citation" data-doc-id="${esc(meta.docId)}" data-excerpt="${n}" title="${title}">${n}</a>`;
            }).join(', ');
          return `(Excerpts ${linked})`;
        })
        // Additional styles with dates
        answerHtml = answerHtml
          .replace(/\(\s*Excerpt\s+(\d+)\s*,\s*Date:\s*([0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)\s*\)/gi, (full, n, dateStr)=>{
            const meta = pageMap.get(String(n));
            if(!meta) return full;
            const title = esc([meta.date, meta.section].filter(Boolean).join(' — '));
            return `(Excerpt <a href="#" class="excerpt-citation" data-doc-id="${esc(meta.docId)}" data-excerpt="${esc(n)}" title="${title}">${esc(n)}</a>, Date: ${esc(dateStr)})`;
          })
          .replace(/\(\s*Excerpt\s+(\d+)\s*,\s*([0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)\s*\)/gi, (full, n, dateStr)=>{
            const meta = pageMap.get(String(n));
            if(!meta) return full;
            const title = esc([meta.date, meta.section].filter(Boolean).join(' — '));
            return `(Excerpt <a href="#" class="excerpt-citation" data-doc-id="${esc(meta.docId)}" data-excerpt="${esc(n)}" title="${title}">${esc(n)}</a>, ${esc(dateStr)})`;
          })
          .replace(/\(\s*Excerpt\s+(\d+)\s*,\s*([0-9]{4})\s*\)/gi, (full, n, year)=>{
            const meta = pageMap.get(String(n));
            if(!meta) return full;
            const title = esc([meta.date, meta.section].filter(Boolean).join(' — '));
            return `(Excerpt <a href="#" class="excerpt-citation" data-doc-id="${esc(meta.docId)}" data-excerpt="${esc(n)}" title="${title}">${esc(n)}</a>, ${esc(year)})`;
          });
      }

      // Build citation links [1] [2] ... that open the note and highlight the chunk
      if(Array.isArray(matches) && matches.length){
        // Deduplicate by (note_id,page) while preserving order
        const seen = new Set();
        const cites = [];
        for(let i=0;i<matches.length;i++){
          const m = matches[i] || {};
          const nid = String(m.note_id || '');
          const page = (typeof m.page === 'number' && m.page>0) ? m.page : (i+1);
          const key = nid + '::' + page;
          if(!nid || seen.has(key)) continue;
          seen.add(key);
          const titleBits = [];
          if(m.date) titleBits.push(String(m.date));
          if(m.section) titleBits.push(String(m.section));
          const title = esc(titleBits.join(' — '));
          cites.push(`<a href="#" class="excerpt-citation" data-doc-id="${esc(nid)}" data-excerpt="${page}" title="${title}">[${page}]</a>`);
        }
        if(cites.length){
          const citesHtml = `<div class="notes-citations" style="margin-top:6px; font-size:0.95em; color:#444;">Sources: ${cites.join(' ')}</div>`;
          answerHtml = `<div class="notes-answer">${answerHtml}</div>` + citesHtml;
        }      }
      
      // Apply demo masking to the final answer HTML if enabled
      if (window.demoMasking && window.demoMasking.enabled) {
        // Store original for future unmasking
        if (box && !box.dataset.originalHtml) {
          box.dataset.originalHtml = answerHtml;
        }
        answerHtml = window.demoMasking.maskApiResponse(answerHtml);
      }
      
      if(box){ box.style.display=''; box.innerHTML = answerHtml; box.removeAttribute('aria-busy'); try{ box.scrollIntoView({behavior:'smooth', block:'nearest'}); }catch(_e){} }
      if(status) status.textContent = 'Done.';
    } catch(err){
      console.warn('Notes QA error', err);
      const msg = (err && err.message || '').toLowerCase().includes('no patient selected') ? 'Select a patient first, then ask.' : 'Error running notes Q&A.';
      if(status) status.textContent = msg;
      if(box){ box.style.display=''; box.innerHTML = `<em style="color:#b91c1c;">${msg}</em>`; box.removeAttribute('aria-busy'); }
    } finally {
      if(btn){ btn.disabled = false; btn.textContent = prevBtnText || 'Ask'; }
      window._notesAskBusy = false;
    }
  }
  // Expose globally so voice-ask can call directly
  try { window.runNotesAsk = runNotesAsk; } catch(_e){}

  function init(){
    const container = document.getElementById('documentsTable');
    const wrap = document.getElementById('documentsTableWrap');
    const canInitTable = !!container && typeof Tabulator !== 'undefined';
    // Destroy any prior instance to avoid duplicate wiring
    try { if(table && table.destroy){ table.destroy(); } } catch(_e){}
    table = null;

    // Ensure viewer is hidden on initial load; will open only when a note is selected
    try { hideDocOverlay(); } catch(_e){}

    // If user had a saved height for the wrapper, restore it
    try{
      if(wrap){
        const saved = parseInt((localStorage.getItem('docsWrapHeightPx')||''), 10);
        if(Number.isFinite(saved) && saved > 120 && saved < 2000){
          wrap.style.height = saved + 'px';
        }
      }
    }catch(_e){}

    // Helper: read current wrapper height in pixels
    function getWrapHeightPx(){
      try{ if(wrap){ const h = wrap.clientHeight; if(h && h > 0) return h; } }catch(_e){}
      return 360; // fallback
    }

    // Initialize Tabulator without pagination; rely on virtual DOM + infinite append
    if(canInitTable){
      try {
        table = new Tabulator('#documentsTable', {
          data: [],
          layout: 'fitColumns',
          selectable: true,
          movableColumns: true,
          // Keep total table width constant when resizing columns to avoid lateral growth
          columnResizeMode: 'fit',
          columnMinWidth: 60,
          // Use wrapper's current height so table matches resizable area
          height: getWrapHeightPx() + 'px',
          rowClick: onRowClick,
          rowDblClick: onRowClick,
          index: 'doc_id', // ensure stable lookup by id for nav
          // Use a different persistence key on mobile so desktop layout does not override
          persistenceID: (document.getElementById('mobileContent') ? 'docsTable_m_v1' : 'docsTable_v2_kw'),
          persistence: { columns: true, sort: true, filter: false },
          // Added: nicer UX defaults
          placeholder: 'No documents found.',
          tooltips: true,
          rowHeight: 34,
          // Columns are conditional: on mobile show only Keyword, Date, Title in that order
          columns: (function(){
            const isMobileExplore = !!document.getElementById('mobileContent');
            // Reuse existing column definitions with minimal duplication
            const colIndexed = { title: 'Indexed', field: 'indexed', width: 70, headerSort: false, hozAlign: 'center', formatter: function(cell){
              const v = cell.getValue();
              if(v === 'Indexed') return '<span class="idx-icon idx-ok" title="Indexed">✅</span>';
              if(v === 'Indexing') return '<span class="idx-icon idx-progress" title="Indexing">⏳</span>';
              if(v === 'Queued') return '<span class="idx-icon idx-queued" title="Queued">…</span>';
              if(v === 'Error') return '<span class="idx-icon idx-err" title="Error">⚠️</span>';
              return '';
            }};
            const colDate = {
              title: 'Date',
              field: 'date',
              sorter: (a,b,rowA,rowB)=>{
                try{
                  const da = rowA && rowA.getData ? rowA.getData().date : a;
                  const db = rowB && rowB.getData ? rowB.getData().date : b;
                  const ta = _parseDateMs(da);
                  const tb = _parseDateMs(db);
                  // Put valid dates first; invalid dates at the end
                  const aValid = Number.isFinite(ta);
                  const bValid = Number.isFinite(tb);
                  if(aValid && bValid) return ta - tb;
                  if(aValid && !bValid) return -1;
                  if(!aValid && bValid) return 1;
                  return 0;
                }catch(_e){ return 0; }
              },
              width: 130,
              headerFilter: 'input',
              formatter: (cell) => {
                try { return _fmtShortDate(cell.getValue()); } catch(_e) { return String(cell.getValue()||''); }
              },
              headerFilterFunc: function(headerValue, rowValue){
                const q = (headerValue || '').trim();
                if(!q) return true;
                const v = rowValue || '';
                // If the row's date cannot be parsed, keep the row visible rather than excluding it
                const rowMs = _parseDateMs(v);
                if(!Number.isFinite(rowMs)) return true;
                const rowDate = new Date(rowMs);
                function parseInputDate(str){
                  if(!str) return null;
                  const ms = _parseDateMs(str);
                  if(Number.isFinite(ms)) return new Date(ms);
                  return null;
                }
                function dayBounds(d){
                  const start = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0,0,0,0);
                  const end = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23,59,59,999);
                  return [start, end];
                }
                // Range A..B
                if(q.includes('..')){
                  const [aRaw, bRaw] = q.split('..');
                  const a = parseInputDate(aRaw);
                  const b = parseInputDate(bRaw);
                  if(!a && !b) return true;
                  const minT = a ? (aRaw.trim().length <= 10 ? dayBounds(a)[0] : a) : null;
                  const maxT = b ? (bRaw.trim().length <= 10 ? dayBounds(b)[1] : b) : null;
                  if(minT && rowDate < minT) return false;
                  if(maxT && rowDate > maxT) return false;
                  return true;
                }
                // Comparators
                const ops = ['>=','<=','>','<','='];
                for(const op of ops){
                  if(q.startsWith(op)){
                    const d = parseInputDate(q.slice(op.length).trim());
                    if(!d) return true; // unknown -> keep row
                    const [start, end] = dayBounds(d);
                    if(op==='>=') return rowDate >= start;
                    if(op==='<=') return rowDate <= end;
                    if(op==='>') return rowDate > end;
                    if(op=== '<') return rowDate < start;
                    if(op==='=') return rowDate >= start && rowDate <= end;
                  }
                }
                // Bare date -> match within that day
                const d = parseInputDate(q);
                if(d){
                  const [start, end] = dayBounds(d);
                  return rowDate >= start && rowDate <= end;
                }
                // Fallback substring on ISO
                return String(v).toLowerCase().includes(q.toLowerCase());
              }
            };
            const colTitle = { title: 'Title', field: 'title', sorter: 'string', headerFilter: 'input' };
            const colAuthor = { title: 'Author', field: 'author', sorter: 'string', headerFilter: 'input', width: 180 };
            const colEncounter = { title: 'Encounter', field: 'encounter', sorter: 'string', headerFilter: 'input' };
            const colKw = {
              title: isMobileExplore ? 'Keyword' : 'Keywords', field:'kwHits', sorter:'number', width:110, hozAlign:'right',
              formatter:(cell)=>{ const v=cell.getValue(); return (v==null||Number.isNaN(Number(v)))?'':String(Math.round(Number(v))); },
              headerFilter:'input', headerTooltip:'Type keywords: e.g., pneumonia "heart failure"',
              headerFilterLiveFilter: true,
              headerFilterFunc:(val, rowVal)=>{
                const toks = parseKwQuery(val);
                if(!toks.length) return true; // no query => don't filter
                // Treat unknown kwHits (null/undefined) as included until computed
                if(rowVal == null || rowVal === '') return true;
                const n = Number(rowVal);
                if(Number.isNaN(n)) return true; // unknown
                return n > 0;
              }
            };
            return isMobileExplore ? [ colKw, colDate, colTitle ] : [ colIndexed, colDate, colTitle, colAuthor, colEncounter, colKw ];
          })(),
          initialSort: [ {column: 'date', dir: 'desc'} ]
        });
        console.log('[Documents] Tabulator initialized');
        // Clear any restored header filters from persistence to avoid hiding rows on first load
        try{
          const cols = table.getColumns ? table.getColumns() : [];
          cols.forEach(col => { try{ if(col && col.setHeaderFilterValue) col.setHeaderFilterValue(''); } catch(_e){} });
          if(typeof table.clearFilter === 'function'){ table.clearFilter(); }
        }catch(_e){}
        try{
          table.on('tableBuilt', ()=> { positionDocOverlay();
            // Bind keyword header input for live updates
            try{
              const col = table.getColumn && table.getColumn('kwHits');
              const el = col && col.getElement && col.getElement();
              const inp = el && el.querySelector && el.querySelector('input');
              if(inp && !inp._kwBound){
                inp._kwBound = true;
                inp.addEventListener('input', (e)=>{
                  const val = (e && e.target && e.target.value) || '';
                  try{ if(kwHeaderInputDebounce) clearTimeout(kwHeaderInputDebounce); }catch(_e){}
                  kwHeaderInputDebounce = setTimeout(()=>{ updateKwIndexForHeader(val); }, 200);
                });
              }
            }catch(_e){}
          });
          table.on('renderComplete', ()=> { positionDocOverlay();
            // Re-bind in case header DOM was re-rendered
            try{
              const col = table.getColumn && table.getColumn('kwHits');
              const el = col && col.getElement && col.getElement();
              const inp = el && el.querySelector && el.querySelector('input');
              if(inp && !inp._kwBound){
                inp._kwBound = true;
                inp.addEventListener('input', (e)=>{
                  const val = (e && e.target && e.target.value) || '';
                  try{ if(kwHeaderInputDebounce) clearTimeout(kwHeaderInputDebounce); }catch(_e){}
                  kwHeaderInputDebounce = setTimeout(()=>{ updateKwIndexForHeader(val); }, 200);
                });
              }
            }catch(_e){}
          });
          table.on('columnResized', ()=> positionDocOverlay());
        }catch(_e){}

        // Wire keyword header interactions
        try{
          table.on('headerFilterChanged', (column, value)=>{ try{ if((column && column.getField && column.getField()) === 'kwHits'){ updateKwIndexForHeader(value); } }catch(_e){} });
        }catch(_e){}

        // Observe wrapper resize (user drags bottom edge) and keep table + overlay in sync
        try{
          if(wrapResizeObserver){ try { wrapResizeObserver.disconnect(); } catch(_e){} }
          if(window.ResizeObserver && wrap){
            wrapResizeObserver = new ResizeObserver(()=>{
              try{
                const h = getWrapHeightPx();
                if(table && typeof table.setHeight === 'function'){ table.setHeight(h); }
                positionDocOverlay();
                // Persist wrapper height with debounce
                try{
                  if(saveHeightDebounce) clearTimeout(saveHeightDebounce);
                  saveHeightDebounce = setTimeout(()=>{
                    try{
                      const hh = Math.round(wrap.clientHeight || h || 0);
                      if(Number.isFinite(hh) && hh >= 120 && hh <= 3000){
                        localStorage.setItem('docsWrapHeightPx', String(hh));
                      }
                    }catch(_e){}
                  }, 250);
                }catch(_e){}
              }catch(_e){}
            });
            wrapResizeObserver.observe(wrap);
          } else {
            // Fallback: recalc on window resize
            window.addEventListener('resize', ()=>{
              try{ if(table && typeof table.setHeight === 'function'){ table.setHeight(getWrapHeightPx()); } positionDocOverlay(); }catch(_e){}
            });
          }
        }catch(_e){}

        // Update status when selection changes and remember last selection for keyboard open
        try {
          table.on('rowSelectionChanged', (data, rows)=>{
            updateStatusShowing();
            try { if(rows && rows.length){ lastRowSelected = rows[rows.length-1]; _scrollRowToSecondFromTop(lastRowSelected); } } catch(_e){}
          });
        } catch(_e){}

      } catch(err){
        console.warn('[Documents] Tabulator init failed', err);
      }
    }

    // Keyboard shortcuts on the table container
    try {
      if(canInitTable && !container._keysBound){
        container._keysBound = true;
        // Ensure the container can receive focus/keydown
        if(!container.hasAttribute('tabindex')){ container.setAttribute('tabindex','0'); }
        if(!container.hasAttribute('role')){ container.setAttribute('role','grid'); }

        // Auto-open debounce so rapid key navigation doesn't thrash the viewer
        let _autoOpenTimer = null;
        function scheduleAutoOpen(){
          if(!table) return;
          try { if(_autoOpenTimer) clearTimeout(_autoOpenTimer); } catch(_e){}
          _autoOpenTimer = setTimeout(()=>{
            try {
              const sel = table.getSelectedRows() || [];
              const row = sel && sel.length ? sel[sel.length-1] : lastRowSelected;
              if(row && row.getData){ const d = row.getData(); if(d && d.doc_id){ openDocument({ docId: d.doc_id }); } }
            } catch(_e){}
          }, 100);
        }

        // Helpers for PageUp/PageDown
        function _rowHeight(){
          try { const r = container.querySelector('.tabulator-row'); if(r){ const cs = window.getComputedStyle(r); const h = parseFloat(cs.height||'34'); if(Number.isFinite(h) && h>0) return Math.round(h); } } catch(_e){}
          return 34; // fallback to configured rowHeight
        }
        function _pageJumpCount(){
          const holder = container.querySelector('.tabulator-tableholder');
          const vh = holder ? holder.clientHeight : 320;
          const rh = _rowHeight();
          return Math.max(1, Math.floor(vh / rh) - 1);
        }
        // New: scroll helper to keep selected row second from top
        function _scrollRowToSecondFromTop(row){
          try{
            const holder = container.querySelector('.tabulator-tableholder');
            if(!holder) return;
            const el = row && row.getElement && row.getElement();
            if(!el) return;
            // compute offsetTop relative to holder
            let y = 0, n = el;
            while(n && n !== holder){ y += (n.offsetTop || 0); n = n.offsetParent; }
            const rh = _rowHeight();
            let target = Math.max(0, y - rh);
            holder.scrollTo({ top: target, behavior: 'smooth' });
          }catch(_e){}
        }

        // New: when viewer is open, redirect scroll keys to the viewer and focus it
        function _scrollViewerByKey(k){
          try{
            const overlay = document.getElementById('docViewerOverlay');
            const viewer = document.getElementById('docViewText');
            if(!overlay || overlay.style.display === 'none' || !viewer) return false;
            const map = { ArrowUp: -40, ArrowDown: 40, PageUp: -300, PageDown: 300, Home: -1e9, End: 1e9 };
            if(!(k in map)) return false;
            if(k==='Home' || k==='End'){ viewer.scrollTop = (k==='Home') ? 0 : viewer.scrollHeight; }
            else { viewer.scrollTop = Math.max(0, Math.min(viewer.scrollHeight, viewer.scrollTop + map[k])); }
            if(viewer.focus) viewer.focus();
            return true;
          }catch(_e){ return false; }
        }

        // Build active, navigable RowComponents in current filter/sort order
        function _getActiveRows(){
          if(!table) return [];
          // Preferred: Tabulator API to get rows in current active (sorted+filtered) order
          try{
            if(typeof table.getRows === 'function'){ const rows = table.getRows('active'); if(Array.isArray(rows) && rows.length) return rows; }
          }catch(_e){}
          // Fallback: visible rows still respect sort/filter, but only those in viewport
          try{
            if(typeof table.getRows === 'function'){ const rows = table.getRows(); if(Array.isArray(rows) && rows.length) return rows; }
          }catch(_e){}
          // Last resort: build from active data in current display order, then map to RowComponents
          let data = [];
          try { if(typeof table.getData === 'function') data = table.getData(); } catch(_e){ data = []; }
          if(!data.length) return [];
          const rows = [];
          for(const d of data){
            const id = d && d.doc_id;
            if(!id) continue;
            let r = null;
            try { if(typeof table.getRow === 'function') r = table.getRow(id); } catch(_e){}
            if(!r){ try{ const els = container.querySelectorAll('.tabulator-row'); for(const el of els){ if(el.__row && el.__row.getData && el.__row.getData().doc_id === id){ r = el.__row; break; } } } catch(_e){} }
            if(r) rows.push(r);
          }
          return rows;
        }

        function moveSelection(delta){
          if(!table) return;
          const rows = _getActiveRows();
          if(!rows.length) return;
          // Determine current index within active rows
          let current = -1;
          try{
            const sel = table.getSelectedRows() || [];
            if(sel.length){ current = rows.findIndex(r => r === sel[sel.length-1]); }
          } catch(_e){}
          if(current < 0 && lastRowSelected){
            const lid = lastRowSelected.getData && lastRowSelected.getData().doc_id;
            current = rows.findIndex(r => (r.getData && r.getData().doc_id) === lid);
          }
          if(current < 0) current = 0;
          let next;
          if(delta === Number.POSITIVE_INFINITY) next = rows.length - 1;
          else if(delta === Number.NEGATIVE_INFINITY) next = 0;
          else next = current + (delta || 0);
          if(next < 0) next = 0;
          if(next >= rows.length) next = rows.length - 1;
          const row = rows[next];
          if(!row) return;
          try{
            rows.forEach(r=> r.deselect && r.deselect());
            row.select && row.select();
            lastRowSelected = row;
            // Keep the selected row second from the top in the scroll viewport
            _scrollRowToSecondFromTop(row);
            // Auto-open after navigation debounce
            scheduleAutoOpen();
          } catch(_e){}
          updateStatusShowing();
        }
        // Expose navigation so viewer/global handlers can call it even outside this block scope
        try { window._docsMoveSelection = moveSelection; } catch(_e){}

        container.addEventListener('keydown', (e)=>{
          // If viewer is open, let Up/Down/Page/Home/End scroll the viewer instead of moving selection
          if(!e.ctrlKey && !e.metaKey && !e.altKey){
            const k = e.key;
            if(k==='ArrowUp' || k==='ArrowDown' || k==='Home' || k==='End' || k==='PageUp' || k==='PageDown'){
              if(_scrollViewerByKey(k)){ e.preventDefault(); e.stopPropagation(); return; }
            }
          }
          // Enter -> open selected or last clicked row
          if(e.key === 'Enter'){
            e.preventDefault();
            e.stopPropagation();
            let toOpen = null;
            try{ const sel = table.getSelectedRows() || []; if(sel.length){ toOpen = sel[sel.length-1]; } } catch(_e){}
            if(!toOpen) toOpen = lastRowSelected;
            try{ if(toOpen && toOpen.getData){ const d = toOpen.getData(); if(d && d.doc_id){ openDocument({ docId: d.doc_id }); } } } catch(_e){}
            return;
          }
          // Ctrl/Cmd+A -> select all
          if((e.key === 'a' || e.key === 'A') && (e.ctrlKey || e.metaKey)){
            e.preventDefault();
            e.stopPropagation();
            try { selectAll(); } catch(_e){}
            return;
          }
          // Escape -> clear selection
          if(e.key === 'Escape'){
            e.preventDefault();
            e.stopPropagation();
            try { clearSelection(); } catch(_e){}
            return;
          }
          // Left/Right -> move between notes (navigate selection)
          if(!e.ctrlKey && !e.metaKey && !e.altKey){
            if(e.key === 'ArrowLeft'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(-1); }catch(_e){} }
            if(e.key === 'ArrowRight'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(1); }catch(_e){} }
          }
          // Arrow/Page/Home/End navigation (no modifiers)
          if(!e.ctrlKey && !e.metaKey && !e.altKey){
            if(e.key === 'ArrowUp'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(-1); }catch(_e){} }
            if(e.key === 'ArrowDown'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(1); }catch(_e){} }
            if(e.key === 'Home'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(Number.NEGATIVE_INFINITY); }catch(_e){} }
            if(e.key === 'End'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(Number.POSITIVE_INFINITY); }catch(_e){} }
            if(e.key === 'PageUp'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(-_pageJumpCount()); }catch(_e){} }
            if(e.key === 'PageDown'){ e.preventDefault(); e.stopPropagation(); try{ if(window._docsMoveSelection) window._docsMoveSelection(_pageJumpCount()); }catch(_e){} }
          }
        });

        // Global keyboard support: allow Arrow/Home/End/Enter to work without clicking the table first
        if(!window._docsGlobalKeysBound){
          window._docsGlobalKeysBound = true;
          window.addEventListener('keydown', (e)=>{
            if(!table) return;
            // If the event originated inside the table container, let the container handler manage it
            try{ if(container && (e.target===container || (container.contains && container.contains(e.target)))) return; }catch(_e){}
            const tag = (e.target && e.target.tagName || '').toLowerCase();
            const isEditable = (e.target && (e.target.isContentEditable || tag==='input' || tag==='textarea' || tag==='select'));
            if(isEditable) return;
            if(e.ctrlKey || e.metaKey || e.altKey) return;
            const k = e.key;
            const viewer = document.getElementById('docViewText');
            const overlay = document.getElementById('docViewerOverlay');
            const viewerOpen = !!(overlay && overlay.style.display !== 'none');
            // Respect focus in the note viewer: Up/Down should scroll within the note; Left/Right should navigate notes
            const inViewer = !!(viewer && e.target && (e.target===viewer || (viewer.contains && viewer.contains(e.target))));
            if(inViewer){ if(k==='ArrowLeft'){ try{ if(window._docsMoveSelection) window._docsMoveSelection(-1); }catch(_e){} e.preventDefault(); e.stopPropagation(); return; } if(k==='ArrowRight'){ try{ if(window._docsMoveSelection) window._docsMoveSelection(1); }catch(_e){} e.preventDefault(); e.stopPropagation(); return; } }
            // If viewer is open but focus is elsewhere, redirect scroll keys to the viewer
            if(viewerOpen && (k==='ArrowUp' || k==='ArrowDown' || k==='Home' || k==='End' || k==='PageUp' || k==='PageDown')){
              if(_scrollViewerByKey(k)){ e.preventDefault(); e.stopPropagation(); return; }
            }
            if(k==='ArrowUp' || k==='ArrowDown' || k==='Home' || k==='End' || k==='Enter' || k==='PageUp' || k==='PageDown' || k==='ArrowLeft' || k==='ArrowRight'){
              if(k==='Enter'){
                try{ const sel = table.getSelectedRows() || []; const row = sel && sel.length ? sel[sel.length-1] : lastRowSelected; if(row && row.getData){ const d=row.getData(); if(d && d.doc_id){ openDocument({ docId: d.doc_id }); } } } catch(_e){}
                e.preventDefault(); e.stopPropagation(); return;
              } else {
                const map = { ArrowUp:-1, ArrowDown:1, Home:Number.NEGATIVE_INFINITY, End:Number.POSITIVE_INFINITY, PageUp:-_pageJumpCount(), PageDown:_pageJumpCount(), ArrowLeft:-1, ArrowRight:1 };
                const delta = map[k];
                try{ if(window._docsMoveSelection) window._docsMoveSelection(delta); }catch(_e){}
                e.preventDefault(); e.stopPropagation(); return;
              }
            }
          });
        }

        // On initial load, focus the table if nothing else is focused so arrows work immediately
        setTimeout(()=>{
          try{
            const ae = document.activeElement;
            const isBody = !ae || ae === document.body || ae === document.documentElement;
            if(isBody && container && container.focus){ container.focus(); }
          }catch(_e){}
        }, 0);
      }
    } catch(_e){}

    // Make the note viewer focusable and bind Left/Right navigation while allowing Up/Down to scroll within the note
    try{
      const viewerEl = document.getElementById('docViewText');
      if(viewerEl){
        if(!viewerEl.hasAttribute('tabindex')) viewerEl.setAttribute('tabindex','0');
        if(!viewerEl.hasAttribute('role')) viewerEl.setAttribute('role','document');
        if(!viewerEl._focusBind){ viewerEl._focusBind = true; viewerEl.addEventListener('click', ()=>{ try{ viewerEl.focus(); }catch(_e){} }); }
        if(!viewerEl._keysBind){
          viewerEl._keysBind = true;
          viewerEl.addEventListener('keydown', (e)=>{
            if(e.ctrlKey || e.metaKey || e.altKey) return;
            const k = e.key;
            const nav = (typeof window !== 'undefined' && window._docsMoveSelection) ? window._docsMoveSelection : null;
            if(k==='ArrowLeft'){ e.preventDefault(); e.stopPropagation(); if(typeof nav==='function') nav(-1); }
            else if(k==='ArrowRight'){ e.preventDefault(); e.stopPropagation(); if(typeof nav==='function') nav(1); }
            // Do not intercept ArrowUp/ArrowDown/Home/End/PageUp/PageDown to allow native scrolling within the note
          });
        }
      }
      // Wire tab strip buttons
      const navLeft = document.getElementById('docTabsNavLeft');
      const navRight = document.getElementById('docTabsNavRight');
      if(navLeft && !navLeft._bound){ navLeft._bound = true; navLeft.addEventListener('click', ()=>{ try{ if(window._docsMoveSelection) window._docsMoveSelection(-1); }catch(_e){} }); }
      if(navRight && !navRight._bound){ navRight._bound = true; navRight.addEventListener('click', ()=>{ try{ if(window._docsMoveSelection) window._docsMoveSelection(1); }catch(_e){} }); }
      const prevLabel = document.getElementById('docTabPrevLabel');
      const nextLabel = document.getElementById('docTabNextLabel');
      if(prevLabel && !prevLabel._bound){ prevLabel._bound = true; prevLabel.addEventListener('click', ()=>{ const id = prevLabel.dataset && prevLabel.dataset.docId; if(id) openDocument({ docId: id }); }); }
      if(nextLabel && !nextLabel._bound){ nextLabel._bound = true; nextLabel.addEventListener('click', ()=>{ const id = nextLabel.dataset && nextLabel.dataset.docId; if(id) openDocument({ docId: id }); }); }
      const closeBtn = document.getElementById('docTabClose');
      if(closeBtn && !closeBtn._bound){
        closeBtn._bound = true;
        closeBtn.addEventListener('click', ()=>{ hideDocOverlay(); });
      }
      // Initial tabs state
      updateDocTabs();
    }catch(_e){}

    // When filters/sorts change, reprioritize both prefetch and indexing
    if(table){
      table.on('dataFiltered', function(){
        // Recompute keywords (header filters may have changed) and refresh viewer highlights
        recomputeCurrentKeywords();
        refreshViewerHighlights({ scrollToFirst: false });
        schedulePrefetch(200); scheduleIndexRunner(200);
        updateDocTabs();
      });
      table.on('dataSorted', function(){ schedulePrefetch(200); scheduleIndexRunner(200); updateDocTabs(); });
      table.on('rowSelectionChanged', function(){ try{ updateDocTabs(); }catch(_e){} });
    }

    // Attach infinite scroll handler after table builds DOM
    if(container){ setTimeout(()=> attachInfiniteScroll(container), 0); }

    // Delegated row click fallback to ensure viewer always opens on row clicks
    if(container && !container._rowClickProxyBound){
      container._rowClickProxyBound = true;
      container.addEventListener('click', (ev)=>{
        // Ignore clicks on obvious controls (filters, links, buttons)
        const tag = (ev.target && ev.target.tagName || '').toLowerCase();
        if(tag === 'input' || tag === 'select' || tag === 'textarea' || tag === 'button' || tag === 'a') return;
        const rowEl = ev.target && ev.target.closest ? ev.target.closest('.tabulator-row') : null;
        if(rowEl && table){
          try {
            let row = null;
            // Prefer Tabulator API when available
            if(typeof table.getRowFromElement === 'function'){
              row = table.getRowFromElement(rowEl);
            }
            // Fallback: scan visible rows and match DOM element
            if(!row && typeof table.getRows === 'function'){
              const rows = table.getRows();
              for(const r of rows){ try{ if(r && r.getElement && r.getElement() === rowEl){ row = r; break; } }catch(_e){} }
            }
            if(row){ onRowClick(ev, row); }
            else { try { /* no-op */ } catch(_e){} }
          } catch(_e){ /* ignore */ }
        }
      });
    }

    // Wire buttons
    const btnRefresh = document.getElementById('refreshDocsBtn');
    const btnSelectAll = document.getElementById('selectAllDocsBtn');
    const btnClear = document.getElementById('clearDocSelectionBtn');
    const btnCombine = document.getElementById('combineDocsBtn');
    const btnEstimate = document.getElementById('estimateDocsSizeBtn');
    const btnClearIdx = document.getElementById('clearNotesIndexBtn');
    const btnManualIndex = document.getElementById('indexNotesBtn');
    const searchInput = document.getElementById('notesSearchInput');
    const searchBtn = document.getElementById('notesSearchBtn');
    const askInput = document.getElementById('notesAskInput');
    const askBtn = document.getElementById('notesAskBtn');
    // NEW: Summary button
    const summaryBtn = document.getElementById('notesSummaryBtn');
    // Toggle for auto-index runner (checkbox or button)
    const autoToggle = document.getElementById('autoIndexToggle');
    // New keyword filter controls
    const kwInput = document.getElementById('docsKeywordInput');
    const kwBtn = document.getElementById('docsKeywordBtn');
    const kwClearBtn = document.getElementById('docsKeywordClearBtn');
    // New: Indexed-only checkbox
    const indexedOnlyToggle = document.getElementById('docsShowIndexedOnly');
    // New: Copy button for viewer
    const copyBtn = document.getElementById('copyDocTextBtn');

    // Helper: ensure auto-index toggle label/state is correct on init
    function updateAutoIndexLabel(){
      try{
        const label = document.getElementById('autoIndexLabel');
        const isOn = !autoIndexPaused;
        if(label){ label.textContent = isOn ? 'Auto-Index: On' : 'Auto-Index: Paused'; }
        else if(autoToggle && typeof autoToggle.innerText === 'string'){ autoToggle.innerText = isOn ? 'Auto-Index: On' : 'Auto-Index: Paused'; }
        // Sync checkbox state if applicable
        if(autoToggle && typeof autoToggle.checked === 'boolean'){ autoToggle.checked = isOn; }
      }catch(_e){}
    }
    // Fix: guard keyword Clear button binding (was mistakenly inside updateAutoIndexLabel)
    if(kwClearBtn && !kwClearBtn._bound){
      kwClearBtn._bound = true;
      kwClearBtn.addEventListener('click', ()=>{
        try{ if(kwInput) kwInput.value = ''; }catch(_e){}
        currentKeyword = '';
        recomputeCurrentKeywords();
        applyAllFilters();
        refreshViewerHighlights({ scrollToFirst: false });
      });
    }
    // Live-update viewer highlighting as user types in the standalone keyword box
    if(kwInput && !kwInput._bound){
      kwInput._bound = true;
      kwInput.addEventListener('input', ()=>{
        recomputeCurrentKeywords();
        refreshViewerHighlights({ scrollToFirst: false });
        updateStatusShowing();
      });
    }
    // Fix: guard copy button binding and avoid stray closing brace
    if(copyBtn && !copyBtn._bound){
      copyBtn._bound = true;
      copyBtn.addEventListener('click', async ()=>{
        const viewer = document.getElementById('docViewText');
        const statusEl = document.getElementById('docViewStatus');
        if(!viewer) return;
        const text = viewer.innerText || viewer.textContent || '';
        try{
          if(navigator.clipboard && navigator.clipboard.writeText){
            await navigator.clipboard.writeText(text);
          } else {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
          }
          if(statusEl){ const prev = statusEl.textContent; statusEl.textContent = 'Copied'; setTimeout(()=>{ statusEl.textContent = prev || ''; }, 1200); }
        } catch(e){ if(statusEl){ statusEl.textContent = 'Copy failed'; setTimeout(()=>{ statusEl.textContent=''; }, 1500); } }
      });
    }
    
    if(btnRefresh && !btnRefresh._bound){ btnRefresh._bound = true; btnRefresh.addEventListener('click', fetchDocuments); }
    if(btnSelectAll && !btnSelectAll._bound){ btnSelectAll._bound = true; btnSelectAll.addEventListener('click', selectAll); }
    if(btnClear && !btnClear._bound){ btnClear._bound = true; btnClear.addEventListener('click', clearSelection); }
    if(btnCombine && !btnCombine._bound){ btnCombine._bound = true; btnCombine.addEventListener('click', combineAndLoad); }
    if(btnEstimate && !btnEstimate._bound){ btnEstimate._bound = true; btnEstimate.addEventListener('click', estimateTotalSize); }
    if(btnClearIdx && !btnClearIdx._bound){ btnClearIdx._bound = true; btnClearIdx.addEventListener('click', async ()=>{
      const btn = btnClearIdx; const status = document.getElementById('docsStatus');
      try{
        if(btn){ btn.disabled = true; btn.dataset._orig = btn.textContent; btn.textContent = 'Clearing...'; }
        const res = await fetch('/explore/clear_notes_index', { method:'POST' });
        const j = await res.json();
        if(!res.ok || j.error){ throw new Error(j.error || 'Clear failed'); }
        resetIndexedUI();
        if(status) status.textContent = 'Cleared notes index.';
        const box = document.getElementById('notesSearchResults'); if(box){ box.style.display='none'; box.innerHTML=''; }
      } catch(err){ console.warn('Clear index error', err); const s=document.getElementById('docsStatus'); if(s) s.textContent='Error clearing notes index.'; }
      finally{ if(btn){ btn.textContent = btn.dataset._orig || 'Clear Index'; btn.disabled = false; } }
    }); }

    // Manual index button: index selected notes on demand
    if(btnManualIndex && !btnManualIndex._bound){
      btnManualIndex._bound = true;
      btnManualIndex.addEventListener('click', async ()=>{
        if(!table) return;
        const status = document.getElementById('docsStatus');
        const sel = table.getSelectedData();
        if(!sel || !sel.length){ alert('Select at least one note to index.'); return; }
        const ids = sel.map(d=>d.doc_id).filter(Boolean);
        if(!ids.length) return;
        try{
          if(status) status.textContent = `Indexing ${ids.length} selected note(s)...`;
          btnManualIndex.disabled = true;
          const res = await fetch('/explore/index_notes', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ doc_ids: ids, append: true, skip_if_indexed: true }) });
          const j = await res.json();
          if(!res.ok || j.error){ throw new Error(j.error || 'Index failed'); }
          const results = Array.isArray(j.results) ? j.results : [];
          for(const r of results){
            const id = String(r.doc_id || '');
            if(!id) continue;
            const st = String(r.status || '');
            if(st === 'Indexed' || st === 'Skipped') setIndexState(id, 'Indexed'); else if(st === 'Error') setIndexState(id, 'Error');
          }
          if(status) status.textContent = `Indexed ${results.length || ids.length} selected note(s).`;
        } catch(err){ console.warn('Manual index error', err); if(status) status.textContent = 'Error indexing selected notes.'; }
        finally { btnManualIndex.disabled = false; updateStatusShowing(); }
      });
    }

    // Auto-index toggle
    if(autoToggle && !autoToggle._bound){
      autoToggle._bound = true;
      autoToggle.addEventListener('click', ()=>{
        // If checkbox, checked = On; if button, toggle aria-pressed
        const isOn = typeof autoToggle.checked === 'boolean' ? autoToggle.checked : !(autoIndexPaused);
        autoIndexPaused = !isOn;
        // Update label text if element supports text
        try{
          const label = document.getElementById('autoIndexLabel');
          if(label){ label.textContent = isOn ? 'Auto-Index: On' : 'Auto-Index: Paused'; }
          else if(autoToggle && autoToggle.innerText){ autoToggle.innerText = isOn ? 'Auto-Index: On' : 'Auto-Index: Paused'; }
          if(typeof autoToggle.checked === 'boolean'){ autoToggle.checked = isOn; }
        } catch(_e){}
        if(!autoIndexPaused){ scheduleIndexRunner(0); }
      });
      // Initialize label/state on first load
      updateAutoIndexLabel();
    } else {
      // If toggle exists but was bound earlier (e.g., re-init), still refresh label to current state
      updateAutoIndexLabel();
    }

    // Keep legacy auto-index-before-search/Q&A using the same toggle
    async function autoIndexSelectionIfEnabled(contextLabel){
      if(!table) return;
      if(!autoToggle || (typeof autoToggle.checked === 'boolean' && !autoToggle.checked)) return;
      const sel = table.getSelectedData();
      if(!sel || !sel.length) return; // nothing to index
      const ids = sel.map(d=>d.doc_id).filter(Boolean);
      if(!ids.length) return;
      const status = document.getElementById('docsStatus');
      try{
        if(status) status.textContent = `Indexing selected notes before ${contextLabel}...`;
        const res = await fetch('/explore/index_notes', { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ doc_ids: ids, append: true, skip_if_indexed: true }) });
        const j = await res.json();
        if(!res.ok || j.error){ throw new Error(j.error || 'Index failed'); }
        const results = Array.isArray(j.results) ? j.results : [];
        for(const r of results){
          const id = String(r.doc_id || '');
          if(!id) continue;
          const st = String(r.status || '');
          if(st === 'Indexed' || st === 'Skipped') setIndexState(id, 'Indexed'); else if(st === 'Error') setIndexState(id, 'Error');
        }
      } catch(err){ console.warn('Auto-index error', err); }
      finally { updateStatusShowing(); }
    }

    async function runNotesSearch(){
      const q = (searchInput && searchInput.value || '').trim();
      if(!q){ return; }
      await autoIndexSelectionIfEnabled('search');
      const status = document.getElementById('docsStatus');
      const box = document.getElementById('notesSearchResults');
      try{
        if(status) status.textContent = 'Searching indexed notes...';
        const res = await fetch('/explore/notes_search', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ query: q, top_k: 8 }) });
        const j = await res.json();
        if(!res.ok || j.error){ throw new Error(j.error || 'Search failed'); }
        const items = j.matches || [];
        const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c] || ''));
        if(box){
          if(items.length){
            box.style.display = '';
            box.innerHTML = items.map((it, idx)=>{
              const nid = esc(it.note_id||'');
              const rank = (typeof it.rank === 'number' ? it.rank : (idx+1));
              const score = (typeof it.score === 'number' ? it.score.toFixed(3) : '');
              const date = esc(it.date || '');
              const section = esc(it.section || '');
              const snippet = esc(it.snippet || it.text || '');
              const parts = [`#${rank}`];
              if(score) parts.push(score);
              if(date) parts.push(date);
              if(section) parts.push(section);
              const meta = parts.join(' • ');
              return `<div class="search-hit">`
                + `<div><a href="#" class="open-note-link" data-doc-id="${nid}"><strong>${meta}</strong> open note ${nid}</a></div>`
                + `<pre>${snippet}</pre></div>`;
            }).join('');
          } else { box.style.display=''; box.innerHTML = '<em>No matches.</em>'; }
        }
        if(status) status.textContent = `Search done. ${items.length} match(es).`;
      } catch(err){ console.warn('Notes search error', err); if(status) status.textContent = 'Error searching notes.'; }
    }

    if(searchBtn && !searchBtn._bound){ searchBtn._bound = true; searchBtn.addEventListener('click', runNotesSearch); }
    if(searchInput && !searchInput._bound){ searchInput._bound = true; searchInput.addEventListener('keyup', (e)=>{ if(e.key==='Enter') runNotesSearch(); }); }
    if(askBtn && !askBtn._bound){ askBtn._bound = true; askBtn.addEventListener('click', runNotesAsk); }
    if(askInput && !askInput._bound){ askInput._bound = true; askInput.addEventListener('keyup', (e)=>{ if(e.key==='Enter') runNotesAsk(); }); }
    // NEW: Wire Summary to load prompt and call notes Q&A
    if(summaryBtn && !summaryBtn._bound){
      summaryBtn._bound = true;
      summaryBtn.addEventListener('click', async ()=>{
        const status = document.getElementById('docsStatus');
        const prev = summaryBtn.textContent;
        try{
          summaryBtn.disabled = true; summaryBtn.textContent = 'Summarizing…';
          if(status) status.textContent = 'Loading summary prompt...';
          const r = await fetch('/load_health_summary_prompt', { cache: 'no-store' });
          if(!r.ok){ throw new Error('Prompt not found'); }
          const promptText = await r.text();
          // Delegate to existing flow (runs retrieval and rendering)
          await runNotesAsk(promptText);
        } catch(e){
          if(status) status.textContent = 'Error: could not load summary prompt.';
        } finally {
          summaryBtn.disabled = false; summaryBtn.textContent = prev || 'Summary';
        }
      });
    }

    // Click-to-open for citations in search results and QA context
    const resultsBox = document.getElementById('notesSearchResults');
    const answerBox = document.getElementById('notesAnswerBox');

    if(resultsBox && !resultsBox._openBound){ resultsBox._openBound = true; resultsBox.addEventListener('click', handleOpenClick); }
    if(answerBox && !answerBox._openBound){ answerBox._openBound = true; answerBox.addEventListener('click', handleOpenClick); }

    // Hover-to-preview excerpt popups, with outside-click-to-close
    if(resultsBox && !resultsBox._hoverBound){ resultsBox._hoverBound = true; resultsBox.addEventListener('mouseover', handleCiteHover); resultsBox.addEventListener('mouseout', handleCiteOut); }
    if(answerBox && !answerBox._hoverBound){ answerBox._hoverBound = true; answerBox.addEventListener('mouseover', handleCiteHover); answerBox.addEventListener('mouseout', handleCiteOut); }

    // Container click tracer (to confirm clicks reach the table div)
    if(container){
      if(!container._clickTracer){
        container._clickTracer = true;
        container.addEventListener('click', (ev)=>{
          try { console.log('[Documents] container click', ev.target && ev.target.className); } catch(_e){}
        });
      }
    }

    // Seed index state from server before loading docs, so initial rows can reflect it
    seedIndexStateFromServer().finally(()=>{
      // Load data initially
      fetchDocuments().then(()=>{ try{ applyAllFilters(); recomputeCurrentKeywords(); positionDocOverlay(); }catch(_e){} });
    });

    // Subscribe viewer to the central OPEN_DOCUMENT event once per init (even if table isn't available)
    if(!window._documentsOpenSub){
      window._documentsOpenSub = true;
      on(EVENTS.OPEN_DOCUMENT, async ({ docId, excerptText, excerptIndex } = {}) => {
        if(!docId) return;
        lastOpenedDocId = docId; // remember for re-highlighting
        const gen = generation; // guard against stale writes after reset
        const meta = (allRows || []).find(r => r.doc_id === docId) || { doc_id: docId, title: docId };
        // Unhide viewer if it was closed
        showDocOverlay();
        positionDocOverlay();
        renderDocView(meta);
        const statusEl = document.getElementById('docViewStatus');
        const viewer = document.getElementById('docViewText');
        if(statusEl) statusEl.textContent = 'Loading…';
        setLoadState(docId, 'Loading');
        try{
          // Use cache or fetch
          let lines = (noteCache.get(docId) || {}).lines;
          if(!lines){ lines = await fetchNoteText(docId); }
          if(gen !== generation) return; // stale
          setLoadState(docId, 'Ready');
          // Basic render (title/status handled in renderDocView)
          renderDocView(meta);
          if(statusEl) statusEl.textContent = `${(lines||[]).length} line(s)`;
          // Compute excerpt needle (from explicit text or from matches by index)
          let needle = excerptText && String(excerptText).trim();
          if(!needle && typeof excerptIndex !== 'undefined'){
            const matches = Array.isArray(window.lastNotesQAMatches) ? window.lastNotesQAMatches : [];
            const chunk = matches.find(m => String(m.page) === String(excerptIndex) && m.note_id === docId);
            if(chunk && chunk.text) needle = String(chunk.text).trim();
          }
          // Compose full text and apply combined highlighting
          const full = Array.isArray(lines) ? lines.join('\n') : '';
          // Ensure current keywords reflect latest UI
          recomputeCurrentKeywords();
          const { html, skipped } = buildHighlightedHTML(full, currentKeywords, needle);
          if(viewer){ viewer.innerHTML = html || _escapeHtml(full); }
          // Scroll to excerpt if available; else first keyword match
          const span = viewer ? (viewer.querySelector('.excerpt-highlight') || viewer.querySelector('.doc-keyword-highlight')) : null;
          if(span && span.scrollIntoView){ span.scrollIntoView({behavior:'smooth', block:'center'}); }
          if(statusEl && skipped){ statusEl.textContent = `${statusEl.textContent || ''} • Highlights skipped`; }
          // New: ensure focus lands on the viewer so Arrow keys scroll content
          try { if(viewer && viewer.focus) viewer.focus(); } catch(_e){}
        } catch(e){
          if(gen !== generation) return; // stale
          setLoadState(docId, 'Error');
          if(statusEl) statusEl.textContent = 'Error';
          if(viewer) viewer.textContent = 'Error loading note text.';
        }
        // Always refresh tabs after an open
        try{ updateDocTabs(); }catch(_e){}
      });
    }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else { init(); }

  // Expose for debugging
  window.refreshDocuments = fetchDocuments;
  window.resetDocuments = function(){
    // Cancel all in-flight fetches and bump generation to invalidate async work
    cancelAllFetches();
    generation++;
    // Disconnect wrapper observer if present
    try{ if(wrapResizeObserver){ wrapResizeObserver.disconnect(); wrapResizeObserver = null; } }catch(_e){}
    // Clear caches and UI when switching patients
    try{ noteCache.clear(); } catch(_e){}
    try{ loadState.clear(); } catch(_e){}
    resetIndexedUI();
    prefetchRunning = false;
    if(prefetchDebounce){ clearTimeout(prefetchDebounce); prefetchDebounce = null; }
    if(indexRunnerDebounce){ clearTimeout(indexRunnerDebounce); indexRunnerDebounce = null; }
    autoIndexPaused = true; // keep OFF by default on reset
    allRows = []; loadedCount = 0;
    const status = document.getElementById('docsStatus');
    if(status) status.textContent = '';
    const viewerTitle = document.getElementById('docViewTitle');
    const viewerStatus = document.getElementById('docViewStatus');
    const viewerText = document.getElementById('docViewText');
    if(viewerTitle) viewerTitle.textContent = '';
    if(viewerStatus) viewerStatus.textContent = '';
    if(viewerText) viewerText.textContent = '';
    // Ensure viewer is hidden again on reset; will open on selection
    try{ const ov = document.getElementById('docViewerOverlay'); if(ov){ ov.style.display='none'; } viewerClosed = true; positionDocOverlay(); }catch(_e){}
    // Fully destroy and rebuild the table to avoid Tabulator internal state issues
    try { if(table && table.destroy){ table.destroy(); } } catch(_e){}
    table = null;
    init();
  };
  window._prefetchNotesNow = runPrefetch;
  try { window._documentsNoteCache = noteCache; } catch(_e){}
  try { window.openDocById = openDocById; } catch(_e){}
})();

(function(){
  // === Voice Ask (wake phrase + press-to-hold mic button) ===
  const VOICE_ASK = {
    timer: null,
    active: false,
    mode: null,               // 'wake' | 'manual'
    baselineLen: 0,
    baselineText: '',
    lastWakePos: -1,
    wakeConsumedUpTo: 0,      // do not re-arm on the same earlier wake phrase
    startedRecording: false,
    armedAt: 0,
    cancelAfterMs: 15000,
    intervalIdle: 4000,       // when idle and not active
    intervalArmed: 600,       // when waiting for next sentence
    intervalRecording: 2500,  // when recording but not armed
    cancelTimer: null,
    pointerActive: false
  };
  const WAKE_REGEX = /(hey|hi|hello|ok|okay)\s*,?\s*omar\b\s*,?/i;
  const ENABLE_WAKE_FOR_ASK = false; // Only capture while button is pressed
  const CAPTURE_MAX_WAIT_MS = 6000;   // was 2000; allow more time for backend to flush
  const CAPTURE_POLL_MS = 200;        // poll cadence while waiting to settle
  const GRACE_AFTER_STOP_MS = 500;    // new: small delay after stop to let final chunk land
  const ISOLATE_ASK_FROM_TRANSCRIPT = true; // if we started recording for this mic, trim the live transcript back after capture

  async function fetchScribeStatus(){
    try{
      const r = await fetch('/scribe/status', {cache:'no-store'});
      if(!r.ok) return { is_recording:false, transcript:'', pending_chunks: 0 };
      const j = await r.json();
      return { is_recording: !!j.is_recording, transcript: String(j.transcript||''), pending_chunks: Number(j.pending_chunks||0) };
    }catch(_e){ return { is_recording:false, transcript:'', pending_chunks: 0 }; }
  }
  async function setRecording(on){ try{ await fetch(on? '/scribe/start_recording':'/scribe/stop_recording', { method:'POST' }); }catch(_e){} }
  function startAskGlow(){
    try{ const el = document.getElementById('notesAskInput'); if(el) el.classList.add('glow-pulse'); }catch(_e){}
    try{ const mic = document.getElementById('notesAskMicBtn'); if(mic){ mic.classList.add('mic-active'); mic.style.setProperty('--ask-glow','24px'); } }catch(_e){}
  }
  function stopAskGlow(){
    try{ const el = document.getElementById('notesAskInput'); if(el) el.classList.remove('glow-pulse'); }catch(_e){}
    try{ const mic = document.getElementById('notesAskMicBtn'); if(mic){ mic.classList.remove('mic-active'); mic.style.removeProperty('--ask-glow'); } }catch(_e){}
  }
  function setVoiceStatus(msg){ try{ const s = document.getElementById('notesAskVoiceStatus'); if(s) s.textContent = msg || ''; }catch(_e){} }
  function setHoldVisual(on){
    try{
      const mic = document.getElementById('notesAskMicBtn');
      const container = mic ? mic.closest('.notes-ask-inline') : null;
      if(container){ container.classList.toggle('hold-active', !!on); }
    }catch(_e){}
  }

  function submitAskText(text){
    const askEl = document.getElementById('notesAskInput');
    if(!askEl) return;
    askEl.value = String(text||'').trim();
    // Clear any transient voice status (e.g., "Transcribing…") once the query appears
    try{ const s = document.getElementById('notesAskVoiceStatus'); if(s) s.textContent = ''; }catch(_e){}
    if(typeof window.runNotesAsk === 'function') { try{ window.runNotesAsk(); return; }catch(_e){} }
    try{ const b=document.getElementById('notesAskBtn'); if(b){ b.click(); return; } }catch(__){}
  }

  function extractNextSentence(fromText, startIdx){
    const t = String(fromText||'');
    const s = Math.max(0, Number(startIdx||0));
    if(s >= t.length) return '';
    const CLEAN_PREFIX_RE = /^[\s,;:\-–—"'“”‘’\u200B\u200E\u200F\uFEFF]+/;
    let tail = t.slice(s).replace(CLEAN_PREFIX_RE, '');
    const m = tail.match(/[^\n\.?\!]+(?:[\.?\!]|$)|[^\n]+\n/);
    if(m && m.index != null){
      const seg = tail.slice(0, m.index + m[0].length);
      return seg.replace(CLEAN_PREFIX_RE, '').replace(/\s+/g,' ').trim();
    }
    const words = tail.trim().split(/\s+/);
    if(words.length >= 8) return words.slice(0, Math.min(words.length, 24)).join(' ');
    return '';
  }

  async function waitForFinalDelta(baseLen){
    const t0 = Date.now();
    let lastLen = -1;
    let lastDelta = '';
    while(Date.now() - t0 < CAPTURE_MAX_WAIT_MS){
      const { transcript, pending_chunks } = await fetchScribeStatus();
      const delta = String(transcript||'').slice(Math.max(0, baseLen)).trim();
      const len = delta.length;
      // If transcript stopped changing and there are no pending chunks, treat as final
      if(len > 0 && len === lastLen && pending_chunks === 0){
        return delta;
      }
      lastLen = len;
      lastDelta = delta;
      await new Promise(r=>setTimeout(r, CAPTURE_POLL_MS));
    }
    return lastDelta; // best effort
  }

  async function loop(){
    let nextDelay = VOICE_ASK.intervalIdle;
    try{
      const { is_recording, transcript } = await fetchScribeStatus();
      if(is_recording) nextDelay = VOICE_ASK.intervalRecording;
      // Look for wake phrase only when not manually active
      if(ENABLE_WAKE_FOR_ASK && is_recording && !VOICE_ASK.active){
        const scanFrom = Math.max(0, VOICE_ASK.wakeConsumedUpTo || 0);
        const slice = transcript.slice(scanFrom);
        const relIdx = slice.search(WAKE_REGEX);
        if(relIdx >= 0){
          const m = slice.match(WAKE_REGEX);
          const absIdx = scanFrom + relIdx;
          const endIdx = absIdx + (m && m[0] ? m[0].length : 0);
          VOICE_ASK.wakeConsumedUpTo = Math.max(VOICE_ASK.wakeConsumedUpTo || 0, endIdx);
          VOICE_ASK.active = true; VOICE_ASK.mode = 'wake';
          VOICE_ASK.lastWakePos = endIdx;
          VOICE_ASK.baselineLen = Math.max(endIdx, transcript.length);
          VOICE_ASK.armedAt = Date.now();
          startAskGlow(); setHoldVisual(true); setVoiceStatus('Listening…');
          try{
            const immediate = extractNextSentence(transcript, endIdx);
            if(immediate && immediate.length >= 3){
              submitAskText(immediate);
              stopAskGlow(); setHoldVisual(false);
              VOICE_ASK.active = false; VOICE_ASK.mode = null; VOICE_ASK.startedRecording = false; VOICE_ASK.lastWakePos = -1; VOICE_ASK.baselineLen = transcript.length; VOICE_ASK.armedAt = 0;
              setVoiceStatus('Sent');
            }
          }catch(_e){}
        }
      }
      if(VOICE_ASK.active){
        // In manual (press-and-hold) mode, do not submit inside the loop; wait for release
        if(VOICE_ASK.mode === 'wake'){
          nextDelay = VOICE_ASK.intervalArmed;
          const startAt = Math.max(VOICE_ASK.baselineLen, VOICE_ASK.lastWakePos>=0? VOICE_ASK.lastWakePos : 0);
          const next = extractNextSentence(transcript, startAt);
          if(next && next.length >= 3){
            submitAskText(next);
            stopAskGlow(); setHoldVisual(false);
            VOICE_ASK.active = false; VOICE_ASK.mode = null; VOICE_ASK.startedRecording = false; VOICE_ASK.lastWakePos = -1; VOICE_ASK.baselineLen = transcript.length; VOICE_ASK.armedAt = 0;
            setVoiceStatus('Sent');
          } else if(VOICE_ASK.armedAt && Date.now() - VOICE_ASK.armedAt > VOICE_ASK.cancelAfterMs){
            VOICE_ASK.active = false; VOICE_ASK.mode = null; VOICE_ASK.startedRecording = false; VOICE_ASK.lastWakePos = -1; VOICE_ASK.armedAt = 0;
            stopAskGlow(); setHoldVisual(false); setVoiceStatus('Timed out');
          }
        } else {
          // manual hold: keep a gentle glow; poll faster but no auto-submit
          nextDelay = VOICE_ASK.intervalArmed;
        }
      }
    } finally {
      VOICE_ASK.timer = setTimeout(loop, nextDelay);
    }
  }

  async function onAskMicPressStart(ev){
    if(ev){ ev.preventDefault && ev.preventDefault(); ev.stopPropagation && ev.stopPropagation(); }
    if(VOICE_ASK.active) return; // already listening
    VOICE_ASK.active = true; VOICE_ASK.mode = 'manual'; VOICE_ASK.lastWakePos = -1; VOICE_ASK.armedAt = Date.now();
    // Start auto-cancel in case pointerup is missed
    try{ if(VOICE_ASK.cancelTimer) clearTimeout(VOICE_ASK.cancelTimer); }catch(_e){}
    VOICE_ASK.cancelTimer = setTimeout(()=>{ try{ onAskMicPressEnd(); }catch(_e){} }, Math.max(3000, Number(VOICE_ASK.cancelAfterMs)||15000));

    const { is_recording, transcript } = await fetchScribeStatus();
    // Harden baseline: clamp to current transcript length (avoid out-of-range if server trimmed)
    const curLen = String(transcript||'').length;
    VOICE_ASK.baselineLen = curLen;
    VOICE_ASK.baselineText = String(transcript||'');

    if(!is_recording){ try{ await setRecording(true); VOICE_ASK.startedRecording = true; }catch(_e){ VOICE_ASK.startedRecording = false; } }
    else { VOICE_ASK.startedRecording = false; }

    startAskGlow(); setHoldVisual(true); setVoiceStatus('Listening…');
    if(!VOICE_ASK.timer){ loop(); }
  }

  async function onAskMicPressEnd(ev){
    if(ev){ ev.preventDefault && ev.preventDefault(); }
    try{ if(VOICE_ASK.cancelTimer){ clearTimeout(VOICE_ASK.cancelTimer); VOICE_ASK.cancelTimer = null; } }catch(_e){}
    if(!VOICE_ASK.active && !VOICE_ASK.startedRecording){ setHoldVisual(false); stopAskGlow(); setVoiceStatus(''); return; }

    // UI feedback on release: keep visual off, but show that we're finalizing audio
    stopAskGlow(); setHoldVisual(false); setVoiceStatus('Transcribing…');

    // Stop recording only if we started it
    if(VOICE_ASK.startedRecording){ try{ await setRecording(false); }catch(_e){} }

    // Post-stop grace: let backend flush final chunk
    try{ await new Promise(r=>setTimeout(r, GRACE_AFTER_STOP_MS)); }catch(_e){}

    // Clamp baseline to current transcript length in case server trimmed text
    try{ const st = await fetchScribeStatus(); VOICE_ASK.baselineLen = Math.min(Math.max(0, VOICE_ASK.baselineLen||0), String(st.transcript||'').length); }catch(_e){}

    // Wait briefly for any trailing transcription to land, then capture
    let captured = '';
    try{
      captured = await waitForFinalDelta(Math.max(0, VOICE_ASK.baselineLen||0));
      if(captured){
        // Prefer the first sentence; fallback to full captured
        captured = extractNextSentence(captured, 0) || captured;
      }
    }catch(_e){}

    // Optionally trim global transcript back to what it was before our press
    try{
      if(ISOLATE_ASK_FROM_TRANSCRIPT && VOICE_ASK.startedRecording && typeof VOICE_ASK.baselineText === 'string'){
        await fetch('/scribe/set_live_transcript', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ text: VOICE_ASK.baselineText }) });
      }
    }catch(_e){}

    // Reset flags
    VOICE_ASK.active = false; VOICE_ASK.mode = null; VOICE_ASK.armedAt = 0; VOICE_ASK.lastWakePos = -1;
    VOICE_ASK.startedRecording = false;

    // Submit after stabilization
    if(captured && captured.length >= 3){ submitAskText(captured); }
  }

  function install(){
    try{
      const mic = document.getElementById('notesAskMicBtn');
      if(mic && !mic._voiceAskBound){
        mic._voiceAskBound = true;
        // Pointer-based binding (covers mouse, pen, touch)
        mic.addEventListener('pointerdown', (e)=>{
          try{ mic.setPointerCapture && mic.setPointerCapture(e.pointerId); }catch(_e){}
          VOICE_ASK.pointerActive = true;
          onAskMicPressStart(e);
        });
        const end = (e)=>{
          if(!VOICE_ASK.pointerActive) return;
          VOICE_ASK.pointerActive = false;
          onAskMicPressEnd(e);
        };
        mic.addEventListener('pointerup', end);
        mic.addEventListener('pointercancel', end);
        mic.addEventListener('lostpointercapture', end);
        // Keyboard fallback (Space/Enter)
        mic.tabIndex = mic.tabIndex || 0;
        mic.addEventListener('keydown', (e)=>{
          if(e.code === 'Space' || e.code === 'Enter'){ e.preventDefault(); if(!VOICE_ASK.active){ onAskMicPressStart(e); } }
        });
        mic.addEventListener('keyup', (e)=>{
          if(e.code === 'Space' || e.code === 'Enter'){ e.preventDefault(); if(VOICE_ASK.active){ onAskMicPressEnd(e); } }
        });
      }
    }catch(_e){}
    if(!VOICE_ASK.timer){ loop(); }
    try{ window.addEventListener('beforeunload', ()=>{ try{ if(VOICE_ASK.cancelTimer) clearTimeout(VOICE_ASK.cancelTimer); }catch(_e){} }, {once:true}); }catch(_e){}
  }

  try{ if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', install, {once:true}); } else { install(); } }catch(_e){ install(); }
})();