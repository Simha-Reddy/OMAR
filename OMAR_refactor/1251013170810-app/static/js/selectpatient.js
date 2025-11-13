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
        const url = `/api/patient/${encodeURIComponent(String(dfn))}/sensitive`;
        const r = await fetch(url, { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
        const j = await r.json();
        if (!r.ok) return { allowed: true, message: '' };
        return { allowed: !!j.allowed, message: j.message || '' };
    } catch(_e) {
        // Be permissive on network failures to avoid blocking workflow
        return { allowed: true, message: '' };
    }
}

async function fetchPatientDemographics(dfn) {
    // Use refactor quick demographics API directly without mutating global DFN
    const url = `/api/patient/${encodeURIComponent(String(dfn))}/quick/demographics`;
    const r = await fetch(url, { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
    const quick = await r.json();
    if (!r.ok || (quick && quick.error)) throw new Error((quick && quick.error) || 'Demographics retrieval failed');
    // Normalize to expected fields of confirm modal
    return {
        name: quick.Name || quick.name || '',
        sex: quick.Gender || quick.gender || '',
        dob: quick.DOB || quick.DOB_ISO || quick.dob || '',
        ssn: quick.SSN || quick.ssn || '',
        ssnFormatted: quick.SSN || quick.ssn || ''
    };
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
    body.innerHTML = `${(message || 'This patient record is sensitive.').toString()}<div style="margin-top:8px;color:#6c757d;font-size:0.95em;">Proceeding will be audited.</div>`;
    const footer = document.createElement('div');
    footer.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;padding:10px 14px;border-top:1px solid #eee;';
    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    const proceedBtn = document.createElement('button');
    proceedBtn.textContent = 'Proceed';
    proceedBtn.style.cssText = 'background:#0d6efd;color:#fff;border:none;padding:6px 12px;border-radius:6px;';
    footer.appendChild(cancelBtn);
    footer.appendChild(proceedBtn);
    panel.appendChild(header);
    panel.appendChild(body);
    panel.appendChild(footer);
    overlay.appendChild(panel);
    return new Promise(resolve => {
        function cleanup(){ try { overlay.remove(); } catch(_){} }
        cancelBtn.onclick = () => { cleanup(); resolve(false); };
        proceedBtn.onclick = () => { cleanup(); resolve(true); };
        overlay.addEventListener('click', (e)=>{ if (e.target === overlay){ cleanup(); resolve(false); } });
        document.addEventListener('keydown', function esc(e){ if (e.key === 'Escape'){ cleanup(); resolve(false); document.removeEventListener('keydown', esc);} });
        document.body.appendChild(overlay);
    });
}

async function guardAndConfirmPatientLoad(dfn, nameForDisplay) {
    const resultsDiv = document.getElementById('patientLookupResults');
    try {
        if (resultsDiv) resultsDiv.textContent = 'Checking access...';
        const sens = await checkSensitiveAccess(dfn);
        if (!sens.allowed) {
            const proceedSensitive = await showSensitiveNotice(sens.message || 'Sensitive record. Access restricted.');
            if (!proceedSensitive) {
                if (resultsDiv) resultsDiv.textContent = '';
                return false;
            }
        }
        if (resultsDiv) resultsDiv.textContent = 'Fetching demographics...';
        const demo = await fetchPatientDemographics(dfn);
        // Cache minimal demographics for dropdown display (Last4 | DOB | age)
        try {
            window.__patientDemoCache = window.__patientDemoCache || new Map();
            window.__patientDemoCache.set(String(dfn), { dob: demo.dob, dobFileman: demo.dobFileman, ssn: demo.ssn, ssnFormatted: demo.ssnFormatted });
        } catch(_){}
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
                    const w = document.getElementById('feedbackReply')?.innerText || '';
                    return (t.trim().length + n.trim().length + w.trim().length) > 0;
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
            // Clear draft note (feedbackReply)
            const fr = document.getElementById('feedbackReply');
            if (fr) fr.innerText = '';
            // Reset To Do checklist if module is present; fallback to clearing visible list
            try {
                if (window.WorkspaceModules && window.WorkspaceModules['To Do'] && typeof window.WorkspaceModules['To Do'].setChecklistData === 'function') {
                    window.WorkspaceModules['To Do'].setChecklistData([]);
                } else {
                    const checklist = document.querySelector('#checklist-items');
                    if (checklist) checklist.innerHTML = '<div class="checklist-empty">No checklist items. Add one below.</div>';
                }
            } catch(_e){}
            // Reset in-memory Explore QA history
            try { window.exploreQAHistory = []; if (typeof window.updateExploreQAHistory === 'function') window.updateExploreQAHistory(); } catch(_){}
        } catch(_e){}

        // Stop any active scribe session using refactor endpoint
        try { await fetch('/api/scribe/stop', { method: 'POST' }); } catch(_e){}

        // Unbind the archive name to prevent autosave from writing to old file
        try { localStorage.removeItem('ssva:currentArchiveName'); } catch(_e){}

        // Clear any cached patient selection so drafts won’t restore on fresh load
        let prevDfn = '';
        try { prevDfn = sessionStorage.getItem('CURRENT_PATIENT_DFN') || window.CURRENT_PATIENT_DFN || ''; } catch(_e){}
        try { sessionStorage.removeItem('CURRENT_PATIENT_DFN'); } catch(_e){}

        // Clear any locally cached draft notes (both legacy and DFN-scoped)
        try { localStorage.removeItem('workspace_feedback_reply'); } catch(_e){}
        try {
            if (prevDfn) localStorage.removeItem(`workspace_feedback_reply:${prevDfn}`);
            // Also sweep any leaked DFN-scoped drafts
            const toDelete = [];
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                if (k && k.startsWith('workspace_feedback_reply:')) toDelete.push(k);
            }
            toDelete.forEach(k => { try { localStorage.removeItem(k); } catch(_e){} });
        } catch(_e){}

        // No server-side session DFN to clear in refactor; client holds DFN

        // Prevent draft restore until a new patient is selected
        try { if (window.SessionManager) SessionManager._allowScribeDraftRestore = false; } catch(_e){}

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
        if (inp) { inp.value = ''; inp.blur(); }
    } catch(_) {}
}

