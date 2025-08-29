// Explore page Agent (Safe Modules) integration
// - Shows the Agent panel if SAFE_MODULES is enabled
// - Wires the Generate Plan button to POST /api/agent/plan with current patient DFN

function _q(id){ return document.getElementById(id); }

// Simple in-page debug console (non-PHI): logs only statuses and sizes
const AgentDebug = (function(){
  let box, area, copyBtn, clearBtn;
  function ts(){ const d=new Date(); return d.toLocaleTimeString(); }
  function ensure(){
    if(box) return;
    const panel = _q('agentPanel') || document.body;
    box = document.createElement('div');
    box.id = 'agentDebugBox';
    box.style.marginTop = '8px';
    box.style.border = '1px solid #e0e0e0';
    box.style.borderRadius = '6px';
    box.style.background = '#fafafa';
    box.style.padding = '6px';
    box.style.fontSize = '12px';
    const hdr = document.createElement('div');
    hdr.style.display = 'flex';
    hdr.style.justifyContent = 'space-between';
    hdr.style.alignItems = 'center';
    const title = document.createElement('strong');
    title.textContent = 'Agent Debug Log';
    const btns = document.createElement('div');
    copyBtn = document.createElement('button'); copyBtn.textContent = 'Copy'; copyBtn.style.marginRight = '6px';
    clearBtn = document.createElement('button'); clearBtn.textContent = 'Clear';
    btns.appendChild(copyBtn); btns.appendChild(clearBtn);
    hdr.appendChild(title); hdr.appendChild(btns);
    area = document.createElement('textarea');
    area.readOnly = true; area.style.width = '100%'; area.style.height = '120px'; area.style.marginTop = '6px'; area.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
    box.appendChild(hdr); box.appendChild(area);
    panel.appendChild(box);
    copyBtn.addEventListener('click', async () => { try{ await navigator.clipboard.writeText(area.value); copyBtn.textContent = 'Copied'; setTimeout(()=>copyBtn.textContent='Copy', 1000); }catch{} });
    clearBtn.addEventListener('click', () => { area.value=''; });
  }
  function log(msg){ ensure(); try{ area.value += `[${ts()}] ${msg}\n`; area.scrollTop = area.scrollHeight; }catch{} }
  return { log };
})();
// Make AgentDebug available globally for other scripts
try { window.AgentDebug = AgentDebug; } catch {}

// LLM conversation trace UI (debug)
const LLMTrace = (function(){
  let box, list, clearBtn;
  function ensure(){
    if(box && list) return;
    box = _q('agentLLMTraceBox');
    if(!box){
      const panel = _q('agentPanel') || document.body;
      box = document.createElement('div');
      box.id = 'agentLLMTraceBox';
      box.className = 'panel';
      box.style.marginTop = '10px';
      panel.appendChild(box);
    }
    box.innerHTML = '';
    const titleRow = document.createElement('div');
    titleRow.style.display = 'flex';
    titleRow.style.justifyContent = 'space-between';
    titleRow.style.alignItems = 'center';
    const lbl = document.createElement('label');
    lbl.textContent = 'LLM conversation (debug)';
    lbl.style.fontWeight = 'bold';
    clearBtn = document.createElement('button');
    clearBtn.id = 'agentLLMTraceClearBtn';
    clearBtn.textContent = 'Clear';
    titleRow.appendChild(lbl);
    titleRow.appendChild(clearBtn);
    list = document.createElement('div');
    list.id = 'agentLLMTraceList';
    list.style.marginTop = '6px';
    list.style.background = '#fff';
    list.style.border = '1px solid #e5e5e5';
    list.style.borderRadius = '6px';
    list.style.padding = '8px';
    list.style.maxHeight = '240px';
    list.style.overflowY = 'auto';
    box.appendChild(titleRow);
    box.appendChild(list);
    clearBtn.addEventListener('click', () => { try{ list.innerHTML = ''; }catch{} });
  }
  function bubble(role, content){
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.margin = '6px 0';
    const b = document.createElement('div');
    b.style.maxWidth = '80%';
    b.style.whiteSpace = 'pre-wrap';
    b.style.wordBreak = 'break-word';
    b.style.padding = '6px 8px';
    b.style.borderRadius = '10px';
    b.style.border = '1px solid #e0e0e0';
    const meta = document.createElement('div');
    meta.style.fontSize = '11px';
    meta.style.color = '#666';
    meta.style.marginBottom = '4px';
    meta.textContent = role;
    const body = document.createElement('div');
    body.textContent = typeof content === 'string' ? content : (content ? JSON.stringify(content, null, 2) : '');
    b.appendChild(meta);
    b.appendChild(body);
    if(role === 'assistant'){
      row.style.justifyContent = 'flex-start';
      b.style.background = '#f5faff';
    } else if(role === 'system'){
      row.style.justifyContent = 'center';
      b.style.background = '#fafafa';
    } else { // user
      row.style.justifyContent = 'flex-end';
      b.style.background = '#f9fff5';
    }
    row.appendChild(b);
    return row;
  }
  function addTrace(trace){
    try{
      ensure();
      const stage = trace?.stage || 'unknown';
      const header = document.createElement('div');
      header.style.textAlign = 'center';
      header.style.fontSize = '12px';
      header.style.color = '#555';
      header.style.margin = '4px 0';
      header.textContent = `— ${stage.toUpperCase()} —` + (trace.used_stub ? ' (stub)' : '');
      list.appendChild(header);
      const msgs = Array.isArray(trace?.messages) ? trace.messages : [];
      msgs.forEach(m => { list.appendChild(bubble(m.role || 'system', m.content || '')); });
      if(trace?.response_content){ list.appendChild(bubble('assistant', trace.response_content)); }
      list.scrollTop = list.scrollHeight;
    }catch{}
  }
  return { addTrace, ensure, clear: () => { try{ ensure(); list.innerHTML='' }catch{} } };
})();
try { window.LLMTrace = LLMTrace; } catch {}

