// Note Module for Workspace
// Clinical note writing and management

window.WorkspaceModules = window.WorkspaceModules || {};

window.WorkspaceModules['Note'] = {
    currentNote: '',
    promptData: {},
    chatHistory: [],
    isRecording: false,
    statusPollInterval: null,
    _oneLinerBusy: false,
    // New: orchestrator-aware polling state
    _statusAbortController: null,
    _statusAbortCleanup: null,
    _switchListenersBound: false,
    // New: transcript modal keyboard handler ref
    _transcriptKeyHandler: null,
    // Track created body-level modal element
    _transcriptModalEl: null,
    templates: {},

    async render(container, options = {}) {        try {
            this.container = container;
            container.innerHTML = `        <!-- Add styling for the header row and prompt selector layout -->
        <style>
            .note-header-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
                gap: 12px;
            }
            
            /* New: make entire Note module fill available tab height */
            .note-module {
                display: flex;
                flex-direction: column;
                height: 100%;
                min-height: 0; /* allow child to grow/shrink */
            }
            
            .note-header-row h2 {
                margin: 0;
                flex: 1;
            }
            
            .note-prompt-row {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 16px;
                flex-wrap: wrap;
            }
            
            .note-prompt-selector {
                flex: 1 1 auto;
                min-width: 200px;
                padding: 8px 12px;
                font-size: 14px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                height: 36px;
                box-sizing: border-box;
            }
            
            .note-record-btn {
                flex: 0 0 auto;
                height: 72px; /* Doubled from 36px */
                width: 72px;  /* Doubled from 36px */
                background: transparent;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
                transition: all 0.2s ease;
                border-radius: 50%;
            }
            
            .note-record-btn img {
                width: 68px; /* Doubled from 32px */
                height: 68px; /* Doubled from 32px */
                object-fit: contain;
            }
            
            .note-record-btn:hover {
                transform: scale(1.05);
                background-color: rgba(52, 152, 219, 0.1);
            }
            
            .note-record-btn:active {
                transform: scale(0.95);
            }            

            /* New: editable draft area should scroll and flex to fill */
            .note-module #feedbackReply {
                flex: 1 1 auto;
                min-height: 0;            /* allow container to control height */
                max-height: none;         /* remove caps */
                overflow-y: auto;         /* scroll within the area */
            }

            /* Wrapper to position the one-liner button over the draft box */
            .note-draft-wrapper {
                position: relative;
                flex: 1 1 auto;
                min-height: 0;
                display: flex;
                flex-direction: column;
            }
            .note-draft-wrapper #feedbackReply { flex: 1 1 auto; min-height: 0; }
            .add-one-liner-btn {
                position: absolute;
                top: 8px;
                right: 8px;
                background: #2ecc71; /* solid green */
                color: #fff;
                border: none;
                padding: 5px 10px;
                font-size: 12px;
                border-radius: 4px;
                cursor: pointer;
                z-index: 2;
                box-shadow: 0 1px 2px rgba(0,0,0,0.15);
            }
            .add-one-liner-btn:hover { filter: brightness(0.95); }
            .add-one-liner-btn:disabled { opacity: 0.6; cursor: not-allowed; }

            /* New: transcript modal styles */
            .note-modal {
                display: none; /* flex when open */
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.45);
                z-index: 9999;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .note-modal-content {
                background: #fff;
                color: #222;
                width: min(900px, 96vw);
                max-height: 85vh;
                border-radius: 8px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .note-modal-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 12px 16px;
                border-bottom: 1px solid #eee;
            }
            .note-modal-title { margin: 0; font-size: 16px; }
            .note-modal-close {
                background: transparent;
                border: none;
                font-size: 20px;
                cursor: pointer;
                line-height: 1;
            }
            .note-modal-body {
                padding: 12px 16px 16px;
                overflow: auto;
            }
            .note-modal-body pre {
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                font-size: 13px;
                line-height: 1.45;
            }
            .transcript-meta {
                font-size: 12px;
                color: #666;
                margin-bottom: 8px;
            }

            /* Responsive adjustments */
            @media (max-width: 768px) {
                .note-header-row {
                    flex-direction: column;
                    align-items: center;
                    gap: 16px;
                }
                
                .note-header-row h2 {
                    align-self: flex-start;
                }
                
                .note-prompt-row {
                    flex-direction: column;
                    align-items: stretch;
                }
                
                .note-prompt-selector {
                    min-width: unset;
                    width: 100%;
                }
            }
            
            @media (max-width: 480px) {
                .note-prompt-selector {
                    font-size: 13px;
                }
                
                .note-record-btn {
                    height: 56px; /* Scaled down for mobile but still larger than original */
                    width: 56px;
                }
                
                .note-record-btn img {
                    width: 52px;
                    height: 52px;
                }
            }
        </style>        
        <!-- module wrapper filling tab height -->
        <div class="note-module">
        <!-- header with title and recording button -->
        <div class="note-header-row">
            <h2>Draft Note</h2>
            <button id="noteRecordBtn"
                    class="note-record-btn image-record-btn"
                    title="Record"
                    aria-label="Record"
                    data-visual="image"
                    data-start-src="/static/images/start_Recording_circle_button.png"
                    data-stop-src="/static/images/stop_Recording_circle_button.png">
                <img id="noteRecordBtnImg" src="/static/images/start_Recording_circle_button.png" alt="Start Recording" />
            </button>
        </div>
          <!-- prompt selector -->
        <div class="note-prompt-row">
            <select id="promptSelector" class="note-prompt-selector">
                <option value="">Loading prompts...</option>
            </select>
        </div>

        <!-- prompt preview (hidden) -->
        <textarea id="promptPreview" style="display: none;"></textarea>

        <!-- note creation -->
        <div class="button-row">
            <button id="createUpdateDraftBtn" onclick="createNote()">Create Draft</button>
            <button onclick="copyFinalNote()" style="margin-right: auto;">Copy Final Note</button>
            <button id="showTranscriptBtn" title="Show live transcript in a modal">Show Transcript</button>
            <button id="loadUnsignedCprsBtn" title="Load most recent unsigned CPRS note into draft">Unsigned Note from CPRS</button>
            <!-- Removed save-to-VistA capability -->
            <!-- <button id="saveUnsignedCprsBtn" title="Save current draft back to the imported unsigned CPRS note (no signature)" disabled>Save Unsigned</button> -->
        </div>
        <div class="note-draft-wrapper">
          <button id="addOneLinerBtn" class="add-one-liner-btn" title="Add one-line IDENTIFICATION" aria-label="Add one-liner to top">Add one-liner</button>
          <div id="feedbackReply"
             contenteditable="true"
             role="textbox"
             aria-multiline="true"
             tabindex="0"
             spellcheck="true"
             title="Click to edit the draft note"
             style="margin-top:12px; padding:10px; background:#f9f9f9; min-height:300px; white-space: pre-wrap; border: 1px solid #ddd; border-radius: 4px; outline: none;">
          </div>
        </div>
        <!-- user feedback -->
        <input id="feedbackInput"
               type="text"
               placeholder="Type feedback, further instructions or questions here and press Enter…"
               style="width:100%; margin-top:10px"
               onkeypress="if(event.key==='Enter'){ submitFeedback(); return false; }" />

        <!-- Transcript Modal -->
        <div id="transcriptModal" class="note-modal" role="dialog" aria-modal="true" aria-labelledby="transcriptModalTitle" aria-describedby="transcriptModalBody" style="display:none;">
          <div class="note-modal-content" role="document">
            <div class="note-modal-header">
              <h3 id="transcriptModalTitle" class="note-modal-title">Live Transcript</h3>
              <button id="closeTranscriptModalBtn" class="note-modal-close" aria-label="Close transcript">×</button>
            </div>
            <div class="note-modal-body">
              <div class="transcript-meta" id="transcriptMeta"></div>
              <pre id="transcriptModalBody">Loading…</pre>
            </div>
          </div>
        </div>
        </div>

            `;            this.setupEventListeners();
            // Removed legacy loadDraftNote/loadRecentNotes; feedbackReply now manages persistence
            
            // Start polling for transcript updates
            this.startStatusPolling();

            // Bind orchestrator switch listeners once
            this._bindSwitchListeners && this._bindSwitchListeners();

            // NEW: Workspace auto-archive triggers
            try {
                const feedbackEl = container.querySelector('#feedbackReply');
                if (feedbackEl) {
                    // Restore from localStorage if empty and cached exists
                    try {
                        const cachedDraft = localStorage.getItem('workspace_feedback_reply');
                        const dfn = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                        const dfnScoped = dfn ? localStorage.getItem(`workspace_feedback_reply:${dfn}`) : null;
                        const hasContent = !!(feedbackEl.innerText && feedbackEl.innerText.trim().length);
                        // Only restore when a patient is active and the draft is empty
                        if (!hasContent && dfn) {
                            const candidate = (dfnScoped != null ? dfnScoped : cachedDraft);
                            if (candidate) feedbackEl.innerText = candidate;
                        }
                    } catch(_e) {}

                    const kick = async () => {
                        try {
                            // Ensure archive name exists and start auto-archive loop
                            if (typeof ensureArchiveNameInitialized === 'function') await ensureArchiveNameInitialized();
                            if (typeof startAutoArchiveForCurrentPatient === 'function') await startAutoArchiveForCurrentPatient();
                        } catch(_e) {}
                    };
                    // Trigger on first input
                    let armed = true;
                    const onAnyEdit = async () => {
                        if (!armed) return;
                        armed = false;
                        await kick();
                    };
                    feedbackEl.addEventListener('input', onAnyEdit, { passive: true });
                    feedbackEl.addEventListener('paste', onAnyEdit, { passive: true });
                    feedbackEl.addEventListener('keydown', (e)=>{
                        if (armed && (e.key.length === 1 || e.key === 'Backspace' || e.key === 'Delete' || e.key === 'Enter')) {
                            onAnyEdit();
                        }
                    });

                    // Debounced auto-save of draft edits (local + server session)
                    const saveFeedbackDraftDebounced = this.debounce(async () => {
                        try {
                            const text = feedbackEl.innerText || '';
                            const dfn = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                            // Save both DFN-scoped and legacy key for backward compatibility
                            if (dfn) localStorage.setItem(`workspace_feedback_reply:${dfn}`, text);
                            localStorage.setItem('workspace_feedback_reply', text);
                        } catch(_e) {}
                        try {
                            if (typeof SessionManager !== 'undefined' && SessionManager.saveToSession) {
                                await SessionManager.saveToSession();
                            }
                        } catch(_e) {}
                    }, 800);

                    const triggerAutoSave = (ev) => {
                        // Only debounce on real editing keystrokes when keydown
                        if (ev && ev.type === 'keydown') {
                            const k = ev.key;
                            if (!(k === 'Backspace' || k === 'Delete' || k === 'Enter' || (typeof k === 'string' && k.length === 1))) return;
                        }
                        saveFeedbackDraftDebounced();
                    };

                    feedbackEl.addEventListener('input', triggerAutoSave, { passive: true });
                    feedbackEl.addEventListener('paste', triggerAutoSave, { passive: true });
                    feedbackEl.addEventListener('keydown', triggerAutoSave);
                }

                // Wire up Add one-liner button
                const addBtn = container.querySelector('#addOneLinerBtn');
                if (addBtn) {
                    if (!addBtn._bound) {
                        addBtn._bound = true;
                        addBtn.addEventListener('click', () => this.addOneLiner());
                    }
                    // Initial enable/disable based on patient context
                    const dfnNow = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                    addBtn.disabled = !dfnNow;
                    // Update on patient switch/load events
                    try {
                        window.addEventListener('workspace:patientSwitched', () => { try { addBtn.disabled = true; } catch(_e){} });
                        window.addEventListener('patient:loaded', () => { try {
                            const d = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                            addBtn.disabled = !d;
                        } catch(_e){} });
                    } catch(_e){}
                }

                // Mirror enable/disable for Unsigned CPRS note button within container scope as well
                try {
                    const unsignedBtn = container.querySelector('#loadUnsignedCprsBtn');
                    if (unsignedBtn) {
                        const dNow = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                        unsignedBtn.disabled = !dNow;
                        window.addEventListener('workspace:patientSwitched', () => { try { unsignedBtn.disabled = true; } catch(_e){} });
                        window.addEventListener('patient:loaded', () => { try {
                            const d = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                            unsignedBtn.disabled = !d;
                        } catch(_e){} });
                    }
                } catch(_e){}

                // Wire Show Transcript button + modal handlers
                try {
                    const showBtn = container.querySelector('#showTranscriptBtn');
                    if (showBtn && !showBtn._bound) {
                        showBtn._bound = true;
                        showBtn.addEventListener('click', () => this.openTranscriptModal());
                    }
                } catch(_e){}
            } catch(_e) {}

        } catch (error) {
            container.innerHTML = `
                <div class="module-error">
                    <h3>Note Module</h3>
                    <p>Error loading note module: ${error.message}</p>
                </div>
            `;
        }
    },
    // Refresh the Create/Update Draft button label based on patient DFN and session flag
    _refreshCreateUpdateDraftLabel() {
        try {
            const btn = this.container ? this.container.querySelector('#createUpdateDraftBtn') : document.getElementById('createUpdateDraftBtn');
            if (!btn) return;
            const dfn = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
            if (!dfn) {
                btn.textContent = 'Create Draft';
                return;
            }
            const created = sessionStorage.getItem(`scribe:draftCreated:${dfn}`) === '1';
            btn.textContent = created ? 'Update Draft' : 'Create Draft';
        } catch(_e){}
    },
    setupEventListeners() {
        // Removed legacy template-select, save/clear buttons, and legacy textarea editor handlers
        // Removed local recordBtn wiring; app.js handles all .image-record-btn buttons
        const promptSelector = document.getElementById('promptSelector');

        // Wire Unsigned CPRS note button
        try {
            const btn = document.getElementById('loadUnsignedCprsBtn');
            if (btn && !btn._bound) {
                btn._bound = true;
                btn.addEventListener('click', () => this.fetchAndInsertLastUnsignedNote());
                // Initial enable/disable based on patient context
                const dfnNow = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                btn.disabled = !dfnNow;
                // Update on patient switch/load events
                try {
                    window.addEventListener('workspace:patientSwitched', () => { try { btn.disabled = true; } catch(_e){} });
                    window.addEventListener('patient:loaded', () => { try {
                        const d = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                        btn.disabled = !d;
                    } catch(_e){} });
                } catch(_e){}
            }
        } catch(_e){}

        // Wire Save Unsigned button
        try {
            const saveBtn = document.getElementById('saveUnsignedCprsBtn');
            if (saveBtn) {
                // Remove button from DOM if present from cached HTML
                saveBtn.parentNode && saveBtn.parentNode.removeChild(saveBtn);
            }
        } catch(_e){}

        // Prompt selector functionality
        if (promptSelector) {
            this.loadPrompts();
            promptSelector.addEventListener('change', (e) => {
                const promptPreview = document.getElementById('promptPreview');
                if (promptPreview && this.promptData) {
                    const selectedPrompt = this.promptData[e.target.value] || '';
                    promptPreview.value = selectedPrompt;
                    if (e.target.value) {
                        localStorage.setItem('lastPrompt', e.target.value);
                    }
                }
            });
        }

        // No legacy template selection, save, clear, or legacy textarea editor handlers remain

        // Initialize and wire Create/Update Draft button label to patient events
        try {
            this._refreshCreateUpdateDraftLabel();
            window.addEventListener('workspace:patientSwitched', () => {
                try {
                    const btn = document.getElementById('createUpdateDraftBtn');
                    if (btn) btn.textContent = 'Create Draft';
                } catch(_e){}
            });
            window.addEventListener('patient:loaded', () => this._refreshCreateUpdateDraftLabel());
        } catch(_e){}
    },

    // New: bind once to orchestrator events to pause/resume polling
    _bindSwitchListeners() {
        if (this._switchListenersBound) return;
        this._switchListenersBound = true;
        try {
            window.addEventListener('PATIENT_SWITCH_START', () => {
                try { this.stopStatusPolling(); } catch(_e){}
            });
            window.addEventListener('PATIENT_SWITCH_DONE', () => {
                try { this.startStatusPolling(); } catch(_e){}
            });
        } catch(_e){}
    },

    async fetchAndInsertLastUnsignedNote(){
        const btn = this.container ? this.container.querySelector('#loadUnsignedCprsBtn') : document.getElementById('loadUnsignedCprsBtn');
        const saveBtn = this.container ? this.container.querySelector('#saveUnsignedCprsBtn') : document.getElementById('saveUnsignedCprsBtn');
        if (btn) btn.disabled = true;
        try {
            const r = await fetch('/last_unsigned_note?include_text=1', { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
            const j = await r.json().catch(()=>({}));
            if (!r.ok) {
                const msg = (j && (j.error || j.message)) ? (j.error || j.message) : `Request failed (${r.status})`;
                throw new Error(msg);
            }
            const note = j && j.note;
            if (!note) {
                const m = (j && j.message) ? j.message : 'No unsigned note found.';
                alert(m);
                // Clear any previous state
                this._lastUnsignedMeta = null;
                if (saveBtn) saveBtn.disabled = true;
                return;
            }
            const lines = Array.isArray(note.text) ? note.text : [];
            const text = lines.join('\n');
            const el = document.getElementById('feedbackReply');
            if (el) {
                el.innerText = text || '';
                try { el.focus(); } catch(_e){}
                try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch(_e){}
            } else {
                alert('Draft editor not available.');
            }
            // Remember imported unsigned note metadata for Save
            this._lastUnsignedMeta = { docId: String(note.doc_id || ''), status: String(note.status || ''), author_doz: String(note.author_duz || '') };
            if (saveBtn) {
                const hasDraft = !!(text && text.trim());
                saveBtn.disabled = !(this._lastUnsignedMeta.docId && hasDraft);
            }
        } catch(e){
            alert(e && e.message ? e.message : 'Failed to load unsigned note.');
        } finally {
            if (btn) {
                try {
                    const d = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
                    btn.disabled = !d;
                } catch(_e){ btn.disabled = false; }
            }
        }
    },

    async saveUnsignedNote(){
        // Feature removed
        alert('Saving to VistA has been disabled.');
        return;
    },

    // New: Remove legacy editor helpers (insertText/insertBulletPoint/insertTimestamp/updateStats/saveDraft/loadDraftNote/saveNote/getSavedNotes/loadRecentNotes/loadNote)
    // Kept: debounce utility and all current note features
    
    // Utility function for debouncing
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    async refresh() {
        if (this.container) {
            await this.render(this.container);
        }
    },

    destroy() {
        // Stop status polling when module is destroyed/hidden
        this.stopStatusPolling();
    },

    // Recording control is handled globally via app.js and ScribeRuntime.
    // This module only listens to status events to reflect state locally.
    startStatusPolling() {
        this.stopStatusPolling();
        try {
            if (window.ScribeRuntime && typeof window.ScribeRuntime.onStatus === 'function') {
                this._statusUnsub = window.ScribeRuntime.onStatus((st) => {
                    try { this.isRecording = !!(st && st.active); } catch(_e){}
                });
            }
        } catch(_e){}
        // Prime initial state from runtime if available
        try {
            if (window.ScribeRuntime && typeof window.ScribeRuntime.getStatus === 'function') {
                window.ScribeRuntime.getStatus().then((st)=>{ try { this.isRecording = !!(st && st.active); } catch(_e){} });
            }
        } catch(_e){}
    },

    stopStatusPolling() {
        try { if (this._statusUnsub) { this._statusUnsub(); this._statusUnsub = null; } } catch(_e){}
        // Abort any in-flight status request (legacy cleanup)
        try { if (this._statusAbortController) this._statusAbortController.abort(); } catch(_e){}
        try { if (this._statusAbortCleanup) this._statusAbortCleanup(); } catch(_e){}
        this._statusAbortController = null;
        this._statusAbortCleanup = null;
    },

    // Prompt loading functionality
    async loadPrompts() {
        const selector = document.getElementById('promptSelector');
        if (!selector) return;
        try {
            let data = null;
            // Load bundled defaults; no legacy server prompt endpoint
            try {
                const r2 = await fetch('/static/prompts/default_prompts.json', { cache: 'no-store' });
                if (r2.ok) data = await r2.json();
            } catch(_e) {}
            if (!data || typeof data !== 'object' || !Object.keys(data).length) {
                // Final fallback: a single simple prompt
                data = {
                    'Primary Care Progress Note': 'Summarize the visit into a concise SOAP-style note with pertinent positives/negatives and assessment/plan.'
                };
            }

            this.promptData = data;

            // Clear and populate
            selector.innerHTML = '';
            for (let name in data) {
                const option = document.createElement('option');
                option.value = name;
                option.text = name;
                selector.appendChild(option);
            }

            // Determine initial selection
            const stored = localStorage.getItem('lastPrompt');
            let initialName = null;
            if (stored && data[stored]) {
                initialName = stored;
            } else if (data['Primary Care Progress Note']) {
                initialName = 'Primary Care Progress Note';
            } else {
                const first = Object.keys(data)[0];
                if (first) initialName = first;
            }

            // Apply initial selection
            if (initialName) {
                selector.value = initialName;
                const promptPreview = document.getElementById('promptPreview');
                if (promptPreview) {
                    promptPreview.value = data[initialName] || '';
                }
                localStorage.setItem('lastPrompt', initialName);
            }
        } catch (error) {
            console.error('Error loading prompts:', error);
        }
    },

    // FHIR placeholder replacement functions
    async replaceFhirPlaceholders(text) {
        if (!text || typeof text !== 'string') return text;
        try {
            if (window.DotPhrases && DotPhrases.replace) {
                return await DotPhrases.replace(text);
            }
        } catch(_e) {}
        return text;
    },

    async replaceFhirPlaceholdersSelective(text) {
        if (!text || typeof text !== 'string') return text;
        try {
            if (window.DotPhrases && DotPhrases.replace) {
                return await DotPhrases.replace(text);
            }
        } catch(_e) {}
        return text;
    },

    async resolveFhirToken(/* token */) {
        // Deprecated: use DotPhrases.resolve
        return null;
    },

    formatMedsList(meds) {
        if (!Array.isArray(meds) || meds.length === 0) {
            return 'No medications on file';
        }
        
        return meds.map(med => {
            const name = med.name || 'Unknown medication';
            const dose = med.dose ? ` ${med.dose}` : '';
            const frequency = med.frequency ? ` ${med.frequency}` : '';
            return `• ${name}${dose}${frequency}`;
        }).join('\n');
    },

    formatProblemsList(problems) {
        if (!Array.isArray(problems) || problems.length === 0) {
            return 'No problems on file';
        }
        
        const active = problems.filter(p => p.active);
        if (active.length === 0) {
            return 'No active problems';
        }
          return active.map(problem => `• ${problem.name || 'Unknown problem'}`).join('\n');
    },

    // Insert a concise IDENTIFICATION one-liner at the top of the draft note
    async addOneLiner(){
        if (this._oneLinerBusy) return;
        const btn = this.container && this.container.querySelector('#addOneLinerBtn');
        const feedbackEl = this.container && this.container.querySelector('#feedbackReply');
        // Ensure patient context
        const dfn = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
        if (!dfn) { try { alert('Select a patient first.'); } catch(_e){} return; }
        try {
            this._oneLinerBusy = true;
            if (btn) { btn.disabled = true; btn.textContent = 'Adding…'; }
            // Load one-liner prompt
            const r = await fetch('/load_one_liner_prompt', { cache: 'no-store' });
            if (!r.ok) throw new Error('Prompt not found');
            const promptText = await r.text();
            // Run notes QA over chart with demo masking flag
            const demoMode = !!(window.demoMasking && window.demoMasking.enabled);
            const res = await fetch('/explore/notes_qa', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': (window.getCsrfToken ? window.getCsrfToken() : (document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''))
                },
                body: JSON.stringify({ query: promptText, top_k: 8, demo_mode: demoMode })
            });
            const data = await res.json().catch(()=>({}));
            if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
            const answerRaw = String(data.answer || '').trim();
            if (!answerRaw) throw new Error('No summary returned');
            const clean = this._cleanOneLinerText(answerRaw);
            const prefix = `IDENTIFICATION: ${clean}`;
            // Insert at the very beginning
            const existing = (feedbackEl && feedbackEl.innerText) ? String(feedbackEl.innerText) : '';
            const needsGap = existing && !existing.startsWith('\n') ? '\n\n' : '';
            const combined = prefix + (existing ? (needsGap + existing) : '');
            if (feedbackEl) {
                feedbackEl.innerText = combined;
                // Place caret after the inserted line
                try {
                    const sel = window.getSelection && window.getSelection();
                    if (sel && document.createRange) {
                        const range = document.createRange();
                        range.selectNodeContents(feedbackEl);
                        range.collapse(true);
                        // Move to after the prefix
                        // Create a temporary text node to measure
                        const tmp = document.createTextNode(prefix + '\n\n');
                        feedbackEl.prepend(tmp);
                        range.setStart(tmp, tmp.textContent.length);
                        range.setEnd(tmp, tmp.textContent.length);
                        sel.removeAllRanges(); sel.addRange(range);
                        tmp.remove();
                    }
                } catch(_e){}
                // Trigger autosave listeners
                try { feedbackEl.dispatchEvent(new Event('input', { bubbles: true })); } catch(_e){}
            }
            // Also persist immediately to DFN-scoped cache and session
            try {
                const text = combined;
                if (dfn) localStorage.setItem(`workspace_feedback_reply:${dfn}`, text);
                localStorage.setItem('workspace_feedback_reply', text);
            } catch(_e){}
            try { if (typeof SessionManager !== 'undefined' && SessionManager.saveToSession) await SessionManager.saveToSession(); } catch(_e){}
        } catch (e) {
            console.warn('Add one-liner failed', e);
            try { alert('Could not add one-liner: ' + (e && e.message ? e.message : 'Unknown error')); } catch(_e){}
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Add one-liner'; }
            this._oneLinerBusy = false;
        }
    },

    _cleanOneLinerText(text){
        let s = String(text || '');
        // Remove HTML tags if any
        s = s.replace(/<[^>]+>/g, '');
        // Strip markdown links [text](url) -> text
        s = s.replace(/\[([^\]]+)\]\((?:[^)]+)\)/g, '$1');
        // Strip bold/italic/code markers
        s = s.replace(/\*\*([^*]+)\*\*/g, '$1')
             .replace(/\*([^*]+)\*/g, '$1')
             .replace(/__([^_]+)__/g, '$1')
             .replace(/_([^_]+)_/g, '$1')
             .replace(/`([^`]+)`/g, '$1')
             .replace(/^>\s?/gm, '')
             .replace(/^#{1,6}\s*/gm, '');
        // Remove parenthetical citations that contain the word Excerpt/Excerpts
        s = s.replace(/\([^()]*\bExcerpts?\b[^()]*\)/gi, '');
        // Collapse whitespace and newlines to a single space
        s = s.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();
        // Remove leading IDENTIFICATION: if server already added
        s = s.replace(/^\s*IDENTIFICATION:\s*/i, '');
        // Ensure ending punctuation
        if (s && !/[\.!?]$/.test(s)) s += '.';
        return s;
    },

    // New: Transcript modal controls (body-level, like Radiology viewer)
    async openTranscriptModal(){
        try {
            // If already open, close first
            if (this._transcriptModalEl && this._transcriptModalEl.parentNode) {
                try { this._transcriptModalEl.parentNode.removeChild(this._transcriptModalEl); } catch(_){}
                this._transcriptModalEl = null;
            }
            // Build overlay (copy pattern from Radiology)
            const modal = document.createElement('div');
            modal.className = 'document-modal';
            modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 10000; display: flex; align-items: center; justify-content: center;`;

            const modalContent = document.createElement('div');
            modalContent.className = 'document-modal-content';
            modalContent.style.cssText = `background: white; border-radius: 10px; width: 90%; max-width: 1000px; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 20px 40px rgba(0,0,0,0.3);`;

            const header = document.createElement('div');
            header.style.cssText = `padding: 20px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center;`;
            header.innerHTML = `
                <div>
                    <h3 style="margin:0; color:#333; font-size:1.3em;">Live Transcript</h3>
                    <div id="noteTranscriptMeta" style="margin-top:8px; font-size:0.9em; color:#666;"></div>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                  <button id="noteTranscriptClose" style="background:none; border:none; font-size:24px; cursor:pointer; padding:5px; color:#666; border-radius:50%; width:40px; height:40px;" title="Close">&times;</button>
                </div>`;

            const content = document.createElement('div');
            content.style.cssText = `padding: 20px; overflow-y: auto; flex: 1; font-family: 'Courier New', monospace; line-height: 1.6; background: #fafafa; white-space: pre-wrap;`;
            content.textContent = 'Loading…';

            modalContent.appendChild(header);
            modalContent.appendChild(content);
            modal.appendChild(modalContent);
            document.body.appendChild(modal);
            this._transcriptModalEl = modal;

            let _unsubTranscript = null;
            const close = () => {
                try { if (this._transcriptModalEl && this._transcriptModalEl.parentNode) this._transcriptModalEl.parentNode.removeChild(this._transcriptModalEl); } catch(_){}
                this._transcriptModalEl = null;
                try { if (typeof _unsubTranscript === 'function') _unsubTranscript(); } catch(__){}
            };
            modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
            const closeBtn = modalContent.querySelector('#noteTranscriptClose');
            if (closeBtn) closeBtn.addEventListener('click', close);
            const escListener = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escListener); } };
            document.addEventListener('keydown', escListener);

            // Fetch transcript (prefer session cache, then fresh, then endpoint)
            let txt = '';
            try { if (typeof SessionManager !== 'undefined' && SessionManager.peekTranscriptFromSession) { txt = SessionManager.peekTranscriptFromSession() || ''; } } catch(_e){}
            if (!txt) {
                try { if (typeof SessionManager !== 'undefined' && SessionManager.getTranscript) { txt = await SessionManager.getTranscript(0); } } catch(_e){}
            }
            // No legacy network fallback; rely on SessionManager/Workspace caches only
            txt = (typeof txt === 'string') ? txt.trim() : '';
            if (!txt) {
                content.textContent = 'No live transcript available.';
            } else {
                content.textContent = txt;
                const meta = modalContent.querySelector('#noteTranscriptMeta');
                if (meta) {
                    try { meta.textContent = `${txt.split(/\s+/).filter(Boolean).length} words`; } catch(_e){}
                }
            }

            // Live updates while modal is open
            try {
                if (window.ScribeRuntime && typeof window.ScribeRuntime.onTranscript === 'function'){
                    _unsubTranscript = window.ScribeRuntime.onTranscript((ev) => {
                        try{
                            const t = (ev && (ev.text||ev.delta||'')) || '';
                            const s = String(t).trim();
                            content.textContent = s || 'No live transcript available.';
                            const meta = modalContent.querySelector('#noteTranscriptMeta');
                            if (meta && s) meta.textContent = `${s.split(/\s+/).filter(Boolean).length} words`;
                        }catch(__){}
                    });
                }
            } catch(__){}
        } catch(_e) {
            try { alert('Could not load transcript.'); } catch(__){}
        }
    },
    closeTranscriptModal(){
        // Close body-level modal if present
        try {
            if (this._transcriptModalEl && this._transcriptModalEl.parentNode) {
                this._transcriptModalEl.parentNode.removeChild(this._transcriptModalEl);
            }
        } catch(_e) {}
        this._transcriptModalEl = null;
    }
};