// Handles patient selection
window.selectPatientDFN = async function(dfn, name) {
    // New: sensitive check + demographics confirmation before proceeding
    const ok = await guardAndConfirmPatientLoad(dfn, name);
    if (!ok) return;

    // Stop CPRS auto-sync while performing a manual switch and persist a paused state
    try { if (window.stopCprsPatientSync) window.stopCprsPatientSync(); } catch(_e){}
    try { window.__CPRS_MANUAL_SWITCH_AT = Date.now(); window.__CPRS_MANUAL_DFN = dfn; } catch(_e){}
    try { localStorage.setItem('ssva:cprsPaused', '1'); } catch(_e){}

    // Close search UI promptly; orchestrator will handle clearing/UI/events
    closePatientSearchUI();

    // Use centralized orchestrator for identical behavior
    try { console.info('[Switch] Manual selectPatientDFN via Patient.switchTo', dfn); } catch(_e){}
    const switched = await (window.Patient && typeof window.Patient.switchTo === 'function'
        ? window.Patient.switchTo(dfn, { displayName: name })
        : (async () => false)());

    // Do not auto-resume CPRS; user must click "⟳ Resume CPRS" to re-enable sync
    if (switched) {
        try { /* keep paused until explicit resume */ } catch(_e){}
    }

    // Ensure masked/unmasked top-bar reflects latest dataset
    try { if (typeof updatePatientNameDisplay === 'function') updatePatientNameDisplay(); } catch(_e){}
};

