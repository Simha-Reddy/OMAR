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
  exploreRestored: false, // Flag to indicate if Explore data has been restored
  autosaveStarted: false, // begin saving only after transcript or visit notes has content

  _transcriptCacheTs: 0,
  _transcriptCacheText: '',
  _allowScribeDraftRestore: false, // Only allow restoring feedbackReply when a patient is active
  isRestoring: false, // Guard to pause autosave during restoration to avoid partial saves mid-restore

  peekTranscriptFromSession() {
    try {
      return (this.lastLoadedData && this.lastLoadedData.scribe && this.lastLoadedData.scribe.transcript) ? this.lastLoadedData.scribe.transcript : '';
    } catch(_e) { return ''; }
  },

  async getTranscript(minFreshMs = 10000) {
    try {
      const now = Date.now();
      if ((now - (this._transcriptCacheTs || 0)) < minFreshMs && typeof this._transcriptCacheText === 'string') {
        return this._transcriptCacheText;
      }
      let txt = '';
      try {
        const r = await fetch('/scribe/live_transcript', { cache: 'no-store' });
        if (r && r.ok) txt = await r.text();
      } catch(_e) {}
      if (!txt) {
        // Fallback to DOM text area if present
        try {
          const el = document.getElementById('rawTranscript');
          if (el && el.value) txt = el.value;
        } catch(_e) {}
      }
      this._transcriptCacheText = (typeof txt === 'string') ? txt : '';
      this._transcriptCacheTs = Date.now();
      return this._transcriptCacheText;
    } catch(_e) { return ''; }
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

    const newData = await this.collectData();
    let mergedData = {};

    // Try to load existing session data first
    try {
      const response = await fetch('/load_session');
      if (response.ok) {
        const existingData = await response.json();
        mergedData = deepMerge(existingData, newData);
      } else {
        mergedData = newData;
      }
    } catch (err) {
      console.warn("Could not load existing session, saving only current page data.");
      mergedData = newData;
    }    // Save merged data
    try {
      const response = await fetch('/save_session', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
        },
        body: JSON.stringify(mergedData),
      });
      if (response.ok) {
        console.log('Session saved to server.');
        this.lastLoadedData = mergedData; // <-- Add this line
      } else {
        console.error('Failed to save session to server.');
      }
    } catch (err) {
      console.error('Error saving session to server:', err);
    }
  },

  async loadFromSession() {
    try {
      const response = await fetch('/load_session');
      if (response.ok) {
        const data = await response.json();
        this.lastLoadedData = data; // <-- Store for later

        // Determine if a patient is currently active; only then allow restoring draft note
        let activeDfn = null;
        try {
          if (window.PatientContext && typeof window.PatientContext.get === 'function') {
            const meta = await window.PatientContext.get();
            activeDfn = meta && (meta.dfn || meta.patient_dfn || meta.patientDFN);
          } else {
            const pm = await fetch('/get_patient', { cache: 'no-store' });
            if (pm.ok) {
              const meta = await pm.json();
              activeDfn = meta && (meta.dfn || meta.patient_dfn || meta.patientDFN);
            }
          }
        } catch(_e) {}
        this._allowScribeDraftRestore = !!(activeDfn) || !!(data && data.patient_record);

        this.restoreData(data);
        console.log('Session loaded from server:', data);

        // Call displayPatientInfo to update patient name and record
        if (typeof displayPatientInfo === "function") {
          displayPatientInfo(data.patient_record);
        }

        // If no active patient, ensure any stale draft note is blank in the UI
        if (!this._allowScribeDraftRestore) {
          try { const el = document.getElementById('feedbackReply'); if (el) el.innerText = ''; } catch(_e) {}
        }
      } else {
        console.error('Failed to load session from server.');
      }
    } catch (err) {
      console.error('Error loading session from server:', err);
    }
  },

  async clearSession() {
    try {
      const token = window.getCsrfToken ? window.getCsrfToken() : '';
      const response = await fetch('/clear_session', { method: 'POST', headers: { 'X-CSRF-Token': token } });
      if (response.ok) {
        console.log('Session cleared on server.');
        window.exploreQAHistory = [];
        // Also clear any cached local copy and prevent restoring drafts until a patient is selected
        try { this.lastLoadedData = {}; } catch(_e) {}
        this._allowScribeDraftRestore = false;
      } else {
        console.error('Failed to clear session on server.');
      }
    } catch (err) {
      console.error('Error clearing session from server:', err);
    }
  },
  async saveFullSession(name) {
    const data = await this.collectData();
    try {
      const token = window.getCsrfToken ? window.getCsrfToken() : '';
      const response = await fetch('/save_full_session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
        body: JSON.stringify({ name, ...data }),
      });
      if (response.ok) {
        const result = await response.json();
        console.log('Full session saved to server:', result);
      } else {
        console.error('Failed to save full session to server.');
      }
    } catch (err) {
      console.error('Error saving full session to server:', err);
    }
  },

  async loadSavedSession(filename) {
    try {
      const response = await fetch(`/load_saved_session/${filename}`);
      if (response.ok) {
        const data = await response.json();
        this.restoreData(data.data);
        console.log('Saved session loaded from server:', data);
      } else {
        console.error('Failed to load saved session from server.');
      }
    } catch (err) {
      console.error('Error loading saved session from server:', err);
    }
  },

  async listSessions() {
    try {
      const response = await fetch('/list_sessions');
      if (response.ok) {
        const sessions = await response.json();
        console.log('Available sessions:', sessions);
        return sessions;
      } else {
        console.error('Failed to list sessions from server.');
        return [];
      }
    } catch (err) {
      console.error('Error listing sessions from server:', err);
      return [];
    }
  },

  async deleteSession(filename) {
    try {
      const response = await fetch(`/delete_session/${filename}`, { method: 'DELETE' });
      if (response.ok) {
        console.log(`Session ${filename} deleted from server.`);
      } else {
        console.error(`Failed to delete session ${filename} from server.`);
      }
    } catch (err) {
      console.error(`Error deleting session ${filename} from server:`, err);
    }
  },

  async endSession(sessionName) {
    // Use sessionName as provided (already sanitized in app.js)

    try {
      // Collect full session data first
      const fullData = await this.collectData();      // Save the session to the server
      const saveResponse = await fetch('/save_full_session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : '' },
        body: JSON.stringify({ name: sessionName, ...fullData }),
      });

      if (!saveResponse.ok) {
        console.error("❌ Failed to save session to server.");
        alert("Failed to save session. Please try again.");
        return;
      }

      const saveResult = await saveResponse.json();
      console.log("✅ Session saved to server:", saveResult);

      // Clear the session from the server
      const clearResponse = await fetch('/clear_session', { method: 'POST', headers: { 'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : '' } });

      if (!clearResponse.ok) {
        console.error("❌ Failed to clear session on server.");
        alert("Failed to clear session. Please try again.");
        return;
      }

      // Only clear live_transcript.txt after save and clear session are both successful
      await fetch('/scribe/clear_live_transcript', { method: 'POST', headers: { 'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : '' } });

      console.log("✅ Session cleared on server.");
      alert(`Session "${sessionName}" has been saved and cleared.`);
    } catch (err) {
      console.error("❌ Error ending session:", err);
      alert("An error occurred while ending the session. Please try again.");
    }
  },

  collectData: async function() {
    const data = {};

    // Scribe page data
    // Fetch from cached getter, which falls back to DOM when needed
    let transcript = '';
    try {
      transcript = await this.getTranscript(10000);
    } catch (err) {
      console.error("Failed to get transcript for session save:", err);
      try {
        const transcriptEl = document.getElementById('rawTranscript');
        if (transcriptEl) transcript = transcriptEl.value;
      } catch(_e) {}
    }
    data.scribe = { transcript };

    const visitNotesEl = document.getElementById('visitNotes');
    if (visitNotesEl) data.scribe.visitNotes = visitNotesEl.value;

    const instructionsBox = document.getElementById('patientInstructionsBox');
    if (instructionsBox) data.scribe.patientInstructions = instructionsBox.value;

    const promptSelectorEl = document.getElementById('promptSelector');
    if (promptSelectorEl) data.scribe.promptTemplate = promptSelectorEl.value;

    const feedbackReplyEl = document.getElementById('feedbackReply');
    if (feedbackReplyEl) data.scribe.feedbackReply = feedbackReplyEl.innerText;

    // Collect checklist data from workspace todo module
    if (window.WorkspaceModules && window.WorkspaceModules['To Do'] && window.WorkspaceModules['To Do'].getChecklistData) {
      data.scribe.checklist = window.WorkspaceModules['To Do'].getChecklistData();
    }

    // Explore page data
    const chunkTextEl = document.getElementById('chunkText');
    if (chunkTextEl) data.explore = { chunkText: chunkTextEl.value };

    const exploreResultsEl = document.getElementById('exploreGptAnswer');
    if (exploreResultsEl) data.explore.exploreResults = exploreResultsEl.innerHTML;
    if (window.exploreQAHistory) data.explore = { ...data.explore, qaHistory: window.exploreQAHistory };

    // Explore page module results
    const moduleResults = {};
    document.querySelectorAll('.panel').forEach(panel => {
        const title = panel.querySelector('h2')?.textContent || "";
        const output = panel.querySelector('.module-output')?.innerHTML || "";
        if (title) moduleResults[title] = output;
    });
    if (Object.keys(moduleResults).length) {
        data.explore = data.explore || {};
        data.explore.moduleResults = moduleResults;
    }

    return data;
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

      // Restore Scribe data
      if (data.scribe) {
        const transcriptEl = document.getElementById('rawTranscript');
        if (transcriptEl) transcriptEl.value = data.scribe.transcript || '';

        const visitNotesEl = document.getElementById('visitNotes');
        if (visitNotesEl) visitNotesEl.value = data.scribe.visitNotes || '';

        const instructionsBox = document.getElementById('patientInstructionsBox');
        if (instructionsBox && data.scribe.patientInstructions !== undefined) {
            instructionsBox.value = data.scribe.patientInstructions;
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

        const promptSelectorEl = document.getElementById('promptSelector');
        if (promptSelectorEl) promptSelectorEl.value = data.scribe.promptTemplate || '';

        const feedbackReplyEl = document.getElementById('feedbackReply');
        if (feedbackReplyEl) {
          if (this._allowScribeDraftRestore) {
            feedbackReplyEl.innerText = data.scribe.feedbackReply || '';
          } else {
            feedbackReplyEl.innerText = '';
          }
        }

        // Restore checklist data to workspace todo module
        if (data.scribe.checklist && window.WorkspaceModules && window.WorkspaceModules['To Do'] && window.WorkspaceModules['To Do'].setChecklistData) {
          window.WorkspaceModules['To Do'].setChecklistData(data.scribe.checklist);
        }
        if (data.scribe && data.scribe.transcript) {
          await fetch('/scribe/set_live_transcript', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
            },
            body: JSON.stringify({ text: data.scribe.transcript })
          });
        }

        // If restored content includes any meaningful text, enable autosave
        try {
          const hasT = !!(data.scribe.transcript && String(data.scribe.transcript).trim().length);
          const hasV = !!(data.scribe.visitNotes && String(data.scribe.visitNotes).trim().length);
          const hasD = !!(data.scribe.feedbackReply && String(data.scribe.feedbackReply).trim().length);
          const hasA = !!(data.scribe.patientInstructions && String(data.scribe.patientInstructions).trim().length);
          if (hasT || hasV || hasD || hasA) this.autosaveStarted = true;
        } catch(_e) {}

        // Mark that Scribe content was restored, so other logic can avoid overwriting it
        SessionManager.scribeRestored = true;
      }

      // Restore Explore data
      if (data.explore) {
        const chunkTextEl = document.getElementById('chunkText');
        if (chunkTextEl) chunkTextEl.value = data.explore.chunkText || '';

        const exploreResultsEl = document.getElementById('exploreGptAnswer');
        if (exploreResultsEl) exploreResultsEl.innerHTML = data.explore.exploreResults || '';

        if (data.explore.qaHistory) {
          window.exploreQAHistory = data.explore.qaHistory;
          if (typeof window.updateExploreQAHistory === "function") {
            window.updateExploreQAHistory();
          }
        }
      }
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
  });
} catch(_e){}

// Only register autosave with exit if we actually have meaningful content to save
if (document.getElementById('rawTranscript') || document.getElementById('chunkText')) {
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