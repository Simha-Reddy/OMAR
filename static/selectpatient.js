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
        // Flush current archive file one last time before switching
        try {
            const prev = localStorage.getItem('ssva:currentArchiveName');
            if (prev && window.SessionManager && SessionManager.saveFullSession) {
                await SessionManager.saveFullSession(prev);
            }
        } catch(_e){}
        // Unbind the archive name to prevent autosave from writing to old file
        try { localStorage.removeItem('ssva:currentArchiveName'); } catch(_e){}
        await fetch('/clear_session', { method: 'POST' });
    } catch (e) {
        console.warn('Pre-switch save/clear warning', e);
    }
}

async function setNewArchiveForPatient(patientName) {
    try {
        const base = buildArchiveBaseName(patientName || '');
        localStorage.setItem('ssva:currentArchiveName', base);

        // Defer initial write; avoid creating an empty archive snapshot
        const hasContent = () => {
            try {
                const t = document.getElementById('rawTranscript')?.value || '';
                const n = document.getElementById('visitNotes')?.value || '';
                const x = document.getElementById('exploreChunkText')?.value || document.getElementById('chunkText')?.value || '';
                return (t.trim().length + n.trim().length + x.trim().length) > 0;
            } catch(_e){ return false; }
        };

        // Start auto-archive loop if available
        if (window.startAutoArchiveForCurrentPatient) await window.startAutoArchiveForCurrentPatient();

        // Schedule an initial save only if there’s content
        setTimeout(async () => {
            try {
                if (hasContent() && window.SessionManager && SessionManager.saveFullSession) {
                    await SessionManager.saveFullSession(base);
                }
            } catch(_e){}
        }, 1200);
    } catch (e) { console.warn('Set new archive warning', e); }
}