// --- CPRS current patient sync (poll ORWPT TOP every 5s) ---
(function(){
    let cprsSyncTimer = null;
    let cprsSyncInFlight = false;
    let cprsLastDFN = null; // last DFN observed from ORWPT TOP
    const INTERVAL_MS = 5000;

    // Backoff/debounce state
    let failureCount = 0;
    let pauseUntil = 0;
    let lastSwitchAt = 0;
    let consecutiveCandidate = null;
    let consecutiveCount = 0;
    const REQUIRED_CONSECUTIVE = 2; // require 2 consecutive polls with same DFN before switching
    const MIN_SWITCH_DWELL_MS = 10000; // min time between auto-switches
    const FAILURE_BACKOFF_BASE_MS = 2000;
    const MANUAL_HOLD_MS = 30000; // pause auto-sync for 30s after a manual switch

    // Initialize persisted hold if present (e.g., set during archive restore across redirects)
    try {
        const holdUntil = parseInt(localStorage.getItem('ssva:cprsHoldUntil') || '0', 10) || 0;
        if (holdUntil && Date.now() < holdUntil) {
            pauseUntil = Math.max(pauseUntil, holdUntil);
            try { window.__CPRS_MANUAL_SWITCH_AT = Date.now(); } catch(_e){}
            try { window.__CPRS_MANUAL_DFN = localStorage.getItem('ssva:cprsHoldDFN') || null; } catch(_e){}
        } else {
            // Clear expired/empty hold artifacts
            try { localStorage.removeItem('ssva:cprsHoldUntil'); localStorage.removeItem('ssva:cprsHoldDFN'); localStorage.removeItem('ssva:cprsHoldReason'); } catch(_e){}
        }
    } catch(_e){}

    function isCprsSyncEnabled(){
        try {
            const v = localStorage.getItem('ssva:autoCprsSync');
            const autoEnabled = (v === null ? true : v === '1');
            // Also respect a persistent paused flag set during archive restore
            const paused = localStorage.getItem('ssva:cprsPaused') === '1';
            return autoEnabled && !paused;
        } catch(_) { return true; }
    }

    function getCurrentDfn(){
        try { return window.CURRENT_PATIENT_DFN || sessionStorage.getItem('CURRENT_PATIENT_DFN') || ''; } catch(_) { return ''; }
    }

    async function fetchCprsTop(){
        try {
            const r = await fetch('/api/cprs/sync', { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
            const j = await r.json();
            if (!r.ok) return { ok: false, dfn: '', name: '' };
            return { ok: !!j.ok, dfn: String(j.dfn || ''), name: String(j.name || '') };
        } catch(_e) {
            return { ok: false, dfn: '', name: '' };
        }
    }

    async function silentSwitchToDFN(dfn, displayName){
        if (!dfn) return false;
        if (cprsSyncInFlight) return false;
        cprsSyncInFlight = true;
        try {
            // Sensitive-record guard: pause and ask before switching
            try {
                const sens = await checkSensitiveAccess(dfn);
                if (!sens.allowed) {
                    const proceed = await showSensitiveNotice(sens.message || 'Sensitive record. Access restricted.');
                    if (!proceed) {
                        return false; // decline -> no switch
                    }
                }
            } catch(_e) {
                // If sensitive check fails, be conservative and do not switch
                return false;
            }

            // Use centralized orchestrator so auto and manual match exactly
            try { console.info('[CPRS Sync] Switching via Patient.switchTo', dfn); } catch(_e){}
            const ok = await (window.Patient && typeof window.Patient.switchTo === 'function'
                ? window.Patient.switchTo(dfn, { displayName })
                : (async () => false)());
            if (ok) {
                try { console.log('[CPRS Sync] Switched to DFN', dfn, 'via ORWPT TOP'); } catch(_e){}
                return true;
            }
            return false;
        } catch(e){
            console.warn('[CPRS Sync] Silent switch error', e);
            return false;
        } finally {
            cprsSyncInFlight = false;
        }
    }

    async function cprsSyncTick(){
        if (!isCprsSyncEnabled()) return;
        if (cprsSyncInFlight) return;
        const now = Date.now();
        if (now < pauseUntil) return;

        // Respect recent manual switch hold window (in-memory and persisted)
        try {
            const manualAt = window.__CPRS_MANUAL_SWITCH_AT || 0;
            if (manualAt && (now - manualAt) < MANUAL_HOLD_MS) {
                return; // hold: don't attempt to follow CPRS yet
            }
            const holdUntil = parseInt(localStorage.getItem('ssva:cprsHoldUntil') || '0', 10) || 0;
            if (holdUntil && now < holdUntil) {
                // Also set pauseUntil so general guard respects it
                pauseUntil = Math.max(pauseUntil, holdUntil);
                return;
            } else if (holdUntil && now >= holdUntil) {
                // Clear expired artifacts
                try { localStorage.removeItem('ssva:cprsHoldUntil'); localStorage.removeItem('ssva:cprsHoldDFN'); localStorage.removeItem('ssva:cprsHoldReason'); } catch(_e){}
            }
        } catch(_){}

        const current = getCurrentDfn();
        const top = await fetchCprsTop();
        if (!top.ok) {
            failureCount += 1;
            if (failureCount >= 3) {
                const backoffMs = Math.min(60000, FAILURE_BACKOFF_BASE_MS * Math.pow(2, Math.min(5, failureCount - 3)));
                pauseUntil = Date.now() + backoffMs;
            }
            return;
        }
        // Reset failure backoff on success
        failureCount = 0;

        const { dfn, name } = top;
        if (!dfn) { // no active CPRS patient
            consecutiveCandidate = null;
            consecutiveCount = 0;
            return;
        }
        cprsLastDFN = dfn;
        if (current && dfn === current) {
            consecutiveCandidate = null;
            consecutiveCount = 0;
            return;
        }

        // Require stability across polls
        if (dfn === consecutiveCandidate) {
            consecutiveCount += 1;
        } else {
            consecutiveCandidate = dfn;
            consecutiveCount = 1;
        }
        if (consecutiveCount < REQUIRED_CONSECUTIVE) return;

        // Minimum dwell between switches
        if ((Date.now() - lastSwitchAt) < MIN_SWITCH_DWELL_MS) return;

        const switched = await silentSwitchToDFN(dfn, name);
        if (switched) {
            lastSwitchAt = Date.now();
        } else {
            // If declined or failed, pause briefly to avoid repeated prompts
            pauseUntil = Date.now() + 15000;
        }
        // Reset consecutive detection after an attempt
        consecutiveCandidate = null;
        consecutiveCount = 0;
    }

    function startCprsPatientSync(){
        // Do not start if auto-sync is disabled or globally paused
        if (!isCprsSyncEnabled()) {
            try { window.dispatchEvent(new CustomEvent('cprs-sync-state', { detail: { running: false } })); } catch(_){}
            return;
        }
        if (cprsSyncTimer) return;
        // Stagger first run a bit to avoid hammering on load
        cprsSyncTimer = setInterval(cprsSyncTick, INTERVAL_MS);
        // Run an initial check shortly after load
        setTimeout(cprsSyncTick, 1500);
        try { window.dispatchEvent(new CustomEvent('cprs-sync-state', { detail: { running: true } })); } catch(_){}
    }

    function stopCprsPatientSync(){
        if (cprsSyncTimer) { clearInterval(cprsSyncTimer); cprsSyncTimer = null; }
        try { window.dispatchEvent(new CustomEvent('cprs-sync-state', { detail: { running: false } })); } catch(_){}
    }

    // Helper: determine if a hold is active (manual or persisted)
    function isCprsHoldActive(){
        try {
            const now = Date.now();
            if (window.__CPRS_MANUAL_SWITCH_AT && (now - window.__CPRS_MANUAL_SWITCH_AT) < MANUAL_HOLD_MS) return true;
            const holdUntil = parseInt(localStorage.getItem('ssva:cprsHoldUntil') || '0', 10) || 0;
            if (holdUntil && now < holdUntil) return true;
            // Treat persistent pause as a hold for UI purposes
            if (localStorage.getItem('ssva:cprsPaused') === '1') return true;
            return false;
        } catch(_) { return false; }
    }

    // Allow other scripts to resume CPRS immediately and clear holds
    async function resumeCprsSync(){
        try {
            window.__CPRS_MANUAL_SWITCH_AT = 0; window.__CPRS_MANUAL_DFN = null;
        } catch(_){ }
        try { localStorage.removeItem('ssva:cprsHoldUntil'); localStorage.removeItem('ssva:cprsHoldDFN'); localStorage.removeItem('ssva:cprsHoldReason'); } catch(_){}
        try { localStorage.removeItem('ssva:cprsPaused'); } catch(_){}
        try { if (!cprsSyncTimer && isCprsSyncEnabled()) startCprsPatientSync(); } catch(_e){}
    }

    // Expose for debugging/toggling/UI
    try { window.startCprsPatientSync = startCprsPatientSync; } catch(_e){}
    try { window.stopCprsPatientSync = stopCprsPatientSync; } catch(_e){}
    try { window.isCprsHoldActive = isCprsHoldActive; } catch(_e){}
    try { window.resumeCprsSync = resumeCprsSync; } catch(_e){}

    // Auto-start on DOM ready
    window.addEventListener('DOMContentLoaded', () => {
        if (isCprsSyncEnabled()) startCprsPatientSync();

        // UI: toggle the top-bar Resume CPRS button based on hold/running state
        try {
            const btn = document.getElementById('cprsResumeBtn');
            if (btn) {
                const refreshBtn = () => {
                    // Show when CPRS is paused/held (including persistent pause) and could be resumed by the user
                    const autoPref = (localStorage.getItem('ssva:autoCprsSync') === null ? true : localStorage.getItem('ssva:autoCprsSync') === '1');
                    const paused = localStorage.getItem('ssva:cprsPaused') === '1';
                    const show = autoPref && (paused || isCprsHoldActive());
                    btn.style.display = show ? '' : 'none';
                };
                btn.addEventListener('click', async () => {
                    btn.disabled = true;
                    try { await resumeCprsSync(); } finally {
                        btn.disabled = false;
                        refreshBtn();
                    }
                });
                window.addEventListener('cprs-sync-state', refreshBtn);
                // Also refresh on visibility change and periodically for safety
                document.addEventListener('visibilitychange', refreshBtn);
                setTimeout(refreshBtn, 0);
                setInterval(refreshBtn, 2000);
            }
        } catch(_e){}
    });
})();

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
            // Stop CPRS sync and persist paused state for manual switch
            try { if (window.stopCprsPatientSync) window.stopCprsPatientSync(); } catch(_e){}
            try { window.__CPRS_MANUAL_SWITCH_AT = Date.now(); window.__CPRS_MANUAL_DFN = patient_dfn; } catch(_e){}
            try { localStorage.setItem('ssva:cprsPaused', '1'); } catch(_e){}
            // Close search UI and switch via orchestrator
            closePatientSearchUI();
            try { console.info('[Switch] Manual selectPatientBtn via Patient.switchTo', patient_dfn); } catch(_e){}
            const switched = await (window.Patient && typeof window.Patient.switchTo === 'function'
                ? window.Patient.switchTo(patient_dfn, {})
                : (async () => false)());
            // Do not auto-resume CPRS; remain paused until the user clicks Resume
            if (switched) {
                try { /* remain paused */ } catch(_e){}
            }
            try { if (typeof updatePatientNameDisplay === 'function') updatePatientNameDisplay(); } catch(_e){}
        };
    }
});

