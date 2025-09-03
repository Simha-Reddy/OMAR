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

// Sensitive access check + demographics confirmation helpers
async function checkSensitiveAccess(dfn) {
    try {
        const r = await fetch('/vista_sensitive_check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dfn }),
            cache: 'no-store'
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
        return data; // {allowed, message}
    } catch (e) {
        console.warn('Sensitive check error', e);
        return { allowed: false, message: 'Unable to verify access.' };
    }
}

async function fetchPatientDemographics(dfn) {
    const r = await fetch('/vista_patient_demographics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dfn }),
        cache: 'no-store'
    });
    const data = await r.json();
    if (!r.ok || data.error) throw new Error(data.error || 'Demographics retrieval failed');
    return data; // { name, sex, dob, ssnFormatted, ... }
}

function maskSsnForDemo(ssn) {
    try {
        if (!ssn) return ssn;
        if (window.demoMasking && window.demoMasking.enabled) {
            const digits = (ssn || '').replace(/\D+/g, '');
            if (digits.length === 9) return `***-**-${digits.slice(-4)}`;
            return '***-**-****';
        }
        return ssn;
    } catch (_) { return ssn; }
}

function buildConfirmModal({ name, sex, dob, ssnFormatted }) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:2000;display:flex;align-items:center;justify-content:center;';
    const panel = document.createElement('div');
    panel.style.cssText = 'background:#fff; width:min(560px,92vw); border-radius:8px; box-shadow:0 8px 30px rgba(0,0,0,0.35);';
    const header = document.createElement('div');
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid #eee;font-weight:600;';
    header.textContent = 'Confirm Patient';
    const body = document.createElement('div');
    body.style.cssText = 'padding:14px 16px; line-height:1.6;';
    const footer = document.createElement('div');
    footer.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;padding:10px 14px;border-top:1px solid #eee;';

    const row = (label, val) => {
        const d = document.createElement('div');
        const l = document.createElement('div'); l.style.fontWeight = '600'; l.textContent = label;
        const v = document.createElement('div'); v.textContent = val || '';
        d.appendChild(l); d.appendChild(v);
        d.style.marginBottom = '8px';
        return d;
    };

    const demoSSN = maskSsnForDemo(ssnFormatted);
    body.appendChild(row('NAME:', name || ''));
    body.appendChild(row('SEX:', sex || ''));
    body.appendChild(row('DOB:', dob || ''));
    body.appendChild(row('SSN:', demoSSN || ''));

    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    const okBtn = document.createElement('button');
    okBtn.textContent = 'Proceed';
    okBtn.style.cssText = 'background:#0d6efd;color:#fff;border:none;padding:6px 12px;border-radius:6px;';

    footer.appendChild(cancelBtn);
    footer.appendChild(okBtn);

    panel.appendChild(header);
    panel.appendChild(body);
    panel.appendChild(footer);
    overlay.appendChild(panel);

    return new Promise(resolve => {
        function cleanup() { try { overlay.remove(); } catch(_){} }
        cancelBtn.onclick = () => { cleanup(); resolve(false); };
        okBtn.onclick = () => { cleanup(); resolve(true); };
        overlay.addEventListener('click', (e) => { if (e.target === overlay) { cleanup(); resolve(false); } });
        document.addEventListener('keydown', function esc(e){ if (e.key === 'Escape'){ cleanup(); resolve(false); document.removeEventListener('keydown', esc);} });
        document.body.appendChild(overlay);
    });
}

function showSensitiveNotice(message) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:2000;display:flex;align-items:center;justify-content:center;';
    const panel = document.createElement('div');
    panel.style.cssText = 'background:#fff; width:min(520px,92vw); border-radius:8px; box-shadow:0 8px 30px rgba(0,0,0,0.35);';
    const header = document.createElement('div');
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid #eee;font-weight:600;color:#b02a37;';
    header.textContent = 'Sensitive Record';
    const body = document.createElement('div');
    body.style.cssText = 'padding:14px 16px;';
    body.textContent = message || 'This patient record is sensitive. Access is restricted.';
    const footer = document.createElement('div');
    footer.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;padding:10px 14px;border-top:1px solid #eee;';
    const okBtn = document.createElement('button'); okBtn.textContent = 'OK';
    footer.appendChild(okBtn);
    panel.appendChild(header); panel.appendChild(body); panel.appendChild(footer); overlay.appendChild(panel);
    return new Promise(resolve => {
        function cleanup(){ try { overlay.remove(); } catch(_){} }
        okBtn.onclick = () => { cleanup(); resolve(); };
        overlay.addEventListener('click', (e)=>{ if (e.target === overlay){ cleanup(); resolve(); } });
        document.addEventListener('keydown', function esc(e){ if (e.key === 'Escape'){ cleanup(); resolve(); document.removeEventListener('keydown', esc);} });
        document.body.appendChild(overlay);
    });
}