async function getCurrentPatientId() {
  try {
    const res = await fetch('/get_patient', { headers: { 'Accept': 'application/json' } });
    if (!res.ok) return null;
    const meta = await res.json();
    return (meta && meta.dfn) ? String(meta.dfn) : null;
  } catch {
    return null;
  }
}

async function generatePlan() {
  const btn = _q('agentGeneratePlanBtn');
  const statusEl = _q('agentStatus');
  const out = _q('agentPlanOutput');
  const queryEl = _q('agentQuery');
  if (!btn || !out) return;
  const query = (queryEl?.value || '').trim();
  AgentDebug.log('Planning…');
  btn.disabled = true;
  statusEl.textContent = 'Planning…';
  out.textContent = '';
  try {
    const patient_id = await getCurrentPatientId() || 'demo';
    const res = await fetch('/api/agent/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, patient_id, debug: true })
    });
    if (res.status === 403) {
      statusEl.textContent = 'Agent disabled by server feature flag.';
      AgentDebug.log('Plan failed: feature disabled');
      return;
    }
    const data = await res.json();
    if (!res.ok || data.error) {
      statusEl.textContent = 'Plan error: ' + (data.error || res.status);
      out.textContent = (data.detail || JSON.stringify(data, null, 2));
      AgentDebug.log(`Plan error: ${data.error || res.status}`);
      return;
    }
    statusEl.textContent = 'Plan ready.';
    out.textContent = JSON.stringify(data, null, 2);
    if(data && data.llm_trace){ try{ LLMTrace.addTrace(data.llm_trace); }catch{} }
    AgentDebug.log('Plan OK');
    const approveBtn = _q('agentApproveRunBtn'); if(approveBtn) approveBtn.disabled = false;
    const renderBtn = _q('agentRenderBtn'); if(renderBtn) renderBtn.disabled = true; // wait until datasets
  } catch (e) {
    statusEl.textContent = 'Network error creating plan.';
    out.textContent = String(e);
    AgentDebug.log('Plan network error');
  } finally {
    btn.disabled = false;
  }
}