// Handles patient selection
window.selectPatientDFN = async function(dfn, name) {
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
    // Removed transient flash: do not set 'Selected: ... (DFN: ...)' in the top bar
    // document.getElementById("patientLookupResults").textContent = `Selected: ${name} (DFN: ${dfn})`;
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
            // 1) Save & Clear current session
            await preSwitchSaveAndClear();
            // 2) Load new patient
            const res = await fetch("/select_patient", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ patient_dfn })
            });
            const data = await res.json();
            // Cache-buster key
            try { window.CURRENT_PATIENT_DFN = patient_dfn; } catch(_e){}
            // Ordering guard
            let meta = null;
            try { const mr = await fetch('/get_patient', { cache: 'no-store' }); meta = await mr.json(); await new Promise(r=> setTimeout(r, 60)); } catch(_e){}
            if (data && !data.error) {
                console.log(data); // Log the full medical record for debugging or further use
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
                const patientName = (meta && meta.name) || '';
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

    if (searchInput) {
        let currentDropdownIndex = -1;
        let dropdownItems = [];
        let debounceTimer = null;
        let lastQuery = '';
        let currentAbort = null;

        function cleanupDropdown(){ if (dropdown) { dropdown.remove(); dropdown = null; } }

        async function runSearch(query){
            try {
                if (currentAbort) { currentAbort.abort(); }
                currentAbort = new AbortController();
                // Normalize: remove exactly one space right after the first comma
                const normalized = (query || '').replace(/^([^,]*,)\s(.*)$/,'$1$2');
                const res = await fetch("/vista_patient_search", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ query: normalized }),
                    signal: currentAbort.signal
                });
                const data = await res.json();
                if (!data.matches || !data.matches.length) { cleanupDropdown(); return; }
                // Create dropdown
                cleanupDropdown();
                dropdown = document.createElement("div");
                dropdown.className = "patient-dropdown";
                dropdown.style.position = "absolute";
                dropdown.style.background = "#fff";
                dropdown.style.border = "1px solid #ccc";
                dropdown.style.zIndex = 1000;
                dropdownItems = [];
                currentDropdownIndex = -1;                data.matches.forEach((match, idx) => {
                    const item = document.createElement("div");
                    let displayText = `${match.name} (DFN: ${match.dfn})`;
                    
                    // Apply demo masking if enabled
                    if (window.demoMasking && window.demoMasking.enabled) {
                        const maskedName = window.demoMasking.maskName(match.name);
                        displayText = `${maskedName} (DFN: ${match.dfn})`;
                        item.dataset.originalText = `${match.name} (DFN: ${match.dfn})`;
                    }
                    
                    item.textContent = displayText;
                    item.style.padding = "4px 8px";
                    item.style.cursor = "pointer";
                    item.tabIndex = 0;
                    item.onmouseenter = () => {
                        dropdownItems.forEach(i => i.classList.remove("selected-patient"));
                        item.classList.add("selected-patient");
                        currentDropdownIndex = idx;
                    };
                    item.onclick = async () => { selectPatientFromDropdown(match, item); };
                    dropdown.appendChild(item);
                    dropdownItems.push(item);
                });
                // Position dropdown below input
                const rect = searchInput.getBoundingClientRect();
                dropdown.style.left = rect.left + "px";
                dropdown.style.top = (rect.bottom + window.scrollY) + "px";
                dropdown.style.width = rect.width + "px";
                document.body.appendChild(dropdown);
            } catch (err) {
                if (err.name === 'AbortError') return; // expected on rapid input
                cleanupDropdown();
                console.warn('Patient search failed', err);
            }
        }
        searchInput.addEventListener("input", function() {
            // In demo mode, conceal characters but keep value intact and allow search
            if (window.demoMasking && window.demoMasking.enabled && window.demoMasking.concealInput) {
                window.demoMasking.concealInput(this);
            }
            
            // Normalize: remove exactly one space right after the first comma
            const normalizedValue = (this.value || '').replace(/^([^,]*,)\s(.*)$/,'$1$2');
            const query = normalizedValue.trim();
            if (!query) { cleanupDropdown(); lastQuery = ''; if (currentAbort) currentAbort.abort(); return; }
            if (query === lastQuery) return; // avoid duplicate
            lastQuery = query;
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => runSearch(query), 400);
        });
        // Keyboard navigation and Enter selection
        searchInput.addEventListener("keydown", function(e) {
            if (!dropdownItems.length) return;
            if (e.key === "ArrowDown") {
                e.preventDefault();
                currentDropdownIndex = (currentDropdownIndex + 1) % dropdownItems.length;
                dropdownItems.forEach(i => i.classList.remove("selected-patient"));
                dropdownItems[currentDropdownIndex].classList.add("selected-patient");
                dropdownItems[currentDropdownIndex].scrollIntoView({ block: "nearest" });
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                currentDropdownIndex = (currentDropdownIndex - 1 + dropdownItems.length) % dropdownItems.length;
                dropdownItems.forEach(i => i.classList.remove("selected-patient"));
                dropdownItems[currentDropdownIndex].classList.add("selected-patient");
                dropdownItems[currentDropdownIndex].scrollIntoView({ block: "nearest" });
            } else if (e.key === "Enter") {
                if (currentDropdownIndex >= 0 && dropdownItems[currentDropdownIndex]) {
                    dropdownItems[currentDropdownIndex].click();
                }
            }
        });
        // Remove dropdown on blur
        searchInput.addEventListener("blur", () => setTimeout(() => cleanupDropdown(), 200));
    }

    async function selectPatientFromDropdown(match, item) {
        // Highlight selected
        if (dropdown) {
            Array.from(dropdown.children).forEach(i => i.classList.remove("selected-patient"));
            item.classList.add("selected-patient");
        }
        searchInput.value = match.name;
        if (dropdown) dropdown.remove();
        // Mask name in demo mode for the transient fetching message
        const displayName = (window.demoMasking && window.demoMasking.enabled && window.demoMasking.maskName)
            ? window.demoMasking.maskName(match.name)
            : match.name;
        resultsDiv.textContent = `Fetching chart for ${displayName}...`;
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
        const patientName = (match && match.name) || (meta && meta.name) || '';
        await setNewArchiveForPatient(patientName);
    }
});