(function(){
  window.WorkspaceModules = window.WorkspaceModules || {};
  const MODULE_NAME = 'Documents';

  // Documents module with server-side pagination, debounced keyword search, optional grouping, and a keyboard-enabled viewer.

  function _formatDate(iso){ try{ if(!iso) return ''; const d = new Date(iso); if(isNaN(d)) return iso; return d.toLocaleString(); }catch(e){return iso||'';} }
  function escapeHtml(s){ if(s===null||s===undefined) return ''; return String(s).replace(/[&<>"]/g, function(c){ return ({'&':'&amp;','<':'&lt;','>':'&gt;', '"':'&quot;'}[c]); }); }
  function _debounce(fn, ms){ let t=null; return function(...args){ clearTimeout(t); t=setTimeout(()=>fn.apply(this,args), ms); } }

  function renderSkeleton(container){
    container.innerHTML = `
      <div class="documents-module" style="height:100%; display:flex; flex-direction:column; position:relative;">
        <div style="display:flex; gap:8px; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
          <input id="docsKeywordInput" type="text" placeholder="Keyword search (full text + title/author/type)" style="flex:1; min-width:160px;" />
          <button id="docsClearBtn" title="Clear search">Clear</button>
          <label style="margin-left:8px; display:flex; align-items:center; gap:4px;">
            <input type="checkbox" id="docsGroupToggle" /> Group by type
          </label>
          <label style="margin-left:auto; display:flex; align-items:center; gap:6px;">
            <span>Sort</span>
            <select id="docsSort">
              <option value="date:desc">Date ↓</option>
              <option value="date:asc">Date ↑</option>
              <option value="title:asc">Title A→Z</option>
              <option value="title:desc">Title Z→A</option>
              <option value="author:asc">Author A→Z</option>
              <option value="author:desc">Author Z→A</option>
              <option value="type:asc">Type A→Z</option>
              <option value="type:desc">Type Z→A</option>
              <option value="encounter:asc">Encounter A→Z</option>
              <option value="encounter:desc">Encounter Z→A</option>
            </select>
          </label>
          <span id="docsStatus" style="font-size:0.9em; color:#555;"></span>
          <span id="docsSizeEstimate" style="font-size:0.9em; color:#555;"></span>
        </div>
        <div id="documentsTable" style="flex:1; overflow:auto; padding:4px; border-top:1px solid #eee;"></div>
        <div style="margin-top:6px; display:flex; gap:8px; justify-content:flex-end;">
          <button id="docsLoadMoreBtn" style="display:none;">Load more</button>
        </div>
        <div id="docViewerOverlay" class="doc-viewer-overlay" style="display:none;">
          <div id="docTabsBar" class="doc-tabs">
            <button id="docTabLeft" class="doc-tab" title="Previous">Prev</button>
            <button id="docTabCurrent" class="doc-tab current" title="Current">Current</button>
            <button id="docTabRight" class="doc-tab" title="Next">Next</button>
            <button id="docTabClose" class="doc-tab-close" title="Close">×</button>
          </div>
          <div class="doc-viewer-wrap">
            <pre id="docViewText" class="doc-viewer"></pre>
          </div>
          <div id="docViewStatus" class="doc-viewer-status"></div>
        </div>
      </div>
    `;
  }

  function renderRows(tableEl, items, mode, opts){
    // opts: { group:boolean }
    const group = !!(opts && opts.group);
    const buildRow = (it)=>{
      const title = it.title || it.localTitle || it.displayName || '(Untitled)';
      const date = it.date || it.referenceDateTime || it.entered || it.dateTime || '';
      const facility = it.facility || '';
      const dtype = it.documentType || it.type || '';
      const docId = it.docId || it.doc_id || '';
      const snippet = (mode==='search' && it.snippet) ? `<div class="doc-snippet" style="color:#666; font-size:0.85em; margin-top:2px;">${escapeHtml(it.snippet)}</div>` : '';
      return `<tr class="doc-row" data-docid="${encodeURIComponent(docId)}">
        <td style="padding:6px; border-bottom:1px solid #f3f3f3;">
          <div style="font-weight:500;">${escapeHtml(title)}</div>
          ${snippet}
        </td>
        <td style="padding:6px; border-bottom:1px solid #f3f3f3;">${escapeHtml(_formatDate(date))}</td>
        <td style="padding:6px; border-bottom:1px solid #f3f3f3;">${escapeHtml(facility)}</td>
        <td style="padding:6px; border-bottom:1px solid #f3f3f3;">${escapeHtml(dtype)}</td>
      </tr>`;
    };
    let html = '<table class="documents-list" style="width:100%; border-collapse:collapse; font-size:0.95em;">';
    html += '<thead><tr style="text-align:left; border-bottom:1px solid #ddd;"><th style="padding:6px; width:44%">Title</th><th style="padding:6px; width:18%">Date</th><th style="padding:6px; width:18%">Facility</th><th style="padding:6px; width:20%">Type</th></tr></thead>';
    html += '<tbody>';
    if (group){
      const byType = new Map();
      for(const it of items){
        const t = (it.documentType || it.type || 'Other');
        if(!byType.has(t)) byType.set(t, []);
        byType.get(t).push(it);
      }
      const types = Array.from(byType.keys()).sort((a,b)=> String(a).localeCompare(String(b)));
      for(const t of types){
        html += `<tr><td colspan="4" style="padding:6px 4px; background:#f6f6f6; border-bottom:1px solid #e7e7e7; font-weight:600;">${escapeHtml(t)}</td></tr>`;
        const arr = byType.get(t).slice().sort((a,b)=> String(a.title||'').localeCompare(String(b.title||'')));
        for(const it of arr){ html += buildRow(it); }
      }
    } else {
      for(const it of items){ html += buildRow(it); }
    }
    html += '</tbody></table>';
    tableEl.innerHTML = html;
  }

  async function fetchList(params){
    return window.Api.list('documents', params || {});
  }
  async function fetchSearch(params){
    return window.Api.documentsSearch(params || {});
  }

  async function fetchNoteText(docId){
    try{
      const body = await window.Api.documentsTextBatch([docId]);
      const arr = (body && body.notes) ? body.notes : [];
      if(Array.isArray(arr) && arr.length){
        const lines = arr[0].text || [];
        return Array.isArray(lines) ? lines.join('\n') : String(lines||'');
      }
      return '';
    }catch(e){ return ''; }
  }

  function escapeRegExp(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  function highlightHtml(text, query){
    try{
      if(!text || !query) return escapeHtml(text||'');
      const raw = String(text);
      const escaped = escapeHtml(raw);
      // Build tokens from query (ignore short < 3)
      const terms = Array.from(new Set(String(query).toLowerCase().match(/[A-Za-z0-9']+/g) || []))
        .filter(t => t && t.length >= 3);
      if(!terms.length) return escaped;
      let out = escaped;
      // Replace tokens as word-prefix matches; do phrases later if needed
      for(const t of terms){
        const re = new RegExp(`\\b(${escapeRegExp(t)}[A-Za-z0-9']*)`, 'gi');
        out = out.replace(re, '<mark class="doc-keyword-highlight">$1</mark>');
      }
      return out;
    }catch(_e){ return escapeHtml(text||''); }
  }

  function installViewerKeys(overlay, getNav, onClose){
    const handler = (e)=>{
      if (overlay.style.display === 'none') return;
      if (e.key === 'ArrowLeft'){ try{ getNav().prev(); }catch(_e){} e.preventDefault(); }
      if (e.key === 'ArrowRight'){ try{ getNav().next(); }catch(_e){} e.preventDefault(); }
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown'){
        try{ const pre = overlay.querySelector('#docViewText'); if(pre){ const delta = (e.key==='ArrowUp' ? -80 : 80); pre.scrollTop = Math.max(0, pre.scrollTop + delta); e.preventDefault(); } }catch(_e){}
      }
      if (e.key === 'Escape'){ try{ onClose(); }catch(_e){} }
    };
    try{ document.addEventListener('keydown', handler); }catch(_e){}
    return ()=>{ try{ document.removeEventListener('keydown', handler); }catch(_e){} };
  }

  window.WorkspaceModules[MODULE_NAME] = {
    _container: null,
    _mode: 'list', // 'list' | 'search'
    _sort: 'date:desc',
    _group: false,
    _items: [], // currently visible page(s)
    _next: null,
    _idOrder: [], // ordered docIds for nav
    _currentIndex: -1,
    _unbindKeys: null,
  _lastQuery: '',
    async render(container){
      this._container = container;
      renderSkeleton(container);
      const table = container.querySelector('#documentsTable');
      const loadMore = container.querySelector('#docsLoadMoreBtn');
      const statusEl = container.querySelector('#docsStatus');
      const sizeEl = container.querySelector('#docsSizeEstimate');
      const sortSel = container.querySelector('#docsSort');
      const groupToggle = container.querySelector('#docsGroupToggle');
      const searchInput = container.querySelector('#docsKeywordInput');
      const clearBtn = container.querySelector('#docsClearBtn');

      const setStatus = (s)=>{ if(statusEl) statusEl.textContent = s||''; };
      const setSize = (n, total)=>{ if(sizeEl) sizeEl.textContent = (total!=null) ? `Showing ${n} of ${total}` : `Showing ${n}`; };

      const wireRows = ()=>{
        table.querySelectorAll('.doc-row').forEach(tr => {
          tr.addEventListener('click', async () => {
            const docId = decodeURIComponent(tr.dataset.docid || '') || '';
            if(!docId) return;
            this._currentIndex = this._idOrder.indexOf(docId);
            if (this._currentIndex < 0){ this._idOrder = this._items.map(it => (it.docId || it.doc_id || '')); this._currentIndex = this._idOrder.indexOf(docId); }
            await this._openViewer(docId);
          });
        });
      };

      const renderAndWire = (mode, res)=>{
        this._mode = mode;
        this._next = (res && res.next) ? res.next : null;
        const items = Array.isArray(res && res.items) ? res.items : [];
        if (this._append){
          this._items = this._items.concat(items);
        } else {
          this._items = items;
          table.scrollTop = 0;
        }
        // maintain nav order by currently visible list
        this._idOrder = this._items.map(it => (it.docId || it.doc_id || '')).filter(Boolean);
        renderRows(table, this._items, mode, { group: this._group });
        wireRows();
        setStatus('');
        setSize(this._items.length, res ? res.total : null);
        loadMore.style.display = this._next ? 'inline-block' : 'none';

        // Hint the backend to embed the top 50 in the current view (policy: recent/sorted/search results)
        try{
          const top50 = this._idOrder.slice(0, 50);
          if (top50.length && window.Api && typeof window.Api.embedDocuments === 'function'){
            window.Api.embedDocuments(top50).catch(()=>{});
          }
        }catch(_e){}
      };

      const loadList = async (append)=>{
        this._append = !!append;
        setStatus('Loading...');
        try{
          this._lastQuery = '';
          const params = { sort: this._sort };
          if (append && this._next) params.offset = this._next;
          const res = await fetchList(params);
          renderAndWire('list', res);
        }catch(e){ table.innerHTML = `<div class="module-error">Failed to load documents: ${escapeHtml((e&&e.message)||e)}</div>`; setStatus(''); }
      };
      const loadSearch = async (q, append)=>{
        this._append = !!append;
        if (!q || !q.trim()){ await loadList(false); return; }
        setStatus('Searching...');
        try{
          this._lastQuery = q.trim();
          const params = { q: q.trim(), limit: 50 };
          if (append && this._next) params.offset = this._next;
          const res = await fetchSearch(params);
          renderAndWire('search', res);
        }catch(e){ table.innerHTML = `<div class=\"module-error\">Failed to search documents: ${escapeHtml((e&&e.message)||e)}</div>`; setStatus(''); }
      };

      // Events
      loadMore.onclick = async ()=>{ if (this._mode==='search'){ await loadSearch(searchInput.value, true); } else { await loadList(true); } };
      sortSel.onchange = async ()=>{ this._sort = sortSel.value || 'date:desc'; if (this._mode==='list'){ await loadList(false); } };
      groupToggle.onchange = ()=>{ this._group = !!groupToggle.checked; renderRows(table, this._items, this._mode, { group: this._group }); wireRows(); };
      clearBtn.onclick = async ()=>{ searchInput.value=''; await loadList(false); };
      const debouncedSearch = _debounce(async ()=>{ const q=(searchInput.value||'').trim(); if (q){ await loadSearch(q, false); } else { await loadList(false); } }, 300);
      searchInput.addEventListener('input', debouncedSearch);

      // Infinite scroll
      table.addEventListener('scroll', async ()=>{
        try{
          if (!this._next) return;
          const nearBottom = (table.scrollTop + table.clientHeight + 80) >= table.scrollHeight;
          if (nearBottom){ if (this._mode==='search'){ await loadSearch(searchInput.value, true); } else { await loadList(true); } }
        }catch(_e){}
      });

      // Initial load
      await loadList(false);
    },
    async _openViewer(docId){
      const overlay = this._container.querySelector('#docViewerOverlay') || document.getElementById('docViewerOverlay');
      if(!overlay) return;
      const status = overlay.querySelector('#docViewStatus');
      const pre = overlay.querySelector('#docViewText');
      const tabL = overlay.querySelector('#docTabLeft');
      const tabC = overlay.querySelector('#docTabCurrent');
      const tabR = overlay.querySelector('#docTabRight');

      // Helpers to access items/titles
      const getItemByIndex = (idx)=>{ return (idx>=0 && idx < this._items.length) ? this._items[idx] : null; };
      const getTitle = (it)=>{ return (it && (it.title || it.localTitle || it.displayName)) || '(Untitled)'; };
      const updateTabs = ()=>{
        const itCur = getItemByIndex(this._currentIndex);
        const itPrev = getItemByIndex(this._currentIndex-1);
        const itNext = getItemByIndex(this._currentIndex+1);
        if (tabC) { tabC.textContent = getTitle(itCur); }
        if (tabL) {
          tabL.textContent = itPrev ? getTitle(itPrev) : '';
          tabL.disabled = !itPrev;
          tabL.style.opacity = itPrev ? '1' : '0.6';
        }
        if (tabR) {
          tabR.textContent = itNext ? getTitle(itNext) : '';
          tabR.disabled = !itNext;
          tabR.style.opacity = itNext ? '1' : '0.6';
        }
      };
      updateTabs();
      overlay.style.display = 'block';
      if (status) status.textContent = 'Loading document...';
      if (pre) { pre.textContent=''; pre.scrollTop = 0; }

      // Nav helpers
      const canPrev = ()=> (this._currentIndex > 0);
      const canNext = ()=> (this._currentIndex >=0 && this._currentIndex < this._idOrder.length-1);
      const doPrev = async ()=>{ if (!canPrev()) return; this._currentIndex--; updateTabs(); await this._openViewer(this._idOrder[this._currentIndex]); };
      const doNext = async ()=>{ if (!canNext()) return; this._currentIndex++; updateTabs(); await this._openViewer(this._idOrder[this._currentIndex]); };
      if (tabL) tabL.onclick = doPrev;
      if (tabR) tabR.onclick = doNext;
      if (tabC) tabC.onclick = ()=>{}; // no-op
      const closeBtn = overlay.querySelector('#docTabClose');
      const doClose = ()=>{ try{ overlay.style.display='none'; }catch(_e){} try{ if(this._unbindKeys) this._unbindKeys(); }catch(_e){} };
      if (closeBtn) closeBtn.onclick = doClose;
      if (this._unbindKeys) { try{ this._unbindKeys(); }catch(_e){} }
      this._unbindKeys = installViewerKeys(overlay, ()=>({ prev: doPrev, next: doNext }), doClose);

      // Fetch text via text-batch
      try{
        const txt = await fetchNoteText(docId);
        if (pre){
          if (this._mode === 'search' && this._lastQuery){
            pre.innerHTML = highlightHtml(txt || '', this._lastQuery);
          } else {
            pre.textContent = txt || '(No document text available)';
          }
        }
      }catch(_e){ if(pre) pre.textContent = '(Failed to load document text)'; }
      if (status) status.textContent = '';
    },
    refresh(){ try{ if(this._container) this.render(this._container); }catch(_e){} },
    destroy(){ try{ if(this._container){ const ov = this._container.querySelector('#docViewerOverlay'); if(ov) ov.style.display='none'; this._container.innerHTML=''; if(this._unbindKeys) this._unbindKeys(); } }catch(_e){} }
  };
})();