async function guardAndConfirmPatientLoad(dfn, nameForDisplay) {
    const resultsDiv = document.getElementById('patientLookupResults');
    try {
        if (resultsDiv) resultsDiv.textContent = 'Checking access...';
        const sens = await checkSensitiveAccess(dfn);
        if (!sens.allowed) {
            await showSensitiveNotice(sens.message || 'Sensitive record. Access denied.');
            if (resultsDiv) resultsDiv.textContent = '';
            return false;
        }
        if (resultsDiv) resultsDiv.textContent = 'Fetching demographics...';
        const demo = await fetchPatientDemographics(dfn);
        const proceed = await buildConfirmModal(demo);
        if (!proceed) {
            if (resultsDiv) resultsDiv.textContent = '';
            return false;
        }
        if (resultsDiv) {
            const nm = (nameForDisplay || demo.name || '').toString();
            const dispName = (window.demoMasking && window.demoMasking.enabled && window.demoMasking.maskName)
                ? window.demoMasking.maskName(nm)
                : nm;
            resultsDiv.textContent = `Loading chart for ${dispName}...`;
        }
        return true;
    } catch (e) {
        console.warn('guardAndConfirmPatientLoad error', e);
        if (resultsDiv) resultsDiv.textContent = '';
        return false;
    }
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
    // New: sensitive check + demographics confirmation before proceeding
    const ok = await guardAndConfirmPatientLoad(dfn, name);
    if (!ok) return;

    // 1) Save & Clear current session (after confirmation)
    await preSwitchSaveAndClear();

    // Proactively close search UI once a patient is chosen
    closePatientSearchUI();

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
        if (typeof window.displayPatientInfo === "function") window.displayPatientInfo(data);
        if (typeof window.renderMedicationsTable === "function") window.renderMedicationsTable(data);
        if (typeof window.renderLabsTable === "function") window.renderLabsTable(data);
        if (typeof window.initPrimaryNoteUI === "function") window.initPrimaryNoteUI(data);
        if (typeof window.resetDocuments === "function") {
            window.resetDocuments();
        } else if (typeof window.refreshDocuments === "function") {
            window.refreshDocuments();
        }
        if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function') {
            window.VitalsSidebar.refresh();
        }
        if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function') {
            window.RightSidebar.refresh();
        }
        const patientName = (name || (meta && meta.name) || '').toString();
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
            // Guard + confirm
            const ok = await guardAndConfirmPatientLoad(patient_dfn);
            if (!ok) return;
            // 1) Save & Clear current session
            await preSwitchSaveAndClear();
            // Proactively close search UI once a patient is chosen
            closePatientSearchUI();
            // 2) Load new patient
            const res = await fetch("/select_patient", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ patient_dfn })
            });
            const data = await res.json();
            try { window.CURRENT_PATIENT_DFN = patient_dfn; } catch(_e){}
            let meta = null;
            try { const mr = await fetch('/get_patient', { cache: 'no-store' }); meta = await mr.json(); await new Promise(r=> setTimeout(r, 60)); } catch(_e){}
            if (data && !data.error) {
                console.log(data);
                if (typeof window.displayPatientInfo === "function") window.displayPatientInfo(data);
                if (typeof window.renderMedicationsTable === "function") window.renderMedicationsTable(data);
                if (typeof window.renderLabsTable === "function") window.renderLabsTable(data);
                if (typeof window.initPrimaryNoteUI === "function") window.initPrimaryNoteUI(data);
                if (typeof window.resetDocuments === "function") {
                    window.resetDocuments();
                } else if (typeof window.refreshDocuments === "function") {
                    window.refreshDocuments();
                }
                if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function') {
                    window.VitalsSidebar.refresh();
                }
                if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function') {
                    window.RightSidebar.refresh();
                }
                const patientName = (meta && meta.name) || '';
                await setNewArchiveForPatient(patientName);
            } else {
                alert("Failed to select patient: " + (data.error || "Unknown error"));
            }
        };
    }
});