// Global functions called from HTML
window.createNote = async function() {
    console.log('createNote fired');
    
    const module = window.WorkspaceModules['Note'];
    if (!module) return;
    
    try {
        // Persist the currently selected prompt as last used
        const promptSelector = document.getElementById('promptSelector');
        if (promptSelector && promptSelector.value) {
            localStorage.setItem('lastPrompt', promptSelector.value);
        }
        
        // Get transcript with Workspace-first strategy
        let transcript = '';

        // 1) SessionManager cache (lastLoadedData)
        if (typeof SessionManager !== 'undefined') {
            transcript = SessionManager.peekTranscriptFromSession();
        }

        // 2) Fetch fresh transcript from server (server is SoT for privacy/consistency)
        if (!transcript && typeof SessionManager !== 'undefined' && SessionManager.getTranscript) {
            try { transcript = await SessionManager.getTranscript(0); } catch(_e) {}
        }
        
        // 3) Final fallback to module cache if any
        if (!transcript) {
            transcript = module.currentTranscript || '';
        }

        const promptRaw = module.promptData[promptSelector?.value] || '';
        
        // Replace FHIR placeholders in prompt
        const promptText = await module.replaceFhirPlaceholdersSelective(promptRaw);
        const feedbackReply = document.getElementById('feedbackReply');
        
        // Get current draft note content before setting to loading
        const currentDraftNote = feedbackReply ? feedbackReply.innerText.trim() : '';
        
        if (feedbackReply) {
            feedbackReply.innerText = 'Loading…';
        }
        
        const response = await fetch('/scribe/create_note', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
            },
            body: JSON.stringify({
                transcript: transcript,
                prompt_text: promptText,
                current_draft: currentDraftNote
            })
        });
        
        const data = await response.json();
        
        // Replace FHIR placeholders in the generated note
        const finalNote = await module.replaceFhirPlaceholders(data.note || '');
        
        if (feedbackReply) {
            feedbackReply.innerText = finalNote;
        }
        
        // Update chat history
        module.chatHistory = data.messages || [
            { role: 'system', content: 'Note-edit session' },
            { role: 'assistant', content: finalNote }
        ];
        
        // Save to session if available
        if (typeof SessionManager !== 'undefined' && SessionManager.saveToSession) {
            await SessionManager.saveToSession();
        }

        // Mark draft as created for this patient in this session and refresh label
        try {
            const dfn = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
            if (dfn) sessionStorage.setItem(`scribe:draftCreated:${dfn}`, '1');
            if (window.WorkspaceModules && window.WorkspaceModules['Note'] && window.WorkspaceModules['Note']._refreshCreateUpdateDraftLabel) {
                window.WorkspaceModules['Note']._refreshCreateUpdateDraftLabel();
            }
        } catch(_e){}
        
    } catch (error) {
        console.error('Error creating note:', error);
        const feedbackReply = document.getElementById('feedbackReply');
        if (feedbackReply) {
            feedbackReply.innerText = 'Error creating note: ' + error.message;
        }
    }
};

