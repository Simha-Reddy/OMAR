// Resolve current patient id
function _getPatientId(){
    try { if (window.Api && typeof window.Api.getDFN === 'function') { const v = window.Api.getDFN(); if (v) return String(v); } } catch(_e){}
    try { const v = sessionStorage.getItem('CURRENT_PATIENT_DFN'); if (v) return String(v); } catch(_e){}
    try { if (window.CURRENT_PATIENT_DFN) return String(window.CURRENT_PATIENT_DFN); } catch(_e){}
    return '';
}

// Load the list of archived sessions (server-backed)
async function loadArchiveList() {
    const container = document.getElementById('archive-list');
    container.innerHTML = '';
    const patient_id = _getPatientId();
    if (!patient_id) {
        container.innerHTML = '<p>Select a patient to view their archives.</p>';
        return;
    }
    try {
        const r = await fetch(`/api/archive/list?patient_id=${encodeURIComponent(patient_id)}`, { credentials: 'same-origin', cache: 'no-store' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const j = await r.json().catch(()=>({}));
        const items = (j && Array.isArray(j.items)) ? j.items : [];
        if (!items.length) { container.innerHTML = '<p>No archived sessions found.</p>'; return; }
                items.forEach((it) => {
            const div = document.createElement('div');
            div.className = 'transcript-block';
            const when = (function(){ try{ const d = new Date((it.updated_at||it.created_at)*1000 || it.updated_at || it.created_at); return isNaN(d) ? '' : d.toLocaleString(); }catch(_e){ return ''; }})();
            const label = `Archive ${it.archive_id.slice(0,8)}… ${when?`(${when})`:''}`;
            div.innerHTML = `
                <button class="restore-btn" data-arch="${it.archive_id}">Restore</button>
                        <input type="checkbox" class="archive-checkbox" value="${it.archive_id}"> 
                <span class="archive-filename">${label}</span>
            `;
            const btn = div.querySelector('button.restore-btn');
            btn.addEventListener('click', async () => {
                await restoreArchivedSession(it.archive_id);
            });
            container.appendChild(div);
        });
    } catch(e){
        container.innerHTML = '<p>Failed to load archives.</p>';
    }
}

// Utility function to get CSRF token (fallback if app.js not loaded yet)
function csrf(){ 
    // Try to use global function first
    if (window.getCsrfToken) return window.getCsrfToken();
    // Fallback with cookie preference
    try {
        const cookieValue = document.cookie.split('; ')
            .find(row => row.startsWith('csrf_token='))
            ?.split('=')[1];
        if (cookieValue) return cookieValue;
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content'); 
    } catch(_e) { return ''; } 
}

// Restore a specific archived session (server-backed)
async function restoreArchivedSession(archiveId) {
    try {
        // 1) Load the archived session data from server
        const r = await fetch(`/api/archive/load?id=${encodeURIComponent(archiveId)}`, { credentials:'same-origin', cache:'no-store' });
        if (!r.ok) { alert('Failed to load session.'); return; }
        const j = await r.json().catch(()=>({}));
        const data = j && j.archive && j.archive.state;
        if (!data) { alert('Empty archive.'); return; }

        const hasPatient = !!(data.patient_meta && data.patient_meta.dfn);
        if (hasPatient) {
            // 2a) Switch to patient via centralized orchestrator (skip archive setup to preserve current archive name)
            try {
                const dfn = String(data.patient_meta.dfn);
                const displayName = (data.patient_meta && data.patient_meta.name) || '';
                // Pause CPRS auto-sync across the upcoming redirect to prevent it from switching back
                try {
                    // Immediate short hold to avoid the post-redirect race
                    const HOLD_MS = 30000;
                    const until = Date.now() + HOLD_MS;
                    localStorage.setItem('ssva:cprsHoldUntil', String(until));
                    localStorage.setItem('ssva:cprsHoldDFN', dfn);
                    localStorage.setItem('ssva:cprsHoldReason', 'archive-restore');
                    // Additionally, set an indefinite paused flag so CPRS does not resume until user clicks Resume
                    localStorage.setItem('ssva:cprsPaused', '1');
                    if (window.stopCprsPatientSync) window.stopCprsPatientSync();
                    try { window.__CPRS_MANUAL_SWITCH_AT = Date.now(); window.__CPRS_MANUAL_DFN = dfn; } catch(_e){}
                } catch(_e){}
                if (window.Patient && typeof window.Patient.switchTo === 'function') {
                    const ok = await window.Patient.switchTo(dfn, { displayName, skipArchiveSetup: true });
                    if (ok) {
                        // Start auto-archive loop now that patient is active
                        try { if (window.startAutoArchiveForCurrentPatient) await window.startAutoArchiveForCurrentPatient(); } catch(_e){}
                    } else {
                        console.warn('Patient restore via orchestrator failed; proceeding without patient.');
                    }
                } else {
                    console.warn('Patient orchestrator not available; proceeding without patient.');
                }
            } catch (e) {
                console.warn('Patient restore error', e);
            }
        }

        // 2b) Restore scribe/workspace UI and persist to server ephemeral state
        try { SessionManager._allowScribeDraftRestore = true; } catch(_e){}
        await SessionManager.restoreData(data);
        try { SessionManager.lastLoadedData = data; } catch(_e){}
        try { await SessionManager.saveToSession(); } catch(_e){}

        // 4) Redirect to workspace
        window.location.href = '/workspace';
    } catch (e) {
        console.error('Restore failed:', e);
        alert('Restore failed.');
    }
}

// Delete a specific archived session (server-backed)
async function deleteArchivedSession(archiveId) {
    try {
        const r = await fetch(`/api/archive/delete?id=${encodeURIComponent(archiveId)}`, {
            method: 'DELETE',
            headers: { 'X-CSRF-Token': csrf() },
            credentials: 'same-origin'
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return true;
    } catch(e){
        console.warn('Delete failed:', e);
        alert('Failed to delete archive.');
        return false;
    }
}

// Initialize the Archive page
document.addEventListener('DOMContentLoaded', function() {
    // Load the archive list on page load
    loadArchiveList();

    // Delete selected sessions (disabled until server supports delete)
    const delBtn = document.getElementById('deleteSelectedBtn');
    if (delBtn) {
            delBtn.disabled = false;
            delBtn.title = '';
            delBtn.onclick = async function(){
                const checked = document.querySelectorAll('.archive-checkbox:checked');
                if (!checked.length) { alert('No sessions selected.'); return; }
                if (!confirm(`Delete ${checked.length} selected session(s)?`)) return;
                for (const cb of checked) {
                    const id = cb.value;
                    await deleteArchivedSession(id);
                }
                await loadArchiveList();
            };
    }

    // Select all is disabled since delete is disabled
    const selAll = document.getElementById('selectAllBox');
    if (selAll) {
            selAll.disabled = false;
            selAll.title = '';
            selAll.onclick = function(){
                const boxes = document.querySelectorAll('.archive-checkbox');
                boxes.forEach(cb => cb.checked = selAll.checked);
            };
    }
});