// --- Enhanced Patient Search Dropdown with Default Patient List ---
document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("patientSearchInput");
    const resultsDiv = document.getElementById("patientLookupResults");
    let dropdown = null;

    if (searchInput) {
        // ARIA: identify input as combobox
        searchInput.setAttribute('role', 'combobox');
        searchInput.setAttribute('aria-autocomplete', 'list');
        searchInput.setAttribute('aria-expanded', 'false');
        searchInput.setAttribute('aria-haspopup', 'listbox');

        // State management
        let currentDropdownIndex = -1;
        let dropdownItems = [];
        let debounceTimer = null;
        let lastQuery = '';
        let currentAbort = null;
        let defaultPatientList = null;
        let defaultListCache = null;
        let defaultListTimestamp = null;
        let cacheUserKey = null; // DUZ@DIV for invalidation
        let isLoadingDefault = false;
        let focusInitialized = false;
        let defaultListUnavailable = false; // fallback notice flag

        // Pagination state for All Patients
        let paging = {
            query: '',
            hasMore: false,
            nextCursor: null,
            loadingMore: false,
            pageSize: 50,
            container: null // DOM container for All Patients items
        };

        // Cache default list for session (invalidate after 30 minutes or on user change)
        const CACHE_DURATION = 30 * 60 * 1000; // 30 minutes

        function cleanupDropdown() { 
            if (dropdown) { 
                dropdown.remove(); 
                dropdown = null; 
                dropdownItems = [];
                currentDropdownIndex = -1;
                // ARIA update
                searchInput.setAttribute('aria-expanded', 'false');
                searchInput.removeAttribute('aria-controls');
                searchInput.removeAttribute('aria-activedescendant');
                searchInput.removeAttribute('aria-owns');
            } 
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function highlightMatch(text, query) {
            if (!query) return escapeHtml(text);
            const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
            return escapeHtml(text).replace(regex, '<mark>$1</mark>');
        }

        function filterPatients(patients, query) {
            if (!query) return patients;
            const searchTerms = query.toLowerCase().split(/\s+/).filter(Boolean);
            return patients.filter(patient => {
                const searchText = `${patient.name} ${patient.dfn}`.toLowerCase();
                return searchTerms.every(term => searchText.includes(term));
            });
        }

        async function fetchDefaultPatientList() {
            if (isLoadingDefault) return defaultListCache;
            
            // Check cache validity
            if (defaultListCache && defaultListTimestamp && 
                (Date.now() - defaultListTimestamp) < CACHE_DURATION) {
                return defaultListCache;
            }

            isLoadingDefault = true;
            defaultListUnavailable = false;
            try {
                const response = await fetch('/vista_default_patient_list', {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' },
                    cache: 'no-store'
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }
                // Invalidate cache if user/site changed
                const duz = data.user && data.user.duz || null;
                const div = data.user && data.user.division || null;
                const newKey = `${duz || ''}@${div || ''}`;
                if (cacheUserKey && newKey && newKey !== cacheUserKey) {
                    defaultListCache = null;
                }
                cacheUserKey = newKey;
                defaultListCache = data.patients || [];
                defaultListTimestamp = Date.now();
                return defaultListCache;
            } catch (error) {
                console.warn('Failed to fetch default patient list:', error);
                defaultListUnavailable = true;
                defaultListCache = [];
                defaultListTimestamp = Date.now();
                return defaultListCache;
            } finally {
                isLoadingDefault = false;
            }
        }

        function showLoadingState(message = 'Loading patients...') {
            cleanupDropdown();
            dropdown = document.createElement("div");
            dropdown.className = "patient-dropdown";
            dropdown.setAttribute('role', 'status');
            dropdown.setAttribute('aria-live', 'polite');
            
            Object.assign(dropdown.style, {
                position: "absolute",
                background: "#fff",
                border: "1px solid #ccc",
                borderRadius: "4px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                zIndex: "1000",
                maxHeight: "100px"
            });

            const loadingDiv = document.createElement("div");
            loadingDiv.className = "loading-state";
            loadingDiv.textContent = message;
            dropdown.appendChild(loadingDiv);

            positionDropdown();
            document.body.appendChild(dropdown);
        }

        function showErrorState(message) {
            cleanupDropdown();
            dropdown = document.createElement("div");
            dropdown.className = "patient-dropdown";
            dropdown.setAttribute('role', 'alert');
            
            Object.assign(dropdown.style, {
                position: "absolute",
                background: "#fff",
                border: "1px solid #dc3545",
                borderRadius: "4px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                zIndex: "1000",
                maxHeight: "100px"
            });

            const errorDiv = document.createElement("div");
            errorDiv.className = "error-state";
            errorDiv.textContent = message;
            dropdown.appendChild(errorDiv);

            positionDropdown();
            document.body.appendChild(dropdown);
            
            // Auto-hide error after 5 seconds
            setTimeout(cleanupDropdown, 5000);
        }

        async function runSearch(query) {
            try {
                if (currentAbort) { currentAbort.abort(); }
                currentAbort = new AbortController();
                
                // Normalize: remove exactly one space right after the first comma
                const normalized = (query || '').replace(/^([^,]*,)\s(.*)$/,'$1$2');
                
                showLoadingState();
                
                const res = await fetch("/vista_patient_search", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ query: normalized, pageSize: paging.pageSize }),
                    signal: currentAbort.signal,
                    cache: 'no-store'
                });
                
                const data = await res.json();
                const allPatients = (data.matches || []).slice();
                paging.query = query;
                paging.hasMore = !!data.hasMore;
                paging.nextCursor = data.nextCursor || null;
                paging.loadingMore = false;
                
                // Get default list
                const defaultList = await fetchDefaultPatientList();
                
                // Filter both lists
                const filteredDefault = filterPatients(defaultList, query);
                const filteredAll = filterPatients(allPatients, query);
                
                // Remove duplicates from All Patients that are in Default List
                const defaultDfns = new Set(filteredDefault.map(p => p.dfn));
                const uniqueAll = filteredAll.filter(p => !defaultDfns.has(p.dfn));
                
                // Sort All Patients alphabetically
                uniqueAll.sort((a, b) => a.name.localeCompare(b.name));
                
                createDropdown(filteredDefault, uniqueAll, query);
                
            } catch (err) {
                if (err.name === 'AbortError') return;
                cleanupDropdown();
                showErrorState('Patient search failed. Please try again.');
                console.warn('Patient search failed', err);
            }
        }

        function createDropdown(defaultPatients, allPatients, query) {
            cleanupDropdown();
            
            dropdown = document.createElement("div");
            dropdown.className = "patient-dropdown";
            dropdown.setAttribute('role', 'listbox');
            dropdown.setAttribute('aria-label', 'Patient search results');
            const listboxId = 'patient-dropdown-listbox';
            dropdown.id = listboxId;
            // Link input to listbox
            searchInput.setAttribute('aria-controls', listboxId);
            searchInput.setAttribute('aria-owns', listboxId);
            searchInput.setAttribute('aria-expanded', 'true');
            
            // Styling
            Object.assign(dropdown.style, {
                position: "absolute",
                background: "#fff",
                border: "1px solid #ccc",
                borderRadius: "4px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                zIndex: "1000",
                maxHeight: "300px",
                overflowY: "auto"
            });

            let itemIndex = 0;

            // Optional notice when default list unavailable
            if (defaultListUnavailable) {
                const notice = document.createElement('div');
                notice.textContent = 'Default patient list unavailable. Showing All Patients.';
                Object.assign(notice.style, { padding: '8px 12px', color: '#6c757d', fontStyle: 'italic' });
                dropdown.appendChild(notice);
            }

            // Default Patient List Section
            if (defaultPatients && defaultPatients.length > 0) {
                const defaultHeader = document.createElement("div");
                defaultHeader.className = "section-header";
                defaultHeader.textContent = "My Default Patient List";
                defaultHeader.setAttribute('role', 'group');
                defaultHeader.setAttribute('aria-label', 'Default patient list');
                defaultHeader.id = 'default-patient-group';
                Object.assign(defaultHeader.style, {
                    padding: "8px 12px",
                    background: "#f8f9fa",
                    borderBottom: "1px solid #e9ecef",
                    fontWeight: "600",
                    fontSize: "14px",
                    color: "#495057"
                });
                dropdown.appendChild(defaultHeader);

                defaultPatients.forEach(patient => {
                    const item = createPatientItem(patient, query, itemIndex++, 'default');
                    // Associate option to header for AT context
                    try { item.setAttribute('aria-describedby', 'default-patient-group'); } catch(_){}
                    dropdown.appendChild(item);
                    dropdownItems.push(item);
                });
            }

            // All Patients Section
            const allHeader = document.createElement("div");
            allHeader.className = "section-header";
            allHeader.textContent = "All Patients";
            allHeader.setAttribute('role', 'group');
            allHeader.setAttribute('aria-label', 'All patients');
            allHeader.id = 'all-patient-group';
            Object.assign(allHeader.style, {
                padding: "8px 12px",
                background: "#f8f9fa",
                borderBottom: "1px solid #e9ecef",
                borderTop: (defaultPatients && defaultPatients.length > 0) ? "1px solid #e9ecef" : "none",
                fontWeight: "600",
                fontSize: "14px",
                color: "#495057"
            });
            dropdown.appendChild(allHeader);

            // Container for All Patients items (for appending on scroll)
            const allContainer = document.createElement('div');
            allContainer.id = 'all-patients-container';
            dropdown.appendChild(allContainer);
            paging.container = allContainer;

            if (allPatients && allPatients.length > 0) {
                allPatients.forEach(patient => {
                    const item = createPatientItem(patient, query, itemIndex++, 'all');
                    try { item.setAttribute('aria-describedby', 'all-patient-group'); } catch(_){}
                    allContainer.appendChild(item);
                    dropdownItems.push(item);
                });
            } else {
                const emptyItem = document.createElement("div");
                emptyItem.textContent = defaultPatients && defaultPatients.length > 0 ? "No additional patients found" : "No patients found";
                emptyItem.style.padding = "12px";
                emptyItem.style.textAlign = "center";
                emptyItem.style.color = "#6c757d";
                emptyItem.style.fontStyle = "italic";
                allContainer.appendChild(emptyItem);
            }

            // Position and show dropdown
            positionDropdown();
            document.body.appendChild(dropdown);

            // Attach infinite scroll if more pages available
            attachInfiniteScroll(query, itemIndex);
        }

        let nextOptionIdSeq = 0;
        function createPatientItem(patient, query, index, section) {
            const item = document.createElement("div");
            item.className = "patient-item";
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', 'false');
            item.tabIndex = -1;
            item.dataset.index = index;
            item.dataset.section = section;
            const optionId = `patient-option-${++nextOptionIdSeq}`;
            item.id = optionId;

            // Build display text with highlighting
            let displayName = patient.name;
            let displayDfn = patient.dfn;
            
            // Apply demo masking if enabled
            if (window.demoMasking && window.demoMasking.enabled) {
                displayName = window.demoMasking.maskName(patient.name);
                item.dataset.originalName = patient.name;
            }

            const nameHtml = highlightMatch(displayName, query);
            const dfnHtml = highlightMatch(displayDfn, query);
            
            item.innerHTML = `
                <div class="patient-name">${nameHtml}</div>
                <div class="patient-dfn">DFN: ${dfnHtml}</div>
                ${patient.clinic ? `<div class="patient-clinic">${escapeHtml(patient.clinic)}</div>` : ''}
            `;

            // Styling
            Object.assign(item.style, {
                padding: "8px 12px",
                cursor: "pointer",
                borderBottom: "1px solid #f1f3f4",
                transition: "background-color 0.15s ease"
            });

            // Event handlers
            item.addEventListener('mouseenter', () => selectItem(index, optionId));
            item.addEventListener('click', () => selectPatientFromDropdown(patient, item));
            
            // Store patient data
            item._patientData = patient;

            return item;
        }

        function selectItem(index, optionId) {
            dropdownItems.forEach((item, i) => {
                const isSelected = i === index;
                item.classList.toggle('selected-patient', isSelected);
                item.setAttribute('aria-selected', isSelected);
                item.style.backgroundColor = isSelected ? '#e3f2fd' : '';
            });
            currentDropdownIndex = index;
            if (optionId) {
                searchInput.setAttribute('aria-activedescendant', optionId);
            } else if (dropdownItems[index]) {
                searchInput.setAttribute('aria-activedescendant', dropdownItems[index].id);
            }
        }

        function positionDropdown() {
            if (!dropdown || !searchInput) return;
            
            const rect = searchInput.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            const spaceBelow = viewportHeight - rect.bottom;
            const spaceAbove = rect.top;
            
            // Position dropdown
            dropdown.style.left = rect.left + "px";
            dropdown.style.width = Math.max(rect.width, 300) + "px";
            
            // Show above or below based on available space
            if (spaceBelow < 200 && spaceAbove > spaceBelow) {
                dropdown.style.bottom = (viewportHeight - rect.top) + "px";
                dropdown.style.top = "auto";
                dropdown.style.maxHeight = Math.min(spaceAbove - 10, 300) + "px";
            } else {
                dropdown.style.top = (rect.bottom + window.scrollY) + "px";
                dropdown.style.bottom = "auto";
                dropdown.style.maxHeight = Math.min(spaceBelow - 10, 300) + "px";
            }
        }

        async function showDefaultListOnFocus() {
            if (searchInput.value.trim()) {
                return; // Don't show default list if user has typed something
            }

            try {
                const defaultList = await fetchDefaultPatientList();
                createDropdown(defaultList, [], '');
            } catch (error) {
                console.warn('Failed to show default list on focus:', error);
            }
        }

        // Infinite scroll handler
        function attachInfiniteScroll(query, startIndex) {
            if (!dropdown) return;
            const onScroll = async () => {
                if (!paging.hasMore || paging.loadingMore || !paging.container) return;
                const threshold = 64; // px from bottom
                const scroller = dropdown;
                if ((scroller.scrollTop + scroller.clientHeight + threshold) >= scroller.scrollHeight) {
                    paging.loadingMore = true;
                    // Show loading indicator inside All Patients section
                    let loadingEl = document.getElementById('all-patients-loading');
                    if (!loadingEl) {
                        loadingEl = document.createElement('div');
                        loadingEl.id = 'all-patients-loading';
                        loadingEl.textContent = 'Loading more...';
                        Object.assign(loadingEl.style, { padding: '8px 12px', color: '#6c757d', fontStyle: 'italic' });
                        paging.container.appendChild(loadingEl);
                    }
                    try {
                        const res = await fetch('/vista_patient_search', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ query, pageSize: paging.pageSize, cursor: paging.nextCursor }),
                            cache: 'no-store'
                        });
                        const data = await res.json();
                        const newMatches = (data.matches || []);
                        paging.hasMore = !!data.hasMore;
                        paging.nextCursor = data.nextCursor || null;
                        if (newMatches.length) {
                            // Exclude any duplicates (by DFN) already present
                            const existingDfns = new Set(dropdownItems.map(it => it._patientData && it._patientData.dfn).filter(Boolean));
                            // Also exclude any in default list
                            const defaultDfns = new Set((defaultListCache || []).map(p => p.dfn));
                            const filtered = newMatches.filter(p => !existingDfns.has(p.dfn) && !defaultDfns.has(p.dfn));
                            // Keep alphabetical order
                            filtered.sort((a, b) => a.name.localeCompare(b.name));
                            let idx = dropdownItems.length;
                            filtered.forEach(p => {
                                const item = createPatientItem(p, query, idx++, 'all');
                                paging.container.appendChild(item);
                                dropdownItems.push(item);
                            });
                        }
                    } catch (e) {
                        console.warn('Load more failed', e);
                    } finally {
                        // Remove loading indicator
                        const l = document.getElementById('all-patients-loading');
                        if (l) l.remove();
                        paging.loadingMore = false;
                    }
                }
            };
            dropdown.addEventListener('scroll', onScroll);
        }

        // Event Listeners
        searchInput.addEventListener("focus", async function() {
            if (!focusInitialized) {
                focusInitialized = true;
                await showDefaultListOnFocus();
            } else if (!dropdown && !this.value.trim()) {
                await showDefaultListOnFocus();
            }
        });

        searchInput.addEventListener("input", function() {
            // In demo mode, conceal characters but keep value intact and allow search
            if (window.demoMasking && window.demoMasking.enabled && window.demoMasking.concealInput) {
                window.demoMasking.concealInput(this);
            }
            
            // Normalize: remove exactly one space right after the first comma
            const normalizedValue = (this.value || '').replace(/^([^,]*,)\s(.*)$/,'$1$2');
            const query = normalizedValue.trim();
            
            if (!query) { 
                cleanupDropdown(); 
                lastQuery = ''; 
                if (currentAbort) currentAbort.abort(); 
                // Reset paging
                paging = { query: '', hasMore: false, nextCursor: null, loadingMore: false, pageSize: paging.pageSize, container: null };
                showDefaultListOnFocus();
                return; 
            }
            
            if (query === lastQuery) return; // avoid duplicate
            lastQuery = query;
            // Reset paging for new query
            paging.query = query; paging.hasMore = false; paging.nextCursor = null; paging.loadingMore = false; paging.container = null;
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => runSearch(query), 250);
        });

        // Enhanced keyboard navigation
        searchInput.addEventListener("keydown", function(e) {
            if (!dropdown || !dropdownItems.length) {
                if (e.key === "ArrowDown" && !dropdown) {
                    e.preventDefault();
                    showDefaultListOnFocus();
                }
                return;
            }
            
            switch (e.key) {
                case "ArrowDown":
                    e.preventDefault();
                    {
                        const nextIndex = currentDropdownIndex < dropdownItems.length - 1 ? 
                            currentDropdownIndex + 1 : 0;
                        selectItem(nextIndex);
                        dropdownItems[nextIndex].scrollIntoView({ block: "nearest" });
                    }
                    break;
                    
                case "ArrowUp":
                    e.preventDefault();
                    {
                        const prevIndex = currentDropdownIndex > 0 ? 
                            currentDropdownIndex - 1 : dropdownItems.length - 1;
                        selectItem(prevIndex);
                        dropdownItems[prevIndex].scrollIntoView({ block: "nearest" });
                    }
                    break;
                    
                case "Enter":
                    e.preventDefault();
                    if (currentDropdownIndex >= 0 && dropdownItems[currentDropdownIndex]) {
                        dropdownItems[currentDropdownIndex].click();
                    }
                    break;
                    
                case "Escape":
                    e.preventDefault();
                    cleanupDropdown();
                    searchInput.blur();
                    break;
            }
        });

        // Remove dropdown on blur with delay to allow for clicks
        searchInput.addEventListener("blur", () => {
            setTimeout(() => cleanupDropdown(), 200);
        });

        // Close dropdown when clicking outside
        document.addEventListener("click", (e) => {
            if (!searchInput.contains(e.target) && (!dropdown || !dropdown.contains(e.target))) {
                cleanupDropdown();
            }
        });

        // Handle window resize
        window.addEventListener("resize", () => {
            if (dropdown) {
                positionDropdown();
            }
        });
    }

    async function selectPatientFromDropdown(match, item) {
        // Highlight selected
        if (dropdown) {
            Array.from(dropdown.children).forEach(i => i.classList.remove("selected-patient"));
            item.classList.add("selected-patient");
        }
        searchInput.value = match.name;
        if (dropdown) dropdown.remove();
        // Close search UI only after confirmation path completes
        
        // Mask name in demo mode for status
        const displayName = (window.demoMasking && window.demoMasking.enabled && window.demoMasking.maskName)
            ? window.demoMasking.maskName(match.name)
            : match.name;
        resultsDiv.textContent = `Checking access for ${displayName}...`;

        // Guard + confirm
        const ok = await guardAndConfirmPatientLoad(match.dfn, match.name);
        if (!ok) return;

        // 1) Save & Clear current session
        await preSwitchSaveAndClear();
        // Close search UI after confirmation
        closePatientSearchUI();

        // 2) Fetch FHIR bundle
        const res2 = await fetch("/select_patient", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patient_dfn: match.dfn })
        });
        const fhirData = await res2.json();
        try { window.CURRENT_PATIENT_DFN = match.dfn; } catch(_e){}
        let meta = null;
        try { const mr = await fetch('/get_patient', { cache: 'no-store' }); meta = await mr.json(); await new Promise(r=> setTimeout(r, 60)); } catch(_e){}
        const jsonEl = document.getElementById("patientRecordJson");
        if (jsonEl) {
            jsonEl.remove();
            const container = document.getElementById("patientRecordDisplay");
            if (container) container.remove();
        }
        if (typeof window.displayPatientInfo === "function") window.displayPatientInfo(fhirData);
        if (typeof window.renderMedicationsTable === "function") window.renderMedicationsTable(fhirData);
        if (typeof window.renderLabsTable === "function") window.renderLabsTable(fhirData);
        if (typeof window.initPrimaryNoteUI === "function") window.initPrimaryNoteUI(fhirData);
        if (typeof window.resetDocuments === "function") {
            window.resetDocuments();
        } else if (typeof window.refreshDocuments === "function") {
            window.refreshDocuments();
        }
        if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function') {
            window.VitalsSidebar.refresh();
        }
        if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function') {
            window.RightSidebar.refresh();
        }
        const patientName = (match && match.name) || (meta && meta.name) || '';
        await setNewArchiveForPatient(patientName);
    }
});