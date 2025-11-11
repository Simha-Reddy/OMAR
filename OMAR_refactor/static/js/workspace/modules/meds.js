// filepath: static/workspace/modules/meds.js
(function(){
  window.WorkspaceModules = window.WorkspaceModules || {};
  const MODULE_NAME = 'Meds';
  const controllers = new Set();
  const state = {
    items: [],
    filtered: [],
    sortKey: 'startTs',
    sortDir: 'desc',
    days: 365,
    status: 'ALL',
    search: '',
    loading: false,
    error: '',
    columnWidths: {}
  };
  const COLUMNS = [
    { key: 'name', label: 'Medication', type: 'text', width: '32%' },
    { key: 'statusLabel', label: 'Status', type: 'text', width: '16%' },
    { key: 'startTs', label: 'Start Date', type: 'date', width: '16%' },
    { key: 'endTs', label: 'End Date', type: 'date', width: '16%' },
    { key: 'durationDays', label: 'Days', type: 'number', width: '12%' }
  ];

  let containerRef = null;
  let tableBody = null;
  let statusEl = null;
  let searchInput = null;
  let daysSelect = null;
  let statusSelect = null;
  let headerRow = null;

  function ensureSharedStyles(){
    const id = 'workspace-shared-detail-styles';
    if(document.getElementById(id)) return;
    const style = document.createElement('style');
    style.id = id;
    style.textContent = `
      .ws-col-resize-handle { position:absolute; top:0; right:-3px; width:8px; cursor:col-resize; user-select:none; height:100%; }
      .ws-col-resize-handle::after { content:''; position:absolute; top:0; bottom:0; left:3px; width:2px; background:transparent; transition:background 0.15s ease; }
      th:hover .ws-col-resize-handle::after { background:rgba(0,0,0,0.18); }
      .ws-detail-modal { position:fixed; inset:0; display:none; align-items:center; justify-content:center; z-index:10000; font-family:inherit; }
      .ws-detail-modal[aria-hidden="true"] { display:none; }
      .ws-detail-modal .ws-modal-backdrop { position:absolute; inset:0; background:rgba(0,0,0,0.42); }
      .ws-detail-modal .ws-modal-panel { position:relative; width:min(880px, 92%); max-height:88vh; background:#ffffff; border-radius:10px; box-shadow:0 18px 44px rgba(15,23,42,0.45); display:flex; flex-direction:column; overflow:hidden; }
      .ws-detail-modal .ws-modal-header { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:1px solid #d9dee7; background:#f5f7fb; }
      .ws-detail-modal .ws-modal-title { font-weight:600; color:#1f2933; margin-right:12px; flex:1; }
      .ws-detail-modal .ws-modal-close { border:none; background:transparent; font-size:18px; cursor:pointer; padding:4px 8px; color:#1f2933; }
  .ws-detail-modal pre { margin:0; padding:16px; flex:1; overflow:auto; background:#0f172a; color:#e2e8f0; font-size:13px; line-height:1.5; }
  .labs-table-wrap th, .labs-table-wrap td,
  .meds-table-wrap th, .meds-table-wrap td,
  .documents-module th, .documents-module td { box-sizing:border-box; }
    `;
    document.head.appendChild(style);
  }

  function ensureStyles(){
    ensureSharedStyles();
    const id = 'meds-module-styles';
    if(document.getElementById(id)) return;
    const style = document.createElement('style');
    style.id = id;
    style.textContent = `
      .meds-module { display:flex; flex-direction:column; gap:12px; height:100%; }
      .meds-module .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
      .meds-module .controls select,
      .meds-module .controls input[type="search"] { padding:4px 6px; font-size:0.95em; }
      .meds-module .controls label { display:flex; align-items:center; gap:4px; font-size:0.92em; color:#444; }
      .meds-table-wrap { flex:1; min-height:240px; border:1px solid #e1e1e1; border-radius:8px; overflow:auto; background:#fff; display:flex; flex-direction:column; max-height:100%; }
  .meds-table-wrap table { width:auto; min-width:100%; border-collapse:collapse; font-size:0.95em; table-layout:auto; }
      .meds-table-wrap thead { background:linear-gradient(180deg,#f5f7fb,#e8ecf5); }
      .meds-table-wrap th { text-align:left; padding:8px 10px; font-weight:600; color:#31405f; cursor:pointer; user-select:none; border-bottom:1px solid #d5dbe7; position:relative; }
      .meds-table-wrap th.sort-asc::after { content:'^'; margin-left:6px; font-size:0.75em; }
      .meds-table-wrap th.sort-desc::after { content:'v'; margin-left:6px; font-size:0.75em; }
      .meds-table-wrap td { padding:8px 10px; border-bottom:1px solid #eef1f6; vertical-align:top; color:#2b2b2b; }
      .meds-table-wrap tbody tr:hover { background:#f7f9fc; }
      .med-name { font-weight:600; color:#1f4e92; }
      .med-meta { color:#687086; font-size:0.85em; margin-top:2px; }
      .med-status { font-weight:600; padding:2px 6px; border-radius:12px; font-size:0.85em; background:#eef3ff; color:#1f4e92; display:inline-block; }
      .med-status.pending { background:#fff4e5; color:#a86a12; }
      .med-status.completed { background:#e8f5e9; color:#2e7d32; }
      .med-status.stopped { background:#fdecea; color:#c62828; }
      .meds-empty-row td { text-align:center; color:#777; padding:18px 10px; }
      .meds-module .status-line { font-size:0.9em; color:#4b4b4b; display:flex; gap:12px; align-items:center; }
      .meds-module .status-line strong { color:#1f4e92; }
      @media (max-width: 768px){
        .meds-table-wrap th, .meds-table-wrap td { padding:6px 8px; font-size:0.9em; }
        .meds-module .controls { gap:6px; }
      }
    `;
    document.head.appendChild(style);
  }

  function cancelAll(){
    for(const ctrl of Array.from(controllers)){
      try{ ctrl.abort(); }catch(_e){}
    }
    controllers.clear();
  }

  function escapeHtml(val){
    if(val == null) return '';
    return String(val).replace(/[&<>"']/g, (c)=> ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  }

  function formatDate(iso){
    if(!iso) return '';
    try{
      const d = new Date(iso);
      if(Number.isNaN(d.getTime())) return iso;
      return d.toLocaleDateString();
    }catch(_e){ return iso; }
  }

  function getSharedModal(){
    if(window.__WorkspaceJsonModal) return window.__WorkspaceJsonModal;
    const wrapper = document.createElement('div');
    wrapper.id = 'workspace-json-modal';
    wrapper.className = 'ws-detail-modal';
    wrapper.setAttribute('aria-hidden', 'true');
    wrapper.innerHTML = `
      <div class="ws-modal-backdrop"></div>
      <div class="ws-modal-panel" role="dialog" aria-modal="true" aria-label="Detail">
        <div class="ws-modal-header">
          <span class="ws-modal-title">Detail</span>
          <button type="button" class="ws-modal-close" aria-label="Close">x</button>
        </div>
        <pre class="ws-modal-body"></pre>
      </div>
    `;
    document.body.appendChild(wrapper);
    const backdrop = wrapper.querySelector('.ws-modal-backdrop');
    const closeBtn = wrapper.querySelector('.ws-modal-close');
    const titleEl = wrapper.querySelector('.ws-modal-title');
    const pre = wrapper.querySelector('pre');

    const close = ()=>{
      wrapper.style.display = 'none';
      wrapper.setAttribute('aria-hidden', 'true');
    };
    const open = (title, raw)=>{
      if(titleEl) titleEl.textContent = title || 'Detail';
      if(pre){
        try{
          pre.textContent = typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2);
          pre.scrollTop = 0;
        }catch(_e){ pre.textContent = '(Unable to display raw data)'; }
      }
      wrapper.style.display = 'flex';
      wrapper.removeAttribute('aria-hidden');
    };
    if(backdrop) backdrop.addEventListener('click', close);
    if(closeBtn) closeBtn.addEventListener('click', close);
    const onKey = (ev)=>{ if(ev.key === 'Escape'){ close(); } };
    document.addEventListener('keydown', onKey);
    const api = { open, close };
    wrapper.__modalApi = api;
    window.__WorkspaceJsonModal = api;
    return api;
  }

  function openDetailModal(title, raw){
    try{
      const modal = getSharedModal();
      modal.open(title, raw);
    }catch(_e){}
  }

  function applyColumnWidths(){
    if(!headerRow) return;
    const rows = tableBody ? Array.from(tableBody.querySelectorAll('tr')) : [];
    COLUMNS.forEach((col, idx)=>{
      const headerCell = headerRow.children[idx];
      if(!headerCell) return;
      const stored = state.columnWidths[col.key];
      const fallback = col.width || '';
      const value = stored || fallback;
      if(!value) return;
      headerCell.style.width = value;
      headerCell.style.minWidth = value;
      headerCell.style.maxWidth = '';
      rows.forEach(row => {
        const cell = row.children[idx];
        if(cell){
          cell.style.width = value;
          cell.style.minWidth = value;
          cell.style.maxWidth = '';
        }
      });
    });
  }

  function startColumnResize(index, ev){
    ev.preventDefault();
    ev.stopPropagation();
    const col = COLUMNS[index];
    if(!col || !headerRow) return;
    const target = headerRow.children[index];
    if(!target) return;
    const startX = ev.clientX;
    const startWidth = target.getBoundingClientRect().width;
    const minWidth = 100;
    const onMove = (moveEv)=>{
      const dx = moveEv.clientX - startX;
      const nextWidth = Math.max(minWidth, Math.round(startWidth + dx));
      state.columnWidths[col.key] = `${nextWidth}px`;
      applyColumnWidths();
    };
    const onUp = ()=>{
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  function ensureResizeHandles(){
    if(!headerRow) return;
    Array.from(headerRow.children).forEach((th, idx)=>{
      if(!th) return;
      let handle = th.querySelector('.ws-col-resize-handle');
      if(!handle){
        handle = document.createElement('span');
        handle.className = 'ws-col-resize-handle';
        handle.addEventListener('mousedown', (ev)=> startColumnResize(idx, ev));
        handle.addEventListener('click', (ev)=> ev.stopPropagation());
        th.appendChild(handle);
      }
    });
  }

  function onRowClick(ev){
    const rowEl = ev.target.closest('tr[data-index]');
    if(!rowEl) return;
    const index = Number(rowEl.dataset.index);
    if(Number.isNaN(index)) return;
    const item = state.filtered[index];
    if(!item || !item.raw) return;
    openDetailModal(item.name || 'Medication Detail', item.raw);
  }

  function toTitleCase(text){
    const s = (text || '').toString().trim();
    if(!s) return '';
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function computeDuration(startTs, endTs){
    if(!Number.isFinite(startTs)) return null;
    const end = Number.isFinite(endTs) ? endTs : Date.now();
    const diff = end - startTs;
    if(diff <= 0) return 0;
    return Math.round(diff / (1000 * 60 * 60 * 24));
  }

  function normalizeRow(row){
    const name = row.name || row.display || row.qualifiedName || 'Medication';
    const statusRaw = (row.status || '').toString().trim().toLowerCase();
    const statusLabel = statusRaw ? toTitleCase(statusRaw) : 'Unknown';
    const start = row.startDate || row.start || row.ordered || '';
    const end = row.endDate || row.stop || row.expires || row.expirationDate || '';
    const startTs = start ? Date.parse(start) : NaN;
    const endTs = end ? Date.parse(end) : NaN;
    const durationDays = computeDuration(startTs, endTs);
    const sig = row.sig || row.instructions || row.dose || '';
    return {
      name,
      status: statusRaw,
      statusLabel,
      start,
      end,
      startTs: Number.isFinite(startTs) ? startTs : null,
      endTs: Number.isFinite(endTs) ? endTs : null,
      durationDays: Number.isFinite(durationDays) ? durationDays : null,
      sig: sig || '',
      raw: row
    };
  }

  function renderSkeleton(container){
    container.innerHTML = `
      <div class="meds-module">
        <div class="controls">
          <label>
            Range
            <select data-role="meds-days">
              <option value="90">Last 90 days</option>
              <option value="180">Last 6 months</option>
              <option value="365" selected>Last year</option>
              <option value="all">All available</option>
            </select>
          </label>
          <label>
            Status
            <select data-role="meds-status">
              <option value="ALL" selected>All statuses</option>
              <option value="ACTIVE+PENDING">Active + Pending</option>
              <option value="ACTIVE">Active only</option>
              <option value="PENDING">Pending only</option>
            </select>
          </label>
          <input type="search" data-role="meds-search" placeholder="Search medication" aria-label="Search medications" />
          <button type="button" data-role="meds-refresh">Refresh</button>
          <span class="status-line" data-role="meds-status-line">&nbsp;</span>
        </div>
        <div class="meds-table-wrap">
          <table data-role="meds-table">
            <thead><tr data-role="meds-header"></tr></thead>
            <tbody data-role="meds-body">
              <tr class="meds-empty-row"><td colspan="${COLUMNS.length}">Loading medications...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  function buildHeader(){
    if(!headerRow) return;
    headerRow.innerHTML = '';
    COLUMNS.forEach(col => {
      const th = document.createElement('th');
      const label = document.createElement('span');
      label.textContent = col.label;
      label.className = 'meds-header-label';
      th.appendChild(label);
      th.dataset.sortKey = col.key;
      th.dataset.sortType = col.type;
      th.dataset.colKey = col.key;
      headerRow.appendChild(th);
    });
    updateSortIndicators();
    ensureResizeHandles();
    applyColumnWidths();
  }

  function updateSortIndicators(){
    if(!headerRow) return;
    Array.from(headerRow.querySelectorAll('th')).forEach(th => {
      th.classList.remove('sort-asc','sort-desc');
      const key = th.dataset.sortKey;
      if(!key) return;
      if(state.sortKey === key){
        th.classList.add(state.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  function sortData(items){
    const key = state.sortKey;
    const dir = state.sortDir === 'asc' ? 1 : -1;
    const col = COLUMNS.find(c => c.key === key);
    const type = col ? col.type : 'text';
    const ascending = dir === 1;
    const compare = (a,b)=>{
      const va = a[key];
      const vb = b[key];
      if(type === 'number'){
        const fallback = ascending ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
        const na = (typeof va === 'number' && Number.isFinite(va)) ? va : fallback;
        const nb = (typeof vb === 'number' && Number.isFinite(vb)) ? vb : fallback;
        if(na < nb) return -1;
        if(na > nb) return 1;
      } else if(type === 'date'){
        const fallback = ascending ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
        const ta = Number.isFinite(va) ? va : fallback;
        const tb = Number.isFinite(vb) ? vb : fallback;
        if(ta < tb) return -1;
        if(ta > tb) return 1;
      } else {
        const sa = (va == null ? '' : String(va)).toLowerCase();
        const sb = (vb == null ? '' : String(vb)).toLowerCase();
        if(sa < sb) return -1;
        if(sa > sb) return 1;
      }
      return 0;
    };
    return items.slice().sort((a,b)=> compare(a,b) * dir);
  }

  function renderRows(){
    if(!tableBody) return;
    if(!state.filtered.length){
      tableBody.innerHTML = `<tr class="meds-empty-row"><td colspan="${COLUMNS.length}">No medications match the current filters.</td></tr>`;
      applyColumnWidths();
      return;
    }
    const rows = state.filtered.map((row, index) => {
      const start = formatDate(row.start);
      const end = formatDate(row.end);
      const duration = Number.isFinite(row.durationDays) ? `${row.durationDays}` : '--';
      const statusClass = row.status ? row.status : 'other';
      const statusLabel = row.statusLabel || 'Unknown';
      return `
        <tr data-index="${index}">
          <td>
            <div class="med-name">${escapeHtml(row.name)}</div>
            ${row.sig ? `<div class="med-meta">${escapeHtml(row.sig)}</div>` : ''}
          </td>
          <td><span class="med-status ${escapeHtml(statusClass)}">${escapeHtml(statusLabel)}</span></td>
          <td>${escapeHtml(start)}</td>
          <td>${escapeHtml(end)}</td>
          <td>${escapeHtml(duration)}</td>
        </tr>
      `;
    }).join('');
    tableBody.innerHTML = rows;
    applyColumnWidths();
  }

  function updateStatus(){
    if(!statusEl) return;
    const total = state.items.length;
    const counts = state.items.reduce((acc,row)=>{
      const key = row.status || 'other';
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const parts = [];
    if(counts.active) parts.push(`Active ${counts.active}`);
    if(counts.pending) parts.push(`Pending ${counts.pending}`);
    if(counts.completed) parts.push(`Completed ${counts.completed}`);
    if(counts.stopped) parts.push(`Stopped ${counts.stopped}`);
    statusEl.innerHTML = total
      ? `Showing <strong>${state.filtered.length}</strong> of ${total} medications${parts.length ? ' - ' + parts.join(' | ') : ''}`
      : 'No medications available for this patient.';
  }

  function applyFilters(){
    const search = state.search.trim().toLowerCase();
    let items = state.items.slice();
    if(search){
      items = items.filter(row => row.name.toLowerCase().includes(search) || (row.sig && row.sig.toLowerCase().includes(search)));
    }
    state.filtered = sortData(items);
    renderRows();
    updateStatus();
  }

  function setSort(key){
    if(!key) return;
    if(state.sortKey === key){
      state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      state.sortKey = key;
      state.sortDir = (key === 'startTs' || key === 'endTs' || key === 'durationDays') ? 'desc' : 'asc';
    }
    updateSortIndicators();
    applyFilters();
  }

  function attachEvents(){
    if(!containerRef) return;
    const refreshBtn = containerRef.querySelector('[data-role="meds-refresh"]');
    if(refreshBtn){
      refreshBtn.addEventListener('click', ()=> loadMeds());
    }
    if(daysSelect){
      daysSelect.addEventListener('change', ()=>{
        const value = daysSelect.value;
        state.days = value === 'all' ? null : parseInt(value, 10) || null;
        loadMeds();
      });
    }
    if(statusSelect){
      statusSelect.addEventListener('change', ()=>{
        state.status = statusSelect.value || 'ALL';
        loadMeds();
      });
    }
    if(searchInput){
      let t = null;
      searchInput.addEventListener('input', ()=>{
        clearTimeout(t);
        t = setTimeout(()=>{
          state.search = searchInput.value || '';
          applyFilters();
        }, 160);
      });
    }
    if(headerRow){
      headerRow.addEventListener('click', (ev)=>{
        const th = ev.target.closest('th[data-sort-key]');
        if(!th) return;
        const key = th.dataset.sortKey;
        if(!key) return;
        setSort(key);
      });
    }
    if(tableBody){
      tableBody.addEventListener('click', onRowClick);
    }
  }

  async function loadMeds(){
    if(!containerRef || !tableBody) return;
    const hasPatient = window.Api && typeof Api.requireDFN === 'function';
    if(!hasPatient){
      tableBody.innerHTML = `<tr class="meds-empty-row"><td colspan="${COLUMNS.length}">Patient context unavailable.</td></tr>`;
      applyColumnWidths();
      return;
    }
    cancelAll();
    let ctrl = null;
    try{
      const dfn = Api.requireDFN();
      const params = new URLSearchParams();
      if(state.days && Number.isFinite(state.days)) params.set('days', String(state.days));
      if(state.status) params.set('status', state.status);
      const query = params.toString();
      const url = `/api/patient/${encodeURIComponent(dfn)}/quick/meds${query ? '?'+query : ''}`;
      ctrl = new AbortController();
      controllers.add(ctrl);
      state.loading = true;
      tableBody.innerHTML = `<tr class="meds-empty-row"><td colspan="${COLUMNS.length}">Loading medications...</td></tr>`;
      applyColumnWidths();
      const res = await fetch(url, { credentials: 'same-origin', signal: ctrl.signal });
      if(!res.ok){
        throw new Error(`HTTP ${res.status}`);
      }
      const body = await res.json();
      const list = Array.isArray(body) ? body : (body && Array.isArray(body.medications) ? body.medications : []);
      state.items = list.map(normalizeRow);
      state.error = '';
      applyFilters();
    }catch(err){
      if(err && err.name === 'AbortError') return;
      console.error('[Meds] load error', err);
      state.error = err && err.message ? err.message : 'Unable to load medications';
      tableBody.innerHTML = `<tr class="meds-empty-row"><td colspan="${COLUMNS.length}">${escapeHtml(state.error)}</td></tr>`;
      applyColumnWidths();
      updateStatus();
    }finally{
      if(ctrl) controllers.delete(ctrl);
      state.loading = false;
    }
  }

  async function render(container){
    ensureStyles();
    containerRef = container;
    renderSkeleton(container);
    tableBody = container.querySelector('[data-role="meds-body"]');
    statusEl = container.querySelector('[data-role="meds-status-line"]');
    searchInput = container.querySelector('[data-role="meds-search"]');
    daysSelect = container.querySelector('[data-role="meds-days"]');
    statusSelect = container.querySelector('[data-role="meds-status"]');
    headerRow = container.querySelector('[data-role="meds-header"]');
    if(daysSelect) daysSelect.value = state.days ? String(state.days) : 'all';
    if(statusSelect) statusSelect.value = state.status;
    buildHeader();
    attachEvents();
    await loadMeds();
  }

  async function refresh(){ await loadMeds(); }
  async function refreshSoft(){ await loadMeds(); }

  function destroy(){
    cancelAll();
    containerRef = null;
    tableBody = null;
    statusEl = null;
    searchInput = null;
    daysSelect = null;
    statusSelect = null;
    headerRow = null;
    state.items = [];
    state.filtered = [];
  }

  window.WorkspaceModules[MODULE_NAME] = {
    render,
    refresh,
    refreshSoft,
    destroy,
    preserveOnRefresh: true
  };
})();