async function approveAndRun(){
  const statusEl = _q('agentStatus');
  const planOut = _q('agentPlanOutput');
  const datasetsOut = _q('agentDatasetsOutput');
  if(!planOut){ return; }
  let plan;
  try{ plan = JSON.parse(planOut.textContent || planOut.innerText || '{}'); }catch(e){
    if(statusEl) statusEl.textContent = 'Invalid plan JSON. Generate a plan first.';
    AgentDebug.log('Execute skipped: invalid plan JSON');
    return;
  }
  // Strip debug-only fields not allowed by schema
  try{ if(plan && typeof plan === 'object'){ delete plan.llm_trace; } }catch{}
  const btn = _q('agentApproveRunBtn');
  if(btn) btn.disabled = true;
  if(statusEl) statusEl.textContent = 'Executing plan…';
  AgentDebug.log('Executing plan…');
  try{
    const res = await fetch('/api/agent/execute-plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan })
    });
    const data = await res.json();
    if(res.status === 403){ if(statusEl) statusEl.textContent = 'Agent disabled by server feature flag.'; AgentDebug.log('Execute failed: feature disabled'); return; }
    if(!res.ok || data.error){
      if(statusEl) statusEl.textContent = 'Execute error: ' + (data.error || res.status);
      if(datasetsOut) datasetsOut.textContent = (data.detail || JSON.stringify(data, null, 2));
      AgentDebug.log(`Execute error: ${data.error || res.status}`);
      return;
    }
    // Keep last state for render step
    window._agentLastPlan = plan;
    window._agentLastDatasets = data.datasets || {};
    window._agentLastMeta = data.meta || {};
    if(datasetsOut){ datasetsOut.textContent = JSON.stringify({ sizes: data.meta?.sizes, truncated: data.meta?.truncated }, null, 2); }
    if(statusEl) statusEl.textContent = 'Datasets ready.';
    const sizes = data.meta?.sizes ? JSON.stringify(data.meta.sizes) : '{}';
    AgentDebug.log(`Datasets ready. Sizes=${sizes}`);
    const renderBtn = _q('agentRenderBtn'); if(renderBtn) renderBtn.disabled = false;
  }catch(e){
    if(statusEl) statusEl.textContent = 'Network error executing plan.';
    if(datasetsOut) datasetsOut.textContent = String(e);
    AgentDebug.log('Execute network error');
  }finally{
    if(btn) btn.disabled = false;
  }
}

async function renderFromPlan(){
  const statusEl = _q('agentStatus');
  const codeIn = _q('agentRenderCodeInput');
  const infoOut = _q('agentRenderInfo');
  const mount = _q('agentRenderMount');
  const plan = window._agentLastPlan;
  const datasets = window._agentLastDatasets;
  if(!plan){ if(statusEl) statusEl.textContent = 'No plan. Generate and execute first.'; AgentDebug.log('Render skipped: no plan'); return; }
  if(!datasets){ if(statusEl) statusEl.textContent = 'No datasets. Approve & Run first.'; AgentDebug.log('Render skipped: no datasets'); return; }
  const btn = _q('agentRenderBtn'); if(btn) btn.disabled = true;
  if(statusEl) statusEl.textContent = 'Requesting render code…';
  AgentDebug.log('Requesting render code…');
  try{
    const res = await fetch('/api/agent/render', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ datasets, render_spec: plan.render_spec, debug: true })
    });
    const data = await res.json();
    if(res.status === 403){ if(statusEl) statusEl.textContent = 'Agent disabled by server feature flag.'; AgentDebug.log('Render failed: feature disabled'); return; }
    if(!res.ok || data.error){
      if(statusEl) statusEl.textContent = 'Render endpoint error: ' + (data.error || res.status);
      if(codeIn) codeIn.value = (data.detail || JSON.stringify(data, null, 2));
      AgentDebug.log(`Render endpoint error: ${data.error || res.status}`);
      return;
    }
    if(data && data.llm_trace){ try{ LLMTrace.addTrace(data.llm_trace); }catch{} }
    const code = data.render_code || '';
    if(codeIn){ codeIn.value = code; }
    if(infoOut){ infoOut.textContent = data.explanatory_text || ''; }

    // Persist last render code for Save action
    window._agentLastRenderCode = code;

    // Static checks before sandbox execution
    const chk = (window.AgentStaticChecks && window.AgentStaticChecks.validate) ? window.AgentStaticChecks.validate(code) : { ok:true, errors:[] };
    if(!chk.ok){
      if(statusEl) statusEl.textContent = 'Static checks failed.';
      const msg = 'Static check errors: ' + (chk.errors||[]).join('; ');
      if(infoOut) infoOut.textContent = msg;
      AgentDebug.log(msg);
      if(mount) mount.innerHTML = '';
      return;
    } else {
      AgentDebug.log('Static checks OK');
    }

    // Ensure sandbox runtime is available
    const runner = (window.AgentSandboxRunner && typeof window.AgentSandboxRunner.run === 'function') ? window.AgentSandboxRunner : null;
    if(!runner){
      if(statusEl) statusEl.textContent = 'Sandbox runtime not available.';
      if(infoOut) infoOut.textContent = 'Missing /static/agent/SandboxRunner.js or script error. Check console/network tab.';
      AgentDebug.log('Sandbox runtime missing');
      return;
    }

    if(statusEl) statusEl.textContent = 'Executing in sandbox…';
    if(mount) mount.innerHTML = '';
    AgentDebug.log('Sandbox executing…');
    const result = await runner.run({ code, datasets, mount, timeoutMs: 3000 });
    if(result && result.ok){
      if(statusEl) statusEl.textContent = 'Rendered successfully.';
      AgentDebug.log('Sandbox OK');
      const saveBtn = _q('agentSaveModuleBtn'); if(saveBtn) saveBtn.disabled = false;
    } else {
      if(statusEl) statusEl.textContent = 'Sandbox error.';
      const err = (result?.error || 'Unknown error');
      if(infoOut) infoOut.textContent = 'Sandbox error: ' + err;
      AgentDebug.log('Sandbox error: ' + err);
    }
  }catch(e){
    if(statusEl) statusEl.textContent = 'Error during render.';
    if(codeIn) codeIn.value = String(e);
    AgentDebug.log('Render exception');
    console.error('[Agent render error]', e);
  }finally{
    if(btn) btn.disabled = false;
  }
}

