// Hey OMAR Workspace Module (rewritten)
// - IIFE pattern like other modules (e.g., Documents)
// - Per-container state, strict DOM scoping, no global selectors/IDs
// - Liveness guards + AbortController to prevent cross-tab propagation

(function(){
  window.WorkspaceModules = window.WorkspaceModules || {};
  const MODULE_KEY = 'Hey OMAR';

  // Utilities
  const escHtml = (s)=> String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c] || ''));
  const mdToHtml = (s)=> (window.marked && typeof window.marked.parse === 'function') ? window.marked.parse(String(s)) : escHtml(String(s)).replace(/\n/g,'<br>');
  const nowId = ()=> `hey-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`;

  function getState(container){ return (container && container.__heyState) || null; }
  function ensureState(container){
    if (!container.__heyState) container.__heyState = { isMounted:true, id: nowId(), controllers: [], escHandler:null, limitToVisible:false, lastMatches: [] };
    return container.__heyState;
  }
  function isLive(container){ try{ const st = getState(container); if(!st || !container.isConnected) return false; const inner = container.querySelector('.hey-omar-root'); return !!(inner && inner.getAttribute('data-hey-id') === st.id); }catch(_e){ return false; } }
  function addController(container, ctrl){ try{ const st = ensureState(container); st.controllers.push(ctrl); }catch(_e){} }
  function abortAll(container){ try{ const st = getState(container); (st && st.controllers || []).forEach(c=>{ try{ c.abort(); }catch(_e){} }); if(st) st.controllers = []; }catch(_e){} }

  // Markup
  function renderMarkup(container){
    const st = ensureState(container);
    container.innerHTML = `
      <style>
        .hey-omar-root { display:flex; flex-direction:column; height:100%; min-height:0; position:relative; }
        .hey-answer-box { flex:1 1 auto; min-height:0; overflow:auto; padding:0; border:none !important; background:transparent !important; margin:0; max-height:none !important; }
        .heyomar-controls { flex:0 0 auto; padding-top:8px; margin-top:auto; }
        .heyomar-controls .hey-ask-inline { display:flex; align-items:center; gap:8px; flex-wrap:nowrap; width:100%; overflow:hidden; }
        .hey-ask-input { flex:1 1 auto; min-width:160px; max-width:none; box-sizing:border-box; }
  /* Let global button styles apply; allow labels to wrap when needed */
  .heyomar-controls button { white-space: normal; padding:6px 10px; font-size:13px; }
        .hey-voice-status { margin-left:auto; flex:1 1 auto; min-width:120px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; opacity:0.8; text-align:right; }
        @media (max-width: 600px) { .heyomar-controls .hey-ask-inline { flex-wrap:wrap; } .hey-voice-status { flex:1 1 100%; margin-left:0; text-align:left; } }
        .hey-omar-root a.excerpt-citation { color:#1976d2 !important; text-decoration:underline; }
        /* Modal */
        .hey-omar-doc-modal { position:absolute; inset:0; z-index:9999; display:none; }
        .hey-omar-doc-modal .modal-backdrop { position:absolute; inset:0; background:rgba(0,0,0,0.35); }
        .hey-omar-doc-modal .modal-panel { position:absolute; top:6%; left:5%; right:5%; bottom:6%; background:#fff; border:1px solid var(--paper-border); border-radius:8px; display:flex; flex-direction:column; box-shadow:0 8px 24px rgba(0,0,0,0.25); overflow:hidden; }
        .hey-omar-doc-modal .modal-header { display:flex; align-items:center; gap:12px; padding:10px 12px; border-bottom:1px solid var(--paper-border); background:var(--paper-panel); }
        .hey-omar-doc-modal .modal-title { font-weight:600; color:var(--paper-contrast); flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .hey-omar-doc-modal .modal-close { border:1px solid var(--paper-border); background:#fff; border-radius:4px; padding:4px 8px; cursor:pointer; }
        .hey-omar-doc-modal .modal-body { flex:1; overflow:auto; padding:12px; background:#fff; color:var(--paper-contrast); }
        .hey-omar-doc-modal .doc-pre { white-space:pre-wrap; font-family:'Courier New', monospace; font-size:13px; line-height:1.5; }
        .hey-omar-doc-modal .hl-excerpt { background:#fff3cd; outline:2px solid #f1c40f55; border-radius:2px; padding:0 1px; }
      </style>
      <div class="hey-omar-root" data-hey-id="${st.id}" aria-label="Hey OMAR">
        <div class="hey-answer-box markdown-box" style="display:none;"></div>
        <div class="heyomar-controls">
          <span class="hey-ask-inline">
            <input class="hey-ask-input" type="text" placeholder="Type a question or hold 'Hey, Omar'">
            <button class="hey-ask-btn">Ask</button>
            <button class="hey-summary-btn" title="Generate a one-line clinical summary">Summary</button>
            <label style="display:inline-flex; align-items:center; gap:6px; margin-left:8px; white-space:nowrap; font-size:12px; opacity:0.9;">
              <input type="checkbox" class="hey-deep-toggle" /> Deep Answer
            </label>
            <span class="hey-voice-status voice-status" aria-live="polite"></span>
          </span>
        </div>
        <div class="hey-omar-doc-modal" aria-hidden="true">
          <div class="modal-backdrop"></div>
          <div class="modal-panel" role="dialog" aria-modal="true" aria-label="Document excerpt">
            <div class="modal-header">
              <div class="modal-title omar-modal-title">Document</div>
              <button class="modal-close omar-modal-close">Close</button>
            </div>
            <div class="modal-body"><div class="omar-modal-content doc-pre">Loading…</div></div>
          </div>
        </div>
      </div>
    `;
  }

  // Event wiring
  function bindHandlers(container){
    const st = ensureState(container);
    const q = (sel)=> container.querySelector(sel);
    const input = q('.hey-ask-input');
    const askBtn = q('.hey-ask-btn');
    const sumBtn = q('.hey-summary-btn');
    const limit = q('.hey-limit-visible-docs-toggle');
    const deepToggle = q('.hey-deep-toggle');
    const answerBox = q('.hey-answer-box');
    const modal = q('.hey-omar-doc-modal');

    if (limit){ limit.addEventListener('change', ()=>{ st.limitToVisible = !!limit.checked; }); st.limitToVisible = !!limit.checked; }
    if (deepToggle){ st.deepAnswer = !!deepToggle.checked; deepToggle.addEventListener('change', ()=>{ st.deepAnswer = !!deepToggle.checked; }); } else { st.deepAnswer = false; }
    // Start queries only on actual click/Enter
    if (askBtn){ askBtn.addEventListener('click', ()=> runAsk(container)); }
    if (input){ input.addEventListener('keyup', (e)=>{ if(e.key==='Enter') runAsk(container); }); }
    if (sumBtn){ sumBtn.addEventListener('click', ()=> runSummary(container)); }
    if (answerBox){ answerBox.addEventListener('click', (e)=> handleAnswerClick(container, e)); }

    // Modal close + ESC
    if (modal){
      const close = ()=> closeModal(container);
      modal.querySelector('.modal-backdrop')?.addEventListener('click', close);
      modal.querySelector('.omar-modal-close')?.addEventListener('click', close);
      st.escHandler = (ev)=>{ if(ev.key==='Escape') close(); };
      document.addEventListener('keydown', st.escHandler);
    }

  // Removed mic button placeholder
  }

  // Core actions
  async function runAsk(container, qOverride){
    const st = ensureState(container);
    if (!isLive(container)) return;
    const q = (sel)=> container.querySelector(sel);
    const input = q('.hey-ask-input');
    const btn = q('.hey-ask-btn');
    const status = q('.hey-voice-status');
    const box = q('.hey-answer-box');
    const deepToggle = q('.hey-deep-toggle');
    const text = (qOverride != null ? String(qOverride) : (input && input.value || '')).trim();
    if (!text) return;

    const ctrl = new AbortController(); addController(container, ctrl);

    try{
      // Notify global listeners that a Hey OMAR query has started
      try { window.dispatchEvent(new CustomEvent('heyomar:query-start', { detail: { container, type: 'ask', ts: Date.now() } })); } catch(_e){}
      if (btn) { btn.disabled = true; btn.textContent = 'Asking…'; }
      if (status) status.textContent = 'Asking over notes…';
      if (box) { box.style.display=''; box.innerHTML=''; box.setAttribute('aria-busy','true'); }

      // Render immediate structured data for: "show me ..." (intent) and dot-phrases, but do NOT short-circuit the QA request.
      let hadImmediate = false;
      let immediateRepls = [];
      const intentTokens = interpretShowMeToDotTokens(text);
      if (Array.isArray(intentTokens) && intentTokens.length && window.DotPhrases && DotPhrases.expand){
        try{
          const joined = intentTokens.join('\n');
          const { replacements } = await DotPhrases.expand(joined);
          if (!isLive(container)) return;
          if (Array.isArray(replacements) && replacements.length){
            hadImmediate = true;
            immediateRepls = replacements;
            if (box){
              const html = renderDotExpansions(replacements);
              box.innerHTML = html;
              // Notify listeners (e.g., quick button) that immediate structured data is available
              try { window.dispatchEvent(new CustomEvent('heyomar:immediate-structured', { detail: { container, html, ts: Date.now() } })); } catch(_e){}
            }
            // Keep status as "Asking…" and aria-busy until QA returns
          }
        }catch(_e){}
      }

      const { replaced, dotReplacements } = await replaceFhirPlaceholdersInQueryDetailed(text, ctrl.signal);
      if (!isLive(container)) return; // guard
      if (box && Array.isArray(dotReplacements) && dotReplacements.length){
        const html = renderDotExpansions(dotReplacements);
        // Append if we already showed intent-based expansions; otherwise set
        if (hadImmediate || (box.innerHTML && box.innerHTML.trim().length)) box.innerHTML += html; else box.innerHTML = html;
        hadImmediate = true;
        // Notify listeners for popup display if needed
        try { window.dispatchEvent(new CustomEvent('heyomar:immediate-structured', { detail: { container, html, ts: Date.now() } })); } catch(_e){}
        // Do not mark Ready; we are still awaiting QA
      }

      const demoMode = (window.demoMasking && window.demoMasking.enabled) || false;
      let doc_ids = undefined;
      if (st.limitToVisible && typeof window.getVisibleIndexedDocIds === 'function'){
        try{ doc_ids = window.getVisibleIndexedDocIds(100) || []; }catch(_e){ doc_ids=[]; }
        if ((!doc_ids || !doc_ids.length) && status){ status.textContent = 'No visible indexed notes; using all notes.'; doc_ids = undefined; }
      }
  // Allow Summary to raise recall via overrideTopK
  const overrideTopK = (()=>{ try{ const st=ensureState(container); return st && st.overrideTopK ? st.overrideTopK : null; }catch(_e){ return null; } })();
  const baseBody = { query: replaced, top_k: (overrideTopK || 8) };
      if (doc_ids && doc_ids.length) baseBody.doc_ids = doc_ids;
    // deep_answer deprecated; do not send

      // CLIENT-ASSISTED structured sections
      // If Summary precomputed bundle exists, prefer it; else try planner-only expansion
      let structuredSections = '';
      let clientStructuredRepls = null;
      // Start with any immediate replacements (intent or dot-phrases) so the model gets them too
      try{
        const seed = [];
        if (Array.isArray(immediateRepls) && immediateRepls.length) seed.push(...immediateRepls);
        if (Array.isArray(dotReplacements) && dotReplacements.length) seed.push(...dotReplacements);
        if (seed.length){
          // de-duplicate by raw token text
          const seen = new Set();
          const uniq = seed.filter(r=>{ const key = (r && r.raw) ? String(r.raw) : JSON.stringify(r); if(seen.has(key)) return false; seen.add(key); return true; });
          clientStructuredRepls = uniq;
          const parts = uniq.map(({raw,value})=>{
            const title = `Requested: ${raw}`;
            const underline = '='.repeat(title.length);
            const body = (value && typeof value==='object' && value.markdown) ? String(value.markdown||'') : String(value||'');
            return `${title}\n${underline}\n${body}`;
          });
          structuredSections = parts.join('\n\n');
          if (structuredSections.length > 16000) structuredSections = structuredSections.slice(0,16000) + '\n... (truncated)';
        }
      }catch(_e){}
      if (st && st.summaryBundle){
        structuredSections = String(st.summaryBundle||'');
        clientStructuredRepls = Array.isArray(st.preExpandedReplacements) ? st.preExpandedReplacements : null;
      } else {
        try{
          // Legacy planner call removed; rely on local DotPhrases expansion for now.
          // If a server-side planner is added, integrate here.
        }catch(_e){}
      }

  const body = { ...baseBody };
      if (structuredSections) body.structured_sections = structuredSections;
  // deep_answer deprecated; do not send

      // Ask via unified /api/query/ask endpoint (prefer Api.ask helper when available)
      const Api = window.Api || {};
      const data = await (Api.ask ? Api.ask(replaced, body) : (async ()=>{
        const res = await fetch('/api/query/ask', { method:'POST', headers:{ 'Content-Type':'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').getAttribute('content') || '' }, body: JSON.stringify({ query: replaced, ...body }), signal: ctrl.signal });
        const j = await res.json().catch(()=>({}));
        if (!res.ok || j.error) throw new Error(j.error || `HTTP ${res.status}`);
        return j;
      })());

      if (!isLive(container)) return; // guard after await
  renderAnswer(container, data, { append: !!(hadImmediate || (dotReplacements && dotReplacements.length)) });
  // Notify that an answer is ready (success path)
  try { window.dispatchEvent(new CustomEvent('heyomar:answer-ready', { detail: { container, ts: Date.now() } })); } catch(_e){}
      // Bring the Hey OMAR tab to the foreground when the final answer is ready
      try{
        const tabEl = container.closest('.tab-content')?.dataset?.tabId
          ? document.querySelector(`[data-tab-id="${container.closest('.tab-content').dataset.tabId}"]`)
          : container.closest('.workspace-pane')?.querySelector(`[data-tab-id]`);
        // Prefer using the tab header if available
        const header = tabEl || (function(){
          const pane = container.closest('.workspace-pane');
          if(!pane) return null;
          const id = pane.querySelector('.tab-content.active')?.getAttribute('data-tab-id') || container.closest('.tab-content')?.getAttribute('data-tab-id');
          return id ? document.querySelector(`.tab-bar [data-tab-id="${id}"]`) : null;
        })();
        if (header && typeof header.click === 'function') header.click();
      }catch(_e){}
      // Render structured data like normal dot-phrase expansions
      if (box){
        if (Array.isArray(clientStructuredRepls) && clientStructuredRepls.length){
          box.innerHTML += renderDotExpansions(clientStructuredRepls);
        } else if (data.structured_sections){
          const md = String(data.structured_sections||'');
          const html = mdToHtml(md);
          box.innerHTML += `<details open class="hey-structured-sections" style="margin-top:12px;">
  <summary style="font-weight:600; cursor:pointer;">Structured data (requested)</summary>
  <div style="margin:8px 0 0; border:1px solid var(--paper-border); padding:8px; background:#fafafa;">${html}</div>
</details>`;
        }
      }
      if (status) status.textContent = 'Ready';
    } catch(err){
      if (!isLive(container)) return;
      if (err && err.name === 'AbortError') return;
      if (box){
        box.style.display='';
        const msg = escHtml(err.message || 'Ask failed');
        if (box.innerHTML && /Expanded data/.test(box.innerHTML)) box.innerHTML += `<div class="module-error" style="margin-top:8px;">${msg}</div>`; else box.innerHTML = `<div class="module-error">${msg}</div>`;
      }
      if (status) status.textContent = 'Error';
    } finally {
      if (isLive(container) && btn){ btn.disabled=false; btn.textContent='Ask'; }
      if (isLive(container) && box){ box.removeAttribute('aria-busy'); }
      // Cleanup any Summary overrides for subsequent asks
      try{ const st=ensureState(container); if(st){ delete st.overrideTopK; delete st.summaryBundle; delete st.preExpandedReplacements; } }catch(_e){}
      // Notify global listeners that the query has finished
      try { window.dispatchEvent(new CustomEvent('heyomar:query-finish', { detail: { container, type: 'ask', ts: Date.now() } })); } catch(_e){}
    }
  }

  async function runSummary(container){
    if (!isLive(container)) return;
    const q = (sel)=> container.querySelector(sel);
    const btn = q('.hey-summary-btn');
    const status = q('.hey-voice-status');
    const ctrl = new AbortController(); addController(container, ctrl);
    try{
      try { window.dispatchEvent(new CustomEvent('heyomar:query-start', { detail: { container, type: 'summary', ts: Date.now() } })); } catch(_e){}
      if (btn) { btn.disabled = true; btn.textContent = 'Summarizing…'; }
      if (status) status.textContent = 'Loading summary prompt…';
      const r = await fetch('/load_health_summary_prompt', { cache:'no-store', signal: ctrl.signal });
      if (!r.ok) throw new Error('Prompt not found');
      const promptText = await r.text();
      // Hint at deeper retrieval by enabling deep answer and more documents
      const st = ensureState(container);
      st.deepAnswer = true;
      st.overrideTopK = 16; // Increase recall for Summary
      // Pre-expand a structured bundle for 6 months to feed the model
      try{
        if (window.DotPhrases && DotPhrases.expand){
          const sixMo = 180;
          const tokens = [
            '.meds/active',
            '.allergies',
            `.vitals/${sixMo}`,
            `.labs/a1c,egfr,uacr,cholesterol,ldl,hdl,triglycerides:days=${sixMo}`,
            `.orders:status=current,type=all,days=${sixMo}`
          ];
          const joined = tokens.join('\n');
          const { replacements } = await DotPhrases.expand(joined);
          if (Array.isArray(replacements) && replacements.length){
            const parts = replacements.map(({raw,value})=>{
              const title = `Requested: ${raw}`;
              const underline = '='.repeat(title.length);
              const body = (value && typeof value==='object' && value.markdown) ? String(value.markdown||'') : String(value||'');
              return `${title}\n${underline}\n${body}`;
            });
            let bundle = parts.join('\n\n');
            if (bundle.length > 20000) bundle = bundle.slice(0,20000) + '\n... (truncated)';
            st.summaryBundle = bundle;
            st.preExpandedReplacements = replacements;
          }
        }
      }catch(_e){}
  await runAsk(container, promptText);
  try { window.dispatchEvent(new CustomEvent('heyomar:answer-ready', { detail: { container, type: 'summary', ts: Date.now() } })); } catch(_e){}
      // Bring Hey OMAR to front for summary as well
      try{
        const tab = document.querySelector('.tab-bar [data-module-name="Hey OMAR"], .tab-bar [data-tab-name="Hey OMAR"]');
        if (tab && typeof tab.click === 'function') tab.click();
      }catch(_e){}
    } catch(e){
      if (!isLive(container)) return;
      if (status) status.textContent = 'Error: could not load summary prompt';
    } finally {
      if (isLive(container) && btn){ btn.disabled=false; btn.textContent='Summary'; }
      try { window.dispatchEvent(new CustomEvent('heyomar:query-finish', { detail: { container, type: 'summary', ts: Date.now() } })); } catch(_e){}
    }
  }

  function renderAnswer(container, payload, opts={}){
    if (!isLive(container)) return;
    const st = ensureState(container);
    const append = !!opts.append;
    const box = container.querySelector('.hey-answer-box'); if(!box) return;
    // Normalize: prefer matches; otherwise map citations -> matches-like
    let norm = Array.isArray(payload.matches) ? payload.matches : [];
    if ((!norm || !norm.length) && Array.isArray(payload.citations)){
      norm = payload.citations.map((c, i) => ({
        doc_id: c.doc_id || c.id || c.uid || '',
        docId: c.doc_id || c.id || c.uid || '',
        note_id: c.doc_id || c.id || c.uid || '',
        date: c.date || '',
        section: c.title || c.section || '',
        text: c.preview || c.text || '',
        page: (typeof c.excerpt === 'number') ? c.excerpt : (i + 1)
      }));
    }
    st.lastMatches = Array.isArray(norm) ? norm : [];

    const matches = st.lastMatches;
    const ansHtmlRaw = mdToHtml(payload.answer || '');

    // Build page map
    const pageMap = new Map();
    if (Array.isArray(matches)){
      for (let i=0;i<matches.length;i++){
        const m = matches[i]||{};
        const docId = String(m.note_id || m.doc_id || m.docId || '');
        const page = (typeof m.page === 'number' && m.page>0) ? m.page : (i+1);
        if (docId){ pageMap.set(String(page), { docId, text: m.text||'', date: m.date||'', section: m.section||'' }); }
      }
    }

    let answerHtml = ansHtmlRaw;
    if (pageMap.size){
      const buildAnchor = (n)=>{
        const meta = pageMap.get(String(n)); if(!meta) return null;
        const title = escHtml([meta.date, meta.section].filter(Boolean).join(' — '));
        return `<a href="#" class="excerpt-citation" data-doc-id="${escHtml(meta.docId)}" data-excerpt="${escHtml(n)}" title="${title}">${escHtml(n)}</a>`;
      };
      // (Excerpts 1,2-4)
      answerHtml = answerHtml.replace(/\((Excerpts?)\s+([0-9,\s\-]+)\)/gi, (full, label, nums) => {
        const out=[]; String(nums).split(',').forEach(tok=>{ const t=String(tok).trim(); if(!t) return; const m=t.match(/^(\d+)\s*\-\s*(\d+)$/); if(m){ let a=parseInt(m[1],10), b=parseInt(m[2],10); if(Number.isFinite(a)&&Number.isFinite(b)){ if(a<=b){ for(let n=a;n<=b;n++) out.push(n);} else { for(let n=a;n>=b;n--) out.push(n);} } } else { const n=parseInt(t,10); if(Number.isFinite(n)) out.push(n); } });
        if(!out.length) return full; const linked = out.map(n=> buildAnchor(n) || String(n)).join(', '); return `(${label} ${linked})`;
      });
      // Parenthetical with Excerpt tokens
      answerHtml = answerHtml.replace(/\(([^()]*\bExcerpt[s]?\b[^()]*)\)/g, (full, inner)=>{
        if (/class=\"excerpt-citation\"/.test(inner)) return full;
        inner = inner.replace(/\bExcerpt\s+(\d+)\s*\-\s*(\d+)\b/g, (m,a,b)=>{ const start=parseInt(a,10), end=parseInt(b,10); if(!Number.isFinite(start)||!Number.isFinite(end)) return m; const seq=[]; if(start<=end){ for(let n=start;n<=end;n++) seq.push(n);} else { for(let n=start;n>=end;n--) seq.push(n);} const links = seq.map(n=>buildAnchor(n)||String(n)).join(', '); return `Excerpts ${links}`; });
        inner = inner.replace(/\bExcerpt\s+(\d+)\b/g, (m,n)=>{ const a=buildAnchor(n); return a ? `Excerpt ${a}` : m; });
        return `(${inner})`;
      });
      // Specific forms with Date
      answerHtml = answerHtml
        .replace(/\(\s*Excerpt\s+(\d+)\s*,\s*Date:\s*([0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)\s*\)/gi, (full,n,d)=>{ const a=buildAnchor(n); return a?`(Excerpt ${a}, Date: ${escHtml(d)})`:full; })
        .replace(/\(\s*Excerpt\s+(\d+)\s*,\s*([0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)\s*\)/gi, (full,n,d)=>{ const a=buildAnchor(n); return a?`(Excerpt ${a}, ${escHtml(d)})`:full; })
        .replace(/\(\s*Excerpt\s+(\d+)\s*,\s*([0-9]{4})\s*\)/gi, (full,n,y)=>{ const a=buildAnchor(n); return a?`(Excerpt ${a}, ${escHtml(y)})`:full; });
    }

    // Sources list
    let citesHtml = '';
    if (matches.length){
      const seen = new Set(); const items = [];
      for (let i=0;i<matches.length;i++){
        const m = matches[i]||{}; const nid = String(m.note_id || m.doc_id || m.docId || ''); if(!nid) continue;
        const page = (typeof m.page === 'number' && m.page>0) ? m.page : (i+1); const key = nid+'::'+page; if(seen.has(key)) continue; seen.add(key);
        const date = escHtml(m.date || ''); const section = escHtml(m.section || ''); const label = [date, section].filter(Boolean).join(' — ');
        items.push(`<a href="#" class="excerpt-citation" data-doc-id="${escHtml(nid)}" data-excerpt="${page}">[${page}]${label? ' '+label:''}</a>`);
      }
      if (items.length) citesHtml = `<div class="notes-citations">${items.slice(0,10).join(' ')}</div>`;
    }

    const finalHtml = `<div class="notes-answer" style="${append ? 'margin-top:10px;' : ''}">${answerHtml}</div>${citesHtml}`;
    box.style.display='';
    if (append && box.innerHTML) box.innerHTML += finalHtml; else box.innerHTML = finalHtml;
  }

  function handleAnswerClick(container, e){
    if (!isLive(container)) return;
    const st = ensureState(container);
    const a = e.target.closest('a.excerpt-citation'); if(!a) return; e.preventDefault();
    const matches = st.lastMatches || [];
    let docId = a.getAttribute('data-doc-id') || '';
    const pageAttr = a.getAttribute('data-excerpt');
    const hasIndex = a.hasAttribute('data-excerpt-index');
    let excerptText = '';
    if (pageAttr){
      const pageStr = String(pageAttr); let found = null;
      for (const m of matches){ const nid = String(m.note_id || m.doc_id || m.docId || ''); const p = (typeof m.page === 'number') ? String(m.page) : ''; if((docId && nid===docId && p===pageStr) || (!docId && p===pageStr)) { found=m; break; } }
      if (!found && docId){ found = matches.find(m => String(m.note_id || m.doc_id || m.docId || '') === docId); }
      if (found){ excerptText = found.text || ''; if (!docId) docId = String(found.note_id || found.doc_id || found.docId || ''); }
    } else if (hasIndex){
      const idx = Number(a.getAttribute('data-excerpt-index') || '0'); const m = matches[idx] || {}; if(!docId) docId = m.doc_id || m.docId || m.note_id || ''; excerptText = m.text || '';
    }
    if (!docId) return;
    openExcerptModal(container, { docId, excerptText });
  }

  function openExcerptModal(container, { docId, excerptText }){
    if (!isLive(container)) return;
    const modal = container.querySelector('.hey-omar-doc-modal'); if(!modal) return;
    modal.style.display = 'block';
    const titleEl = modal.querySelector('.omar-modal-title'); const contentEl = modal.querySelector('.omar-modal-content');
    if (titleEl) titleEl.textContent = `Note ${docId}`;
    if (contentEl) contentEl.textContent = 'Loading…';
    try{ modal.querySelector('.omar-modal-close')?.focus(); }catch(_e){}

    const ctrl = new AbortController(); addController(container, ctrl);

    const doRender = (fullText)=>{ if(!isLive(container)) return; renderModalDocument(container, fullText, (excerptText||'').trim()); };
    const doFallback = async ()=>{
      try{
        // Try VPR single-item fetch by id
        const dfn = (window.Api && typeof window.Api.requireDFN==='function') ? window.Api.requireDFN() : null;
        if (!dfn) throw new Error('No DFN');
        const url = `/api/patient/${encodeURIComponent(dfn)}/vpr/document/item?id=${encodeURIComponent(docId)}`;
        const r = await fetch(url, { method:'GET', headers:{ 'Accept':'application/json' }, credentials:'same-origin', cache:'no-store', referrerPolicy:'no-referrer', signal: ctrl.signal });
        const j = await r.json().catch(()=>({}));
        const raw = (j && j.data) ? j.data : j;
        let text = '';
        try{
          const items = raw?.data?.items || raw?.items;
          const item = Array.isArray(items) && items.length ? items[0] : raw;
          const arr = Array.isArray(item?.text) ? item.text : (item?.text ? [item.text] : []);
          if (arr.length){
            const parts = [];
            for (const b of arr){
              if (b && typeof b==='object' && (b.content || b.text || b.summary)) parts.push(String(b.content||b.text||b.summary));
              else if (typeof b==='string') parts.push(b);
            }
            text = parts.join('\n');
          }
          if (!text){
            const rpt = item?.report || item?.impression; if (typeof rpt==='string') text = rpt;
          }
          if (!text){
            for (const k of ['body','content','documentText','noteText','clinicalText','details']){
              const v = item?.[k]; if (typeof v==='string' && v.trim()){ text = v; break; }
            }
          }
        }catch(_ee){}
        doRender(text || '');
      }catch(_e){ const ce = modal.querySelector('.omar-modal-content'); if(ce) ce.textContent='Failed to load document.'; }
    };

    (async ()=>{
      try{
        const Api = window.Api || {};
        if (Api.documentsTextBatch){
          const data = await Api.documentsTextBatch([String(docId)]).catch(()=>({}));
          const notes = Array.isArray(data.notes) ? data.notes : [];
          const hit = notes.find(n => String(n.doc_id) === String(docId));
          if (hit && hit.text){ const text = Array.isArray(hit.text) ? hit.text.join('\n') : String(hit.text || ''); return doRender(text); }
          return doFallback();
        } else {
          return doFallback();
        }
      }catch(_e){ return doFallback(); }
    })();
  }

  function renderModalDocument(container, fullText, excerpt){
    if (!isLive(container)) return;
    const modal = container.querySelector('.hey-omar-doc-modal'); if(!modal) return;
    const contentEl = modal.querySelector('.omar-modal-content'); if(!contentEl) return;
    const tryExact = ()=>{
      if (!excerpt) return null; const i = fullText.indexOf(excerpt); if (i>=0) return { start:i, len:excerpt.length };
      const ftL = fullText.toLowerCase(), exL = String(excerpt).toLowerCase(); const i2 = ftL.indexOf(exL); if(i2>=0) return { start:i2, len:exL.length }; return null;
    };
    const escapeRe = (s)=> String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const tryFuzzy = ()=>{
      if (!excerpt) return null; const toks = String(excerpt).split(/\s+/).filter(w=>w && w.length>=2).slice(0,12); if (!toks.length) return null;
      const gap = "[\n\r\t \f,.;:()\[\]{}\-–—\u2014\u2013\u00AD'\"]*";
      try{ const re = new RegExp(toks.map(t=>escapeRe(t)).join(gap), 'i'); const m = re.exec(fullText); if(m && typeof m.index==='number'){ return { start:m.index, len:m[0].length }; } }catch(_e){}
      return null;
    };
    const range = tryExact() || tryFuzzy();
    let html;
    if (range){ const { start, len } = range; const pre = escHtml(fullText.slice(0,start)); const mid = escHtml(fullText.slice(start,start+len)); const post = escHtml(fullText.slice(start+len)); html = `${pre}<span class="hl-excerpt">${mid}</span>${post}`; }
    else { html = `${escHtml(fullText)}\n\n<em style="color:#a67c00;">Excerpt not found; showing full note.</em>`; }
    contentEl.innerHTML = html; const mark = modal.querySelector('.hl-excerpt'); if (mark){ mark.scrollIntoView({ block:'center', behavior:'smooth' }); }
  }

  function closeModal(container){ const modal = container.querySelector('.hey-omar-doc-modal'); if(!modal) return; modal.style.display='none'; }

  // Startup explainer shown on first load of Hey OMAR tab
  function renderIntro(container){
    if (!isLive(container)) return;
    const box = container.querySelector('.hey-answer-box');
    if (!box) return;
    const md = [
      '## Hey OMAR — Quick start',
      '',
      '- Before asking questions, open the Documents tab and click “Index selected notes” for the current patient.',
      '- Then come back here and ask questions or use “show me …” to pull structured data instantly.',
      '',
      '### Examples (type and press Enter)',
      '- show me the last a1c',
      '- show me the last a1c and lipid panel',
      '- show me recent labs and vitals',
      '- show me current meds',
      '- show me recent orders',
      '- show me all a1c',
      '',
      '### More complex questions',
      '- Summarize the patient’s recent primary care visits.',
      '- Identify trends in A1c over the last 6 months.',
      '- When was metformin started and what changes were made after the last A1c?',
      '- What pending lab orders exist from the last 14 days?',
      '',
      'Tip: You can also use dot-phrases in text: `.labs/a1c:last`, `.labs/a1c:all`, `.vitals/14`, `.orders:status=current,type=labs,days=14`.'
    ].join('\n');
    try{ box.innerHTML = mdToHtml(md); }catch(_e){ box.textContent = md; }
    box.style.display = '';
  }

  // FHIR-like placeholders
  async function replaceFhirPlaceholdersInQueryDetailed(text, signal){
    try{
      const s = String(text ?? '');
      if (!(window.DotPhrases && DotPhrases.expand)) return { replaced: s, dotReplacements: [] };
      // Let shared util do token collection and replacement (skips {.token})
      const { replaced, replacements } = await DotPhrases.expand(s);
      return { replaced, dotReplacements: (Array.isArray(replacements)? replacements: []) };
    }catch(_e){ return { replaced: String(text ?? ''), dotReplacements: [] }; }
  }

  async function resolveFhirToken(tok, signal){
    // Deprecated: use DotPhrases.resolve
    try{ if (window.DotPhrases && DotPhrases.resolve) return await DotPhrases.resolve(tok); }catch(_e){}
    return null;
  }

  function fmtMeds(/* meds */){ return window.DotPhrases && DotPhrases._fmt && DotPhrases._fmt.fmtMeds ? DotPhrases._fmt.fmtMeds.apply(null, arguments) : 'No medications on file'; }
  function fmtProblems(/* problems, activeOnly */){ return window.DotPhrases && DotPhrases._fmt && DotPhrases._fmt.fmtProblems ? DotPhrases._fmt.fmtProblems.apply(null, arguments) : 'No problems on file'; }
  function fmtVitalsTable(/* vitals */){ return window.DotPhrases && DotPhrases._fmt && DotPhrases._fmt.fmtVitalsTable ? DotPhrases._fmt.fmtVitalsTable.apply(null, arguments) : 'No vitals found'; }
  function fmtLabsTable(/* labs */){ return window.DotPhrases && DotPhrases._fmt && DotPhrases._fmt.fmtLabsTable ? DotPhrases._fmt.fmtLabsTable.apply(null, arguments) : 'No labs found'; }
  function fmtOrders(/* orders */){ return window.DotPhrases && DotPhrases._fmt && DotPhrases._fmt.fmtOrders ? DotPhrases._fmt.fmtOrders.apply(null, arguments) : 'No orders found'; }
  function ordersTypeAlias(/* s */){ return window.DotPhrases && DotPhrases._util && DotPhrases._util.ordersTypeAlias ? DotPhrases._util.ordersTypeAlias.apply(null, arguments) : 'all'; }
  function ordersStatusAlias(/* s */){ return window.DotPhrases && DotPhrases._util && DotPhrases._util.ordersStatusAlias ? DotPhrases._util.ordersStatusAlias.apply(null, arguments) : 'current'; }
  function parseOrdersArgs(/* argStr */){ return window.DotPhrases && DotPhrases._util && DotPhrases._util.parseOrdersArgs ? DotPhrases._util.parseOrdersArgs.apply(null, arguments) : { status:'current', type:'all', days:7 }; }
  function parseNaturalDate(/* input, defaultEnd */){ return window.DotPhrases && DotPhrases._util && DotPhrases._util.parseNaturalDate ? DotPhrases._util.parseNaturalDate.apply(null, arguments) : null; }

  // Interpret natural language "show me ..." into one or more .tokens
  function interpretShowMeToDotTokens(input){
    try{
      const s = String(input||'').trim(); if(!s) return null;
      const m = s.match(/^\s*(?:hey\s*,?\s*)?(?:omar\s*,?\s*)?(?:show|display|list|give\s+me|tell\s+me|get\s+me|show\s+me)\s+(.+)$/i);
      if(!m) return null;
      const tail = m[1].trim(); if(!tail) return null;
      const low = tail.toLowerCase();

      // Common time expressions
      // Support numeric windows across days/weeks/months/years
      let days = null;
      (function(){
        const m1 = low.match(/(?:over\s+)?(?:the\s+)?(?:most\s+recent|latest|recent|last|past)\s+(\d+)\s*(day|days|week|weeks|month|months|year|years)\b/);
        if (m1){
          const n = parseInt(m1[1],10);
          const unit = m1[2];
          if (Number.isFinite(n) && n>0){
            if (unit.startsWith('day')) days = n;
            else if (unit.startsWith('week')) days = n*7;
            else if (unit.startsWith('month')) days = n*30;
            else if (unit.startsWith('year')) days = n*365;
          }
        } else {
          const m2 = low.match(/(?:over\s+)?(?:the\s+)?(?:most\s+recent|latest|recent|last|past)\s+(year|month|week|day)\b/);
          if (m2){ const u=m2[1]; days = (u==='year')?365:(u==='month')?30:(u==='week')?7:1; }
        }
      })();
      const sinceMatch = low.match(/\b(?:since|after)\s+([^,;]+?)\b(?:$|\s|,|;)/);
      const rangeMatch = low.match(/\b(?:from|between)\s+([^,;]+?)\s+(?:to|and|through|thru|-)\s+([^,;]+?)\b/);
      const start = rangeMatch ? (parseNaturalDate(rangeMatch[1], false) || null) : (sinceMatch ? (parseNaturalDate(sinceMatch[1], false)||null) : null);
      const end   = rangeMatch ? (parseNaturalDate(rangeMatch[2], true)  || null) : null;

      // Recency mention indicator (used for defaults)
      const recencyMention = /(most\s+recent|latest|recent|last)\b/.test(low);
      const defaultRecentDaysVitals = 14;

      // Helper to extract filters (names/loincs) from remaining text for labs
      function extractFilters(txt){
        const original = String(txt||'');
        let t = ' ' + original.toLowerCase() + ' ';
        // Remove common non-filter words
        t = t.replace(/\b(labs?|lab\s+results?|vitals?|meds?|medications?|problems?|orders?|panel|test|tests)\b/g,' ')
             .replace(/\b(his|her|their|the|a|an|this|that|these|those)\b/g,' ')
             .replace(/\b(last|latest|most\s+recent|all|range|since|after|from|between|to|and|through|thru|past|days?|weeks?|months?|years?)\b/g,' ')
             .replace(/[^a-z0-9\-+,\s]/g,' ');
        // Preserve common multi-word lab phrases if present in original
        const phrases = [];
        const multi = ['lipid panel','basic metabolic panel','comprehensive metabolic panel','cbc','complete blood count','hemoglobin a1c'];
        multi.forEach(p => { if (original.toLowerCase().includes(p)) phrases.push(p); });
        // LOINCs
        const loincs = Array.from((original.match(/loinc\s*([0-9\-]+)/ig)||[])).map(x=>String(x).toLowerCase().replace(/[^0-9\-]/g,''));
        const raw = t.split(/[,+]/).map(x=>x.trim()).filter(Boolean);
        const words = raw.flatMap(x=> x.split(/\s+and\s+|\s+/)).map(x=>x.trim()).filter(Boolean);
        const uniq = Array.from(new Set(words.concat(phrases).concat(loincs)));
        return uniq;
      }

      // Detect lab intent even if the word "labs" is not present (e.g., "last a1c")
      const labTerms = ['a1c','hemoglobin a1c','ldl','hdl','cholesterol','triglycerides','egfr','uacr','microalbumin','scr','creatinine','bun','potassium','sodium','hemoglobin','platelet','wbc','cbc','lipid panel'];
      const hasLabWord = /\blabs?\b|\blab\s+results?\b/.test(low) || labTerms.some(t=> low.includes(t));

      const tokens = [];

      // Demographics shortcuts
      if (/\bname\b/.test(low)) tokens.push('.name');
      if (/\bage\b/.test(low)) tokens.push('.age');
      if (/(\bdob\b|date\s+of\s+birth)/.test(low)) tokens.push('.dob');
      if (/(\bphone\b|phone\s+number|mobile|cell)/.test(low)) tokens.push('.phone');

      // Problems
      if (/\bproblems?\b/.test(low) || /\bproblem\s*list\b/.test(low) || /\bpast\s+medical\s+history\b/.test(low)){
        const act = (/\bactive\b|\bcurrent\b/).test(low);
        tokens.push(act ? '.problems/active' : '.problems');
      }
      // Allergies
      if (/\ballerg(?:y|ies|ens?)\b/.test(low) || /\badverse\s+reactions?\b/.test(low)){
        tokens.push('.allergies');
      }
      // Meds
      if (/\b(meds?|medications?|rx|prescriptions?)\b/.test(low)){
        // Active/current intent if explicitly asked or implied by recency words without a specific window
        const actIntent = (/\bactive\b|\bcurrent\b/).test(low) || (recencyMention && !(days && days>0));

        // Try to detect a specific medication mention after common prepositions
        const medStop = /^(med|meds|medication|medications|medicine|medicines|rx|prescription|prescriptions|and|labs?|vitals?|orders?|problems?|allerg(?:y|ies)|last|recent|current|active|his|her|their|the|this|that|these|those)$/i;
        let drug = null;
        const dm = tail.match(/\b(?:of|for|on)\s+([a-z][a-z0-9\-]{3,})\b/i);
        if (dm){
          const cand = (dm[1]||'').toLowerCase();
          if (!medStop.test(cand)) drug = cand;
        }

        // Build the base token considering time bounds if provided
        let baseToken = actIntent ? '.meds/active' : '.meds';
        if (!drug){
          if (days && days>0){
            baseToken = `.meds/${days}`;
          } else if (start && !end){
            baseToken = `.meds/since=${start}`;
          } else if (start || end){
            const segs = [];
            if (start) segs.push(`start=${start}`);
            if (end) segs.push(`end=${end}`);
            if (segs.length) baseToken = `.meds/${segs.join('/')}`;
          }
        }

        if (drug){
          tokens.push(`${actIntent?'.meds/active':'.meds'}/${drug}`);
        } else {
          tokens.push(baseToken);
        }
      }
      // Med started when user asks when a med was started
      if (/\bwhen\b.*\b(started|begin|initiated)\b/.test(low)){
        const m = low.match(/\b(?:med|medication|rx|drug|of)?\s*([a-z][a-z0-9\-]{3,})\b/i);
        if (m){ tokens.push(`.medstarted/${m[1]}`); }
      }
      // Vitals
      if (/\bvitals?\b/.test(low)){
        if (days && days>0){ tokens.push(`.vitals/${days}`); }
        else if (start || end){
          const segs = [];
          if (start) segs.push(`start=${start}`);
          if (end) segs.push(`end=${end}`);
          tokens.push(`.vitals/${segs.join('/')}`);
        } else if (recencyMention){
          tokens.push(`.vitals/${defaultRecentDaysVitals}`);
        } else { tokens.push('.vitals'); }
      }
      // Labs (including when only tests are mentioned)
      if (hasLabWord){
        const filters = extractFilters(tail);
        const parts = ['.labs'];
        if (filters.length) parts.push('/'+filters.join(','));
        const mods = [];
        if (/(\ball\b|\bevery\b)/.test(low)) mods.push('all'); // NEW: request full history
        if ((/\b(last|latest|most\s+recent)\b/.test(low)) && !(days && days>0)) mods.push('last');
        if (days && days>0) mods.push(`days=${days}`);
        if (start && end) mods.push(`range=${start}..${end}`);
        else if (start && !end) mods.push(`since=${start}`);
        if (mods.length) parts.push(':'+mods.join(','));
        tokens.push(parts.join(''));
      }
      // Orders
      if (/\borders?\b/.test(low)){
        let status = (/\bactive\b/.test(low) ? 'active' : (/\bpending\b/.test(low) ? 'pending' : (/\ball\b/.test(low) ? 'all' : 'current')));
        let type   = (/\blabs?\b/.test(low) ? 'labs' : ((/\bmeds?|medications\b/.test(low)) ? 'meds' : 'all'));
        const args = [];
        if (status) args.push(`status=${status}`);
        if (type) args.push(`type=${type}`);
        if (days && days>0) args.push(`days=${days}`); else if (start) args.push(`since=${start}`);
        tokens.push(`.orders:${args.join(',')}`);
      }

      return tokens.length ? tokens : null;
    }catch(_e){ return null; }
  }

  function renderDotExpansions(dotReplacements){ if(!Array.isArray(dotReplacements) || dotReplacements.length===0) return ''; const defaultsNote = `<div style="font-size:12px; opacity:0.8; margin:4px 0 8px;">Defaults: .vitals with no dates returns all available vitals; .labs with filters and no dates returns full history for the requested test(s); use :last to return the most recent only (e.g., .labs/a1c:last); .labs with no filters and no dates returns the last 14 days; .orders with no args returns current (active+pending) orders for all types over the last 7 days.</div>`; const parts = dotReplacements.map(({raw,value})=>{ const title=escHtml(raw); if(value && typeof value==='object' && value.markdown){ const bodyHtml = mdToHtml(String(value.markdown||'')); return `<details open><summary>${title}</summary><div style="margin:6px 0 12px;">${bodyHtml}</div></details>`; } const body=escHtml(String(value||'')); return `<details open><summary>${title}</summary><pre style="white-space:pre-wrap; margin:6px 0 12px;">${body}</pre></details>`; }); return `<div class="notes-answer"><strong>Expanded data</strong></div>${defaultsNote}${parts.join('')}`; }

  // Module API
  window.WorkspaceModules[MODULE_KEY] = {
    _container: null,

    async render(container /*, options */){
      this._container = container;
      const st = ensureState(container); st.isMounted = true; st.id = st.id || nowId();
      renderMarkup(container);
      bindHandlers(container);
      // Show intro on startup
      renderIntro(container);
    },

    refresh(){
      if (!this._container) return;
      if (!isLive(this._container)) return; // nothing to do; UI is simple
    },

    // Expose minimal run helpers for quick-access integrations
    async runAsk(container, qOverride){
      try { return await runAsk(container, qOverride); } catch(_e){ return false; }
    },
    async runSummary(container){
      try { return await runSummary(container); } catch(_e){ return false; }
    },

    destroy(){
      const container = this._container;
      try{ if(!container) return true; const st=getState(container); if(st){ st.isMounted=false; } abortAll(container); if(st && st.escHandler){ document.removeEventListener('keydown', st.escHandler); st.escHandler=null; } container.innerHTML=''; delete container.__heyState; }catch(_e){}
      return true;
    }
  };
})();
