// Helper to build archive filename base
function buildArchiveBaseName(patientName) {
    const now = new Date();
    const mm = now.getMonth() + 1;
    const dd = now.getDate();
    const yy = String(now.getFullYear()).slice(-2);
    const hh = String(now.getHours()).padStart(2, '0');
    const min = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0'); // add seconds
    const name = (patientName || '').trim();
    return `${mm}-${dd}-${yy} at ${hh}${min}${ss} with ${name}`;
}

async function preSwitchSaveAndClear() {
    try {
        // Pause auto-save loop to avoid race while switching
        try { if (window.stopAutoSaveLoop) window.stopAutoSaveLoop(); } catch(_e){}
        if (window.SessionManager && SessionManager.saveToSession) {
            await SessionManager.saveToSession();
        }
        // Flush current archive file one last time before switching (only if scribe had content)
        try {
            const prev = localStorage.getItem('ssva:currentArchiveName');
            const hadScribeContent = (() => {
                try {
                    const t = document.getElementById('rawTranscript')?.value || '';
                    const n = document.getElementById('visitNotes')?.value || '';
                    return (t.trim().length + n.trim().length) > 0;
                } catch(_e){ return false; }
            })();
            if (prev && hadScribeContent && window.SessionManager && SessionManager.saveFullSession) {
                await SessionManager.saveFullSession(prev);
            }
        } catch(_e){}

        // Immediately clear UI fields so old notes don't carry into the new patient
        try {
            const vn = document.getElementById('visitNotes');
            if (vn) { vn.value = ''; vn.dispatchEvent(new Event('input', { bubbles: true })); }
            const ct = document.getElementById('chunkText');
            if (ct) { ct.value = ''; ct.dispatchEvent(new Event('input', { bubbles: true })); }
            const ans = document.getElementById('exploreGptAnswer');
            if (ans) ans.innerHTML = '';
            // Clear any module outputs
            document.querySelectorAll('.panel .module-output').forEach(el => el.innerHTML = '');
            // Clear scribe transcript textbox if present
            const rt = document.getElementById('rawTranscript');
            if (rt) rt.value = '';
            // Reset in-memory Explore QA history
            try { window.exploreQAHistory = []; if (typeof window.updateExploreQAHistory === 'function') window.updateExploreQAHistory(); } catch(_){}
        } catch(_e){}

        // Clear live transcript file on the server too
        try { await fetch('/scribe/clear_live_transcript', { method: 'POST' }); } catch(_e){}

        // Unbind the archive name to prevent autosave from writing to old file
        try { localStorage.removeItem('ssva:currentArchiveName'); } catch(_e){}

        // Clear server-side session state
        await fetch('/clear_session', { method: 'POST' });

        // Clear client-side patient list caches for privacy and correctness
        try {
            sessionStorage.removeItem('omar:defaultPatientList');
            window._defaultPatientList = null;
            window._allPatientsBrowse = null;
        } catch(_){}

        // Small delay to ensure clears settle before proceeding
        try { await new Promise(r => setTimeout(r, 75)); } catch(_e){}
    } catch (e) {
        console.warn('Pre-switch save/clear warning', e);
    }
}

async function setNewArchiveForPatient(patientName) {
    try {
        const base = buildArchiveBaseName(patientName || '');
        localStorage.setItem('ssva:currentArchiveName', base);

        // Defer initial write; avoid creating an empty archive snapshot
        const hasScribeContent = () => {
            try {
                const t = document.getElementById('rawTranscript')?.value || '';
                const n = document.getElementById('visitNotes')?.value || '';
                return (t.trim().length + n.trim().length) > 0;
            } catch(_e){ return false; }
        };

        // Start auto-archive loop if available
        if (window.startAutoArchiveForCurrentPatient) await window.startAutoArchiveForCurrentPatient();

        // Schedule an initial save only if scribe content exists
        setTimeout(async () => {
            try {
                if (hasScribeContent() && window.SessionManager && SessionManager.saveFullSession) {
                    await SessionManager.saveFullSession(base);
                }
            } catch(_e){}
        }, 1200);
    } catch (e) { console.warn('Set new archive warning', e); }
}

// Utility: close any open patient search UI (desktop/mobile)
function closePatientSearchUI() {
    try {
        const panel = document.getElementById('mobileSearchPanel');
        if (panel) panel.style.display = 'none';
    } catch(_) {}
    try {
        const inp = document.getElementById('patientSearchInput');
        if (inp) inp.blur();
    } catch(_) {}
}