async function runSavedModule(module_id){
  const statusEl = _q('agentStatus');
  const codeIn = _q('agentRenderCodeInput');
  const infoOut = _q('agentRenderInfo');
  const mount = _q('agentRenderMount');
  if(!module_id){ return; }
  if(statusEl) statusEl.textContent = 'Running saved module…';
  if(mount) mount.innerHTML = '';
  try{
    const patient_id = await getCurrentPatientId() || 'demo';
    const res = await fetch('/api/agent/modules/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ module_id, patient_id })
    });
    const data = await res.json();
    if(res.status === 403){ if(statusEl) statusEl.textContent = 'Agent disabled by server feature flag.'; return; }
    if(!res.ok || data.error){
      if(statusEl) statusEl.textContent = 'Run error: ' + (data.error || res.status);
      if(infoOut) infoOut.textContent = data.detail || '';
      return;
    }
    const datasets = data.datasets || {};
    const code = (data.module && data.module.render_code) ? data.module.render_code : '';
    window._agentLastDatasets = datasets;
    window._agentLastRenderCode = code;
    if(codeIn) codeIn.value = code;
    const planHash = data.meta?.plan_hash || (data.module && data.module.plan_hash) || '';
    if(infoOut) infoOut.textContent = `Module ${module_id} • plan ${planHash}`;

    // Static checks then sandbox
    const chk = (window.AgentStaticChecks && window.AgentStaticChecks.validate) ? window.AgentStaticChecks.validate(code) : { ok:true, errors:[] };
    if(!chk.ok){
      if(statusEl) statusEl.textContent = 'Static checks failed.';
      if(infoOut) infoOut.textContent = 'Static check errors: ' + (chk.errors||[]).join('; ');
      return;
    }
    const result = await window.AgentSandboxRunner.run({ code, datasets, mount, timeoutMs: 3000 });
    if(result && result.ok){ if(statusEl) statusEl.textContent = 'Module ran successfully.'; }
    else { if(statusEl) statusEl.textContent = 'Sandbox error running module.'; }
  }catch(e){
    if(statusEl) statusEl.textContent = 'Network error running module.';
  }
}

async function testSandbox(){
  const statusEl = _q('agentStatus');
  const codeIn = _q('agentRenderCodeInput');
  const infoOut = _q('agentRenderInfo');
  const mount = _q('agentRenderMount');
  const runner = (window.AgentSandboxRunner && typeof window.AgentSandboxRunner.run === 'function') ? window.AgentSandboxRunner : null;
  if(!runner){ if(statusEl) statusEl.textContent = 'Sandbox runtime not available.'; return; }
  const code = "function render({container}){ const el=document.createElement('div'); el.style.padding='8px'; el.style.background='#e6f7ff'; el.textContent='Hello Sandbox!'; container.appendChild(el); }";
  const datasets = {};
  if(codeIn) codeIn.value = code;
  if(infoOut) infoOut.textContent = 'Minimal test render.';
  if(mount) mount.innerHTML = '';
  AgentDebug.log('Running minimal sandbox test…');
  if(statusEl) statusEl.textContent = 'Testing sandbox…';
  try{
    const result = await runner.run({ code, datasets, mount, timeoutMs: 3000, minimal: true });
    if(result && result.ok){ if(statusEl) statusEl.textContent = 'Minimal render OK.'; AgentDebug.log('Minimal render OK'); }
    else { if(statusEl) statusEl.textContent = 'Minimal render failed.'; AgentDebug.log('Minimal render failed: '+(result && result.error || 'unknown')); if(infoOut) infoOut.textContent = 'Sandbox error: '+(result && result.error || 'unknown'); }
  }catch(e){ if(statusEl) statusEl.textContent = 'Minimal render threw.'; AgentDebug.log('Minimal render exception'); }
}

