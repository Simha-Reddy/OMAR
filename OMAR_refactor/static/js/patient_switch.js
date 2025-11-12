// Centralized Patient Switch Orchestrator
(function(){
  const Api = (window.Api || null);
  const BUS = (function(){
    try { return window.AppEvents || (window.AppEvents = new EventTarget()); } catch(_e){ return window; }
  })();

  try { console.log('[Patient] patient_switch orchestrator loaded'); } catch(_e){}

  const Patient = window.Patient || {};

  let _isSwitching = false;
  let _currentToken = 0;
  const _abortRegistry = new Set();
  const _hydrationCooldown = new Map();

  function getCurrentSwitchToken(){ return _currentToken; }
  function registerAbortable(controller){ try{ _abortRegistry.add(controller); }catch(_e){} return ()=>{ try{ _abortRegistry.delete(controller); }catch(_e){} }; }
  function abortAllInFlight(){
    try{ _abortRegistry.forEach(ctrl=>{ try{ ctrl.abort(); }catch(_){} }); }catch(_e){}
    try{ _abortRegistry.clear(); }catch(_e){}
  }

  function _resolveHeyOmarModelId(){
    try{
      const stored = localStorage.getItem('HEY_OMAR_MODEL_ID');
      if (stored && String(stored).trim()) return String(stored).trim();
    }catch(_e){}
    return 'default';
  }

  function _emitHeyOmarHydration(detail){
    try{ window.dispatchEvent(new CustomEvent('heyomar:rag-manifest', { detail })); }catch(_e){}
  }

  function _kickoffRagHydration(dfn, token, source){
    const target = (dfn == null) ? '' : String(dfn).trim();
    if (!target) return;
    const model = _resolveHeyOmarModelId();
    const key = `${target}:${model}`;
    const now = Date.now();
    const lastTs = _hydrationCooldown.get(key) || 0;
    if (!source) source = 'switch';
    if (now - lastTs < 4000 && source !== 'retry') {
      return;
    }
    _hydrationCooldown.set(key, now);
    const body = { dfn: target, model };
    if (typeof token !== 'number') {
      try { token = getCurrentSwitchToken(); } catch(_e){}
    }
    const ctrl = new AbortController();
    const unregister = registerAbortable(ctrl);
    (async ()=>{
      try{
        console.log('[Patient] Document index hydration begin', { endpoint: '/api/documents/index/start', body, source });
        try{ window.dispatchEvent(new CustomEvent('heyomar:rag-start', { detail: { dfn: target, model, source, ts: Date.now() } })); }catch(_e){}
        const endpoint = '/api/documents/index/start';
        let res = await fetch(endpoint, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: ctrl.signal,
        });
        if (!res.ok && res.status === 404){
          console.warn('[Patient] Document index hydration endpoint missing at', endpoint, '; retrying legacy /api/query path');
          res = await fetch('/api/query/index/start', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: ctrl.signal,
          });
        }
        if (!res.ok){
          const msg = await res.text().catch(()=>('HTTP '+res.status));
          throw new Error(msg || ('HTTP '+res.status));
        }
        const payload = await res.json().catch(()=>({}));
        if (token && token !== getCurrentSwitchToken()) return;
        if (payload && payload.manifest){
          try{
            const cacheKey = `heyomar:manifest:${body.model}:${body.dfn}`;
            sessionStorage.setItem(cacheKey, JSON.stringify({ ts: Date.now(), manifest: payload.manifest }));
          }catch(_e){}
          console.log('[Patient] Document index hydration complete', { body, manifest: payload.manifest });
          _emitHeyOmarHydration({ dfn: body.dfn, model: body.model, manifest: payload.manifest, status: 'ok' });
        } else if (payload && payload.error){
          console.warn('[Patient] Document index hydration error payload', payload);
          _emitHeyOmarHydration({ dfn: body.dfn, model: body.model, status: 'error', error: payload.error });
        }
      }catch(err){
        if (err && err.name === 'AbortError') return;
        console.warn('[Patient] Document index hydration failed:', err);
        _emitHeyOmarHydration({ dfn: String(dfn), model: body.model, status: 'error', error: String(err && err.message || err) });
      }finally{
        unregister();
      }
    })();
  }

  try{
    window.addEventListener('workspace:patientSwitched', (ev)=>{
      try{
        const detail = ev && ev.detail || {};
        let dfn = detail && detail.dfn ? String(detail.dfn).trim() : '';
        if (!dfn){
          try { dfn = sessionStorage.getItem('CURRENT_PATIENT_DFN') || window.CURRENT_PATIENT_DFN || ''; } catch(_e){}
        }
        if (!dfn) return;
        const token = getCurrentSwitchToken();
        _kickoffRagHydration(dfn, token, 'event');
      }catch(_err){ console.warn('[Patient] Document hydration listener error:', _err); }
    });
  }catch(_e){}

  try{
    window.addEventListener('PATIENT_SWITCH_DONE', (ev)=>{
      try{
        const detail = ev && ev.detail || {};
        const dfn = detail && detail.to ? String(detail.to).trim() : '';
        const token = detail && typeof detail.token === 'number' ? detail.token : getCurrentSwitchToken();
        if (dfn) _kickoffRagHydration(dfn, token, 'done-event');
      }catch(err){ console.warn('[Patient] Document hydration PATIENT_SWITCH_DONE listener error:', err); }
    });
  }catch(_e){}

  try{
    window.addEventListener('patient:loaded', (ev)=>{
      try{
        const detail = ev && ev.detail || {};
        let dfn = detail && detail.dfn ? String(detail.dfn).trim() : '';
        if (!dfn){
          try { dfn = sessionStorage.getItem('CURRENT_PATIENT_DFN') || window.CURRENT_PATIENT_DFN || ''; } catch(_e){}
        }
        if (!dfn) return;
        _kickoffRagHydration(dfn, getCurrentSwitchToken(), 'patient-loaded');
      }catch(err){ console.warn('[Patient] Document hydration patient:loaded listener error:', err); }
    });
  }catch(_e){}

  function _emit(name, detail){
    try{ if (BUS && BUS.dispatchEvent) BUS.dispatchEvent(new CustomEvent(name, { detail })); }catch(_e){}
    try{ window.dispatchEvent(new CustomEvent(name, { detail })); }catch(_e){}
  }

  function _setUiSwitching(on){
    const body = document.body;
    try{ body.classList.toggle('patient-switching', !!on); }catch(_e){}
    // Disable workspace interactions
    try{
      const panes = document.querySelectorAll('.workspace-container, .tab-content-area');
      panes.forEach(el=> el.style.pointerEvents = on ? 'none' : '');
      const search = document.getElementById('patientSearchInput');
      if (search) search.disabled = !!on;
    }catch(_e){}
    // Banner
    try{
      let b = document.getElementById('patientSwitchBanner');
      if (on){
        if (!b){
          b = document.createElement('div');
          b.id = 'patientSwitchBanner';
          Object.assign(b.style, {
            position:'fixed', top:'var(--topbar-h, 60px)', left:'0', right:'0', zIndex:'3000',
            background:'#fff3cd', color:'#856404', borderBottom:'1px solid #ffeeba',
            padding:'8px 12px', textAlign:'center', fontWeight:'600'
          });
          b.textContent = 'Switching patient…';
          document.body.appendChild(b);
        } else { b.style.display = 'block'; b.textContent = 'Switching patient…'; }
      } else if (b){ b.style.display = 'none'; }
    }catch(_e){}
  }

  function _hideTransientUi(){
    try{ const ov = document.getElementById('docViewerOverlay'); if (ov) ov.style.display = 'none'; }catch(_e){}
  }

  // New: strictly blank UI/layout without rehydration (used before switch)
  async function _blankUiAndLayout(){
    try{
      if (window.WorkspaceTabs && typeof window.WorkspaceTabs.blankForNewPatient === 'function'){
        try{ window.WorkspaceTabs.blankForNewPatient(); }catch(_e){}
      }
    }catch(_e){}
  }

  async function _rehydrateLayout(){
    try{
      // Prefer explicit blanking so modules can run destroy()
      if (window.WorkspaceTabs && typeof window.WorkspaceTabs.blankForNewPatient === 'function'){
        try{ window.WorkspaceTabs.blankForNewPatient(); }catch(_e){}
      }
      // Let Workspace handle server/local layout rehydrate (do not emit workspace:patientSwitched here)
      if (window.WorkspaceTabs && typeof window.WorkspaceTabs.restoreLayout === 'function'){
        try{ await window.WorkspaceTabs.restoreLayout(); }catch(_e){}
      }
    }catch(_e){}
  }

  // Removed legacy server-session DFN poll; client holds DFN

  async function _updateHeaderAndModules(){
    try{
      // Ensure global top bar patient info updates promptly in refactor
      try { if (typeof window.updateHeaderFromDemographics === 'function') { await window.updateHeaderFromDemographics(); } } catch(_e) {}
      // Let front-end refresh off DFN using Api; rely on event listeners
      try{ if (typeof window.displayPatientInfo === 'function'){ window.displayPatientInfo(); } }catch(_e){}
      try{ if (typeof window.initPrimaryNoteUI === 'function'){ window.initPrimaryNoteUI({}); } }catch(_e){}
      try{ if (typeof window.resetDocuments === 'function'){ window.resetDocuments(); } else if (typeof window.refreshDocuments === 'function'){ window.refreshDocuments(); } }catch(_e){}
      try{ if (window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function'){ window.VitalsSidebar.refresh(); } }catch(_e){}
      try{ if (window.RightSidebar && typeof window.RightSidebar.refresh === 'function'){ window.RightSidebar.refresh(); } }catch(_e){}
      try{ if (typeof window.updatePatientNameDisplay === 'function'){ window.updatePatientNameDisplay(); } }catch(_e){}
      try{ const fireResize = ()=>{ try{ window.dispatchEvent(new Event('resize')); }catch(_e){} }; fireResize(); setTimeout(fireResize, 60); setTimeout(fireResize, 240); }catch(_e){}
    }catch(_e){}
  }

  function _immediateClearOnSwitchStart(){
    try { if (window.stopAutoSaveLoop) window.stopAutoSaveLoop(); } catch(_e){}

    try {
      const vn = document.getElementById('visitNotes');
      if (vn) { vn.value = ''; vn.dispatchEvent(new Event('input', { bubbles: true })); }
      const rt = document.getElementById('rawTranscript');
      if (rt) rt.value = '';
      const fr = document.getElementById('feedbackReply');
      if (fr) fr.innerText = '';
      const ans = document.getElementById('exploreGptAnswer');
      if (ans) ans.innerHTML = '';
      document.querySelectorAll('.panel .module-output').forEach(el => el.innerHTML = '');
      try {
        if (window.WorkspaceModules && window.WorkspaceModules['To Do'] && typeof window.WorkspaceModules['To Do'].setChecklistData === 'function') {
          window.WorkspaceModules['To Do'].setChecklistData([]);
        } else {
          const checklist = document.querySelector('#checklist-items');
          if (checklist) checklist.innerHTML = '<div class="checklist-empty">No checklist items. Add one below.</div>';
        }
      } catch(_e){}
      try { window.exploreQAHistory = []; if (typeof window.updateExploreQAHistory === 'function') window.updateExploreQAHistory(); } catch(_e){}
    } catch(_e){}

    try { localStorage.removeItem('ssva:currentArchiveName'); } catch(_e){}
    let prevDfn = '';
    try { prevDfn = sessionStorage.getItem('CURRENT_PATIENT_DFN') || window.CURRENT_PATIENT_DFN || ''; } catch(_e){}
    try { sessionStorage.removeItem('CURRENT_PATIENT_DFN'); } catch(_e){}
    try { window.CURRENT_PATIENT_DFN = ''; } catch(_e){}
    try { localStorage.removeItem('workspace_feedback_reply'); } catch(_e){}
    try {
      if (prevDfn) localStorage.removeItem(`workspace_feedback_reply:${prevDfn}`);
      const toDelete = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith('workspace_feedback_reply:')) toDelete.push(k);
      }
      toDelete.forEach(k => { try { localStorage.removeItem(k); } catch(_e){} });
    } catch(_e){}

    try { if (window.SessionManager) window.SessionManager._allowScribeDraftRestore = false; } catch(_e){}
  }

  async function _serverSaveAndClearBeforeSwitch(prevDfn){
    try {
      try { if (window.stopAutoSaveLoop) window.stopAutoSaveLoop(); } catch(_e){}
      try { if (window.SessionManager && SessionManager.saveToSession) { await SessionManager.saveToSession(); } } catch(_e){}

      // Phase 4: save archive snapshot before switching (server-side)
      try { if (typeof window.saveArchiveNow === 'function') await window.saveArchiveNow('pre-switch'); } catch(_e){}

      // Stop scribe via refactor endpoint; CSRF header added by global fetch patch
      try { await fetch('/api/scribe/stop', { method: 'POST' }); } catch(_e){}

      // Purge server ephemeral state for the previous patient to ensure no PHI lingers
      try {
        const pid = (prevDfn == null) ? '' : String(prevDfn).trim();
        if (pid) {
          await fetch('/api/session/purge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: pid }),
            credentials: 'same-origin'
          });
        }
      } catch(_e){}
    } catch (e) {
      console.warn('[Patient] server save/clear before switch warning:', e);
    }
  }

  async function _promptReloadLatestArchiveForPatient(patientId){
    try {
      const pid = (patientId==null)?'':String(patientId).trim();
      if (!pid) return false;
      const r = await fetch(`/api/archive/list?patient_id=${encodeURIComponent(pid)}`, { credentials:'same-origin', cache:'no-store' });
      if (!r.ok) return false;
      const j = await r.json().catch(()=>({}));
      const items = (j && Array.isArray(j.items)) ? j.items : [];
      if (!items.length) return false;
      const latest = items[0];
      const when = (function(){ try{ const d = new Date((latest.updated_at||latest.created_at)*1000 || latest.updated_at || latest.created_at); return isNaN(d) ? '' : d.toLocaleString(); }catch(_e){ return ''; }})();
      const msg = `A previous archive was found for this patient${when?` (last updated ${when})`:''}.\n\nReload it now?`;
      const ok = window.confirm(msg);
      if (!ok) return false;
      const r2 = await fetch(`/api/archive/load?id=${encodeURIComponent(latest.archive_id)}`, { credentials:'same-origin', cache:'no-store' });
      if (!r2.ok) return false;
      const j2 = await r2.json().catch(()=>({}));
      const doc = j2 && j2.archive;
      const state = doc && doc.state;
      if (!state) return false;
      if (window.SessionManager && typeof window.SessionManager.restoreData === 'function') {
        await window.SessionManager.restoreData(state);
        // Persist restored state to ephemeral immediately
        try { if (typeof window.SessionManager.saveToSession === 'function') await window.SessionManager.saveToSession(); } catch(_e){}
        return true;
      }
      return false;
    } catch(_e){ return false; }
  }

  async function switchTo(dfn, opts = {}){
    const target = (dfn == null) ? '' : String(dfn).trim();
    const current = (function(){ try { return String(window.CURRENT_PATIENT_DFN || ''); } catch(_e){ return ''; } })();
    if (!target) return false;
    if (current && target === current){ return true; }
    if (_isSwitching){ console.warn('[Patient] Switch already in progress; ignoring'); return false; }

    _isSwitching = true;
    _currentToken++;
    const token = _currentToken;

    console.log('[Patient] switchTo start', { target, current, opts });
    _emit('PATIENT_SWITCH_START', { from: current || null, to: target });
    _setUiSwitching(true);
    _hideTransientUi();
    abortAllInFlight();

  await _serverSaveAndClearBeforeSwitch(current);

    try { _immediateClearOnSwitchStart(); } catch(_e){}

    await _blankUiAndLayout();

    // Validate DFN using refactor API (demographics)

    const TIMEOUT_MS = 45000;
    function withTimeout(p){
      return Promise.race([
        p,
        new Promise((_, rej)=> setTimeout(()=> rej(new Error('Patient switch timed out')), TIMEOUT_MS))
      ]);
    }

    console.time && console.time('patientSwitch');
    try{
  // Set DFN client-side and validate by fetching demographics
  if (!Api || !Api.setDFN || !Api.quick) throw new Error('Api not available');
  Api.setDFN(target);
  const demo = await withTimeout(Api.quick('demographics'));

      try {
        const u = new URL(window.location.href);
        if (!window.__IS_WORKSPACE) {
          u.searchParams.set('dfn', String(target));
          window.history.replaceState({}, '', u.toString());
        } else {
          if (u.searchParams.has('dfn')) {
            u.searchParams.delete('dfn');
            window.history.replaceState({}, '', u.toString());
          }
        }
      } catch(_e){}

      try{
        if (!(opts && opts.skipArchiveSetup)) {
          let name = opts.displayName || '';
          if (!name){ name = (demo && (demo.name || demo.displayName || demo.fullName)) || String(target); }
          if (window.setNewArchiveForPatient) await window.setNewArchiveForPatient(name);
        }
      } catch(_e){}

    await _rehydrateLayout();
      try{ window.dispatchEvent(new CustomEvent('workspace:patientSwitched', { detail: { dfn: target, alreadyRehydrated: true } })); }catch(_e){}
  await _updateHeaderAndModules();
  try { _kickoffRagHydration(target, token, 'switch'); } catch(_e){}

    // Prompt to reload last archive (if any) for the newly selected patient
    try { await _promptReloadLatestArchiveForPatient(target); } catch(_e){}

      _emit('PATIENT_SWITCH_DONE', { to: target, token });
      try{ window.dispatchEvent(new CustomEvent('patient:changed', { detail: { dfn: target } })); }catch(_e){}
      try{ window.dispatchEvent(new CustomEvent('patient:loaded', { detail: { dfn: target } })); }catch(_e){}
      console.time && console.timeEnd('patientSwitch');
      return true;
    } catch (err){
      console.warn('[Patient] Switch failed:', err);
      _emit('PATIENT_SWITCH_FAILED', { to: target, error: String(err && err.message || err) });
      try{
        let t = document.getElementById('patientSwitchToast');
        if (!t){ t = document.createElement('div'); t.id='patientSwitchToast'; Object.assign(t.style, { position:'fixed', bottom:'16px', right:'16px', background:'#f8d7da', color:'#721c24', border:'1px solid #f5c6cb', padding:'8px 12px', borderRadius:'6px', zIndex:'3000' }); document.body.appendChild(t); }
        t.textContent = 'Patient switch failed. Please try again.';
        setTimeout(()=>{ try{ t.remove(); }catch(_e){} }, 4000);
      }catch(_e){}
      return false;
    } finally {
      _setUiSwitching(false);
      _isSwitching = false;
    }
  }

  try {
    Patient.switchTo = switchTo;
    Patient.getCurrentSwitchToken = getCurrentSwitchToken;
    Patient.registerAbortable = registerAbortable;
    Patient.abortAll = abortAllInFlight;
    Patient.hydrateDocuments = function(opts){
      try {
        let dfn = opts && opts.dfn ? String(opts.dfn).trim() : '';
        if (!dfn){
          try { dfn = sessionStorage.getItem('CURRENT_PATIENT_DFN') || window.CURRENT_PATIENT_DFN || ''; } catch(_e){}
        }
        if (!dfn) throw new Error('Missing DFN for manual hydration');
        _kickoffRagHydration(dfn, getCurrentSwitchToken(), 'manual');
        return true;
      } catch(err){
        console.error('[Patient] Manual document hydration failed:', err);
        return false;
      }
    };
    window.Patient = Patient;
  } catch(_e){}
})();