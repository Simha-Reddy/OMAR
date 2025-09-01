// Minimal mobile top bar for Explore (mobile)
(function(){
  function el(tag, attrs = {}, children = []){
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k,v]) => {
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    (Array.isArray(children) ? children : [children]).forEach(c => { if (c) node.appendChild(c); });
    return node;
  }

  function ensureMobileMenuContainer(){
    // Ensure a #mobileMenu exists so existing app.js toggle works
    let menu = document.getElementById('mobileMenu');
    if (!menu){
      menu = el('div', { id: 'mobileMenu', class: 'mobile-menu' });
      document.body.appendChild(menu);
    }
    // If empty or missing standard links, populate
    if (!menu.dataset.initialized){
      menu.innerHTML = '';
      const links = [
        { href: '/scribe', text: '📝 Scribe' },
        { href: '/explore', text: '🔍 Explore' },
        { href: '/archive', text: '📁 Archive' },
        { href: '/settings', text: '⚙️ Settings' },
        { href: '/scribe?autowrite=1', text: '✍️ Write Notes', id: 'writeNotesLink', title: 'Generate patient education and clinic note' },
      ];
      links.forEach(def => {
        const a = el('a', Object.assign({}, def, { title: def.title || def.text }));
        menu.appendChild(a);
      });
      // Separator
      const hr = el('hr', { class: 'mobile-menu-separator' });
      menu.appendChild(hr);
      // Exit link wired to global exitApp()
      const exit = el('a', { href: '#', class: 'end-session-link', title: 'Exit' });
      exit.textContent = '🚪 Exit';
      exit.addEventListener('click', (e)=>{ e.preventDefault(); try{ window.exitApp && window.exitApp(); }catch(_){} });
      menu.appendChild(exit);
      menu.dataset.initialized = '1';
    }
  }

  function renderTopBar(){
    const top = document.getElementById('mobileTopBar');
    if (!top) return;
    top.innerHTML = '';

    const bar = el('div', { class: 'global-top-bar mobile-top-bar' });

    // Left: search icon button (no container around icon; CSS controls size)
    const searchBtn = el('button', { id: 'mobileSearchBtn', class: 'mobile-search-btn', title: 'Search', 'aria-label': 'Search' });
    const searchImg = el('img', { src: '/static/images/search_icon.png', alt: 'Search', class: 'search-icon' });
    searchBtn.appendChild(searchImg);

    // Middle: patient name + age (reuse #patientLookupResults id)
    const centerWrap = el('div', { class: 'global-center' });
    const centerLbl = el('span', { id: 'patientLookupResults', title: 'Tap for demographics', role: 'button', tabindex: '0', style: 'font-weight:bold;cursor:pointer;' });
    centerWrap.appendChild(centerLbl);

    // Right: hamburger button (reuse existing toggle in app.js)
    const hamBtn = el('button', { id: 'hamburgerBtn', class: 'hamburger-btn', 'aria-label': 'Menu' }, document.createTextNode('\u2630'));

    const left = el('div', { class: 'left-controls' }, searchBtn);
    const right = el('div', { class: 'right-controls' }, hamBtn);

    bar.appendChild(left);
    bar.appendChild(centerWrap);
    bar.appendChild(right);
    top.appendChild(bar);

    // Build search panel, positioned flush under fixed top bar
    let panel = document.getElementById('mobileSearchPanel');
    if (!panel){
      panel = el('div', { id: 'mobileSearchPanel', style: 'display:none; padding:6px 8px; margin:0; background:#f7f7f7; border-bottom:1px solid #ddd; position:fixed; left:0; right:0; z-index:999;' });
      const input = el('input', { id: 'patientSearchInput', type: 'text', placeholder: 'Search patient...', autocomplete: 'off', style: 'width:100%;max-width:540px;margin:0 auto;display:block;padding:8px;border:1px solid #ccc;border-radius:6px;background:#fff;' });
      panel.appendChild(input);
      document.body.appendChild(panel);
    }

    function updatePanelTop(){
      try {
        const tb = document.querySelector('.global-top-bar');
        const h = tb ? tb.offsetHeight : 56; // fallback
        panel.style.top = h + 'px';
      } catch(_e) {}
    }
    updatePanelTop();
    window.addEventListener('resize', updatePanelTop);

    searchBtn.addEventListener('click', () => {
      const vis = panel.style.display !== 'none';
      if (vis) {
        panel.style.display = 'none';
      } else {
        updatePanelTop();
        panel.style.display = 'block';
        const inp = panel.querySelector('#patientSearchInput');
        try { inp && inp.focus(); } catch(_e) {}
      }
    });

    // If patient.js is loaded, clicking center label opens demographics modal
    // (handlers are bound in patient.js on DOMContentLoaded)

    // Ensure menu container so app.js toggle can work
    ensureMobileMenuContainer();

    // Initialize label from current session if available
    try {
      fetch('/session_data', { cache: 'no-store' })
        .then(r => r.json())
        .then(js => {
          const rec = js && js.patient_record;
          if (rec && window.getPatientName && window.getPatientAge){
            const nm = window.getPatientName(rec);
            const ag = window.getPatientAge(rec);
            updatePatientTop(nm, ag);
          }
        })
        .catch(()=>{});
    } catch(_e) {}
  }

  function updatePatientTop(name, age){
    const elc = document.getElementById('patientLookupResults');
    if (!elc) return;
    const safeName = (name && name !== 'Unknown') ? String(name) : '';
    const ageStr = (age && age !== 'Unknown') ? String(age) : '';
    const base = ageStr && safeName ? `${safeName}, Age: ${ageStr}` : safeName;
    if (!elc.dataset.originalText) elc.dataset.originalText = base;
    if (window.demoMasking && window.demoMasking.enabled && typeof window.demoMasking.maskName === 'function'){
      const masked = window.demoMasking.maskName(safeName);
      elc.textContent = ageStr ? `${masked}, Age: ${ageStr}` : masked;
    } else {
      elc.textContent = base;
    }
  }

  // --- Segmented picker + swipe views ---
  const VIEWS = [
    { key: 'notes', label: 'Notes' },
    { key: 'snapshot', label: 'Snapshot' },
    { key: 'hey', label: 'Hey, Omar' },
    { key: 'documents', label: 'Documents' },
    { key: 'labs', label: 'Labs' },
    { key: 'meds', label: 'Meds' },
  ];
  let activeIndex = Math.max(0, VIEWS.findIndex(v => v.key === 'snapshot'));
  let trackEl = null;
  let pickerEl = null;

  function centerActiveSegment(){
    try{
      if(!pickerEl) return;
      const activeBtn = pickerEl.querySelector('.seg-btn.active');
      if(!activeBtn) return;
      const pr = pickerEl.getBoundingClientRect();
      const br = activeBtn.getBoundingClientRect();
      const current = pickerEl.scrollLeft;
      const target = current + (br.left + br.width/2) - (pr.left + pr.width/2);
      pickerEl.scrollTo({ left: target, behavior: 'smooth' });
    }catch(_e){}
  }

  function refreshSnapshotSidebars(){
    // Only attempt refresh if mounts exist
    const hasVitals = !!document.getElementById('vitalsSidebar');
    const hasRight = !!document.getElementById('patientRightSidebar');
    if (hasVitals && window.VitalsSidebar && typeof window.VitalsSidebar.refresh === 'function'){
      try { window.VitalsSidebar.refresh(); } catch(_e) {}
    }
    if (hasRight && window.RightSidebar && typeof window.RightSidebar.refresh === 'function'){
      try { window.RightSidebar.refresh(); } catch(_e) {}
    }
  }

  function setActive(index, opts){
    const i = Math.max(0, Math.min(VIEWS.length-1, index|0));
    activeIndex = i;
    // Update picker
    try{
      const btns = pickerEl ? pickerEl.querySelectorAll('.seg-btn') : [];
      btns.forEach((b, idx)=>{
        if(idx === i){ b.classList.add('active'); b.setAttribute('aria-selected','true'); }
        else { b.classList.remove('active'); b.setAttribute('aria-selected','false'); }
      });
      centerActiveSegment();
    }catch(_e){}
    // Update track
    if(trackEl){
      const pct = -(i * 100);
      trackEl.style.transform = `translateX(${pct}%)`;
    }
    // When switching to Snapshot, refresh its content
    if (VIEWS[i] && VIEWS[i].key === 'snapshot'){
      refreshSnapshotSidebars();
    }
  }

  function renderPickerAndViews(){
    const navHost = document.getElementById('mobilePicker');
    const contentHost = document.getElementById('mobileContent');
    if(!navHost || !contentHost) return;

    // Picker (horizontally scrollable segmented control)
    navHost.innerHTML = '';
    const scroller = el('div', { class: 'segmented-scroll', role: 'tablist', 'aria-label':'Mobile sections' });
    VIEWS.forEach((v, idx)=>{
      const btn = el('button', {
        class: 'seg-btn' + (idx===activeIndex?' active':''),
        role: 'tab',
        'aria-selected': idx===activeIndex ? 'true' : 'false',
        'data-index': String(idx),
        title: v.label,
        text: v.label
      });
      btn.addEventListener('click', ()=> setActive(idx));
      scroller.appendChild(btn);
    });
    navHost.appendChild(scroller);
    pickerEl = scroller;

    // Views (swipeable)
    contentHost.innerHTML = '';
    const wrap = el('div', { class: 'mobile-views-wrap' });
    const track = el('div', { class: 'mobile-views-track' });
    VIEWS.forEach(v => {
      const pane = el('section', { class: 'mobile-view', 'data-key': v.key });
      const h = el('h2', { class: 'mobile-view-title', text: v.label });
      pane.appendChild(h);
      if (v.key === 'snapshot'){
        // Snapshot view: reuse desktop sidebars (stacked)
        const container = el('div', { class: 'mobile-snapshot' });
        const vitalsSec = el('section', { class: 'mobile-snap-section' }, [
          el('h3', { class: 'mobile-snap-title', text: 'Recent Vitals & Labs' }),
          el('div', { id: 'vitalsSidebar', class: 'vitals-sidebar', role: 'region', 'aria-label': 'Recent vitals and labs' })
        ]);
        const rightSec = el('section', { class: 'mobile-snap-section' }, [
          el('h3', { class: 'mobile-snap-title', text: 'Patient Summary' }),
          el('div', { id: 'patientRightSidebar', class: 'vitals-sidebar', role: 'region', 'aria-label': 'Active problems, allergies, medications' })
        ]);
        container.appendChild(vitalsSec);
        container.appendChild(rightSec);
        pane.appendChild(container);
      } else if (v.key === 'hey'){
        // Hey, Omar (Ask) view — reuse desktop handlers and IDs
        const wrapAsk = el('div', { class: 'compartment', id: 'docsResultsCompartment' });
        const body = el('div', { class: 'compartment-body' });
        const row = el('div', { class: 'docs-results-grid' });
        const controls = el('div', { class: 'docs-controls' });
        // Inline ask controls (same IDs as desktop, minus mic/status to avoid duplicates)
        const inline = el('span', { class: 'notes-ask-inline' });
        const input = el('input', { id: 'notesAskInput', type: 'text', placeholder: "Press 'Hey, Omar' and speak", style: 'min-width:260px;' });
        const askBtn = el('button', { id: 'notesAskBtn', text: 'Ask' });
        const summaryBtn = el('button', { id: 'notesSummaryBtn', title: 'Generate a one-line clinical summary', text: 'Summary' });
        inline.appendChild(input);
        inline.appendChild(askBtn);
        inline.appendChild(summaryBtn);
        controls.appendChild(inline);
        // Answer box (status line lives in Documents view to avoid duplicate IDs)
        const answer = el('div', { id: 'notesAnswerBox', class: 'markdown-box', style: 'display:none; margin-top:8px; padding:10px; background:#fff; border:1px solid #e0e0e0; border-radius:6px;' });
        controls.appendChild(answer);
        row.appendChild(controls);
        body.appendChild(row);
        wrapAsk.appendChild(body);
        pane.appendChild(wrapAsk);
        // No immediate import here; documents.js will be loaded after all panes mount
      } else if (v.key === 'notes'){
        const notesWrap = el('div', { class: 'compartment' });
        const body = el('div', { class: 'compartment-body' });
        const label = el('label', { for: 'visitNotes', style: 'display:block; font-weight:600; margin-bottom:4px;' }, document.createTextNode('Notes during visit'));
        const ta = el('textarea', { id: 'visitNotes', placeholder: 'Jot quick notes here...', style: 'width:100%; min-height:200px; resize:vertical; padding:8px; border:1px solid #ddd; border-radius:6px;' });
        body.appendChild(label);
        body.appendChild(ta);
        notesWrap.appendChild(body);
        pane.appendChild(notesWrap);
      } else if (v.key === 'documents'){
        // Documents view: reuse desktop table + overlay viewer structure
        // Controls row
        const controlsRow = el('div', { class: 'docs-controls-row', style: 'margin-bottom:6px;' }, [
          el('label', { style: 'display:inline-flex; align-items:center; gap:6px; margin-left:8px;' }, [
            el('input', { type: 'checkbox', id: 'autoIndexToggle' }),
            el('span', { text: 'Continue Auto-Indexing All Notes' })
          ])
        ]);
        const statusLine = el('div', { style: 'display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px;' }, [
          el('span', { id: 'docsStatus', style: 'font-size:0.9em; color:#555;' }),
          el('span', { id: 'docsSizeEstimate', style: 'font-size:0.9em; color:#555;' })
        ]);
        pane.appendChild(controlsRow);
        pane.appendChild(statusLine);
        // Table + overlay
        const grid = el('div', { class: 'documents-grid' });
        const comp = el('div', { class: 'compartment', id: 'docsListCompartment' });
        const body = el('div', { class: 'compartment-body' });
        const wrapDiv = el('div', { id: 'documentsTableWrap', class: 'doc-table-wrap' });
        const tableDiv = el('div', { id: 'documentsTable', class: 'doc-table' });
        // Overlay
        const overlay = el('div', { id: 'docViewerOverlay', class: 'doc-viewer-overlay', style: 'display:none;' });
        const tabs = el('div', { id: 'docTabs', class: 'doc-tabs', 'aria-label': 'Note navigation' });
        const nav = el('div', { class: 'doc-nav' }, [
          el('button', { class: 'tab-chev left', id: 'docTabsNavLeft', title: 'Previous note', 'aria-label': 'Previous note' }, document.createTextNode('◀')),
          el('button', { class: 'tab-chev right', id: 'docTabsNavRight', title: 'Next note', 'aria-label': 'Next note' }, document.createTextNode('▶'))
        ]);
        const prevTab = el('div', { class: 'doc-tab', id: 'docTabPrev', 'data-state': 'disabled' }, [
          el('button', { class: 'tab-label', id: 'docTabPrevLabel', title: 'Open previous note', 'aria-label': 'Open previous note' })
        ]);
        const currTab = el('div', { class: 'doc-tab current', id: 'docTabCurr' }, [
          el('button', { class: 'tab-label', id: 'docTabCurrLabel', title: 'Current note', 'aria-current': 'page' })
        ]);
        const nextTab = el('div', { class: 'doc-tab', id: 'docTabNext', 'data-state': 'disabled' }, [
          el('button', { class: 'tab-label', id: 'docTabNextLabel', title: 'Open next note', 'aria-label': 'Open next note' })
        ]);
        const closeBtn = el('button', { id: 'docTabClose', class: 'doc-tab-close', title: 'Close viewer', 'aria-label': 'Close viewer' }, document.createTextNode('×'));
        tabs.appendChild(nav);
        tabs.appendChild(prevTab);
        tabs.appendChild(currTab);
        tabs.appendChild(nextTab);
        tabs.appendChild(closeBtn);
        const viewerWrap = el('div', { class: 'doc-viewer-wrap' });
        const pre = el('pre', { id: 'docViewText', class: 'doc-viewer' });
        const copy = el('button', { id: 'copyDocTextBtn', class: 'doc-viewer-copy', title: 'Copy note text' }, document.createTextNode('Copy'));
        viewerWrap.appendChild(pre);
        viewerWrap.appendChild(copy);
        const viewStatus = el('div', { id: 'docViewStatus', style: 'font-size:0.85em; color:#555; padding:4px 6px 6px 6px;' });
        overlay.appendChild(tabs);
        overlay.appendChild(viewerWrap);
        overlay.appendChild(viewStatus);
        // Assemble
        wrapDiv.appendChild(tableDiv);
        wrapDiv.appendChild(overlay);
        body.appendChild(wrapDiv);
        comp.appendChild(body);
        grid.appendChild(comp);
        pane.appendChild(grid);
      } else {
        const p = el('p', { class: 'mobile-view-desc', text: `This is the ${v.label} view.` });
        pane.appendChild(p);
      }
      track.appendChild(pane);
    });
    wrap.appendChild(track);
    contentHost.appendChild(wrap);
    trackEl = track;

    // Touch swipe handlers
    let startX = 0, startY = 0, dx = 0, dy = 0, dragging = false;
    let baseX = 0;
    function onStart(e){
      const t = e.touches ? e.touches[0] : e;
      startX = t.clientX; startY = t.clientY; dx = 0; dy = 0; dragging = true;
      baseX = -activeIndex * wrap.clientWidth;
      track.style.transition = 'none';
    }
    function onMove(e){
      if(!dragging) return;
      const t = e.touches ? e.touches[0] : e;
      dx = t.clientX - startX; dy = t.clientY - startY;
      // Only act on mostly-horizontal moves
      if(Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 6){
        e.preventDefault();
        const w = wrap.clientWidth || 1;
        const pct = ((baseX + dx) / w) * 100;
        track.style.transform = `translateX(${pct}%)`;
      }
    }
    function onEnd(){
      if(!dragging){ return; }
      dragging = false;
      track.style.transition = '';
      const threshold = Math.max(40, (wrap.clientWidth || 300) * 0.15);
      if(Math.abs(dx) > threshold && Math.abs(dx) > Math.abs(dy)){
        if(dx < 0) setActive(activeIndex + 1);
        else setActive(activeIndex - 1);
      } else {
        setActive(activeIndex);
      }
    }
    wrap.addEventListener('touchstart', onStart, { passive: true });
    wrap.addEventListener('touchmove', onMove, { passive: false });
    wrap.addEventListener('touchend', onEnd, { passive: true });

    // Initial position
    setActive(activeIndex, { immediate: true });

    // Ensure snapshot sidebars render at least once
    refreshSnapshotSidebars();

    // Load documents module after panes exist, so it can init table and bind Ask/mic handlers
    setTimeout(() => { try { import('/static/explore/documents.js'); } catch(_e){} }, 0);
  }

  // Expose hook
  try {
    window.omarMobile = window.omarMobile || {};
    window.omarMobile.updatePatientTop = updatePatientTop;
    window.omarMobile.setMobileView = (key)=>{
      const idx = VIEWS.findIndex(v=>v.key===key);
      if(idx>=0) setActive(idx);
    };
  } catch(_e) {}

  // Initialize on DOMContentLoaded
  function init(){ renderTopBar(); renderPickerAndViews(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();