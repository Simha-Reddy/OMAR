// Mobile Workspace - Swipeable Tab Carousel
// Adapts workspace modules for mobile with touch-friendly navigation

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
    let menu = document.getElementById('mobileMenu');
    if (!menu){
      menu = el('div', { id: 'mobileMenu', class: 'mobile-menu' });
      document.body.appendChild(menu);
    }
    if (!menu.dataset.initialized){
      menu.innerHTML = '';
      const links = [
        { href: '/scribe', text: '📝 Scribe' },
        { href: '/explore', text: '🔍 Explore' },
        { href: '/workspace', text: '🏢 Workspace' },
        { href: '/archive', text: '📁 Archive' },
        { href: '/settings', text: '⚙️ Settings' },
        { href: '/workspace?desktop=1', text: '🖥️ Desktop View' },
      ];
      links.forEach(def => {
        const a = el('a', Object.assign({}, def, { title: def.title || def.text }));
        menu.appendChild(a);
      });
      const hr = el('hr', { class: 'mobile-menu-separator' });
      menu.appendChild(hr);
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

    // Left: search icon button
    const searchBtn = el('button', { id: 'mobileSearchBtn', class: 'mobile-search-btn', title: 'Search', 'aria-label': 'Search' });
    const searchImg = el('img', { src: '/static/images/search_icon.png', alt: 'Search', class: 'search-icon' });
    searchBtn.appendChild(searchImg);

    // Middle: patient name + age
    const centerWrap = el('div', { class: 'global-center' });
    const centerLbl = el('span', { id: 'patientLookupResults', title: 'Tap for demographics', role: 'button', tabindex: '0', style: 'font-weight:bold;cursor:pointer;' });
    centerWrap.appendChild(centerLbl);

    // Right: hamburger button
    const hamBtn = el('button', { id: 'hamburgerBtn', class: 'hamburger-btn', 'aria-label': 'Menu' }, document.createTextNode('\u2630'));

    const left = el('div', { class: 'left-controls' }, searchBtn);
    const right = el('div', { class: 'right-controls' }, hamBtn);

    bar.appendChild(left);
    bar.appendChild(centerWrap);
    bar.appendChild(right);
    top.appendChild(bar);

    // Search panel
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
        const h = tb ? tb.offsetHeight : 56;
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

    ensureMobileMenuContainer();

    // Initialize patient display using same approach as desktop workspace
    try {
      updateHeaderFromDemographics().catch(() => {
        // Fallback: show default state if demographics fetch fails
        updatePatientTop('', '');
      });
    } catch(_e) {
      // Fallback: show default state if any error occurs
      updatePatientTop('', '');
    }
  }

  function updatePatientTop(name, age){
    const elc = document.getElementById('patientLookupResults');
    if (!elc) return;
    const safeName = (name && name !== 'Unknown' && String(name).trim()) ? String(name) : '';
    const ageStr = (age && age !== 'Unknown' && String(age).trim()) ? String(age) : '';
    
    // Construct display text
    let base = '';
    if (safeName && ageStr) {
      base = `${safeName}, Age: ${ageStr}`;
    } else if (safeName) {
      base = safeName;
    } else {
      base = 'No patient selected';
    }
    
    if (!elc.dataset.originalText) elc.dataset.originalText = base;
    
    // Apply demo masking if enabled
    if (window.demoMasking && window.demoMasking.enabled && typeof window.demoMasking.maskName === 'function' && safeName){
      const masked = window.demoMasking.maskName(safeName);
      elc.textContent = ageStr ? `${masked}, Age: ${ageStr}` : masked;
    } else {
      elc.textContent = base;
    }
  }

  // --- Workspace Tab Carousel ---
  const WORKSPACE_TABS = [
    { key: 'note', label: 'Note', moduleKey: 'Note' },
    { key: 'todo', label: 'To Do', moduleKey: 'To Do' },
    { key: 'orders', label: 'Orders', moduleKey: 'Orders' },
    { key: 'documents', label: 'Documents', moduleKey: 'Documents' },
    { key: 'snapshot', label: 'Snapshot', moduleKey: 'Snapshot' },
    { key: 'heyomar', label: 'Hey OMAR', moduleKey: 'Hey OMAR' },
    { key: 'labs', label: 'Labs', moduleKey: 'Labs' },
    { key: 'vitals', label: 'Vitals', moduleKey: 'Vitals' },
    { key: 'meds', label: 'Meds', moduleKey: 'Meds' },
    { key: 'problems', label: 'Problems', moduleKey: 'Problems' },
    { key: 'radiology', label: 'Radiology', moduleKey: 'Radiology' },
    { key: 'procedures', label: 'Procedures', moduleKey: 'Procedures' },
    { key: 'timeline', label: 'Timeline', moduleKey: 'Timeline' }
  ];

  let activeIndex = 0; // Start with Note
  let trackEl = null;
  let pickerEl = null;
  let wrapEl = null;
  let loadedModules = new Map();
  let renderedModules = new Map(); // key: tab.key, value: true if rendered
  let moduleContainers = new Map(); // key: tab.key, value: DOM element

  // Load workspace modules (adapted from desktop workspace.js)
  const moduleConfig = {
    'Note': 'note.js',
    'To Do': 'todo.js',
    'Orders': 'orders.js',
    'Documents': 'documents.js',
    'Snapshot': 'snapshot.js',
    'Hey OMAR': 'heyomar.js',
    'Labs': 'labs.js',
    'Vitals': 'vitals.js',
    'Meds': 'meds.js',
    'Problems': 'problems.js',
    'Radiology': 'radiology.js',
    'Procedures': 'procedures.js',
    'Timeline': 'timeline.js'
  };

  // Helper to get current DFN consistently
  function _getCurrentDfn(){
    try {
      return window.CURRENT_PATIENT_DFN || 
             (window.SessionManager && window.SessionManager.get && window.SessionManager.get('patient_meta')?.dfn) ||
             (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('CURRENT_PATIENT_DFN')) ||
             null;
    } catch(_e) { return null; }
  }

  // Compute age from DOB (same logic as desktop workspace)
  function computeAgeFromDob(dobStr){
    try{
      if (!dobStr) return '';
      let dobMs;
      // Handle various date formats
      if (/^\d{4}-\d{2}-\d{2}/.test(dobStr)) {
        dobMs = Date.parse(dobStr);
      } else if (/^\d{1,2}\/\d{1,2}\/\d{4}/.test(dobStr)) {
        dobMs = Date.parse(dobStr);
      } else {
        dobMs = Date.parse(dobStr);
      }
      if (isNaN(dobMs)) return '';
      const ageMs = Date.now() - dobMs;
      const years = Math.floor(ageMs / (365.25 * 24 * 60 * 60 * 1000));
      return years >= 0 ? String(years) : '';
    } catch(_e) { return ''; }
  }

  // Fetch patient demographics and update header (same approach as desktop workspace)
  async function updateHeaderFromDemographics(dfnOverride){
    try{
      const dfn = dfnOverride || _getCurrentDfn();
      if (!dfn) return;
      const url = `/quick/patient/demographics?dfn=${encodeURIComponent(String(dfn))}`;
      const r = await fetch(url, { 
        headers: { 'Accept':'application/json', 'X-Workspace':'1', 'X-Caller':'workspace-mobile-header' }, 
        cache:'no-store', 
        credentials:'same-origin' 
      });
      if (!r.ok) return;
      const js = await r.json();
      const demo = (js && js.demographics) || {};
      const name = (demo.Name || demo['Patient Name'] || '').toString();
      const dobIso = (demo.DOB_ISO || '').toString();
      const dobTxt = (demo.DOB || '').toString();
      if (!name) return;
      const age = computeAgeFromDob(dobIso || dobTxt);
      updatePatientTop(name, age);
    } catch(_e) { 
      console.warn('[Mobile Workspace] Failed to load patient demographics:', _e);
    }
  }

  // Is a patient selected?
  function _isPatientSelected(){
    const dfn = _getCurrentDfn();
    return dfn && String(dfn).trim() !== '';
  }

  // Dynamic module loader
  async function loadModule(moduleName) {
    if (loadedModules.has(moduleName)) {
      return loadedModules.get(moduleName);
    }
    
    try {
      const scriptUrl = `/static/workspace/modules/${moduleConfig[moduleName]}`;
      const script = document.createElement('script');
      script.src = scriptUrl;
      
      const loadPromise = new Promise((resolve, reject) => {
        script.onload = () => {
          const module = window.WorkspaceModules && window.WorkspaceModules[moduleName];
          if (module) {
            resolve(module);
          } else {
            reject(new Error(`Module ${moduleName} not found in WorkspaceModules`));
          }
        };
        script.onerror = () => reject(new Error(`Failed to load module script: ${scriptUrl}`));
      });
      
      document.head.appendChild(script);
      const module = await loadPromise;
      loadedModules.set(moduleName, module);
      return module;
    } catch (error) {
      console.error(`[Mobile Workspace] Error loading module ${moduleName}:`, error);
      throw error;
    }
  }

  function getPanes(){
    try {
      return Array.from(trackEl ? trackEl.querySelectorAll(':scope > .mobile-view') : []);
    } catch(_e) {
      return Array.from(trackEl ? trackEl.children : []);
    }
  }

  function centerActiveSegment(){
    try{
      if(!pickerEl) return;
      const activeBtn = pickerEl.querySelector('.seg-btn.active');
      if(!activeBtn) return;
      const target = Math.max(0, activeBtn.offsetLeft - (pickerEl.clientWidth - activeBtn.offsetWidth) / 2);
      pickerEl.scrollTo({ left: target, behavior: 'smooth' });
    }catch(_e){}
  }

  function setActive(index, opts){
    const i = Math.max(0, Math.min(WORKSPACE_TABS.length-1, index|0));
    console.log(`[Mobile Workspace] setActive(${index}) -> ${i}, tab: ${WORKSPACE_TABS[i]?.label}`);
    activeIndex = i;
    
    // Update picker buttons
    try{
      const btns = pickerEl ? pickerEl.querySelectorAll('.seg-btn') : [];
      btns.forEach((b, btnIndex)=>{
        const on = btnIndex === i;
        if(on){ 
          b.classList.add('active'); 
          b.setAttribute('aria-selected','true'); 
        } else { 
          b.classList.remove('active'); 
          b.setAttribute('aria-selected','false'); 
        }
      });
      centerActiveSegment();
    }catch(_e){
      console.error('[Mobile Workspace] setActive button update error:', _e);
    }
    
    // Update track position
    applyTransformForIndex(i, opts);
    
    // Show/hide module containers instead of re-rendering
    const panes = getPanes();
    panes.forEach((pane, idx) => {
      const container = pane.querySelector('.module-container');
      if (!container) return;
      if (idx === i) {
        container.style.display = '';
      } else {
        container.style.display = 'none';
      }
    });
    
    // Only render if not already rendered
    const tab = WORKSPACE_TABS[i];
    if (tab && !renderedModules.get(tab.key)) {
      loadAndRenderModule(tab).then(() => {
        renderedModules.set(tab.key, true);
      });
    }
  }

  function setActiveByKey(key, opts){
    try{
      const viewIdx = WORKSPACE_TABS.findIndex(v => v.key === key);
      setActive(viewIdx >= 0 ? viewIdx : 0, opts);
    }catch(_e){ setActive(0, opts); }
  }

  function applyTransformForIndex(i, opts){
    try{
      if(!trackEl || !wrapEl) return;
      const panes = getPanes();
      if (!panes || panes.length === 0) return;
      
      const safeIndex = Math.max(0, Math.min(i, panes.length - 1));
      let left = 0;
      const targetPane = panes[safeIndex];
      
      if (targetPane && targetPane.offsetLeft !== undefined && targetPane.offsetLeft >= 0) {
        left = targetPane.offsetLeft;
      } else {
        left = safeIndex * (wrapEl.clientWidth || 300);
      }
      
      const offsetPx = -left;
      const wantsImmediate = !!(opts && opts.immediate);
      if(wantsImmediate){ trackEl.style.transition = 'none'; }
      trackEl.style.transform = `translate3d(${offsetPx}px, 0, 0)`;
      if(wantsImmediate){ requestAnimationFrame(()=>{ try{ trackEl.style.transition = ''; }catch(_e){} }); }
    }catch(_e){
      console.error('[Mobile Workspace] applyTransformForIndex error:', _e);
    }
  }

  async function loadAndRenderModule(tab) {
    if (!tab.moduleKey) return;
    
    try {
      console.log(`[Mobile Workspace] Loading module: ${tab.moduleKey}`);
      const module = await loadModule(tab.moduleKey);
      
      // Find the pane for this tab
      const panes = getPanes();
      const paneIndex = WORKSPACE_TABS.findIndex(t => t.key === tab.key);
      const pane = panes[paneIndex];
      
      if (pane && module && typeof module.render === 'function') {
        const container = pane.querySelector('.module-container');
        if (container) {
          console.log(`[Mobile Workspace] Rendering module: ${tab.moduleKey}`);
          await module.render(container, { 
            pane: `mobile-${tab.key}`,
            mobile: true,
            dfn: _getCurrentDfn()
          });
          renderedModules.set(tab.key, true);
        }
      }
    } catch (error) {
      console.error(`[Mobile Workspace] Error loading/rendering module ${tab.moduleKey}:`, error);
      // Show error in the pane
      const panes = getPanes();
      const paneIndex = WORKSPACE_TABS.findIndex(t => t.key === tab.key);
      const pane = panes[paneIndex];
      if (pane) {
        const container = pane.querySelector('.module-container');
        if (container) {
          container.innerHTML = `
            <div class="module-error">
              <h3>Module Error</h3>
              <p>Failed to load ${tab.label} module: ${error.message}</p>
            </div>
          `;
        }
      }
    }
  }

  function renderPickerAndViews(){
    const navHost = document.getElementById('mobilePicker');
    const contentHost = document.getElementById('mobileContent');
    if(!navHost || !contentHost) return;

    // Picker (horizontally scrollable segmented control)
    navHost.innerHTML = '';
    const scroller = el('div', { class: 'segmented-scroll', role: 'tablist', 'aria-label': 'Workspace tabs' });
    WORKSPACE_TABS.forEach((tab, idx)=>{
      const btn = el('button', {
        class: 'seg-btn' + (idx===activeIndex?' active':''),
        role: 'tab',
        'aria-selected': idx===activeIndex ? 'true' : 'false',
        'data-index': String(idx),
        'data-key': tab.key,
        title: tab.label,
        text: tab.label
      });
      btn.addEventListener('click', ()=> setActiveByKey(tab.key));
      scroller.appendChild(btn);
    });
    navHost.appendChild(scroller);
    pickerEl = scroller;

    // Views (swipeable)
    contentHost.innerHTML = '';
    const wrap = el('div', { class: 'mobile-views-wrap' });
    const track = el('div', { class: 'mobile-views-track', style: 'position:relative; will-change: transform;' });
    moduleContainers = new Map();
    WORKSPACE_TABS.forEach(tab => {
      const pane = el('section', { class: 'mobile-view', 'data-key': tab.key });
      const header = el('div', { class: 'mobile-view-header' }, [
        el('h2', { class: 'mobile-view-title', text: tab.label })
      ]);
      pane.appendChild(header);
      
      // Container for module content
      const container = el('div', { 
        class: 'module-container',
        style: 'flex: 1; padding: 12px; overflow-y: auto;'
      });
      container.innerHTML = `<div class="module-loading">Loading ${tab.label}...</div>`;
      pane.appendChild(container);
      moduleContainers.set(tab.key, container);
      track.appendChild(pane);
    });
    
    wrap.appendChild(track);
    contentHost.appendChild(wrap);
    trackEl = track;
    wrapEl = wrap;

    // Touch swipe handlers
    let startX = 0, startY = 0, dx = 0, dy = 0, dragging = false;
    let baseX = 0;
    
    function onStart(e){
      const t = e.touches ? e.touches[0] : e;
      startX = t.clientX; startY = t.clientY; dx = 0; dy = 0; dragging = true;
      const panes = getPanes();
      const paneLeft = panes[activeIndex] ? panes[activeIndex].offsetLeft : (activeIndex * wrap.clientWidth);
      baseX = -paneLeft;
      track.style.transition = 'none';
    }
    
    function onMove(e){
      if(!dragging) return;
      const t = e.touches ? e.touches[0] : e;
      dx = t.clientX - startX; dy = t.clientY - startY;
      if(Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 6){
        e.preventDefault();
        track.style.transform = `translate3d(${baseX + dx}px, 0, 0)`;
      }
    }
    
    function onEnd(){
      if(!dragging){ return; }
      dragging = false;
      track.style.transition = '';
      const panes = getPanes();
      const paneW = panes[activeIndex] ? panes[activeIndex].offsetWidth : (wrap.clientWidth || 300);
      const threshold = Math.max(40, paneW * 0.15);
      if(Math.abs(dx) > threshold && Math.abs(dx) > Math.abs(dy)){
        if(dx < 0) setActive(activeIndex + 1);
        else setActive(activeIndex - 1);
      } else {
        applyTransformForIndex(activeIndex, { immediate: false });
      }
    }

    wrap.addEventListener('touchstart', onStart, { passive: true });
    wrap.addEventListener('touchmove', onMove, { passive: false });
    wrap.addEventListener('touchend', onEnd, { passive: true });

    // Handle resize events
    try{
      window.addEventListener('resize', ()=>{
        applyTransformForIndex(activeIndex, { immediate: true });
        centerActiveSegment();
      });
      window.addEventListener('orientationchange', ()=>{
        applyTransformForIndex(activeIndex, { immediate: true });
        centerActiveSegment();
      });
      
      if (window.ResizeObserver && wrapEl){
        const ro = new ResizeObserver(() => {
          try {
            applyTransformForIndex(activeIndex, { immediate: true });
            centerActiveSegment();
          } catch(_e){}
        });
        try { ro.observe(wrapEl); } catch(_e){}
      }
    }catch(_e){}

    // Initial position and load first module
    setTimeout(() => {
      setActive(activeIndex, { immediate: true });
      // Preload all other modules in the background (after first render)
      WORKSPACE_TABS.forEach((tab, idx) => {
        if (idx !== activeIndex && !renderedModules.get(tab.key)) {
          loadAndRenderModule(tab).then(() => {
            renderedModules.set(tab.key, true);
          }).catch(()=>{});
        }
      });
    }, 50);
  }

  // Listen for patient changes and update header
  try {
    window.addEventListener('PATIENT_SWITCH_DONE', () => {
      updateHeaderFromDemographics();
    });
    
    // Also listen for any manual patient updates
    window.addEventListener('PATIENT_UPDATED', () => {
      updateHeaderFromDemographics();
    });
  } catch(_e) {}

  // Expose mobile workspace API
  try {
    window.mobileWorkspace = window.mobileWorkspace || {};
    window.mobileWorkspace.updatePatientTop = updatePatientTop;
    window.mobileWorkspace.updateHeaderFromDemographics = updateHeaderFromDemographics;
    window.mobileWorkspace.setTab = (key) => {
      setActiveByKey(key);
    };
    window.mobileWorkspace.getCurrentTab = () => {
      return WORKSPACE_TABS[activeIndex]?.key || null;
    };

    // Make updatePatientNameDisplay available for patient_switch.js
    window.updatePatientNameDisplay = updateHeaderFromDemographics;
  } catch(_e) {}

  // Initialize on DOMContentLoaded
  function init() { 
    renderTopBar(); 
    renderPickerAndViews(); 
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();