// Handles patient selection
window.selectPatientDFN = async function(dfn, name) {
    // Proactively close search UI once a patient is chosen
    closePatientSearchUI();

    // Preview via ORWPT SELECT first
    let preview = null;
    try {
        const resp = await fetch('/vista_patient_select_preview', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dfn })
        });
        const body = await resp.json();
        // Sensitive record gating: show notice and abort
        if (resp.status === 403 && body && body.sensitive) {
            try { await showSensitiveNoticeModal({ message: body.message || 'Sensitive record. Access denied.', dfn }); } catch(_e){}
            return;
        }
        preview = body;
        if (preview && preview.error) throw new Error(preview.error);
    } catch(_e) {
        // Fallback to demographics
        try {
            const r2 = await fetch('/vista_patient_demographics', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dfn, fallback_name: name })
            });
            const demo = await r2.json();
            preview = {
                dfn,
                name: (demo && demo.name) || name,
                ssn: (demo && demo.ssn) || 'Unknown',
                dob: (demo && demo.dob) || 'Unknown'
            };
        } catch(_e2) {
            preview = { dfn, name };
        }
    }

    const confirmed = await showPatientConfirmModal({
        dfn,
        name: (preview && preview.name) || name,
        sex: (preview && preview.sex) || '',
        dob: (preview && preview.dob) || '',
        ssn: (preview && preview.ssn) || '',
        serviceConnected: (preview && (preview.serviceConnected || preview.serviceconnected)) || '',
        scPercent: (preview && (preview.scPercent || preview.scpercent)) || '',
        location: (preview && preview.location) || '',
        roomBed: (preview && (preview.roomBed || preview.roombed)) || '',
        raw: (preview && preview.raw) || ''
    });
    if (!confirmed) return; // user canceled

    // 1) Save & Clear current session
    await preSwitchSaveAndClear();

    // 2) Load new patient
    const res = await fetch("/select_patient", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_dfn: dfn, station: "500" })
    });
    const data = await res.json();
    // Cache-buster key for downstream requests
    try { window.CURRENT_PATIENT_DFN = dfn; } catch(_e){}
    // Ordering guard: confirm session persisted and allow micro-delay
    let meta = null;
    try {
        const metaResp = await fetch('/get_patient', { cache: 'no-store' });
        meta = await metaResp.json();
        await new Promise(r=> setTimeout(r, 60));
    } catch(_e){}
    if (data && !data.error) {
        // Immediately update Explore widgets without reload
        if (typeof window.displayPatientInfo === "function") window.displayPatientInfo(data);
        if (typeof window.renderMedicationsTable === "function") window.renderMedicationsTable(data);
        if (typeof window.renderLabsTable === "function") window.renderLabsTable(data);
        if (typeof window.initPrimaryNoteUI === "function") window.initPrimaryNoteUI(data);
        if (typeof window.resetDocuments === "function") {
            window.resetDocuments();
        } else if (typeof window.refreshDocuments === "function") {
            window.refreshDocuments();
        }
        // New: refresh vitals sidebar
        if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function') {
            window.VitalsSidebar.refresh();
        }
        // New: refresh right sidebar
        if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function') {
            window.RightSidebar.refresh();
        }
        // Start new archive for this patient and start auto-save
        const patientName = ((preview && preview.name) || name || (meta && meta.name) || '').toString();
        await setNewArchiveForPatient(patientName);
    }
    if (typeof updatePatientNameDisplay === "function") updatePatientNameDisplay();
};

