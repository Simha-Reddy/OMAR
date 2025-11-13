// filepath: static/workspace/modules/todo.js
(function(){
  const MODULE_NAME = 'To Do';
  const state = { orders: [], days: 7, status: 'current', otype: 'all', checklist: [] };
  const controllers = new Set();
  let containerRef = null;

  function cancelAll(){ for(const c of Array.from(controllers)){ try{ c.abort(); }catch(_e){} } controllers.clear(); }
  function _dfn(){ try{ return window.CURRENT_PATIENT_DFN || null; }catch(_e){ return null; } }
  function jget(url){
    const ctrl = new AbortController();
    controllers.add(ctrl);
    const sep = url.includes('?')? '&' : '?';
    const dfn = (_dfn()||'');
    const busted = `${url}${sep}_pt=${encodeURIComponent(dfn)}&_ts=${Date.now()}`;
    return fetch(busted, { cache: 'no-store', signal: ctrl.signal })
      .finally(()=> controllers.delete(ctrl))
      .then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); });
  }
  function titleCase(s){ if(!s) return ''; return String(s).toLowerCase().replace(/\b([a-z])/g, (m,a)=>a.toUpperCase()); }
  function fmtDateOnly(s){ try{ const d=new Date(s); return isNaN(d)? '' : d.toLocaleDateString(); }catch(_e){ return ''; } }
  function readSaved(key, def){ try{ const v=localStorage.getItem(key); return v!=null? v: def; }catch(_e){ return def; } }
  function save(key, val){ try{ localStorage.setItem(key, String(val)); }catch(_e){} }
  // Checklist functionality
  function getChecklistData(){
    return state.checklist;
  }

  function setChecklistData(data){
    state.checklist = Array.isArray(data) ? data : [];
    // Persist on any checklist change coming from outside
    saveChecklistToSession();
    if(containerRef){
      renderChecklist(containerRef);
    }
  }
  function saveChecklistToSession(){
    if(typeof SessionManager !== 'undefined' && SessionManager.saveToSession){
      SessionManager.saveToSession().catch(e => console.warn('Failed to save checklist to session:', e));
    }
  }

  // NEW: Reconcile checklist items against placed orders to auto-complete matching tasks
  function reconcileChecklistWithOrders(){
    try{
      const items = Array.isArray(state.checklist) ? state.checklist : [];
      const orders = Array.isArray(state.orders) ? state.orders : [];
      if(!items.length || !orders.length) return;
      const norm = (s)=> String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
      const isPlaced = (o)=>{
        const st = String(o && (o.current_status || o.status_code) || '').toLowerCase();
        // Consider these statuses as meaning the order has been placed/active/completed
        return !!(st.includes('active') || st.includes('ordered') || st.includes('signed') || st.includes('released') || st.includes('complete') || st.includes('completed') || st.includes('resulted'));
      };
      const matchOrder = (text)=>{
        const a = norm(text);
        if(!a) return null;
        for(const o of orders){
          if(!isPlaced(o)) continue;
          const b = norm(o && o.name || '');
          if(!b) continue;
          // Bidirectional contains to handle phrasing differences
          if(a.includes(b) || b.includes(a)) return o;
        }
        return null;
      };
      let changed = false;
      for(const it of items){
        if(!it || it.completed) continue;
        const o = matchOrder(it.text || '');
        if(o){ it.completed = true; it._autoCompletedBy = 'order'; changed = true; }
      }
      if(changed){
        saveChecklistToSession();
        if(containerRef){ try{ renderChecklist(containerRef); }catch(_e){} }
      }
    }catch(_e){}
  }

  async function updateChecklistWithLLM(){
    try {
      // Show loading state in checklist
      const checklistContainer = containerRef?.querySelector('#checklist-items');
      const originalContent = checklistContainer?.innerHTML;
      if (checklistContainer) {
        checklistContainer.innerHTML = '<div class="checklist-empty">🤖 Updating checklist with AI analysis...</div>';
      }
      
      // Gather current data
      const currentChecklist = state.checklist.map(item => 
        `[${item.completed ? 'X' : ' '}] ${item.text}`
      ).join('\n');
      
      const currentOrders = state.orders.map(order => 
        `${order.name || 'Order'} - ${order.current_status || order.status_code || 'Status unknown'}`
      ).join('\n');
      
      // Get transcript from SessionManager or DOM
      let transcript = '';
      try {
        if (typeof SessionManager !== 'undefined' && SessionManager.getTranscript) {
          transcript = await SessionManager.getTranscript(10000);
        }
        if (!transcript) {
          const transcriptEl = document.getElementById('rawTranscript');
          if (transcriptEl) transcript = transcriptEl.value || '';
        }
      } catch(_e) {}

      // NEW: Get current draft note from Note module's editable area
      let draftNote = '';
      try {
        const el = document.getElementById('feedbackReply');
        if (el && typeof el.innerText === 'string') draftNote = el.innerText;
      } catch(_e) {}

      // Build instruction + example and data payload
      const prompt = `You are given the current visit transcript, a draft progress note from the visit, and a list of current active orders (e.g. for labs, meds, imaging) already in the chart.
Your job is to carefully review the transcript and draft note to identify any new action items that were explicitly discussed and should be
added to the checklist, as well as any existing items that have been completed and should be marked as done. Use the list of current orders to identify
if any items have been completed.

!Important!: Only include items that were explicitly mentioned by the provider as needing to be done or having been done. Do not infer or assume any tasks
      
Format your response as a markdown checklist, with each item on its own line starting with "- [ ]" for incomplete items or "- [x]" for completed items. 
Do not include any additional commentary or explanation, just the checklist. If no items are identified, respond with "No changes to checklist."

Here is an example:
- [ ] Order aspirin
- [X] Decrease losartan to 25 mg
- [ ] Order CT chest for nodules
- [ ] Call patient in one week to check in

Here is the data to analyze:

Current Checklist:
${currentChecklist || 'No current checklist items'}

Current Orders:
${currentOrders || 'No current orders'}

Visit Transcript:
${transcript || 'No transcript available'}

Current Draft Note:
${draftNote || 'No draft note available'}`;

      // Send to LLM
      const response = await fetch('/scribe/chat_feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': window.getCsrfToken ? window.getCsrfToken() : ''
        },
        body: JSON.stringify({ 
          messages: [
            { role: 'system', content: 'You are a clinical assistant helping to maintain an accurate checklist.' },
            { role: 'user', content: prompt }
          ]
        })
      });
      
      if (!response.ok) {
        console.warn('Failed to get LLM response for checklist update');
        if (checklistContainer && originalContent) {
          checklistContainer.innerHTML = originalContent;
        }
        return;
      }
      
      const data = await response.json();
      const llmReply = data.reply || '';
      
      // Parse the LLM response to update checklist
      await parseAndUpdateChecklist(llmReply);

      // NEW: After LLM updates, auto-reconcile with orders to cross out placed items
      reconcileChecklistWithOrders();
      
    } catch (error) {
      console.warn('Error updating checklist with LLM:', error);
      // Restore original content on error
      const checklistContainer = containerRef?.querySelector('#checklist-items');
      if (checklistContainer && state.checklist.length === 0) {
        checklistContainer.innerHTML = '<div class="checklist-empty">No checklist items. Add one below.</div>';
      } else if (containerRef) {
        renderChecklist(containerRef);
      }
    }
  }

  async function parseAndUpdateChecklist(llmResponse) {
    try {
      // Debug: inspect raw LLM output (visible in DevTools console)
      try { console.debug('LLM checklist reply:\n', llmResponse); } catch(_e) {}

      // Parse the LLM response for checklist items
      const lines = llmResponse.split('\n').filter(line => line.trim());
      const newChecklist = [];
      let matchedAny = false;

      for (const line of lines) {
        const trimmed = line.trim();
        // Accept optional Markdown bullet before the checkbox and tolerate spaces/case in the checkbox
        // Examples matched:
        //   [ ] Order aspirin
        //   - [x] Decrease losartan
        //   * [ X ] Call patient
        const match = trimmed.match(/^\s*(?:[-*]\s*)?\[\s*([xX ])\s*\]\s*(.+?)\s*$/);
        if (match) {
          matchedAny = true;
          const completed = /x/i.test(match[1]);
          const text = match[2].trim();
          if (!text) continue;

          // Find existing item with same text or create new one
          const existingItem = state.checklist.find(item =>
            String(item.text || '').toLowerCase().trim() === text.toLowerCase().trim()
          );

          if (existingItem) {
            // Update existing item
            existingItem.completed = completed;
          } else {
            // Create new item
            const newItem = {
              id: generateChecklistId(),
              text: text,
              completed: completed,
              createdAt: Date.now()
            };
            newChecklist.push(newItem);
          }
        }
      }

      // If nothing matched the strict task format, try a lenient fallback for lines like "- Order aspirin"
      if (!matchedAny) {
        for (const line of lines) {
          const m = line.trim().match(/^\s*(?:[-*]\s+)(.+)$/);
          if (m && m[1]) {
            const text = m[1].trim();
            if (!text) continue;
            const exists = state.checklist.some(item => String(item.text||'').toLowerCase().trim() === text.toLowerCase().trim());
            if (!exists) {
              newChecklist.push({ id: generateChecklistId(), text, completed: false, createdAt: Date.now() });
            }
          }
        }
      }

      // Add new items to the checklist
      if (newChecklist.length) state.checklist.push(...newChecklist);

      // Save and re-render
      saveChecklistToSession();
      if (containerRef) {
        renderChecklist(containerRef);
      }

    } catch (error) {
      console.warn('Error parsing LLM checklist response:', error);
    }
  }

  function generateChecklistId(){
    return 'item_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }
  function addChecklistItem(text){
    const item = {
      id: generateChecklistId(),
      text: text.trim(),
      completed: false,
      createdAt: Date.now()
    };
    state.checklist.push(item);
    saveChecklistToSession();
    return item;
  }

  function updateChecklistItem(id, updates){
    const index = state.checklist.findIndex(item => item.id === id);
    if(index >= 0){
      state.checklist[index] = { ...state.checklist[index], ...updates };
      saveChecklistToSession();
      return state.checklist[index];
    }
    return null;
  }

  function deleteChecklistItem(id){
    const index = state.checklist.findIndex(item => item.id === id);
    if(index >= 0){
      state.checklist.splice(index, 1);
      saveChecklistToSession();
      return true;
    }
    return false;
  }

  function reorderChecklist(fromIndex, toIndex){
    if(fromIndex < 0 || fromIndex >= state.checklist.length || toIndex < 0 || toIndex >= state.checklist.length) return;
    const item = state.checklist.splice(fromIndex, 1)[0];
    state.checklist.splice(toIndex, 0, item);
    saveChecklistToSession();
  }

  async function loadData(days, status, otype){
    const d = days!=null? days : state.days;
    const st = status || state.status || 'current';
    const tp = otype || state.otype || 'all';
    const url = `/fhir/orders/${encodeURIComponent(st)}/${encodeURIComponent(tp)}/${encodeURIComponent(d)}`;
    const data = await jget(url).catch(err=>{ throw err; });
    state.orders = Array.isArray(data)? data : (data && Array.isArray(data.orders)? data.orders : []);
    state.days = d; state.status = st; state.otype = tp;

    // After state.orders is set, auto-reconcile checklist with placed orders
    try{ reconcileChecklistWithOrders(); }catch(_e){}

    return state.orders;
  }

  function groupByType(list){
    const groups = {};
    (list||[]).forEach(o=>{ const t = (o && o.type) ? String(o.type) : 'other'; const key=t.toLowerCase(); if(!groups[key]) groups[key]=[]; groups[key].push(o); });
    Object.values(groups).forEach(arr=> arr.sort((a,b)=> String(b.date||'').localeCompare(String(a.date||''))));
    return groups;
  }

  function buildOrderItem(o){
    const li = document.createElement('li'); li.className='todo-order'; li.tabIndex = 0; li.setAttribute('role','button'); li.setAttribute('aria-expanded','false');
    const top = document.createElement('div'); top.className='todo-order-top';
    const left = document.createElement('div'); left.className='todo-order-main';
    const dt = document.createElement('span'); dt.className='todo-order-date'; dt.textContent = fmtDateOnly(o.date || o.fm_date || '');
    const nm = document.createElement('span'); nm.className='todo-order-name'; nm.textContent = o.name || 'Order';
    left.appendChild(dt); left.appendChild(document.createTextNode(' ')); left.appendChild(nm);
    const right = document.createElement('div'); right.className='todo-order-status';
    const st = document.createElement('span'); st.className='status-chip'; st.textContent = o.current_status || o.status_code || ''; right.appendChild(st);
    top.appendChild(left); top.appendChild(right);

    const details = document.createElement('div'); details.className='todo-order-details'; details.style.display='none';
    const rows = [];
    if(o.instructions) rows.push({ label:'Instructions', val:o.instructions });
    if(o.sig) rows.push({ label:'Sig', val:o.sig });
    if(o.indication) rows.push({ label:'Indication', val:o.indication });
    if(rows.length===0) rows.push({ label:'', val:'No additional details' });
    for(const r of rows){ const line=document.createElement('div'); line.className='todo-detail-row'; line.innerHTML = r.label? `<strong>${r.label}:</strong> ${String(r.val)}` : String(r.val); details.appendChild(line); }

    function toggle(open){ const isOpen = open==null? details.style.display==='none' : !!open; details.style.display = isOpen? 'block':'none'; li.setAttribute('aria-expanded', isOpen? 'true':'false'); }
    li.addEventListener('click', (e)=>{ e.stopPropagation(); toggle(); });
    li.addEventListener('keydown', (e)=>{ if(e.key==='Enter' || e.key===' '){ e.preventDefault(); toggle(); } });

    li.appendChild(top); li.appendChild(details);
    return li;
  }

  function renderGroups(mount, groups){
    mount.innerHTML='';
    const keys = Object.keys(groups).sort();
    if(!keys.length){ mount.innerHTML = '<div class="module-empty">No orders match the current filters.</div>'; return 0; }
    let total=0;
    for(const key of keys){ const arr = groups[key]||[]; total += arr.length; const det = document.createElement('details'); det.open = true; det.className='todo-group'; const sum=document.createElement('summary'); sum.className='vital-line'; const label = titleCase(key); sum.innerHTML = `${label} <span class="badge">${arr.length}</span>`; det.appendChild(sum); const ul=document.createElement('ul'); ul.className='vital-reads'; arr.forEach(o=> ul.appendChild(buildOrderItem(o))); det.appendChild(ul); mount.appendChild(det); }
    return total;
  }
  function updateTabCount(container, count){
    try{
      const contentEl = container.closest('.tab-content'); if(!contentEl) return;
      const pane = container.closest('.workspace-pane'); if(!pane) return;
      const tabBar = pane.querySelector('.tab-bar'); if(!tabBar) return;
      const tab = tabBar.querySelector(`.tab[data-tab-id="${contentEl.dataset.tabId}"]`); if(!tab) return;
      const labelEl = tab.querySelector('.tab-label'); if(!labelEl) return;
      const base = tab.dataset.baseLabel || labelEl.textContent.replace(/\s*\(.*\)$/,'');
      tab.dataset.baseLabel = base;
      labelEl.textContent = count>0? `${base} (${count})` : base;
    }catch(_e){}
  }

  function buildChecklistItem(item, index){
    const li = document.createElement('li');
    li.className = 'checklist-item';
    li.draggable = true;
    li.dataset.itemId = item.id;
    li.dataset.index = index;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'checklist-checkbox';
    checkbox.checked = item.completed;
    checkbox.addEventListener('change', ()=>{
      updateChecklistItem(item.id, { completed: checkbox.checked });
      text.classList.toggle('completed', checkbox.checked);
    });

    const text = document.createElement('span');
    text.className = 'checklist-text';
    text.textContent = item.text;
    text.classList.toggle('completed', item.completed);
    text.contentEditable = true;
    text.addEventListener('blur', ()=>{
      const newText = text.textContent.trim();
      if(newText && newText !== item.text){
        updateChecklistItem(item.id, { text: newText });
        item.text = newText;
      } else if(!newText){
        text.textContent = item.text;
      }
    });
    text.addEventListener('keydown', (e)=>{
      if(e.key === 'Enter'){
        e.preventDefault();
        text.blur();
      }
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'checklist-delete';
    deleteBtn.innerHTML = '×';
    deleteBtn.title = 'Delete item';
    deleteBtn.addEventListener('click', ()=>{
      if(deleteChecklistItem(item.id)){
        renderChecklist(containerRef);
      }
    });

    const dragHandle = document.createElement('span');
    dragHandle.className = 'checklist-drag-handle';
    dragHandle.innerHTML = '⋮⋮';
    dragHandle.title = 'Drag to reorder';

    li.appendChild(dragHandle);
    li.appendChild(checkbox);
    li.appendChild(text);
    li.appendChild(deleteBtn);

    // Drag and drop functionality
    li.addEventListener('dragstart', (e)=>{
      e.dataTransfer.setData('text/plain', index.toString());
      li.classList.add('dragging');
    });

    li.addEventListener('dragend', ()=>{
      li.classList.remove('dragging');
    });

    li.addEventListener('dragover', (e)=>{
      e.preventDefault();
      const dragging = document.querySelector('.checklist-item.dragging');
      if(dragging && dragging !== li){
        const rect = li.getBoundingClientRect();
        const midpoint = rect.top + rect.height / 2;
        if(e.clientY < midpoint){
          li.classList.add('drag-over-top');
          li.classList.remove('drag-over-bottom');
        } else {
          li.classList.add('drag-over-bottom');
          li.classList.remove('drag-over-top');
        }
      }
    });

    li.addEventListener('dragleave', ()=>{
      li.classList.remove('drag-over-top', 'drag-over-bottom');
    });

    li.addEventListener('drop', (e)=>{
      e.preventDefault();
      li.classList.remove('drag-over-top', 'drag-over-bottom');
      
      const fromIndex = parseInt(e.dataTransfer.getData('text/plain'));
      const toIndex = index;
      
      if(fromIndex !== toIndex){
        const rect = li.getBoundingClientRect();
        const midpoint = rect.top + rect.height / 2;
        const actualToIndex = e.clientY < midpoint ? toIndex : toIndex + 1;
        
        reorderChecklist(fromIndex, actualToIndex > fromIndex ? actualToIndex - 1 : actualToIndex);
        renderChecklist(containerRef);
      }
    });

    return li;
  }

  function renderChecklist(container){
    const checklistContainer = container.querySelector('#checklist-items');
    if(!checklistContainer) return;

    checklistContainer.innerHTML = '';
    
    if(state.checklist.length === 0){
      checklistContainer.innerHTML = '<div class="checklist-empty">No checklist items. Add one below.</div>';
      return;
    }

    const ul = document.createElement('ul');
    ul.className = 'checklist-list';
    
    state.checklist.forEach((item, index) => {
      ul.appendChild(buildChecklistItem(item, index));
    });
    
    checklistContainer.appendChild(ul);
  }
  function bindEvents(container){
    const selDays = container.querySelector('#todo-days');
    const selStatus = container.querySelector('#todo-status');
    const selType = container.querySelector('#todo-type');
    const btn = container.querySelector('#todo-refresh');
    const addItemInput = container.querySelector('#checklist-add-input');
    const addItemBtn = container.querySelector('#checklist-add-btn');    const reload = async ()=>{
      try{
        await loadData(state.days, state.status, state.otype);
        const content=container.querySelector('#todo-content');
        const total = renderGroups(content, groupByType(state.orders));
        updateTabCount(container, total);
        
        // After loading orders, update checklist with LLM intelligence
        await updateChecklistWithLLM();
        
      }catch(e){
        const content=container.querySelector('#todo-content');
        content.innerHTML = `<div class="module-error">Failed to load orders (${e && e.message? e.message:'error'}).</div>`;
        updateTabCount(container, 0);
      }
    };

    // Existing event handlers
    if(selDays && !selDays._bound){ selDays._bound=true; selDays.addEventListener('change', async (e)=>{ const v = Number(e.target.value||7); save('workspace.todo.days', v); state.days=v; await reload(); }); }
    if(selStatus && !selStatus._bound){ selStatus._bound=true; selStatus.addEventListener('change', async (e)=>{ const v = String(e.target.value||'current'); save('workspace.todo.status', v); state.status=v; await reload(); }); }
    if(selType && !selType._bound){ selType._bound=true; selType.addEventListener('change', async (e)=>{ const v = String(e.target.value||'all'); save('workspace.todo.type', v); state.otype=v; await reload(); }); }
    if(btn && !btn._bound){ 
      btn._bound=true; 
      btn.addEventListener('click', async ()=>{ 
        btn.disabled=true; 
        const originalText = btn.textContent;
        btn.textContent = 'Refreshing...';
        
        try{ 
          await reload(); 
        } finally { 
          btn.disabled=false; 
          btn.textContent = originalText;
        } 
      }); 
    }

    // Checklist event handlers
    if(addItemBtn && !addItemBtn._bound){
      addItemBtn._bound = true;
      const addItem = ()=>{
        const text = addItemInput.value.trim();
        if(text){
          addChecklistItem(text);
          addItemInput.value = '';
          renderChecklist(container);
        }
      };
      addItemBtn.addEventListener('click', addItem);
    }

    if(addItemInput && !addItemInput._bound){
      addItemInput._bound = true;
      addItemInput.addEventListener('keydown', (e)=>{
        if(e.key === 'Enter'){
          e.preventDefault();
          const text = addItemInput.value.trim();
          if(text){
            addChecklistItem(text);
            addItemInput.value = '';
            renderChecklist(container);
          }
        }
      });
    }
  }  async function render(container, options){
    containerRef = container;
    const days = Number(readSaved('workspace.todo.days', 7));
    const status = String(readSaved('workspace.todo.status', 'current'));
    const otype = String(readSaved('workspace.todo.type', 'all'));
    state.days = (days===1||days===7||days===90)? days : 7;
    state.status = ['current','active','pending','all'].includes(status)? status : 'current';
    state.otype = ['all','labs','meds'].includes(otype)? otype : 'all';
    // Initialize empty checklist if not already set
    if(!Array.isArray(state.checklist)){
      state.checklist = [];
    }

    container.innerHTML = `
      <div class="todo-module">
        <div class="module-header">
          <h3>To Do</h3>
          <div class="labs-controls todo-controls">
            <label for="todo-status" class="sr-only">Status</label>
            <select id="todo-status" aria-label="Status">
              <option value="current" ${state.status==='current'?'selected':''}>Current</option>
              <option value="active" ${state.status==='active'?'selected':''}>Active</option>
              <option value="pending" ${state.status==='pending'?'selected':''}>Pending</option>
              <option value="all" ${state.status==='all'?'selected':''}>All</option>
            </select>
            <label for="todo-type" class="sr-only">Type</label>
            <select id="todo-type" aria-label="Type">
              <option value="all" ${state.otype==='all'?'selected':''}>All types</option>
              <option value="labs" ${state.otype==='labs'?'selected':''}>Labs</option>
              <option value="meds" ${state.otype==='meds'?'selected':''}>Meds</option>
            </select>
            <label for="todo-days" class="sr-only">Time window</label>
            <select id="todo-days" aria-label="Time window">
              <option value="1" ${state.days===1?'selected':''}>1 day</option>
              <option value="7" ${state.days===7?'selected':''}>7 days</option>
              <option value="90" ${state.days===90?'selected':''}>90 days</option>
            </select>
            <button id="todo-refresh" class="refresh-btn" title="Refresh">Refresh</button>
          </div>
        </div>
        
        <div class="checklist-section">
          <div class="checklist-header">
            <h4>Visit Checklist</h4>
          </div>
          <div id="checklist-items" class="checklist-container">
            <div class="checklist-empty">Loading checklist...</div>
          </div>
          <div class="checklist-add">
            <input type="text" id="checklist-add-input" placeholder="Add new item..." class="checklist-input">
            <button id="checklist-add-btn" class="checklist-add-button">Add</button>
          </div>
        </div>
        
        <div class="orders-section">
          <div class="orders-header">
            <h4>Current Orders</h4>
          </div>
          <div id="todo-content" class="todo-content">
            <div class="module-loading">Loading orders…</div>
          </div>
        </div>
      </div>
    `;

    // Render checklist immediately
    renderChecklist(container);

    // Ensure patient context
    let dfn = _dfn();
    if(!dfn){
      const cont = container.querySelector('#todo-content');
      cont.innerHTML = '<div class="module-empty">Select a patient to view orders.</div>';
      updateTabCount(container, 0);
      bindEvents(container);
      return;
    }

    try{
      await loadData(state.days, state.status, state.otype);
      const content = container.querySelector('#todo-content');
      const total = renderGroups(content, groupByType(state.orders));
      updateTabCount(container, total);
    }catch(e){
      const content = container.querySelector('#todo-content');
      content.innerHTML = `<div class="module-error">Failed to load orders (${e && e.message? e.message:'error'}).</div>`;
      updateTabCount(container, 0);
    }
    bindEvents(container);
  }
  function refresh(){ if(containerRef){ render(containerRef); } }
  function destroy(){ cancelAll(); containerRef=null; }

  window.WorkspaceModules = window.WorkspaceModules || {};
  window.WorkspaceModules[MODULE_NAME] = { 
    render, 
    refresh, 
    destroy,
    getChecklistData,
    setChecklistData
  };
})();