window.copyFinalNote = function() {
    const feedbackReply = document.getElementById('feedbackReply');
    if (!feedbackReply) return;
    
    const text = feedbackReply.innerText;
    
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
            .then(() => alert('Final note copied!'))
            .catch(() => alert('Copy failed'));
    } else {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        
        try {
            document.execCommand('copy');
            alert('Final note copied!');
        } catch (err) {
            alert('Copy failed');
        }
        
        document.body.removeChild(textarea);
    }
};

window.submitFeedback = async function() {
    const module = window.WorkspaceModules['Note'];
    if (!module) return;
    
    const input = document.getElementById('feedbackInput');
    const replyDiv = document.getElementById('feedbackReply');
    const userMsg = input?.value?.trim();
    
    if (!userMsg) return;
    
    // Disable input and show loading
    if (input) {
        input.disabled = true;
        const oldPlaceholder = input.placeholder;
        input.placeholder = 'Loading AI response…';
        
        if (replyDiv) {
            replyDiv.innerText = 'Loading…';
        }
        
        // Ensure the current draft and prompt context are included before the user's feedback
        const currentDraft = replyDiv ? (replyDiv.innerText || '').trim() : '';
        const promptName = (document.getElementById('promptSelector')?.value || '').trim();
        const promptText = (module && module.promptData && promptName) ? (module.promptData[promptName] || '') : '';

        // If chatHistory is empty, seed with the last assistant message as the current draft
        if (!Array.isArray(module.chatHistory) || module.chatHistory.length === 0) {
            module.chatHistory = [];
        }
        // Prepend explicit context for the model
        module.chatHistory.push({ role: 'assistant', content: `DRAFT NOTE:\n${currentDraft || '(empty)'}` });
        if (promptText) {
            module.chatHistory.push({ role: 'system', content: `Prompt template in use: ${promptName}\n---\n${promptText}` });
        }
        
        // Add user message to chat history
        module.chatHistory.push({ role: 'user', content: userMsg });
        
        try {
            const response = await fetch('/scribe/chat_feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
                },
                body: JSON.stringify({ messages: module.chatHistory })
            });
            
            const data = await response.json();
            
            // Display the reply
            if (data.reply && replyDiv) {
                module.chatHistory.push({ role: 'assistant', content: data.reply });
                replyDiv.innerText = data.reply;
            }
            
            // Save to session if available
            if (typeof SessionManager !== 'undefined' && SessionManager.saveToSession) {
                await SessionManager.saveToSession();
            }
            
        } catch (error) {
            console.error('Error submitting feedback:', error);
            if (replyDiv) {
                replyDiv.innerText = 'Error: ' + error.message;
            }
        } finally {
            // Re-enable input
            input.disabled = false;
            input.placeholder = oldPlaceholder;
            input.value = '';
            input.focus();
        }
    }
};
