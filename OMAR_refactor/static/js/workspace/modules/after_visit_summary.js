// filepath: static/workspace/modules/after_visit_summary.js
// After Visit Summary module for Workspace
// Reuses Scribe Patient Instructions flow: live Markdown preview, generate, and print

window.WorkspaceModules = window.WorkspaceModules || {};

(function(){
  const MOD_KEY = 'After Visit Summary';

  // Lazy loader for marked to handle load-order or missing script issues
  async function ensureMarkedLoaded(){
    try{
      if(typeof window !== 'undefined' && window.marked){ return true; }
      if(window.__MARKED_LOAD_PROMISE__){ await window.__MARKED_LOAD_PROMISE__; return !!window.marked; }
      window.__MARKED_LOAD_PROMISE__ = (async ()=>{
        // 1) Try classic script (UMD)
        const loadClassic = ()=> new Promise((resolve)=>{
          try{
            const s = document.createElement('script');
            s.src = '/static/lib/marked.min.js';
            s.async = true;
            s.onload = ()=> resolve(!!window.marked);
            s.onerror = ()=> resolve(false);
            document.head.appendChild(s);
          }catch(_e){ resolve(false); }
        });
        if(await loadClassic()) return true;
        // 2) Try importing as ESM and attach to window
        const loadAsModule = ()=> new Promise((resolve)=>{
          try{
            const s = document.createElement('script');
            s.type = 'module';
            s.textContent = "import * as M from '/static/lib/marked.min.js'; window.marked = (M.marked||M.default||M);";
            s.onload = ()=> resolve(!!window.marked);
            s.onerror = ()=> resolve(false);
            document.head.appendChild(s);
          }catch(_e){ resolve(false); }
        });
        if(await loadAsModule()) return true;
        // 3) CDN UMD fallback (use unpkg to satisfy current CSP)
        const loadCdn = ()=> new Promise((resolve)=>{
          try{
            const s = document.createElement('script');
            s.src = 'https://unpkg.com/marked/marked.min.js';
            s.async = true;
            s.onload = ()=> resolve(!!window.marked);
            s.onerror = ()=> resolve(false);
            document.head.appendChild(s);
          }catch(_e){ resolve(false); }
        });
        const ok = await loadCdn();
        // Some builds expose a namespace; try to attach if needed
        try{
          if(!ok && typeof window !== 'undefined' && window.marked && typeof window.marked.parse !== 'function' && window.marked.marked && typeof window.marked.marked.parse === 'function'){
            window.marked = window.marked.marked;
            return true;
          }
        }catch(_e){}
        return ok;
      })();
      const ok = await window.__MARKED_LOAD_PROMISE__;
      if(!ok){ try{ console.warn('[AVS] marked failed to load; falling back to plain text preview'); }catch(_e){} }
      return !!ok && !!window.marked;
    }catch(_e){ return false; }
  }

  async function getTranscriptWorkspace(){
    // Prefer SessionManager caches
    try{ if (typeof SessionManager!=='undefined' && SessionManager.peekTranscriptFromSession){ const t = SessionManager.peekTranscriptFromSession(); if(t) return t; } }catch(_e){}
    try{ if (typeof SessionManager!=='undefined' && SessionManager.getTranscript){ const t = await SessionManager.getTranscript(10000); if(t) return t; } }catch(_e){}
    try{ const el = document.getElementById('rawTranscript'); if(el && el.value) return el.value; }catch(_e){}
    return '';
  }

  function renderUI(container){
    container.innerHTML = `
      <div class="avs-module" style="display:flex; flex-direction:column; height:100%;">
        <div class="module-header">
          <h3>After Visit Summary</h3>
          <div style="display:flex; gap:8px;">
            <button id="avsGenerateBtn" class="save-btn" title="Generate from transcript and chart">Generate</button>
            <button id="avsPrintBtn" class="refresh-btn" title="Print the summary">Print</button>
          </div>
        </div>
        <div style="display:flex; gap:12px; flex:1; min-height:0;">
          <textarea id="patientInstructionsBox" placeholder="Type or generate your After Visit Summary in Markdown..." style="flex:1; min-height:280px; height:auto; resize:vertical; border:1px solid var(--paper-border); border-radius:6px; padding:12px; font-family: ui-monospace, Menlo, 'Courier New', monospace;"></textarea>
          <div style="flex:1; min-height:0; display:flex; flex-direction:column;">
            <div style="font-weight:600; margin-bottom:6px; color:var(--paper-contrast);">Live Preview</div>
            <div id="patientInstructionsPreview" class="markdown-body" style="flex:1; overflow:auto; background:#fff; border:1px solid var(--paper-border); border-radius:6px; padding:12px;"></div>
          </div>
        </div>
      </div>
    `;
  }

  // Safe markdown renderer supporting both marked.parse and legacy function usage
  function renderMarkdownSafe(text){
    const md = String(text || '');
    try {
      const m = (typeof window !== 'undefined') ? window.marked : null;
      if (m) {
        if (typeof m.parse === 'function') return m.parse(md);
        if (m.marked && typeof m.marked.parse === 'function') return m.marked.parse(md);
        if (typeof m === 'function') return m(md);
        if (m.marked && typeof m.marked === 'function') return m.marked(md);
      }
    } catch(_e) {}
    // Fallback: simple line breaks so it's at least readable
    return md.replace(/\n/g, '<br>');
  }

  async function generateAVS(container){
    const box = container.querySelector('#patientInstructionsBox');
    const preview = container.querySelector('#patientInstructionsPreview');
    if(box) box.value = 'Loading patient instructions...';

    // Ensure markdown library is ready for later preview
    await ensureMarkedLoaded();

    const transcript = await getTranscriptWorkspace();

    // NEW: Get current draft note from workspace Note module
    let draftNote = '';
    try {
      const el = document.getElementById('feedbackReply');
      if (el && typeof el.innerText === 'string') draftNote = el.innerText;
    } catch(_e) {}

    // Load template
    let promptTemplate = '';
    try{ const res = await fetch('/load_patient_instructions_prompt'); if(res.ok) promptTemplate = await res.text(); } catch(_e){}

    const mdInstruction = 'Please format your output as Markdown (using -, *, **, etc.) for clear printing.\n\n';
    let prompt = mdInstruction + (promptTemplate||'').replace(/\{\{transcript\}\}/g, transcript).replace(/\{\{visit_notes\}\}/g, '');

    // Append the current draft note so the AVS can incorporate finalized language
    if (draftNote && draftNote.trim()) {
      prompt += `\n\n---\nCurrent Draft Note (for reference; reflect key plans and instructions):\n${draftNote.trim()}\n`;
    }

    // Expand .tokens conservatively (skip {.token})
    try { if (window.DotPhrases && DotPhrases.replace) { prompt = await DotPhrases.replace(prompt); } } catch(_e){}

    try{
      const r = await fetch('/scribe/create_note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': (window.getCsrfToken? window.getCsrfToken(): '') },
        body: JSON.stringify({ transcript, prompt_text: prompt, current_draft: draftNote || '' })
      });
      const data = await r.json();
      let resolved = String(data.note || '');
      try { if (window.DotPhrases && DotPhrases.replace) { resolved = await DotPhrases.replace(resolved); } } catch(_e){}
      if(box){ box.value = resolved; }
      if(preview){
        try{ preview.innerHTML = renderMarkdownSafe(resolved); } catch(_e){ preview.textContent = resolved; }
        // If markdown library loads slightly late, re-render once
        try { setTimeout(async () => { try { await ensureMarkedLoaded(); preview.innerHTML = renderMarkdownSafe(box ? box.value : resolved); } catch(_e2){} }, 300); } catch(_e3){}
      }
      try{ if (typeof SessionManager!=='undefined'){ SessionManager.autosaveStarted = true; await SessionManager.saveToSession(); } }catch(_e){}
    }catch(e){
      if(box) box.value = 'Error generating instructions: ' + (e && e.message ? e.message : 'Unknown error');
    }
  }

  async function printAVS(container){
    const box = container.querySelector('#patientInstructionsBox');
    await ensureMarkedLoaded();
    const html = renderMarkdownSafe(box ? box.value : '');
    const win = window.open('', '_blank');
    win.document.write(`
      <html>
      <head>
        <title>After Visit Summary</title>
        <style>
          body { font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; }
          h2 { color: #3498db; }
          .markdown-body { font-size: 1.1em; }
        </style>
      </head>
      <body>
        <h2>After Visit Summary</h2>
        <div class="markdown-body">${html}</div>
      </body>
      </html>
    `);
    win.document.close();
    win.focus();
    setTimeout(()=>{ try{ win.print(); }catch(_e){} }, 400);
  }

  window.WorkspaceModules[MOD_KEY] = {
    preserveOnRefresh: true,
    async render(container){
      renderUI(container);

      const box = container.querySelector('#patientInstructionsBox');
      const preview = container.querySelector('#patientInstructionsPreview');
      const genBtn = container.querySelector('#avsGenerateBtn');
      const printBtn = container.querySelector('#avsPrintBtn');

      // Live Markdown preview + autosave
      if(box && preview){
        const updatePreview = async ()=>{
          const txt = box.value || '';
          try{ await ensureMarkedLoaded(); preview.innerHTML = renderMarkdownSafe(txt); } catch(_e){ preview.textContent = txt; }
        };
        box.addEventListener('input', async ()=>{
          await updatePreview();
          try{ if (typeof SessionManager!=='undefined'){ SessionManager.autosaveStarted = true; await SessionManager.saveToSession(); } }catch(_e){}
        });
        // Initial restore from SessionManager if present
        try{
          if (typeof SessionManager!=='undefined' && SessionManager.lastLoadedData && SessionManager.lastLoadedData.scribe && typeof SessionManager.lastLoadedData.scribe.patientInstructions === 'string'){
            if (!box.value) { box.value = SessionManager.lastLoadedData.scribe.patientInstructions; }
          }
        }catch(_e){}
        // Ensure preview renders at least once on initial display
        try{ await updatePreview(); }catch(_e){}
        // Also re-render once shortly after in case marked loads late
        try{ setTimeout(()=>{ try{ updatePreview(); }catch(_e2){} }, 300); }catch(_e3){}
      }

      // Wire buttons
      if(genBtn){ genBtn.addEventListener('click', ()=> generateAVS(container)); }
      if(printBtn){ printBtn.addEventListener('click', ()=> printAVS(container)); }

      // Disable generate if no patient selected (enable on load)
      try{
        const d = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
        if(genBtn) genBtn.disabled = !d;
        window.addEventListener('workspace:patientSwitched', ()=>{ try{ if(genBtn) genBtn.disabled = true; }catch(_e){} });
        window.addEventListener('patient:loaded', ()=>{ try{ const d2=(window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString(); if(genBtn) genBtn.disabled = !d2; }catch(_e){} });
      }catch(_e){}
    },
    async refresh(){ /* preserve content; nothing heavy */ }
  };
})();