// Run edited code from textarea
async function runEditedCode(){
  const statusEl = _q('agentStatus');
  const codeIn = _q('agentRenderCodeInput');
  const infoOut = _q('agentRenderInfo');
  const mount = _q('agentRenderMount');
  const datasets = window._agentLastDatasets || {};
  if(!codeIn){ return; }
  const code = (codeIn.value || '').trim();
  if(!code){ if(statusEl) statusEl.textContent = 'Nothing to run. Enter code first.'; return; }
  const chk = (window.AgentStaticChecks && window.AgentStaticChecks.validate) ? window.AgentStaticChecks.validate(code) : { ok:true, errors:[] };
  if(!chk.ok){ if(statusEl) statusEl.textContent = 'Static checks failed.'; if(infoOut) infoOut.textContent = 'Static check errors: ' + (chk.errors||[]).join('; '); return; }
  const runner = (window.AgentSandboxRunner && typeof window.AgentSandboxRunner.run === 'function') ? window.AgentSandboxRunner : null;
  if(!runner){ if(statusEl) statusEl.textContent = 'Sandbox runtime not available.'; return; }
  if(statusEl) statusEl.textContent = 'Executing edited code…';
  if(mount) mount.innerHTML = '';
  try{
    const result = await runner.run({ code, datasets, mount, timeoutMs: 3000 });
    if(result && result.ok){
      if(statusEl) statusEl.textContent = 'Edited code rendered.';
      window._agentLastRenderCode = code; // keep latest for saving
      const saveBtn = _q('agentSaveModuleBtn'); if(saveBtn) saveBtn.disabled = false;
    } else {
      if(statusEl) statusEl.textContent = 'Sandbox error.';
      if(infoOut) infoOut.textContent = 'Sandbox error: ' + (result && result.error || 'unknown');
    }
  }catch(e){ if(statusEl) statusEl.textContent = 'Error executing edited code.'; if(infoOut) infoOut.textContent = String(e); }
}

async function saveCurrentModule(){
  const statusEl = _q('agentStatus');
  const plan = window._agentLastPlan;
  const codeEl = _q('agentRenderCodeInput');
  const edited = (codeEl && codeEl.value) ? codeEl.value.trim() : '';
  const render_code = edited || window._agentLastRenderCode;
  if(!plan){ if(statusEl) statusEl.textContent = 'Nothing to save. Generate a plan first.'; AgentDebug.log('Save skipped: no plan'); return; }
  if(!render_code){ if(statusEl) statusEl.textContent = 'Nothing to save. Render code is empty.'; AgentDebug.log('Save skipped: no render_code'); return; }
  const defaultTitle = plan?.purpose || 'Untitled Module';
  let title = '';
  try { title = window.prompt('Module title', defaultTitle) || defaultTitle; } catch {}
  if(statusEl) statusEl.textContent = 'Saving module…';
  AgentDebug.log('Saving module…');
  const btn = _q('agentSaveModuleBtn'); if(btn) btn.disabled = true;
  try{
    const res = await fetch('/api/agent/modules/save', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan, render_code, title, approved_by_user: true })
    });
    const data = await res.json();
    if(res.status === 403){ if(statusEl) statusEl.textContent = 'Agent disabled by server feature flag.'; AgentDebug.log('Save failed: feature disabled'); return; }
    if(!res.ok || data.error){
      if(statusEl) statusEl.textContent = 'Save error: ' + (data.error || res.status);
      AgentDebug.log(`Save error: ${data.error || res.status}`);
      return;
    }
    if(statusEl) statusEl.textContent = 'Module saved.';
    AgentDebug.log('Module saved');
    await refreshSavedModules();
  }catch(e){
    if(statusEl) statusEl.textContent = 'Network error saving module.';
    AgentDebug.log('Save network error');
  }finally{
    if(btn) btn.disabled = false;
  }
}

