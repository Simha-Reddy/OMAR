// Load the list of archived sessions
async function loadArchiveList() {
    // Auto-delete if enabled
    try {
        const autoDel = localStorage.getItem('ssva:autoDeleteArchives10d');
        if (autoDel === '1') {
            await fetch('/delete_old_sessions?days=10', { method: 'GET', cache: 'no-store', credentials: 'same-origin', referrerPolicy: 'no-referrer' });
        }
    } catch(_e) {}

    const resp = await fetch('/list_sessions', { cache: 'no-store', credentials: 'same-origin', referrerPolicy: 'no-referrer' });
    const sessions = await resp.json();
    const container = document.getElementById('archive-list');
    container.innerHTML = '';
    if (sessions.length === 0) {
        container.innerHTML = '<p>No archived sessions found.</p>';
        return;
    }
    sessions.forEach(filename => {
        const div = document.createElement('div');
        div.className = "transcript-block";
        div.innerHTML = `
            <button class="restore-btn" onclick="restoreArchivedSession('${filename}')">Restore</button>
            <input type="checkbox" class="archive-checkbox" value="${filename}">
            <span class="archive-filename">${filename.replace('.json', '')}</span>
        `;
        container.appendChild(div);
    });
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

// Restore a specific archived session
async function restoreArchivedSession(filename) {
    try {
        // Continue saving to this archive going forward
        try {
            const base = String(filename).replace(/\.json$/i,''); 
            localStorage.setItem('ssva:currentArchiveName', base);
        } catch(_e){}

        // 1) Clear the current session on the backend
        await fetch('/clear_session', { method: 'POST', headers: { 'X-CSRF-Token': csrf() }, cache: 'no-store', credentials: 'same-origin', referrerPolicy: 'no-referrer' });

        // 2) Load the archived session data
        const resp = await fetch(`/transcripts/${filename}`, { cache: 'no-store', credentials: 'same-origin', referrerPolicy: 'no-referrer' });
        if (!resp.ok) return alert("Failed to load session.");
        const data = await resp.json();
        if (!data) return alert("Empty archive.");

        const hasPatient = !!(data.patient_meta && data.patient_meta.dfn);
        if (hasPatient) {
            // 3a) Switch to patient via centralized orchestrator (skip archive setup to preserve current archive name)
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
                        // Start auto-save loop now that patient is active (keep existing archive target)
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

        // 3b) Restore scribe/explore UI and persist to session
        try { SessionManager._allowScribeDraftRestore = true; } catch(_e){}
        await SessionManager.restoreData(data);
        try { SessionManager.lastLoadedData = data; } catch(_e){}
        await fetch('/save_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
            body: JSON.stringify({ scribe: data.scribe || {}, explore: data.explore || {} }),
            cache: 'no-store', credentials: 'same-origin', referrerPolicy: 'no-referrer'
        });

        // 4) Redirect to workspace
        window.location.href = '/workspace';
    } catch (e) {
        console.error('Restore failed:', e);
        alert('Restore failed.');
    }
}

// Delete a specific archived session
async function deleteArchivedSession(filename) {
    const resp = await fetch(`/delete_session/${filename}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrf() }, cache: 'no-store', credentials: 'same-origin', referrerPolicy: 'no-referrer' });
    if (resp.ok) loadArchiveList();
    else alert("Failed to delete session.");
}

// Initialize the Archive page
document.addEventListener('DOMContentLoaded', function() {
    // Load the archive list on page load
    loadArchiveList();

    // Delete selected sessions
    document.getElementById('deleteSelectedBtn').onclick = async function() {
        const checked = document.querySelectorAll('.archive-checkbox:checked');
        if (checked.length === 0) {
            alert("No sessions selected.");
            return;
        }
        if (!confirm(`Delete ${checked.length} selected session(s)?`)) return;
        for (const cb of checked) {
            await deleteArchivedSession(cb.value);
        }
        loadArchiveList();
    };

    // Select or deselect all sessions
    document.getElementById('selectAllBox').onclick = function() {
        const boxes = document.querySelectorAll('.archive-checkbox');
        boxes.forEach(cb => cb.checked = this.checked);
    };
});