// Attach event listeners
window.addEventListener("DOMContentLoaded", () => {
    const selectPatientBtn = document.getElementById("selectPatientBtn");

    if (selectPatientBtn) {
        selectPatientBtn.onclick = async function() {
            const patient_dfn = prompt("Enter patient DFN:");
            if (!patient_dfn) return;

            // Preview and confirm
            let preview = null;
            try {
                const resp = await fetch('/vista_patient_select_preview', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dfn: patient_dfn })
                });
                const body = await resp.json();
                if (resp.status === 403 && body && body.sensitive){
                    try { await showSensitiveNoticeModal({ message: body.message || 'Sensitive record. Access denied.', dfn: patient_dfn }); } catch(_e){}
                    return;
                }
                preview = body;
                if (preview && preview.error) throw new Error(preview.error);
            } catch(_e) {
                try {
                    const r2 = await fetch('/vista_patient_demographics', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ dfn: patient_dfn })
                    });
                    const demo = await r2.json();
                    preview = { dfn: patient_dfn, name: (demo && demo.name) || '', ssn: (demo && demo.ssn) || '', dob: (demo && demo.dob) || '' };
                } catch(_e2) { preview = { dfn: patient_dfn }; }
            }
            const ok = await showPatientConfirmModal({
                dfn: patient_dfn,
                name: (preview && preview.name) || '',
                sex: (preview && preview.sex) || '',
                dob: (preview && preview.dob) || '',
                ssn: (preview && preview.ssn) || '',
                serviceConnected: (preview && (preview.serviceConnected || preview.serviceconnected)) || '',
                scPercent: (preview && (preview.scPercent || preview.scpercent)) || '',
                location: (preview && preview.location) || '',
                roomBed: (preview && (preview.roomBed || preview.roombed)) || '',
                raw: (preview && preview.raw) || ''
            });
            if (!ok) return;

            // 1) Save & Clear current session
            await preSwitchSaveAndClear();
            // Proactively close search UI once a patient is chosen
            closePatientSearchUI();
            // 2) Load new patient
            const res = await fetch("/select_patient", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ patient_dfn: patient_dfn })
            });
            const data = await res.json();
            // Cache-buster key
            try { window.CURRENT_PATIENT_DFN = patient_dfn; } catch(_e){}
            // Ordering guard
            let meta = null;
            try { const mr = await fetch('/get_patient', { cache: 'no-store' }); meta = await mr.json(); await new Promise(r=> setTimeout(r, 60)); } catch(_e){}
            if (data && !data.error) {
                if (typeof window.displayPatientInfo === "function") window.displayPatientInfo(data);
                if (typeof window.renderMedicationsTable === "function") window.renderMedicationsTable(data);
                if (typeof window.renderLabsTable === "function") window.renderLabsTable(data);
                if (typeof window.initPrimaryNoteUI === "function") window.initPrimaryNoteUI(data);
                if (typeof window.resetDocuments === "function") {
                    window.resetDocuments();
                } else if (typeof window.refreshDocuments === "function") {
                    window.refreshDocuments();
                }
                // New: refresh vitals sidebar
                if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function') {
                    window.VitalsSidebar.refresh();
                }
                // New: refresh right sidebar
                if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function') {
                    window.RightSidebar.refresh();
                }
                // Start new archive for this patient and start auto-save
                const patientName = (preview && preview.name) || (meta && meta.name) || '';
                await setNewArchiveForPatient(patientName);
            } else {
                alert("Failed to select patient: " + (data.error || "Unknown error"));
            }
        };
    }
});

