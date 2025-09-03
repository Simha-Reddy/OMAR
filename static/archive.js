// Load the list of archived sessions
async function loadArchiveList() {
    // Auto-delete if enabled
    try {
        const autoDel = localStorage.getItem('ssva:autoDeleteArchives10d');
        if (autoDel === '1') {
            await fetch('/delete_old_sessions?days=10', { method: 'GET' });
        }
    } catch(_e) {}

    const resp = await fetch('/list_sessions');
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

// Restore a specific archived session
async function restoreArchivedSession(filename) {
    try {
        // Continue saving to this archive going forward
        try {
            const base = String(filename).replace(/\.json$/i,''); 
            localStorage.setItem('ssva:currentArchiveName', base);
        } catch(_e){}

        // 1) Clear the current session on the backend
        await fetch('/clear_session', { method: 'POST' });

        // 2) Load the archived session data
        const resp = await fetch(`/transcripts/${filename}`);
        if (!resp.ok) return alert("Failed to load session.");
        const data = await resp.json();
        if (!data) return alert("Empty archive.");

        let hasPatient = !!(data.patient_meta && data.patient_meta.dfn);
        if (hasPatient) {
            const dfn = String(data.patient_meta.dfn);
            // 3a) Sensitive record gate + preview
            try {
                const prev = await fetch('/vista_patient_select_preview', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dfn })
                });
                if (prev.status === 403) {
                    // Sensitive record: notify and skip selecting
                    try {
                        const body = await prev.json();
                        alert((body && body.message) ? body.message : 'This patient record is marked sensitive and cannot be opened.');
                    } catch(_) { alert('This patient record is marked sensitive and cannot be opened.'); }
                    hasPatient = false;
                } else if (!prev.ok) {
                    console.warn('Preview failed during archive restore; proceeding without patient.');
                    hasPatient = false;
                } else {
                    // OK to proceed with selection (no modal confirmation in restore flow)
                    const sel = await fetch('/select_patient', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ patient_dfn: dfn })
                    });
                    if (!sel.ok) {
                        console.warn('Patient restore failed, proceeding without patient.');
                        hasPatient = false;
                    } else {
                        // Start auto-save (no new archive will be created)
                        try { if (window.startAutoArchiveForCurrentPatient) await window.startAutoArchiveForCurrentPatient(); } catch(_e){}
                    }
                }
            } catch (e) {
                console.warn('Patient restore error', e);
                hasPatient = false;
            }
        }

        // 3b) Restore scribe/explore UI and persist to session
        await SessionManager.restoreData(data);
        await fetch('/save_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scribe: data.scribe || {}, explore: data.explore || {} })
        });

        // 4) Redirect based on whether a patient was restored
        window.location.href = hasPatient ? '/explore' : '/scribe';
    } catch (e) {
        console.error('Restore failed:', e);
        alert('Restore failed.');
    }
}

// Delete a specific archived session
async function deleteArchivedSession(filename) {
    const resp = await fetch(`/delete_session/${filename}`, { method: 'DELETE' });
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