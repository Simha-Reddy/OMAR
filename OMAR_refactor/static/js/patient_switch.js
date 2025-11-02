// Centralized Patient Switch Orchestrator
(function(){
  const Api = (window.Api || null);
  const BUS = (function(){
    try { return window.AppEvents || (window.AppEvents = new EventTarget()); } catch(_e){ return window; }
  })();

  const Patient = window.Patient || {};

  let _isSwitching = false;
  let _currentToken = 0;
  const _abortRegistry = new Set();

  function getCurrentSwitchToken(){ return _currentToken; }
  function registerAbortable(controller){ try{ _abortRegistry.add(controller); }catch(_e){} return ()=>{ try{ _abortRegistry.delete(controller); }catch(_e){} }; }
  function abortAllInFlight(){
    try{ _abortRegistry.forEach(ctrl=>{ try{ ctrl.abort(); }catch(_){} }); }catch(_e){}
    try{ _abortRegistry.clear(); }catch(_e){}
  }

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

  async function _serverSaveAndClearBeforeSwitch(){
    try {
      try { if (window.stopAutoSaveLoop) window.stopAutoSaveLoop(); } catch(_e){}
      try { if (window.SessionManager && SessionManager.saveToSession) { await SessionManager.saveToSession(); } } catch(_e){}

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

      // Stop scribe via refactor endpoint; CSRF header added by global fetch patch
      try { await fetch('/api/scribe/stop', { method: 'POST' }); } catch(_e){}
    } catch (e) {
      console.warn('[Patient] server save/clear before switch warning:', e);
    }
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

    _emit('PATIENT_SWITCH_START', { from: current || null, to: target });
    _setUiSwitching(true);
    _hideTransientUi();
    abortAllInFlight();

    await _serverSaveAndClearBeforeSwitch();

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
    window.Patient = Patient;
  } catch(_e){}
})();