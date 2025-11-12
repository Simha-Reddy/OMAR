// filepath: static/workspace/modules/labs.js
(function(){
    window.WorkspaceModules = window.WorkspaceModules || {};
    const MODULE_NAME = 'Labs';
    const controllers = new Set();
    const state = {
        items: [],
        filtered: [],
        sortKey: 'resultedTs',
        sortDir: 'desc',
        days: 365,
        search: '',
        abnormalOnly: false,
        loading: false,
        error: '',
        columnWidths: {}
    };
    const COLUMNS = [
        { key: 'test', label: 'Test', type: 'text', width: '26%' },
        { key: 'resultNumeric', label: 'Result', type: 'number', width: '18%' },
        { key: 'referenceRange', label: 'Reference Range', type: 'text', width: '18%' },
        { key: 'panel', label: 'Panel', type: 'text', width: '18%' },
        { key: 'resultedTs', label: 'Result Date', type: 'date', width: '20%' },
        { key: 'statusLabel', label: 'Status', type: 'text', width: '12%' }
    ];

    let containerRef = null;
    let tableBody = null;
    let statusEl = null;
    let searchInput = null;
    let daysSelect = null;
    let abnormalToggle = null;
    let headerRow = null;
    let tableRoot = null;

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
        const id = 'labs-module-styles';
        if(document.getElementById(id)) return;
        const style = document.createElement('style');
        style.id = id;
        style.textContent = `
            .labs-module { display:flex; flex-direction:column; gap:12px; height:100%; }
            .labs-module .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
            .labs-module .controls select,
            .labs-module .controls input[type="search"] { padding:4px 6px; font-size:0.95em; }
            .labs-module .controls label { display:flex; align-items:center; gap:4px; font-size:0.92em; color:#444; }
            .labs-table-wrap { flex:1; min-height:240px; border:1px solid #e1e1e1; border-radius:8px; overflow:auto; background:#fff; display:flex; flex-direction:column; max-height:100%; }
            .labs-table-wrap table { width:auto; min-width:100%; border-collapse:collapse; font-size:0.95em; table-layout:auto; }
            .labs-table-wrap thead { background:linear-gradient(180deg,#f5f7fb,#e8ecf5); }
            .labs-table-wrap th { text-align:left; padding:8px 10px; font-weight:600; color:#31405f; cursor:pointer; user-select:none; border-bottom:1px solid #d5dbe7; position:relative; }
            .labs-table-wrap th.sort-asc::after { content:'^'; margin-left:6px; font-size:0.75em; }
            .labs-table-wrap th.sort-desc::after { content:'v'; margin-left:6px; font-size:0.75em; }
            .labs-table-wrap td { padding:8px 10px; border-bottom:1px solid #eef1f6; vertical-align:top; color:#2b2b2b; }
            .labs-table-wrap tbody tr:hover { background:#f7f9fc; }
            .labs-table-wrap .lab-result { font-weight:600; color:#1f4e92; }
            .labs-table-wrap .lab-result.abnormal { color:#c62828; }
            .labs-table-wrap .lab-ref { color:#555; font-size:0.9em; }
            .labs-table-wrap .lab-meta { color:#687086; font-size:0.85em; margin-top:2px; }
            .labs-table-wrap .lab-status { font-weight:600; }
            .labs-table-wrap .lab-status.abnormal { color:#c62828; }
            .labs-table-wrap .lab-status.normal { color:#2e7d32; }
            .labs-empty-row td { text-align:center; color:#777; padding:18px 10px; }
            .labs-module .status-line { font-size:0.9em; color:#4b4b4b; display:flex; gap:12px; align-items:center; }
            .labs-module .status-line strong { color:#1f4e92; }
            @media (max-width: 768px){
                .labs-table-wrap th, .labs-table-wrap td { padding:6px 8px; font-size:0.9em; }
                .labs-module .controls { gap:6px; }
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
        const minWidth = 90;
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
        openDetailModal(item.test || 'Lab Detail', item.raw);
    }

    function normalizeResult(value){
        if(value == null) return '';
        const str = String(value).trim();
        const num = parseFloat(str.replace(/[^0-9+\-.,]/g,''));
        return { display: str, numeric: Number.isFinite(num) ? num : null };
    }

    function normalizeSpecimen(row){
        const raw = row && (row.specimen ?? row.specimenType ?? row.sample ?? row.source ?? row.bodySite ?? null);
        if(raw == null) return { label: '', code: '' };
        if(typeof raw === 'string'){
            return { label: raw, code: '' };
        }
        if(typeof raw === 'object'){
            const code = raw.code != null ? String(raw.code) : '';
            const labelSource = raw.name ?? raw.display ?? raw.text ?? raw.description ?? code ?? '';
            return { label: labelSource != null ? String(labelSource) : '', code };
        }
        return { label: String(raw), code: '' };
    }

    function extractLabList(payload){
        if(Array.isArray(payload)) return payload;
        if(payload && Array.isArray(payload.result)) return payload.result;
        if(payload && Array.isArray(payload.labs)) return payload.labs;
        if(payload && Array.isArray(payload.items)) return payload.items;
        if(payload && payload.result && typeof payload.result === 'object' && Array.isArray(payload.result.items)){
            return payload.result.items;
        }
        return [];
    }

    function normalizeRow(row){
        const test = (row.test || row.name || row.display || row.localName || 'Unknown').toString();
        const resultObj = normalizeResult(row.result != null ? row.result : row.value);
        const units = row.unit || row.units || '';
        const range = row.referenceRange || row.refRange || '';
        const abnormal = row.abnormal === true ? true : (row.abnormal === false ? false : null);
        const panel = row.panelName || row.groupName || '';
        const specimenInfo = normalizeSpecimen(row);
        const specimen = specimenInfo.label ? specimenInfo.label : '';
        const specimenCode = specimenInfo.code ? specimenInfo.code : '';
        const loinc = row.loinc || row.code || '';
        const observed = row.resulted || row.observedDate || row.collected || row.date || '';
        const ts = observed ? Date.parse(observed) : NaN;
        const id = row.uid || row.localId || `${test}-${observed}-${resultObj.display}`;
    const statusLabel = abnormal === true ? 'Abnormal' : (abnormal === false ? 'Normal' : 'Unknown');
        const searchTokens = [test, panel, specimen, specimenCode, loinc, resultObj.display, units].join(' ').toLowerCase();
        return {
            id,
            test,
            result: resultObj.display,
            resultNumeric: Number.isFinite(resultObj.numeric) ? resultObj.numeric : null,
            unit: units,
            referenceRange: range,
            abnormal,
            statusLabel,
            panel,
            specimen,
            specimenCode,
            loinc,
            resulted: observed,
            resultedTs: Number.isFinite(ts) ? ts : null,
            searchTokens,
            raw: row
        };
    }

    function renderSkeleton(container){
        container.innerHTML = `
            <div class="labs-module">
                <div class="controls">
                    <label>
                        Range
                        <select data-role="labs-days">
                            <option value="30">Last 30 days</option>
                            <option value="90">Last 90 days</option>
                            <option value="180">Last 6 months</option>
                            <option value="365" selected>Last year</option>
                            <option value="all">All available</option>
                        </select>
                    </label>
                    <label>
                        <input type="checkbox" data-role="labs-abnormal" /> Abnormal only
                    </label>
                    <input type="search" data-role="labs-search" placeholder="Search test, panel, specimen" aria-label="Search labs" />
                    <button type="button" data-role="labs-refresh">Refresh</button>
                    <span class="status-line" data-role="labs-status">&nbsp;</span>
                </div>
                        <div class="labs-table-wrap">
                    <table data-role="labs-table">
                        <thead><tr data-role="labs-header"></tr></thead>
                        <tbody data-role="labs-body">
                            <tr class="labs-empty-row"><td colspan="${COLUMNS.length}">Loading labs...</td></tr>
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
            label.className = 'labs-header-label';
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
                const mappedKey = key === 'resultedTs' ? 'resultedTs' : (key === 'resultNumeric' ? 'resultNumeric' : key);
                if(state.sortKey === mappedKey){
                th.classList.add(state.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
            }
        });
    }

    function sortData(items){
        const key = state.sortKey;
        const dir = state.sortDir === 'asc' ? 1 : -1;
        const type = (COLUMNS.find(c=> c.key === key) || {}).type || 'text';
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
                    const fa = ascending ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
                    const ta = Number.isFinite(va) ? va : fa;
                    const tb = Number.isFinite(vb) ? vb : fa;
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
            tableBody.innerHTML = `<tr class="labs-empty-row"><td colspan="${COLUMNS.length}">No lab results match the current filters.</td></tr>`;
            applyColumnWidths();
            return;
        }
        const rowsHtml = state.filtered.map((row, idx) => {
            const dateText = formatDate(row.resulted);
            const resultClass = row.abnormal ? 'lab-result abnormal' : 'lab-result';
            const statusClass = row.abnormal === true ? 'lab-status abnormal' : (row.abnormal === false ? 'lab-status normal' : 'lab-status');
            return `
                <tr data-index="${idx}">
                    <td>
                        <div>${escapeHtml(row.test)}</div>
                        ${row.specimen ? `<div class="lab-meta">Specimen: ${escapeHtml(row.specimen)}${row.specimenCode ? ` (${escapeHtml(row.specimenCode)})` : ''}</div>` : ''}
                        ${row.loinc ? `<div class="lab-meta">LOINC: ${escapeHtml(row.loinc)}</div>` : ''}
                    </td>
                    <td>
                        <div class="${resultClass}">${escapeHtml(row.result)}${row.unit ? ` ${escapeHtml(row.unit)}` : ''}</div>
                    </td>
                    <td><div class="lab-ref">${escapeHtml(row.referenceRange)}</div></td>
                    <td>${escapeHtml(row.panel)}</td>
                    <td>${escapeHtml(dateText)}</td>
                    <td><span class="${statusClass}">${escapeHtml(row.statusLabel)}</span></td>
                </tr>
            `;
        }).join('');
        tableBody.innerHTML = rowsHtml;
        applyColumnWidths();
    }

    function updateStatus(){
        if(!statusEl) return;
        const total = state.items.length;
        const abnormalCount = state.items.filter(r=> r.abnormal === true).length;
        const showing = state.filtered.length;
        statusEl.innerHTML = total
            ? `Showing <strong>${showing}</strong> of ${total} labs - abnormal: ${abnormalCount}`
            : 'No labs available for this patient.';
    }

    function applyFilters(){
        const search = state.search.trim().toLowerCase();
        const abnormalOnly = state.abnormalOnly;
        let items = state.items.slice();
        if(abnormalOnly){
            items = items.filter(row => row.abnormal === true);
        }
        if(search){
            items = items.filter(row => row.searchTokens.includes(search));
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
                state.sortDir = (key === 'resultedTs' || key === 'resultNumeric') ? 'desc' : 'asc';
        }
        updateSortIndicators();
        applyFilters();
    }

    function attachEvents(){
        if(!containerRef) return;
        const refreshBtn = containerRef.querySelector('[data-role="labs-refresh"]');
        if(refreshBtn){
            refreshBtn.addEventListener('click', ()=> loadLabs());
        }
        if(daysSelect){
            daysSelect.addEventListener('change', ()=>{
                const value = daysSelect.value;
                state.days = value === 'all' ? null : parseInt(value, 10) || null;
                loadLabs();
            });
        }
        if(abnormalToggle){
            abnormalToggle.addEventListener('change', ()=>{
                state.abnormalOnly = abnormalToggle.checked;
                applyFilters();
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

    async function loadLabs(){
        if(!containerRef || !tableBody) return;
        const hasPatient = window.Api && typeof Api.requireDFN === 'function';
        if(!hasPatient){
            tableBody.innerHTML = `<tr class="labs-empty-row"><td colspan="${COLUMNS.length}">Patient context unavailable.</td></tr>`;
            applyColumnWidths();
            return;
        }
        cancelAll();
        let ctrl = null;
        try{
            const dfn = Api.requireDFN();
            const params = new URLSearchParams();
            if(state.days && Number.isFinite(state.days)) params.set('days', String(state.days));
            params.set('maxPanels', '120');
            const query = params.toString();
            const url = `/api/patient/${encodeURIComponent(dfn)}/quick/labs${query ? '?'+query : ''}`;
            ctrl = new AbortController();
            controllers.add(ctrl);
            state.loading = true;
            tableBody.innerHTML = `<tr class="labs-empty-row"><td colspan="${COLUMNS.length}">Loading labs...</td></tr>`;
            applyColumnWidths();
            const res = await fetch(url, { credentials: 'same-origin', signal: ctrl.signal });
            if(!res.ok){
                throw new Error(`HTTP ${res.status}`);
            }
            const body = await res.json();
            const list = extractLabList(body);
            state.items = list.map(normalizeRow);
            state.error = '';
            applyFilters();
        }catch(err){
            if(err && err.name === 'AbortError') return;
            console.error('[Labs] load error', err);
            state.error = err && err.message ? err.message : 'Unable to load labs';
            tableBody.innerHTML = `<tr class="labs-empty-row"><td colspan="${COLUMNS.length}">${escapeHtml(state.error)}</td></tr>`;
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
        tableBody = container.querySelector('[data-role="labs-body"]');
        statusEl = container.querySelector('[data-role="labs-status"]');
        searchInput = container.querySelector('[data-role="labs-search"]');
        daysSelect = container.querySelector('[data-role="labs-days"]');
        abnormalToggle = container.querySelector('[data-role="labs-abnormal"]');
        headerRow = container.querySelector('[data-role="labs-header"]');
        buildHeader();
        state.search = '';
        state.abnormalOnly = false;
        if(abnormalToggle) abnormalToggle.checked = false;
        if(daysSelect) daysSelect.value = state.days ? String(state.days) : 'all';
        attachEvents();
        await loadLabs();
    }

    async function refresh(){ await loadLabs(); }
    async function refreshSoft(){ await loadLabs(); }

    function destroy(){
        cancelAll();
        containerRef = null;
        tableBody = null;
        statusEl = null;
        searchInput = null;
        daysSelect = null;
        abnormalToggle = null;
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