// --- Dynamic patient search and dropdown selection ---
document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("patientSearchInput");
    const resultsDiv = document.getElementById("patientLookupResults");
    let dropdown = null;

    if (!searchInput) return;

    // ARIA setup for combobox
    try {
        searchInput.setAttribute('role', 'combobox');
        searchInput.setAttribute('aria-autocomplete', 'list');
        searchInput.setAttribute('aria-expanded', 'false');
        searchInput.setAttribute('aria-haspopup', 'listbox');
    } catch(_){}

    // Caches and state
    const DEFAULT_CACHE_KEY = 'omar:defaultPatientList';
    let defaultList = null; // { matches:[], ts, cached }
    let allBrowse = { items: [], next_cursor: '', loading: false, exhausted: false };
    let currentItemsFlat = []; // flattened list of option elements for keyboard nav
    let currentIndex = -1;
    let debounceTimer = null;
    let currentAbort = null;

    function announce(msg){
        let live = document.getElementById('patientDropdownLive');
        if (!live){
            live = document.createElement('div');
            live.id = 'patientDropdownLive';
            live.setAttribute('aria-live','polite');
            live.setAttribute('class','sr-only');
            live.style.position='absolute'; live.style.width='1px'; live.style.height='1px'; live.style.overflow='hidden'; live.style.clip='rect(1px,1px,1px,1px)';
            document.body.appendChild(live);
        }
        live.textContent = msg || '';
    }

    function escapeHtml(s){
        return String(s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
    }
    function highlight(text, query){
        const t = String(text||'');
        const q = String(query||'').trim();
        if (!q) return escapeHtml(t);
        const idx = t.toUpperCase().indexOf(q.toUpperCase());
        if (idx === -1) return escapeHtml(t);
        return escapeHtml(t.slice(0, idx)) + '<mark>' + escapeHtml(t.slice(idx+q.length)) + '<\/mark>' + escapeHtml(t.slice(idx+q.length));
    }

    function cleanupDropdown(){ if (dropdown) { dropdown.remove(); dropdown = null; searchInput.setAttribute('aria-expanded','false'); } currentItemsFlat=[]; currentIndex=-1; }

    function ensureDropdownShell(){
        cleanupDropdown();
        const rect = searchInput.getBoundingClientRect();
        dropdown = document.createElement('div');
        dropdown.className = 'patient-dropdown';
        dropdown.style.position = 'absolute';
        dropdown.style.background = '#fff';
        dropdown.style.border = '1px solid #ccc';
        dropdown.style.borderRadius = '6px';
        dropdown.style.boxShadow = '0 6px 16px rgba(0,0,0,0.15)';
        dropdown.style.zIndex = 1000;
        dropdown.style.left = rect.left + 'px';
        dropdown.style.top = (rect.bottom + window.scrollY) + 'px';
        dropdown.style.width = rect.width + 'px';
        dropdown.setAttribute('role','listbox');
        dropdown.id = 'patientDropdownListbox';
        searchInput.setAttribute('aria-controls','patientDropdownListbox');
        searchInput.setAttribute('aria-expanded','true');
        document.body.appendChild(dropdown);
        // Keep positioned on resize/scroll
        const reposition = () => {
            if (!dropdown) return; const r = searchInput.getBoundingClientRect();
            dropdown.style.left = r.left + 'px'; dropdown.style.top = (r.bottom + window.scrollY) + 'px'; dropdown.style.width = r.width + 'px';
        };
        window.addEventListener('resize', reposition, { passive:true, once:true });
        window.addEventListener('scroll', reposition, { passive:true, capture:true, once:true });
    }

    function sectionHeader(label){
        const h = document.createElement('div');
        h.textContent = label;
        h.style.fontSize = '0.85rem';
        h.style.fontWeight = '600';
        h.style.padding = '6px 8px';
        h.style.background = '#f7f7f7';
        h.style.borderBottom = '1px solid #eee';
        h.setAttribute('role','presentation');
        return h;
    }
    function sectionWrap(ariaLabel){
        const w = document.createElement('div');
        w.setAttribute('role','group');
        w.setAttribute('aria-label', ariaLabel);
        return w;
    }

    function makeOption(match, displayHtml){
        const item = document.createElement('div');
        item.setAttribute('role','option');
        item.setAttribute('aria-selected','false');
        // ID for aria-activedescendant targeting
        const optId = `patient-opt-${match.dfn}`;
        item.id = optId;
        item.tabIndex = -1;
        item.className = 'patient-option';
        item.style.padding = '6px 8px';
        item.style.cursor = 'pointer';
        item.innerHTML = displayHtml;
        // Demo masking support for live updates
        if (window.demoMasking && window.demoMasking.enabled) {
            item.dataset.originalText = `${match.name} (DFN: ${match.dfn})`;
        }
        item.addEventListener('mouseenter', () => {
            currentItemsFlat.forEach(i => { i.classList.remove('selected-patient'); i.setAttribute('aria-selected','false'); });
            item.classList.add('selected-patient');
            item.setAttribute('aria-selected','true');
            currentIndex = currentItemsFlat.indexOf(item);
            try { searchInput.setAttribute('aria-activedescendant', item.id); } catch(_){}
        });
        item.addEventListener('click', () => selectPatientFromDropdown(match, item));
        return item;
    }

    function renderState(div, text){
        const s = document.createElement('div');
        s.style.padding = '8px';
        s.style.color = '#666';
        s.innerHTML = escapeHtml(text);
        div.appendChild(s);
    }

    function buildGroupedDropdown(query){
        ensureDropdownShell();
        const q = (query||'').trim();
        // Default section
        const defWrap = sectionWrap('My Default Patient List');
        defWrap.appendChild(sectionHeader('My Default Patient List'));
        const defBody = document.createElement('div');
        defWrap.appendChild(defBody);
        dropdown.appendChild(defWrap);

        // All Patients section
        const allWrap = sectionWrap('All Patients');
        allWrap.appendChild(sectionHeader('All Patients'));
        const allBody = document.createElement('div');
        allBody.style.maxHeight = '260px';
        allBody.style.overflowY = 'auto';
        allWrap.appendChild(allBody);
        dropdown.appendChild(allWrap);

        let defCount = 0, allCount = 0;
        // Populate Default List
        try {
            const list = (defaultList && Array.isArray(defaultList.matches)) ? defaultList.matches : [];
            const filtered = q ? list.filter(m => (m.name||'').toUpperCase().includes(q.toUpperCase())) : list;
            defCount = filtered.length;
            if (filtered.length){
                filtered.forEach(m => {
                    const display = `${highlight(m.name, q)} <span style="opacity:.7">(DFN: ${escapeHtml(m.dfn)})<\/span>`;
                    const opt = makeOption(m, display);
                    defBody.appendChild(opt);
                    currentItemsFlat.push(opt);
                });
            } else {
                if (!defaultList || (defaultList.error)){ renderState(defBody, 'Default list unavailable.'); }
                else renderState(defBody, q ? 'No matches in your default list.' : (list.length? '': 'No patients in your default list.'));
            }
        } catch(e){ renderState(defBody, 'Could not render your default list.'); }

        // Populate All Patients depending on query
        if (!q){
            // Browsing mode with infinite scroll
            const items = allBrowse.items || [];
            allCount = items.length;
            if (!items.length){ renderState(allBody, allBrowse.loading? 'Loading…' : ''); }
            items.forEach(m => {
                const display = `${escapeHtml(m.name)} <span style="opacity:.7">(DFN: ${escapeHtml(m.dfn)})<\/span>`;
                const opt = makeOption(m, display);
                allBody.appendChild(opt);
                currentItemsFlat.push(opt);
            });
            // Infinite scroll
            allBody.addEventListener('scroll', async () => {
                if (allBrowse.loading || allBrowse.exhausted) return;
                const nearBottom = (allBody.scrollTop + allBody.clientHeight) / Math.max(1, allBody.scrollHeight) > 0.8;
                if (nearBottom){ await loadNextAllPatientsPage(q, allBody); }
            });
        } else {
            // Filtered mode: use server search for All Patients
            const target = allBody;
            target.innerHTML = '';
            const controller = new AbortController();
            if (currentAbort) currentAbort.abort();
            currentAbort = controller;
            renderState(target, 'Searching…');
            fetch('/vista_patient_search', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ query: q }), signal: controller.signal
            }).then(r=>r.json()).then(data => {
                target.innerHTML = '';
                const matches = Array.isArray(data.matches)? data.matches : [];
                matches.sort((a,b)=> (a.name||'').localeCompare(b.name||''));
                allCount = matches.length;
                if (!matches.length){ renderState(target, 'No matches in all patients.'); return; }
                matches.forEach(m => {
                    const display = `${highlight(m.name, q)} <span style="opacity:.7">(DFN: ${escapeHtml(m.dfn)})<\/span>`;
                    const opt = makeOption(m, display);
                    target.appendChild(opt);
                    currentItemsFlat.push(opt);
                });
            }).catch(err => {
                if (err && err.name === 'AbortError') return;
                target.innerHTML=''; renderState(target, 'Search failed.');
            });
        }

        // Announce section counts for accessibility
        try { announce(`My Default Patient List: ${defCount} item${defCount===1?'':'s'}. All Patients: ${allCount} item${allCount===1?'':'s'} loaded.`); } catch(_){}
        // Update masking if demo enabled
        try { if (window.demoMasking && window.demoMasking.enabled && typeof window.demoMasking.maskDropdownItems === 'function') window.demoMasking.maskDropdownItems(); } catch(_){ }
    }

    async function ensureDefaultList(){
        if (defaultList && Array.isArray(defaultList.matches)) return defaultList;
        // Try client sessionStorage
        try {
            const raw = sessionStorage.getItem(DEFAULT_CACHE_KEY);
            if (raw){ defaultList = JSON.parse(raw); }
        } catch(_){ defaultList = null; }
        if (defaultList && Array.isArray(defaultList.matches)) return defaultList;
        // Fetch from server
        try {
            const resp = await fetch('/vista_default_patient_list', { cache:'no-store' });
            const data = await resp.json();
            if (data && Array.isArray(data.matches)){
                defaultList = { matches: data.matches, ts: Date.now(), cached: !!data.cached };
                try { sessionStorage.setItem(DEFAULT_CACHE_KEY, JSON.stringify(defaultList)); } catch(_){ }
            } else {
                defaultList = { matches: [], ts: Date.now(), error: data && data.error };
            }
        } catch(e){ defaultList = { matches: [], ts: Date.now(), error: String(e) }; }
        return defaultList;
    }

    async function loadNextAllPatientsPage(query, bodyEl){
        if (query) return; // only browse when no query
        if (allBrowse.loading || allBrowse.exhausted) return;
        allBrowse.loading = true;
        try {
            const res = await fetch('/vista_patient_browse', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ cursor: allBrowse.next_cursor || '', limit: 50 })
            });
            const data = await res.json();
            if (data && Array.isArray(data.matches)){
                if (!data.matches.length){ allBrowse.exhausted = true; }
                else {
                    // Alphabetical already enforced server-side, but keep stable
                    const newOnes = data.matches;
                    allBrowse.items = allBrowse.items.concat(newOnes);
                    allBrowse.next_cursor = data.next_cursor || allBrowse.next_cursor;
                    // If dropdown visible, append
                    if (dropdown && bodyEl){
                        newOnes.forEach(m => {
                            const display = `${escapeHtml(m.name)} <span style=\"opacity:.7\">(DFN: ${escapeHtml(m.dfn)})<\/span>`;
                            const opt = makeOption(m, display);
                            bodyEl.appendChild(opt);
                            currentItemsFlat.push(opt);
                        });
                    }
                }
            } else {
                allBrowse.exhausted = true;
            }
        } catch(e){
            // Mark exhausted to prevent loops; user can refocus to retry
            allBrowse.exhausted = true;
        } finally { allBrowse.loading = false; }
    }

    function resetKeyboard(){ currentIndex = -1; currentItemsFlat.forEach(i=> i.classList.remove('selected-patient')); }
    function moveSelection(delta){
        if (!currentItemsFlat.length) return;
        if (currentIndex === -1){ currentIndex = 0; }
        else { currentIndex = (currentIndex + delta + currentItemsFlat.length) % currentItemsFlat.length; }
        currentItemsFlat.forEach(i=> { i.classList.remove('selected-patient'); i.setAttribute('aria-selected','false'); });
        const el = currentItemsFlat[currentIndex];
        if (el){ el.classList.add('selected-patient'); el.setAttribute('aria-selected','true'); el.scrollIntoView({ block: 'nearest' }); try { searchInput.setAttribute('aria-activedescendant', el.id); } catch(_){} }
    }

    async function openDropdown(initialQuery){
        await ensureDefaultList();
        buildGroupedDropdown(initialQuery || '');
        if (!initialQuery){
            // Kick off first All Patients page
            allBrowse = { items: [], next_cursor: '', loading: false, exhausted: false };
            const allBody = dropdown && dropdown.querySelector('[aria-label="All Patients"] > div:last-child');
            await loadNextAllPatientsPage('', allBody);
        }
        announce('Patient list opened');
    }

    // Focus opens dropdown and preloads lists
    searchInput.addEventListener('focus', async () => {
        try { if (!dropdown) await openDropdown(''); } catch(_e){}
    });

    // Input filter with debounce (200–300ms)
    searchInput.addEventListener('input', function(){
        if (window.demoMasking && window.demoMasking.enabled && window.demoMasking.concealInput) {
            window.demoMasking.concealInput(this);
        }
        const val = (this.value || '').replace(/^([^,]*,)\s(.*)$/,'$1$2');
        const q = val.trim();
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            await ensureDefaultList();
            buildGroupedDropdown(q);
        }, 250);
    });

    // Keyboard navigation
    searchInput.addEventListener('keydown', (e) => {
        if (!dropdown) return;
        if (e.key === 'ArrowDown'){ e.preventDefault(); moveSelection(+1); }
        else if (e.key === 'ArrowUp'){ e.preventDefault(); moveSelection(-1); }
        else if (e.key === 'Enter'){
            if (currentIndex >= 0 && currentItemsFlat[currentIndex]) currentItemsFlat[currentIndex].click();
        } else if (e.key === 'Escape'){
            cleanupDropdown();
            try { searchInput.removeAttribute('aria-activedescendant'); } catch(_){}
        }
    });

    // Blur closes dropdown (delay to allow click)
    searchInput.addEventListener('blur', () => setTimeout(() => cleanupDropdown(), 180));
});

