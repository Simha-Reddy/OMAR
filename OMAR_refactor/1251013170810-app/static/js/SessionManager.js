// SessionManager.js

// Deep merge utility
function deepMerge(target, source) {
  for (const key in source) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key])
    ) {
      if (!target[key]) target[key] = {};
      deepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

const SessionManager = {
  scribeRestored: false, // Flag to indicate if Scribe data has been restored
  exploreRestored: false, // Deprecated (Explore paths removed in Phase 2)
  autosaveStarted: false, // begin saving only after transcript or visit notes has content

  _transcriptCacheTs: 0,
  _transcriptCacheText: '',
  _allowScribeDraftRestore: false, // Only allow restoring feedbackReply when a patient is active
  isRestoring: false, // Guard to pause autosave during restoration to avoid partial saves mid-restore
  lastLoadedDataDfn: '', // Tracks which patient DFN lastLoadedData corresponds to

  // Helper to read DFN/patient_id
  _getPatientId() {
    try {
      if (window.Api && typeof window.Api.getDFN === 'function') {
        const v = window.Api.getDFN(); if (v) return v;
      }
    } catch(_e){}
    try {
      const v = (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '';
      if (v) return v;
    } catch(_e){}
    try { const v = (window.CURRENT_PATIENT_DFN || '').toString(); if (v) return v; } catch(_e){}
    return '';
  },

  peekTranscriptFromSession() {
    try {
      return (this.lastLoadedData && typeof this.lastLoadedData.transcript === 'string') ? this.lastLoadedData.transcript : '';
    } catch(_e) { return ''; }
  },

  async getTranscript(minFreshMs = 10000) {
    try {
      const now = Date.now();
      if ((now - (this._transcriptCacheTs || 0)) < minFreshMs && typeof this._transcriptCacheText === 'string') {
        return this._transcriptCacheText;
      }
      // Strategy (Server is source of truth):
      // 1) Fetch from server scribe transcript endpoint for current patient
      let txt = '';
      try {
        const pid = this._getPatientId();
        if (pid) {
          const r = await fetch(`/api/scribe/transcript?patient_id=${encodeURIComponent(pid)}`, { credentials: 'same-origin', cache: 'no-store' });
          if (r && r.ok) {
            const j = await r.json().catch(()=>({}));
            const t = j && j.transcript;
            if (typeof t === 'string') { txt = t; }
          }
        }
      } catch(_e) {}
      // 2) If server returned nothing, try last restored session data
      if (!txt) {
        try {
          const pid = this._getPatientId();
          if (this.lastLoadedData && typeof this.lastLoadedData.transcript === 'string' && pid && pid === this.lastLoadedDataDfn) {
            txt = this.lastLoadedData.transcript;
          }
        } catch(_e) {}
      }
      // 3) As a final fallback for immediate UX, try the live DOM or runtime
      if (!txt) {
        try {
          const el = document.getElementById('rawTranscript');
          if (el && el.value) txt = el.value;
        } catch(_e) {}
      }
      if (!txt) {
        try {
          if (window.ScribeRuntime && typeof window.ScribeRuntime.getTranscript === 'function') {
            txt = await window.ScribeRuntime.getTranscript();
          }
        } catch(_e) {}
      }
      this._transcriptCacheText = (typeof txt === 'string') ? txt : '';
      this._transcriptCacheTs = Date.now();
      return this._transcriptCacheText;
    } catch(_e) { return ''; }
  },

  async getRecordingStatus() {
    // Single place for scripts to ask if recording is active
    try {
      // Prefer an app-provided runtime
      if (window.ScribeRuntime && typeof window.ScribeRuntime.getStatus === 'function') {
        const st = await window.ScribeRuntime.getStatus();
        // Accept booleans or objects like { status: 'active'|'stopped' }
        if (typeof st === 'boolean') return st;
        if (st && typeof st.status === 'string') return st.status === 'active';
      }
    } catch(_e) {}
    // Fallback to UI-managed global from app.js
    try { if (typeof window.currentRecordingState !== 'undefined') return !!window.currentRecordingState; } catch(_e) {}
    return false;
  },

  async saveToSession() {
    // Skip saving while we're actively restoring data
    if (this.isRestoring) return;
    try {
      // Check gating condition: start only when transcript, visit notes, workspace draft note, or AVS has content
      const transcriptEl = document.getElementById('rawTranscript');
      const visitNotesEl = document.getElementById('visitNotes');
      const feedbackReplyEl = document.getElementById('feedbackReply');
      const avsEl = document.getElementById('patientInstructionsBox');
      const hasTranscript = !!(transcriptEl && transcriptEl.value && transcriptEl.value.trim().length);
      const hasVisitNotes = !!(visitNotesEl && visitNotesEl.value && visitNotesEl.value.trim().length);
      const hasWorkspaceDraft = !!(feedbackReplyEl && feedbackReplyEl.innerText && feedbackReplyEl.innerText.trim().length);
      const hasAvs = !!(avsEl && avsEl.value && avsEl.value.trim().length);
      const shouldStart = hasTranscript || hasVisitNotes || hasWorkspaceDraft || hasAvs;
      if (!this.autosaveStarted) {
        if (!shouldStart) {
          // Do not create a session yet
          return;
        }
        // First time we have real content — start autosave and create session
        this.autosaveStarted = true;
      }
    } catch(_e) {
      // If DOM isn't ready, skip save silently
      return;
    }
    const statePatch = await this.collectData();
    const patient_id = this._getPatientId();
    if (!patient_id) return; // No patient context — don't persist
    try {
      const body = { patient_id, ...statePatch };
      const res = await fetch('/api/session/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
  const data = await res.json().catch(()=>({}));
  if (data && data.state) { this.lastLoadedData = data.state; this.lastLoadedDataDfn = patient_id; }
      try { console.debug('Session saved to server state'); } catch(_e){}
    } catch (err) {
      console.warn('Error saving session to server state:', err);
    }
  },

  async loadFromSession() {
    try {
      const patient_id = this._getPatientId();
      if (!patient_id) return;
      const res = await fetch(`/api/session/state?patient_id=${encodeURIComponent(patient_id)}`, { credentials: 'same-origin', cache: 'no-store' });
      if (!res.ok) { return; }
      const json = await res.json().catch(()=>({}));
      const state = (json && json.state) ? json.state : null;
      if (!state) return;
  this.lastLoadedData = state;
  this.lastLoadedDataDfn = patient_id;

      // Determine if a patient is currently active; only then allow restoring draft note
      let activeDfn = null;
      try {
        if (window.PatientContext && typeof window.PatientContext.get === 'function') {
          const meta = await window.PatientContext.get();
          activeDfn = meta && (meta.dfn || meta.patient_dfn || meta.patientDFN);
        }
      } catch(_e) {}
      this._allowScribeDraftRestore = !!activeDfn;

      await this.restoreData(state);
      try { console.debug('Session loaded from server state'); } catch(_e){}

      // If no active patient, ensure any stale draft note is blank in the UI
      if (!this._allowScribeDraftRestore) {
        try { const el = document.getElementById('feedbackReply'); if (el) el.innerText = ''; } catch(_e) {}
      }
    } catch (err) {
      console.warn('Error loading session from server state:', err);
    }
  },

  async clearSession() {
    try {
      const patient_id = this._getPatientId();
      if (!patient_id) return;
      await fetch('/api/session/purge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patient_id }), credentials: 'same-origin' });
      this.lastLoadedData = {};
  this.lastLoadedDataDfn = '';
      this._allowScribeDraftRestore = false;
      try { console.debug('Session cleared (server state).'); } catch(_e){}
    } catch (err) {
      console.warn('Error clearing session from server state:', err);
    }
  },
  async saveFullSession(name) {
    // Phase 5: client-side archives removed; use server archive APIs instead
    console.warn('saveFullSession is deprecated. Use server-backed auto-archive.');
  },

  async loadSavedSession(filename) {
    console.warn('loadSavedSession is deprecated. Use /api/archive/load.');
  },

  async listSessions() {
    console.warn('listSessions is deprecated. Use /api/archive/list.');
    return [];
  },

  async deleteSession(filename) {
    console.warn('deleteSession is deprecated. Server delete not yet available.');
  },

  async endSession(sessionName) {
    console.warn('endSession is deprecated. Use server-backed archive save.');
  },

  collectData: async function() {
    // Produce server-side state shape for Phase 2
    const state = {};

    // Transcript
    let transcript = '';
    try {
      transcript = await this.getTranscript(10000);
    } catch (err) {
      try {
        const transcriptEl = document.getElementById('rawTranscript');
        if (transcriptEl) transcript = transcriptEl.value || '';
      } catch(_e) {}
    }
    state.transcript = typeof transcript === 'string' ? transcript : '';

    // Draft note (workspace markdown/editor content)
    try {
      const feedbackReplyEl = document.getElementById('feedbackReply');
      state.draftNote = (feedbackReplyEl && typeof feedbackReplyEl.innerText === 'string') ? feedbackReplyEl.innerText : '';
    } catch(_e) { state.draftNote = ''; }

    // Patient instructions (AVS)
    try {
      const instructionsBox = document.getElementById('patientInstructionsBox');
      state.patientInstructions = (instructionsBox && typeof instructionsBox.value === 'string') ? instructionsBox.value : '';
    } catch(_e) { state.patientInstructions = ''; }

    // To Do checklist
    try {
      if (window.WorkspaceModules && window.WorkspaceModules['To Do'] && window.WorkspaceModules['To Do'].getChecklistData) {
        const items = window.WorkspaceModules['To Do'].getChecklistData();
        state.to_dos = Array.isArray(items) ? items : [];
      } else {
        state.to_dos = [];
      }
    } catch(_e) { state.to_dos = []; }

    // Hey OMAR queries (placeholder until module exposes history)
    state.heyOmarQueries = [];

    return state;
  },

  async restoreData(data) {
    if (!data) return;

    // Begin restoration guard
    this.isRestoring = true;
    try {
      // Determine/enable draft-restore gate based on current or restored patient context
      try {
        const dfnActive = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
        const dfnInData = (data.patient_meta && data.patient_meta.dfn) ? String(data.patient_meta.dfn) : '';
        const hasPatientRecord = !!(data.patient_record && Object.keys(data.patient_record).length);
        if (dfnActive || dfnInData || hasPatientRecord) {
          this._allowScribeDraftRestore = true;
        }
      } catch(_e) {}

      // Restore fields (Phase 2 shape)
      const transcriptEl = document.getElementById('rawTranscript');
      if (transcriptEl) transcriptEl.value = data.transcript || '';

      const instructionsBox = document.getElementById('patientInstructionsBox');
      if (instructionsBox && data.patientInstructions !== undefined) {
        instructionsBox.value = data.patientInstructions || '';
      }
      // Always regenerate preview from Markdown (deduped storage)
      const previewDiv = document.getElementById('patientInstructionsPreview');
      if (previewDiv && instructionsBox && typeof instructionsBox.value === 'string') {
        try {
          const md = instructionsBox.value;
          let html = md;
          const m = (typeof window !== 'undefined') ? window.marked : null;
          if (m) {
            if (typeof m.parse === 'function') html = m.parse(md);
            else if (m.marked && typeof m.marked.parse === 'function') html = m.marked.parse(md);
            else if (typeof m === 'function') html = m(md);
            else if (m.marked && typeof m.marked === 'function') html = m.marked(md);
          }
          previewDiv.innerHTML = html;
        } catch(_e){ previewDiv.textContent = instructionsBox.value; }
      }

      const feedbackReplyEl = document.getElementById('feedbackReply');
      if (feedbackReplyEl) {
        if (this._allowScribeDraftRestore) {
          feedbackReplyEl.innerText = data.draftNote || '';
        } else {
          feedbackReplyEl.innerText = '';
        }
      }

      // Restore checklist data to workspace todo module
      if (data.to_dos && window.WorkspaceModules && window.WorkspaceModules['To Do'] && window.WorkspaceModules['To Do'].setChecklistData) {
        window.WorkspaceModules['To Do'].setChecklistData(Array.isArray(data.to_dos) ? data.to_dos : []);
      }

      // If restored content includes any meaningful text, enable autosave
      try {
        const hasT = !!(data.transcript && String(data.transcript).trim().length);
        const hasD = !!(data.draftNote && String(data.draftNote).trim().length);
        const hasA = !!(data.patientInstructions && String(data.patientInstructions).trim().length);
        if (hasT || hasD || hasA) this.autosaveStarted = true;
      } catch(_e) {}

      // Mark that Scribe content was restored, so other logic can avoid overwriting it
      SessionManager.scribeRestored = true;
    } finally {
      // End restoration guard
      this.isRestoring = false;
    }
  },

  restoreModuleResults(moduleResults) {
    if (!moduleResults) return;
    document.querySelectorAll('.panel').forEach(panel => {
      const title = panel.querySelector('h2')?.textContent || "";
      if (title && moduleResults[title]) {
        const outputEl = panel.querySelector('.module-output');
        if (outputEl) outputEl.innerHTML = moduleResults[title];
      }
    });
  },
};

// Expose globally
window.SessionManager = SessionManager;

// Reset transcript cache on patient switch to avoid carry-over
try{
  window.addEventListener('PATIENT_SWITCH_START', () => {
    try { SessionManager._transcriptCacheText = ''; } catch(_e){}
    try { SessionManager._transcriptCacheTs = 0; } catch(_e){}
    // Also reset autosave gating and any stale restored data so nothing gets saved for the new patient
    try { SessionManager.autosaveStarted = false; } catch(_e){}
    try { SessionManager.scribeRestored = false; } catch(_e){}
    try { SessionManager.lastLoadedData = {}; } catch(_e){}
    try { SessionManager.lastLoadedDataDfn = ''; } catch(_e){}
  });
} catch(_e){}

// Only register autosave with exit if we actually have meaningful content to save
if (document.getElementById('rawTranscript')) {
  window.addEventListener('beforeunload', async () => {
    try {
      const transcriptEl = document.getElementById('rawTranscript');
      const visitNotesEl = document.getElementById('visitNotes');
      const feedbackReplyEl = document.getElementById('feedbackReply');
      const avsEl = document.getElementById('patientInstructionsBox');
      const hasTranscript = !!(transcriptEl && transcriptEl.value && transcriptEl.value.trim().length);
      const hasVisitNotes = !!(visitNotesEl && visitNotesEl.value && visitNotesEl.value.trim().length);
      const hasWorkspaceDraft = !!(feedbackReplyEl && feedbackReplyEl.innerText && feedbackReplyEl.innerText.trim().length);
      const hasAvs = !!(avsEl && avsEl.value && avsEl.value.trim().length);
      if (!(hasTranscript || hasVisitNotes || hasWorkspaceDraft || hasAvs)) return; // nothing to archive yet
    } catch(_e) {}
    console.log("Page is unloading. Attempting to save session...");
    if (typeof SessionManager !== "undefined" && SessionManager.saveToSession) {
      await SessionManager.saveToSession();
    }
  });
}