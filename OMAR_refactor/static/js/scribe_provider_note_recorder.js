// scribe_provider_note_recorder.js
// Provider that wires NoteRecorder (/api/scribe/* pipeline) into ScribeRuntime
(function(){
  if (!window.ScribeRuntime) return; // runtime must be loaded first
  if (window.__ScribeNoteProviderLoaded) return;
  window.__ScribeNoteProviderLoaded = true;

  // Utility: CSRF token
  function _csrf(){
    try{
      const cookieValue = document.cookie.split('; ').find(r=> r.startsWith('csrf_token='))?.split('=')[1];
      if (cookieValue) return cookieValue;
      return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }catch(_e){ return ''; }
  }

  // Resolve patient DFN from context
  async function _getPatientId(){
    try { if (window.CURRENT_PATIENT_DFN) return String(window.CURRENT_PATIENT_DFN); } catch(_e){}
    try { if (sessionStorage) { const d = sessionStorage.getItem('CURRENT_PATIENT_DFN'); if (d) return String(d); } } catch(_e){}
    try {
      if (window.PatientContext && typeof window.PatientContext.get === 'function'){
        const meta = await window.PatientContext.get();
        const id = meta && (meta.dfn || meta.patient_dfn || meta.patientDFN);
        if (id) return String(id);
      }
    } catch(_e){}
    return '';
  }

  // Local transcript accumulator so UI can read without server round-trips
  let _transcript = '';
  let _statusTimer = null;
  function _appendDelta(delta){
    if (!delta) return;
    _transcript += String(delta);
    try { window.ScribeRuntime.setTranscript(_transcript); } catch(_e){}
  }

  async function _pollStatus(){
    try{
      const sid = window.currentScribeSessionId || null;
      if (!sid) return;
      const url = `/api/scribe/status?session_id=${encodeURIComponent(sid)}`;
      const res = await fetch(url, { method:'GET', cache:'no-store', credentials:'same-origin' });
      if (!res.ok) return;
      const j = await res.json().catch(()=>null);
      if (!j) return;
      // Update status
      try { window.ScribeRuntime.setStatus(String(j.status||'') === 'active'); } catch(_e){}
      // Update transcript if changed
      const t = (j.transcript || '').toString();
      if (t && t !== _transcript){
        _transcript = t;
        try { window.ScribeRuntime.setTranscript(_transcript); } catch(_e){}
      }
    }catch(_e){}
  }

  function _startStatusPolling(){
    try { if (_statusTimer) { clearInterval(_statusTimer); _statusTimer = null; } } catch(_e){}
    _statusTimer = setInterval(_pollStatus, 1500);
  }
  function _stopStatusPolling(){
    try { if (_statusTimer) clearInterval(_statusTimer); } catch(_e){}
    _statusTimer = null;
  }

  // Custom uploader that mirrors NoteRecorder default but taps transcript deltas
  async function _uploader({ patientId, generation, blob, seq, mimeType }){
    const sid = window.currentScribeSessionId || null;
    if (!sid) throw new Error('No scribe session');
    const url = `/api/scribe/stream?session_id=${encodeURIComponent(sid)}&seq=${seq}`;
    const headers = {
      'x-patient-id': String(patientId || ''),
      'x-patient-generation': String(generation || ''),
      'content-type': mimeType || 'application/octet-stream',
      'X-CSRF-Token': _csrf()
    };
    let res;
    try {
      res = await fetch(url, { method: 'POST', headers, body: blob, credentials: 'same-origin' });
    } catch (e) {
      throw new Error('Upload failed (network)');
    }
    if (!res.ok) {
      let detail = '';
      try { detail = await res.text(); } catch {}
      throw new Error(`Upload failed: ${res.status}${detail ? ' - ' + detail : ''}`);
    }
    // If provider returned JSON with transcript delta, fold it into runtime
    if (String(res.headers.get('content-type')||'').includes('application/json')){
      try {
        const j = await res.json();
        const d = j && (j.transcript_delta || j.delta || j.text || '');
        if (d) _appendDelta(d);
      } catch(_e){}
    }
    return { ok: true };
  }

  // Keep a singleton NoteRecorder instance
  let _rec = null;
  let _active = false;

  async function start(){
    // If already recording, no-op
    if (_active && _rec) return;
    const patientId = await _getPatientId();
    if (!patientId) throw new Error('Select a patient before recording');

    // Ensure NoteRecorder is available
    if (typeof window.NoteRecorder !== 'function') throw new Error('NoteRecorder not loaded');

    // Consent: opt-in via localStorage; default allow for demo
    let hasConsent = true;
    try { const v = localStorage.getItem('ssva:scribeConsent'); if (v !== null) hasConsent = (v === '1' || v === 'true'); } catch(_e){}

    _rec = new window.NoteRecorder({
      patientId,
      getGeneration: () => null,
      onStatus: (st) => {
        try { window.ScribeRuntime.setStatus(!!(st && st.active)); } catch(_e){}
      },
      onError: (e) => { console.warn('[ScribeProvider]', e && (e.message||e)); },
      uploader: _uploader,
      chunkMs: (typeof window !== 'undefined' && window.SCRIBE_CHUNK_MS ? Number(window.SCRIBE_CHUNK_MS) : 2000),
      requireConsent: false,
      hasConsent: !!hasConsent,
      forceWav: !!window.FORCE_WAV_RECORDING
    });

    // Reset local transcript buffer at start
    _transcript = '';
    try { window.ScribeRuntime.setTranscript(''); } catch(_e){}

    await _rec.start();
    _active = true;
    try { window.ScribeRuntime.setStatus(true); } catch(_e){}
    _startStatusPolling();
  }

  async function stop(){
    if (_rec) {
      try { await _rec.stop(); } catch(_e){}
    }
    _rec = null;
    _active = false;
    try { window.ScribeRuntime.setStatus(false); } catch(_e){}
    _stopStatusPolling();
  }

  async function getStatus(){
    return { active: !!_active, status: _active ? 'active' : 'stopped' };
  }

  // Stop cleanly on patient switch
  try { window.addEventListener('PATIENT_SWITCH_START', () => { try { stop(); } catch(_e){} try{ _stopStatusPolling(); }catch(__){} }); } catch(_e){}

  // Register with runtime
  try { window.ScribeRuntime.registerProvider({ start, stop, getStatus }); } catch(_e){}
})();