async function selectPatientFromDropdown(match, item) {
    // Re-query elements locally to avoid closure scope issues
    const searchInputEl = document.getElementById("patientSearchInput");
    const resultsDivEl = document.getElementById("patientLookupResults");
    const dropdownEl = document.getElementById('patientDropdownListbox');

    // Highlight selected
    if (dropdownEl) {
        Array.from(dropdownEl.querySelectorAll('[role="option"]')).forEach(i => i.classList.remove("selected-patient"));
        if (item) item.classList.add("selected-patient");
    }

    if (searchInputEl) searchInputEl.value = match.name;
    if (dropdownEl) dropdownEl.remove();
    // Close search UI immediately after user chooses a patient
    closePatientSearchUI();

    // Fetch ORWPT SELECT preview to confirm selection (fallback to demographics)
    let preview = null;
    try {
        const resp = await fetch('/vista_patient_select_preview', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dfn: match.dfn })
        });
        const body = await resp.json();
        if (resp.status === 403 && body && body.sensitive){
            try { await showSensitiveNoticeModal({ message: body.message || 'Sensitive record. Access denied.', dfn: match.dfn }); } catch(_e){}
            return;
        }
        preview = body;
        if (preview && preview.error) throw new Error(preview.error);
    } catch(_e) {
        // Fallback minimal fields via demographics
        try {
            const r2 = await fetch('/vista_patient_demographics', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dfn: match.dfn, fallback_name: match.name })
            });
            const demo = await r2.json();
            preview = {
                dfn: match.dfn,
                name: (demo && demo.name) || match.name,
                ssn: (demo && demo.ssn) || 'Unknown',
                dob: (demo && demo.dob) || 'Unknown'
            };
        } catch(_e2) {
            preview = { dfn: match.dfn, name: match.name };
        }
    }

    const confirmed = await showPatientConfirmModal({
        dfn: match.dfn,
        name: (preview && preview.name) || match.name,
        sex: (preview && preview.sex) || '',
        dob: (preview && preview.dob) || '',
        ssn: (preview && preview.ssn) || '',
        serviceConnected: (preview && (preview.serviceConnected || preview.serviceconnected)) || '',
        scPercent: (preview && (preview.scPercent || preview.scpercent)) || '',
        location: (preview && preview.location) || '',
        roomBed: (preview && (preview.roomBed || preview.roombed)) || '',
        raw: (preview && preview.raw) || ''
    });
    if (!confirmed) return; // user canceled

    if (resultsDivEl) {
        const displayName = (window.demoMasking && window.demoMasking.enabled && window.demoMasking.maskName)
            ? window.demoMasking.maskName(((preview && preview.name) || match.name))
            : ((preview && preview.name) || match.name);
        resultsDivEl.textContent = `Fetching chart for ${displayName}...`;
    }

    // 1) Save & Clear current session
    await preSwitchSaveAndClear();
    // 2) Fetch FHIR bundle
    const res2 = await fetch("/select_patient", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_dfn: match.dfn })
    });
    const fhirData = await res2.json();
    // Cache-buster key
    try { window.CURRENT_PATIENT_DFN = match.dfn; } catch(_e){}
    // Ordering guard
    let meta = null;
    try { const mr = await fetch('/get_patient', { cache: 'no-store' }); meta = await mr.json(); await new Promise(r=> setTimeout(r, 60)); } catch(_e){}
    // Update patient record display (removed JSON dump feature)
    const jsonEl = document.getElementById("patientRecordJson");
    if (jsonEl) {
        jsonEl.remove();
        const container = document.getElementById("patientRecordDisplay");
        if (container) container.remove();
    }
    // Render tables and panels; refresh documents list
    if (typeof window.displayPatientInfo === "function") window.displayPatientInfo(fhirData);
    if (typeof window.renderMedicationsTable === "function") window.renderMedicationsTable(fhirData);
    if (typeof window.renderLabsTable === "function") window.renderLabsTable(fhirData);
    if (typeof window.initPrimaryNoteUI === "function") window.initPrimaryNoteUI(fhirData);
    if (typeof window.resetDocuments === "function") {
        window.resetDocuments();
    } else if (typeof window.refreshDocuments === "function") {
        window.refreshDocuments();
    }
    // New: refresh vitals sidebar
    if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function') {
        window.VitalsSidebar.refresh();
    }
    // New: refresh right sidebar
    if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function') {
        window.RightSidebar.refresh();
    }
    // Start new archive for this patient and start auto-save
    const patientName = ((preview && preview.name) || (match && match.name)) || (meta && meta.name) || '';
    await setNewArchiveForPatient(patientName);
}