// Defensive: clear any transcript/draft on switch events in case modules rehydrate late
try {
    window.addEventListener('PATIENT_SWITCH_START', () => {
        try { if (window.SessionManager) window.SessionManager._allowScribeDraftRestore = false; } catch(_e){}
        try { const rt = document.getElementById('rawTranscript'); if (rt) rt.value=''; } catch(_e){}
        try { const vn = document.getElementById('visitNotes'); if (vn) { vn.value=''; vn.dispatchEvent(new Event('input',{bubbles:true})); } } catch(_e){}
        try { const fr = document.getElementById('feedbackReply'); if (fr) fr.innerText=''; } catch(_e){}
    });
} catch(_e){}

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
            // If query is LAST5 (e.g., J1234), do not filter
            if (/^[A-Za-z]\d{4}$/.test(query.trim())) {
                return patients;
            }
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
                    headers: { 
                        "Content-Type": "application/json",
                        "X-CSRF-Token": window.getCsrfToken ? window.getCsrfToken() : ''
                    },
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
                
                // Ensure LAST5 filters also apply to Default Patient List by intersecting DFNs
                const isLast5 = /^[A-Za-z]\d{4}$/.test((query || '').trim());
                let filteredDefault, filteredAll;
                if (isLast5) {
                    const serverDfns = new Set(allPatients.map(p => p.dfn));
                    filteredDefault = (defaultList || []).filter(p => serverDfns.has(p.dfn));
                    // All patients already server-filtered; keep client filter for highlighting structure
                    filteredAll = filterPatients(allPatients, query);
                } else {
                    // Non-LAST5: use existing client-side filter for both
                    filteredDefault = filterPatients(defaultList, query);
                    filteredAll = filterPatients(allPatients, query);
                }
                
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

            // Auto-select the first actual patient item if present so Enter picks it
            try {
                const first = dropdownItems && dropdownItems.length ? dropdownItems[0] : null;
                if (first) {
                    const idx = parseInt(first.dataset.index || '0', 10) || 0;
                    selectItem(idx, first.id);
                    // Ensure into view for above-positioned dropdowns
                    first.scrollIntoView({ block: 'nearest' });
                }
            } catch(_) {}

            // Background-enrich top items with demographics so we can show Last4 | DOB | age
            try {
                const toEnrich = (dropdownItems || []).slice(0, 12);
                for (const it of toEnrich) {
                    const dfn = (it && it._patientData && it._patientData.dfn) ? String(it._patientData.dfn) : '';
                    if (!dfn) continue;
                    const cached = (window.__patientDemoCache && window.__patientDemoCache.get(dfn)) || null;
                    if (cached && (cached.dob || cached.ssn || cached.ssnFormatted)) {
                        updateItemSublineFromCache(it, dfn);
                        continue;
                    }
                    // Fetch demographics quietly; ignore failures
                    (async () => {
                        try {
                            const r = await fetch(`/api/patient/${encodeURIComponent(dfn)}/quick/demographics`, { method: 'GET', credentials:'same-origin', cache:'no-store' });
                            const demo = await r.json();
                            if (r.ok && demo && (demo.DOB || demo.DOB_ISO || demo.SSN)) {
                                try {
                                    window.__patientDemoCache = window.__patientDemoCache || new Map();
                                    const dobFileman = null; // not provided by quick; keep null
                                    window.__patientDemoCache.set(dfn, { dob: (demo.DOB || demo.DOB_ISO || ''), dobFileman, ssn: (demo.SSN || ''), ssnFormatted: (demo.SSN || '') });
                                } catch(_){ }
                                updateItemSublineFromCache(it, dfn);
                            }
                        } catch(_e) {}
                    })();
                }
            } catch(_) {}
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
            item.dataset.dfn = String(patient.dfn || '');
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
            // Derive Last4 | DOB | age
            const raw = String(patient.raw || '');
            let dobDisplay = '';
            let last4 = '';
            let ageStr = '';
            try {
                // Attempt to fetch demographics quickly to compute DOB/SSN; fallback to raw parsing
                // Avoid synchronous network call here; parse from raw line if possible
                const parts = raw.split('^');
                // Try to get DFN, Name present already; ORWPT returns minimal here
                // We'll get DOB/SSN via a lightweight heuristic only if provided in raw; otherwise leave blank and compute on demand
            } catch(_e) {}
            // Compute Last4 from DFN is not correct; instead, leave from demographics lookup later; for display now we try to infer from cached demographics map
            try {
                // Use a simple in-memory LRU cache for demo fields keyed by DFN if previously loaded during this session
                window.__patientDemoCache = window.__patientDemoCache || new Map();
                const d = window.__patientDemoCache.get(String(patient.dfn));
                if (d) {
                    const digits = (d.ssn || d.ssnFormatted || '').replace(/\D+/g, '');
                    if (digits && digits.length >= 4) last4 = digits.slice(-4);
                    dobDisplay = d.dob || '';
                    // compute age
                    if (d.dobFileman && /^\d{7}(?:\.\d+)?$/.test(d.dobFileman)) {
                        const y = 1700 + parseInt(d.dobFileman.slice(0,3));
                        const m = parseInt(d.dobFileman.slice(3,5));
                        const dd = parseInt(d.dobFileman.slice(5,7));
                        const b = new Date(Date.UTC(y, m-1, dd));
                        const today = new Date();
                        let age = today.getUTCFullYear() - b.getUTCFullYear();
                        const mo = today.getUTCMonth() - b.getUTCMonth();
                        if (mo < 0 || (mo === 0 && today.getUTCDate() < b.getUTCDate())) age--;
                        if (!isNaN(age)) ageStr = String(age);
                    }
                }
            } catch(_) {}

            // Build the second line text
            let subline = '';
            if (last4 || dobDisplay || ageStr) {
                const parts = [];
                if (last4) parts.push(`${last4}`);
                if (dobDisplay) parts.push(`${dobDisplay}`);
                if (ageStr) parts.push(`${ageStr}`);
                subline = parts.join(' | ');
            } else {
                // Fallback to DFN if we have no demographics
                subline = `DFN: ${displayDfn}`;
            }

            const subHtml = highlightMatch(subline, query);
            
            item.innerHTML = `
                <div class="patient-name">${nameHtml}</div>
                <div class="patient-dfn">${subHtml}</div>
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
            // Handle mouse selection on mousedown to beat input blur/cleanup races
            item.addEventListener('mousedown', (e) => {
                try { e.preventDefault(); e.stopPropagation(); } catch(_e){}
                // Mark to suppress subsequent click handler when triggered by the same action
                item._mouseSelecting = true;
                // Proceed with selection immediately
                // Note: don't await here to avoid blocking the event loop; selection orchestrates async work itself
                try { selectPatientFromDropdown(patient, item); } finally {
                    // Clear the guard soon after; use a microtask to avoid racing the click event
                    setTimeout(() => { try { item._mouseSelecting = false; } catch(_){} }, 0);
                }
            });
            // Keep click for keyboard (Enter triggers .click()) and non-mouse activation
            item.addEventListener('click', (e) => {
                if (item._mouseSelecting) { try { e.preventDefault(); e.stopPropagation(); } catch(_e){} return; }
                selectPatientFromDropdown(patient, item);
            });
            
            // Store patient data
            item._patientData = patient;

            return item;
        }

        function updateItemSublineFromCache(item, dfn) {
            try {
                const cache = window.__patientDemoCache || new Map();
                const d = cache.get(String(dfn));
                if (!d) return;
                const sub = formatSubline(d);
                if (!sub) return;
                const subEl = item.querySelector('.patient-dfn');
                if (subEl) subEl.textContent = sub;
            } catch(_){}
        }

        function formatSubline(demo) {
            try {
                const parts = [];
                const digits = (demo.ssn || demo.ssnFormatted || '').replace(/\D+/g, '');
                if (digits && digits.length >= 4) parts.push(digits.slice(-4));
                if (demo.dob) parts.push(demo.dob);
                // age from dobFileman
                let ageStr = '';
                const fm = demo.dobFileman;
                if (fm && /^\d{7}(?:\.\d+)?$/.test(fm)) {
                    const y = 1700 + parseInt(fm.slice(0,3));
                    const m = parseInt(fm.slice(3,5));
                    const dd = parseInt(fm.slice(5,7));
                    const b = new Date(Date.UTC(y, m-1, dd));
                    const today = new Date();
                    let age = today.getUTCFullYear() - b.getUTCFullYear();
                    const mo = today.getUTCMonth() - b.getUTCMonth();
                    if (mo < 0 || (mo === 0 && today.getUTCDate() < b.getUTCDate())) age--;
                    if (!isNaN(age)) ageStr = String(age);
                }
                if (ageStr) parts.push(ageStr);
                return parts.join(' | ');
            } catch(_) { return ''; }
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
                    try {                        const res = await fetch('/vista_patient_search', {
                            method: 'POST',                            headers: { 
                                'Content-Type': 'application/json',
                                'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
                            },
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

        // Remove dropdown on blur with delay; avoid cleanup if focus moved into dropdown
        searchInput.addEventListener("blur", () => {
            setTimeout(() => {
                try{
                    const ae = document.activeElement;
                    if (dropdown && (dropdown === ae || (ae && dropdown.contains(ae)))) return;
                }catch(_e){}
                cleanupDropdown();
            }, 250);
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
        // Clear the search box immediately on selection
        searchInput.value = '';
        if (dropdown) dropdown.remove();
        
        // Mask name in demo mode for status
        const displayName = (window.demoMasking && window.demoMasking.enabled && window.demoMasking.maskName)
            ? window.demoMasking.maskName(match.name)
            : match.name;
        resultsDiv.textContent = `Checking access for ${displayName}...`;

        // Guard + confirm
        const ok = await guardAndConfirmPatientLoad(match.dfn, match.name);
        if (!ok) return;

    // Stop CPRS sync and persist paused state for manual switch
    try { if (window.stopCprsPatientSync) window.stopCprsPatientSync(); } catch(_e){}
    try { window.__CPRS_MANUAL_SWITCH_AT = Date.now(); window.__CPRS_MANUAL_DFN = match.dfn; } catch(_e){}
    try { localStorage.setItem('ssva:cprsPaused', '1'); } catch(_e){}

        // Close search UI and use orchestrator for switch
        closePatientSearchUI();
        try { console.info('[Switch] Dropdown selection via Patient.switchTo', match.dfn); } catch(_e){}
        await (window.Patient && typeof window.Patient.switchTo === 'function'
            ? window.Patient.switchTo(match.dfn, { displayName: match.name })
            : (async () => false)());

        // CPRS sync will be restarted by global hold timer in other handlers if needed
    }
});