function renderModulesList(items){
  const listEl = _q('agentSavedModulesList');
  if(!listEl) return;
  if(!Array.isArray(items) || items.length === 0){ listEl.innerHTML = '<em>No saved modules.</em>'; return; }
  const frag = document.createDocumentFragment();
  items.forEach(it => {
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.alignItems = 'center';
    row.style.justifyContent = 'space-between';
    row.style.padding = '4px 6px';
    row.style.borderBottom = '1px solid #e8eefc';
    const left = document.createElement('div');
    left.style.minWidth = '0';
    const when = it.updated_at || it.created_at || '';
    left.innerHTML = `<strong>${(it.title||'Untitled')}</strong><br><span style="font-size:0.85em;color:#666;">${when}</span>`;
    const right = document.createElement('div');
    const runBtn = document.createElement('button');
    runBtn.textContent = 'Run';
    runBtn.addEventListener('click', () => runSavedModule(it.id));
    right.appendChild(runBtn);
    row.appendChild(left);
    row.appendChild(right);
    frag.appendChild(row);
  });
  listEl.innerHTML = '';
  listEl.appendChild(frag);
}

async function refreshSavedModules(){
  const statusEl = _q('agentStatus');
  try{
    const res = await fetch('/api/agent/modules/list', { headers: { 'Accept': 'application/json' } });
    if(res.status === 403){ if(statusEl) statusEl.textContent = 'Agent disabled by server feature flag.'; AgentDebug.log('List failed: feature disabled'); return; }
    const data = await res.json();
    if(!res.ok || data.error){
      if(statusEl) statusEl.textContent = 'List error: ' + (data.error || res.status);
      AgentDebug.log(`List error: ${data.error || res.status}`);
      return;
    }
    renderModulesList(data.modules || []);
    AgentDebug.log(`Loaded saved modules: ${data.count ?? (data.modules?.length||0)}`);
  }catch(e){
    if(statusEl) statusEl.textContent = 'Network error listing modules.';
    AgentDebug.log('List network error');
  }
}

function initAgentPanel(){
  const panel = _q('agentPanel');
  if (!panel) return;
  const enabled = (typeof window !== 'undefined') && (window.SAFE_MODULES_ENABLED === true || window.SAFE_MODULES_ENABLED === 'true');
  if (!enabled) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';
  const genBtn = _q('agentGeneratePlanBtn');
  if (genBtn) {
    genBtn.disabled = false;
    genBtn.addEventListener('click', generatePlan);
  }
  const approveBtn = _q('agentApproveRunBtn');
  if(approveBtn){ approveBtn.addEventListener('click', approveAndRun); }
  const renderBtn = _q('agentRenderBtn');
  if(renderBtn){ renderBtn.addEventListener('click', renderFromPlan); }
  const saveBtn = _q('agentSaveModuleBtn');
  if(saveBtn){ saveBtn.addEventListener('click', saveCurrentModule); }
  const refreshBtn = _q('agentSavedModulesRefreshBtn');
  if(refreshBtn){ refreshBtn.addEventListener('click', refreshSavedModules); }
  const testBtn = _q('agentTestSandboxBtn');
  if(testBtn){
    try{ if(!window.SANDBOX_DEBUG) testBtn.style.display='none'; }catch{}
    testBtn.addEventListener('click', testSandbox);
  }
  const runCustomBtn = _q('agentRunCustomCodeBtn');
  if(runCustomBtn){ runCustomBtn.addEventListener('click', runEditedCode); }
  const codeEl = _q('agentRenderCodeInput');
  if(codeEl){ codeEl.addEventListener('input', () => { try{ window._agentLastRenderCode = codeEl.value; }catch{} }); }
  // LLM trace clear hookup if static HTML exists
  const traceClear = _q('agentLLMTraceClearBtn');
  if(traceClear){ try{ traceClear.addEventListener('click', () => LLMTrace.clear()); }catch{} }
  // Initial load of saved modules
  AgentDebug.log('Agent panel ready');
  refreshSavedModules();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAgentPanel, { once: true });
} else {
  initAgentPanel();
}