// Simple confirm modal with ARIA for patient selection
async function showPatientConfirmModal({ name, ssn, dob, dfn, sex, serviceConnected, scPercent, location, roomBed, raw }){
    return new Promise(resolve => {
        // Overlay
        const overlay = document.createElement('div');
        overlay.style.position = 'fixed';
        overlay.style.left = '0';
        overlay.style.top = '0';
        overlay.style.right = '0';
        overlay.style.bottom = '0';
        overlay.style.background = 'rgba(0,0,0,0.45)';
        overlay.style.zIndex = '2000';
        overlay.addEventListener('click', (e) => { if (e.target === overlay) cleanup(false); });

        // Dialog
        const dialog = document.createElement('div');
        dialog.setAttribute('role','dialog');
        dialog.setAttribute('aria-modal','true');
        dialog.setAttribute('aria-labelledby','patient-confirm-title');
        dialog.style.position = 'absolute';
        dialog.style.left = '50%';
        dialog.style.top = '20%';
        dialog.style.transform = 'translateX(-50%)';
        dialog.style.minWidth = '320px';
        dialog.style.maxWidth = '90vw';
        dialog.style.background = '#fff';
        dialog.style.borderRadius = '8px';
        dialog.style.boxShadow = '0 12px 28px rgba(0,0,0,0.25)';
        dialog.style.padding = '16px';

        const title = document.createElement('h2');
        title.id = 'patient-confirm-title';
        title.textContent = 'Confirm patient selection';
        title.style.margin = '0 0 8px 0';
        title.style.fontSize = '1.1rem';

        const body = document.createElement('div');
        body.style.marginBottom = '12px';
        body.innerHTML = `
                <div style="display:grid; grid-template-columns: 120px 1fr; gap: 4px 8px; align-items:center;">
                    <div><strong>Name:<\/strong><\/div><div>${name ? escapeHtml(name) : 'Unknown'}<\/div>
                    <div><strong>Sex:<\/strong><\/div><div>${sex ? escapeHtml(sex) : 'Unknown'}<\/div>
                    <div><strong>DOB:<\/strong><\/div><div>${dob ? escapeHtml(dob) : 'Unknown'}<\/div>
                    <div><strong>SSN:<\/strong><\/div><div>${ssn ? escapeHtml(ssn) : 'Unknown'}<\/div>
                    <div><strong>Service Conn.:<\/strong><\/div><div>${serviceConnected ? escapeHtml(String(serviceConnected)) : 'Unknown'}<\/div>
                    <div><strong>SC%:<\/strong><\/div><div>${scPercent ? escapeHtml(String(scPercent)) : 'Unknown'}<\/div>
                    <div><strong>Location:<\/strong><\/div><div>${location ? escapeHtml(location) : 'Unknown'}<\/div>
                    <div><strong>Room/Bed:<\/strong><\/div><div>${roomBed ? escapeHtml(roomBed) : 'Unknown'}<\/div>
                <\/div>
                <div style="margin: 10px 0 0 0; color: #444">DFN: ${escapeHtml(String(dfn||''))}<\/div>
                <div style="margin-top: 12px; color:#666">Is this the patient you want to select?<\/div>
            `;

        const btnRow = document.createElement('div');
        btnRow.style.display = 'flex';
        btnRow.style.gap = '8px';
        btnRow.style.justifyContent = 'flex-end';

        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.style.padding = '6px 12px';
        cancelBtn.addEventListener('click', () => cleanup(false));

        const confirmBtn = document.createElement('button');
        confirmBtn.type = 'button';
        confirmBtn.textContent = 'Confirm';
        confirmBtn.style.padding = '6px 12px';
        confirmBtn.style.background = '#0b5ed7';
        confirmBtn.style.color = 'white';
        confirmBtn.style.border = 'none';
        confirmBtn.style.borderRadius = '4px';
        confirmBtn.addEventListener('click', () => cleanup(true));

        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(confirmBtn);

        dialog.appendChild(title);
        dialog.appendChild(body);
        dialog.appendChild(btnRow);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // Focus management
        const prevActive = document.activeElement;
        confirmBtn.focus();
        function onKey(e){
            if (e.key === 'Escape'){ e.preventDefault(); cleanup(false); }
            if (e.key === 'Enter'){ e.preventDefault(); cleanup(true); }
        }
        document.addEventListener('keydown', onKey);

        function cleanup(val){
            document.removeEventListener('keydown', onKey);
            try { document.body.removeChild(overlay); } catch(_){ }
            try { if (prevActive && prevActive.focus) prevActive.focus(); } catch(_){ }
            resolve(!!val);
        }
    });
}

