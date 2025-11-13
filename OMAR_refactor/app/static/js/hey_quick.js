(function(){
  // Lightweight popup for Hey OMAR quick ask
  function buildPopup(){
    const wrap = document.createElement('div');
    wrap.className = 'hey-quick-popup';
    Object.assign(wrap.style, {
      width: 'min(520px, 92vw)',
      maxWidth: '520px',
      color: '#111',
    });
    const form = document.createElement('form');
    form.setAttribute('autocomplete', 'off');
    form.style.margin = '0';

    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.alignItems = 'center';
    row.style.gap = '8px';

    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = "Ask Hey OMAR";
    input.style.flex = '1 1 auto';
    input.style.padding = '10px 12px';
    input.style.border = '1px solid #d1d5db';
    input.style.borderRadius = '6px';
    input.style.fontSize = '16px';

    const askBtn = document.createElement('button');
    askBtn.type = 'submit';
    askBtn.textContent = 'Ask';
    askBtn.className = 'refresh-btn';
    askBtn.style.fontSize = '14px';

    const sumBtn = document.createElement('button');
    sumBtn.type = 'button';
    sumBtn.textContent = 'Summary';
    sumBtn.className = 'refresh-btn';
    sumBtn.style.fontSize = '14px';

    row.appendChild(input); row.appendChild(askBtn); row.appendChild(sumBtn);
    form.appendChild(row);

    // Removed tip per request

    wrap.appendChild(form);

    return { wrap, form, input, askBtn, sumBtn };
  }

  // Helper: detect if a patient is selected
  function hasPatient(){
    try {
      const d = (window.CURRENT_PATIENT_DFN || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString().trim();
      return !!d;
    } catch(_e){ return false; }
  }

  function findHeyTab(){
    const leftBar = document.getElementById('leftTabBar');
    const rightBar = document.getElementById('rightTabBar');
    const byName = (bar)=> bar ? Array.from(bar.children||[]).find(t => ((t.dataset.moduleName||t.dataset.tabName||'')==='Hey OMAR')) : null;
    return byName(leftBar) || byName(rightBar) || null;
  }

  function openHeyTab(){
    const tab = findHeyTab();
    if (tab) {
      try { tab.click(); } catch(_e) {}
    }
  }

  function getHeyContainer(){
    const tab = findHeyTab(); if(!tab) return null;
    const pane = tab.closest('.workspace-pane');
    const contentArea = pane && pane.querySelector('.tab-content-area');
    const content = contentArea && contentArea.querySelector(`[data-tab-id="${tab.dataset.tabId}"]`);
    return content || null;
  }

  async function ensureHeyModule(){
    if (!window.loadModule) return false;
    try { await window.loadModule('Hey OMAR'); return true; } catch(_e){ return false; }
  }

  async function runHeyAsk(text, { summary } = {}){
    // Load module script if needed
    const ok = await ensureHeyModule();
    if (!ok) return false;
    const tab = findHeyTab(); if(!tab) return false;
    const container = getHeyContainer(); if (!container) return false;
    const module = window.WorkspaceModules && window.WorkspaceModules['Hey OMAR'];
    if (!module) return false;

    // Render module in background if not already rendered
    try{
      if (container && !container.dataset.moduleLoaded) {
        const body = container.querySelector('.tab-content-body') || container;
        body.innerHTML = '';
        await module.render(body, { pane: container.closest('.workspace-pane')?.id });
        container.dataset.moduleLoaded = 'true';
      }
    }catch(_e){}

    const body = container.querySelector('.tab-content-body') || container;
    const input = body.querySelector('.hey-ask-input');
    if (input && typeof text === 'string') { input.value = text; }

    // Trigger the exact same UI actions as the tab (no special-casing)
    try{
      if (summary) {
        const btn = body.querySelector('.hey-summary-btn');
        if (btn) btn.click();
        else if (typeof module.runSummary === 'function') await module.runSummary(body);
      } else {
        const btn = body.querySelector('.hey-ask-btn');
        if (btn) btn.click();
        else if (typeof module.runAsk === 'function') await module.runAsk(body, text);
      }
      return true;
    }catch(_e){ return false; }
  }
  // Removed spinner and pulse to keep behavior simple and mirror the tab exactly

  function openQuickPopup(){
    const anchor = document.getElementById('heyQuickBtn');
    if (!(anchor && window.Popups && typeof window.Popups.show === 'function')) return;
    // If no patient is selected, show a big message
    if (!hasPatient()){
      const msg = document.createElement('div');
      msg.textContent = 'Please select patient';
      msg.style.fontSize = '18px';
      msg.style.fontWeight = '600';
      msg.style.padding = '6px 2px';
      msg.style.textAlign = 'left';
      window.Popups.show(anchor, msg, { maxWidth: '420px', fontSize: '16px' });
      return;
    }

    const { wrap, form, input, askBtn, sumBtn } = buildPopup();
    // Ensure the Hey OMAR module is ready so we can mirror the input
    (async ()=>{
      const ok = await ensureHeyModule();
      if (!ok) return;
      const cont = getHeyContainer();
      if (!cont) return;
      const module = window.WorkspaceModules && window.WorkspaceModules['Hey OMAR'];
      if (!module) return;
      // Render background if needed
      try{
        if (!cont.dataset.moduleLoaded){
          const body = cont.querySelector('.tab-content-body') || cont;
          body.innerHTML = '';
          await module.render(body, { pane: cont.closest('.workspace-pane')?.id });
          cont.dataset.moduleLoaded = 'true';
        }
      }catch(_e){}
      const body = cont.querySelector('.tab-content-body') || cont;
      const realInput = body.querySelector('.hey-ask-input');
      // Seed popup input from tab input
      if (realInput && typeof realInput.value === 'string') {
        input.value = realInput.value;
      }
      // Mirror keystrokes from popup to tab input
      input.addEventListener('input', ()=>{ if (realInput) realInput.value = input.value; });
      // Optional: pressing Escape just closes (no action)
    })();

    const pop = window.Popups.show(anchor, wrap, { maxWidth: '520px', fontSize: '16px' });
    setTimeout(()=>{ try{ input.focus(); }catch(_e){} }, 0);

    async function doRun(summary){
      const text = input.value.trim();
      // Start spinner immediately only if Summary or non-empty text for Ask
      try { 
        const shouldStart = summary || !!text;
        if (shouldStart) window.dispatchEvent(new CustomEvent('heyomar:query-start', { detail:{ source:'quick', type: summary?'summary':'ask', ts: Date.now() } })); 
      } catch(_e){}
      let started = null;
      try {
        started = await runHeyAsk(text, { summary });
      } finally {
        // Close popup promptly
        try{ window.Popups.close && window.Popups.close(); }catch(_e){}
        // If the run did not start (e.g., module failed to load), clear spinner ourselves
        // Otherwise, rely on the module's own heyomar:query-finish to avoid premature clearing
        try{
          if (typeof started === 'boolean' && !started){
            window.dispatchEvent(new CustomEvent('heyomar:query-finish', { detail:{ source:'quick', type: summary?'summary':'ask', ts: Date.now() } }));
          }
        }catch(_e){}
      }
    }

    form.addEventListener('submit', (e)=>{ e.preventDefault(); doRun(false); });
    askBtn.addEventListener('click', (e)=>{ e.preventDefault(); doRun(false); });
    sumBtn.addEventListener('click', (e)=>{ e.preventDefault(); doRun(true); });
  }

  function bind(){
    const btn = document.getElementById('heyQuickBtn');
    if (!btn || btn._heyBound) return;
    btn._heyBound = true;
    btn.addEventListener('click', (e)=>{ e.preventDefault(); openQuickPopup(); });

    // Show immediate structured data as a popup if Hey OMAR tab isn't active
    window.addEventListener('heyomar:immediate-structured', (ev)=>{
      try{
        const anchor = document.getElementById('heyQuickBtn');
        if (!(anchor && window.Popups && typeof window.Popups.show === 'function')) return;
        // Determine if Hey OMAR tab is currently active/visible
        const tab = (function(){
          const leftBar = document.getElementById('leftTabBar');
          const rightBar = document.getElementById('rightTabBar');
          const find = (bar)=> bar ? Array.from(bar.children||[]).find(t => ((t.dataset.moduleName||t.dataset.tabName||'')==='Hey OMAR')) : null;
          return find(leftBar) || find(rightBar);
        })();
        const isActive = !!(tab && tab.classList && (tab.classList.contains('active') || tab.getAttribute('aria-selected')==='true'));
        if (isActive) return; // If visible, don't show popup

        // Show the structured data HTML in a popup near the top button
        const wrap = document.createElement('div');
        wrap.style.maxWidth = '560px';
        wrap.style.fontSize = '14px';
        wrap.innerHTML = ev.detail && ev.detail.html ? String(ev.detail.html) : '<em>No data</em>';
        // Footer with a quick jump to the Hey OMAR tab
        const footer = document.createElement('div');
        footer.style.display = 'flex';
        footer.style.justifyContent = 'flex-end';
        footer.style.marginTop = '8px';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = 'Go to Hey OMAR';
        btn.className = 'refresh-btn';
        btn.style.fontSize = '13px';
        btn.addEventListener('click', (e)=>{
          e.preventDefault();
          try{ window.Popups.close && window.Popups.close(); }catch(_e){}
          try{ openHeyTab(); }catch(_e){}
        });
        footer.appendChild(btn);
        wrap.appendChild(footer);
        window.Popups.show(anchor, wrap, { maxWidth: '560px', fontSize: '14px' });
        // Auto-dismiss after a short delay; pause if the user hovers
        try{
          const autoCloseMs = 7000;
          let hovering = false;
          wrap.addEventListener('mouseenter', ()=> { hovering = true; });
          wrap.addEventListener('mouseleave', ()=> { hovering = false; });
          setTimeout(()=>{
            if (!hovering) {
              try{ window.Popups.close && window.Popups.close(); }catch(_e){}
            }
          }, autoCloseMs);
        }catch(_e){}
      }catch(_e){}
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
