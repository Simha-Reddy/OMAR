// scribe_runtime.js
// Lightweight event bus + runtime wrapper for transcript/status
(function(){
  if (window.ScribeRuntime) return; // singleton

  let _active = false;
  let _transcript = '';
  let _provider = null; // pluggable implementation (e.g., NoteRecorder)

  function dispatch(name, detail){
    try { window.dispatchEvent(new CustomEvent(name, { detail })); } catch(_e) {}
  }

  async function getTranscriptFallback(){
    // 1) Prefer SessionManager caches
    try { if (window.SessionManager && SessionManager.peekTranscriptFromSession){ const t = SessionManager.peekTranscriptFromSession(); if (t) return t; } } catch(_e) {}
    // 2) DOM fallback (Scribe page text area)
    try { const el = document.getElementById('rawTranscript'); if (el && el.value) return el.value; } catch(_e) {}
    return '';
  }

  const API = {
    // Status (public events; provider may also call these)
    setStatus(active){
      _active = !!active;
      try { window.currentRecordingState = _active; } catch(_e) {}
      dispatch('scribe:status', { active: _active, status: _active ? 'active' : 'stopped' });
    },
    async getStatus(){
      // Prefer provider if available
      try {
        if (_provider && typeof _provider.getStatus === 'function') {
          const st = await _provider.getStatus();
          if (typeof st === 'boolean') return { active: !!st, status: st ? 'active' : 'stopped' };
          if (st && typeof st === 'object' && typeof st.active !== 'undefined') return st;
        }
      } catch(_e){}
      return { active: !!_active, status: _active ? 'active' : 'stopped' };
    },

    // Transcript
    setTranscript(text){
      _transcript = (typeof text === 'string') ? text : '';
      dispatch('scribe:transcript', { text: _transcript });
    },
    async getTranscript(){
      if (typeof _transcript === 'string' && _transcript.length) return _transcript;
      return await getTranscriptFallback();
    },

    // Provider control
    registerProvider(provider){
      // provider: { start(opts), stop(), getStatus(), getTranscript? }
      _provider = provider || null;
      return !!_provider;
    },
    async start(opts){
      if (_provider && typeof _provider.start === 'function') {
        await _provider.start(opts || {});
        return true;
      }
      throw new Error('No scribe provider registered');
    },
    async stop(){
      if (_provider && typeof _provider.stop === 'function') {
        await _provider.stop();
        return true;
      }
      // Soft-fallback: just flip status
      API.setStatus(false);
      return false;
    },

    // Subscribe helpers
    onStatus(listener){
      const fn = (ev) => { try { listener(ev.detail); } catch(_e) {} };
      window.addEventListener('scribe:status', fn);
      return () => window.removeEventListener('scribe:status', fn);
    },
    onTranscript(listener){
      const fn = (ev) => { try { listener(ev.detail); } catch(_e) {} };
      window.addEventListener('scribe:transcript', fn);
      return () => window.removeEventListener('scribe:transcript', fn);
    }
  };

  try { window.ScribeRuntime = API; } catch(_e) {}
})();