// Sensitive record notice modal (non-persistent)
async function showSensitiveNoticeModal({ message, dfn }){
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.style.position = 'fixed'; overlay.style.left = '0'; overlay.style.top = '0'; overlay.style.right = '0'; overlay.style.bottom = '0';
        overlay.style.background = 'rgba(0,0,0,0.45)'; overlay.style.zIndex = '2100';
        overlay.addEventListener('click', (e)=>{ if (e.target === overlay) cleanup(); });

        const dialog = document.createElement('div');
        dialog.setAttribute('role','dialog'); dialog.setAttribute('aria-modal','true');
        dialog.style.position = 'absolute'; dialog.style.left = '50%'; dialog.style.top = '24%'; dialog.style.transform = 'translateX(-50%)';
        dialog.style.minWidth = '320px'; dialog.style.maxWidth = '90vw'; dialog.style.background = '#fff'; dialog.style.borderRadius = '8px';
        dialog.style.boxShadow = '0 12px 28px rgba(0,0,0,0.25)'; dialog.style.padding = '16px';

        const title = document.createElement('h2');
        title.textContent = 'Sensitive Record';
        title.style.margin = '0 0 8px 0'; title.style.fontSize = '1.1rem';

        const body = document.createElement('div');
        body.innerHTML = `
            <div style="color:#b00020; margin-bottom:8px;"><strong>Access blocked</strong><\/div>
            <div style="color:#444; white-space:pre-wrap;">${escapeHtml(String(message||'This record is marked sensitive and cannot be opened.'))}<\/div>
            <div style="margin-top:10px; color:#666;">DFN: ${escapeHtml(String(dfn||''))}<\/div>
        `;

        const btns = document.createElement('div');
        btns.style.display='flex'; btns.style.justifyContent='flex-end'; btns.style.gap='8px'; btns.style.marginTop='12px';
        const close = document.createElement('button');
        close.type='button'; close.textContent='OK'; close.style.padding='6px 12px';
        close.addEventListener('click', ()=> cleanup());
        btns.appendChild(close);

        dialog.appendChild(title); dialog.appendChild(body); dialog.appendChild(btns);
        overlay.appendChild(dialog); document.body.appendChild(overlay);

        const prev = document.activeElement; close.focus();
        function onKey(e){ if (e.key === 'Escape' || e.key === 'Enter'){ e.preventDefault(); cleanup(); } }
        document.addEventListener('keydown', onKey);
        function cleanup(){ document.removeEventListener('keydown', onKey); try{ document.body.removeChild(overlay);}catch(_){} try{ if(prev&&prev.focus) prev.focus(); }catch(_){} resolve(); }
    });
}