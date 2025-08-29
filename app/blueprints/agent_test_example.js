(function(global){
  'use strict';
  // Simple test helper for /api/agent endpoints. Usage in browser console:
  //   await AgentTest.fullFlow('diabetes summary', 'demo')
  // Or call individually, e.g.:
  //   const plan = await AgentTest.plan('diabetes', 'demo');
  //   const exec = await AgentTest.executePlan(plan);
  //   const rend = await AgentTest.render(exec.datasets, plan.render_spec);
  //   const saved = await AgentTest.save(plan, rend.render_code, 'My Test Module');
  //   const list = await AgentTest.list();
  //   const run  = await AgentTest.run(saved.module.id);

  const BASE = '/api/agent';

  async function http(path, opts){
    const o = Object.assign({
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin'
    }, opts||{});
    try{
      const res = await fetch(BASE + path, o);
      let data = null;
      try { data = await res.json(); } catch { data = null; }
      if(!res.ok){
        console.warn(`[AgentTest] ${path} -> HTTP ${res.status}`, data||res.statusText);
      }
      return { ok: res.ok, status: res.status, data };
    }catch(e){
      console.error(`[AgentTest] ${path} -> network error`, e);
      return { ok:false, status:0, data:{ error:'NETWORK_ERROR', detail: String(e) } };
    }
  }

  const AgentTest = {
    async plan(query='diabetes control snapshot', patient_id='demo'){
      const body = { query, patient_id };
      const r = await http('/plan', { method:'POST', body: JSON.stringify(body) });
      if(r.status === 403) console.warn('SAFE_MODULES_DISABLED: enable feature flag on server to test.');
      if(!r.ok) return null;
      console.log('[AgentTest.plan] plan:', r.data);
      return r.data;
    },

    async executePlan(plan){
      if(!plan){ console.warn('[AgentTest.executePlan] missing plan'); return null; }
      const r = await http('/execute-plan', { method:'POST', body: JSON.stringify({ plan }) });
      if(!r.ok) return null;
      console.log('[AgentTest.executePlan] meta:', r.data && r.data.meta);
      return r.data;
    },

    async render(datasets, render_spec){
      const body = { datasets: datasets||{}, render_spec: render_spec||{} };
      const r = await http('/render', { method:'POST', body: JSON.stringify(body) });
      if(!r.ok) return null;
      console.log('[AgentTest.render] explanatory_text:', r.data && r.data.explanatory_text);
      return r.data;
    },

    async save(plan, render_code, title){
      if(!plan || !render_code){ console.warn('[AgentTest.save] plan and render_code are required'); return null; }
      const t = title || `Test Module ${new Date().toISOString().slice(0,19).replace('T',' ')}`;
      const r = await http('/modules/save', { method:'POST', body: JSON.stringify({ plan, render_code, title: t, approved_by_user: true }) });
      if(!r.ok) return null;
      console.log('[AgentTest.save] saved module id:', r.data && r.data.module && r.data.module.id);
      return r.data;
    },

    async list(){
      const r = await http('/modules/list', { method:'GET' });
      if(!r.ok) return null;
      console.log(`[AgentTest.list] count=${r.data && r.data.count}`, r.data && r.data.modules);
      return r.data;
    },

    async run(module_id){
      if(!module_id){ console.warn('[AgentTest.run] module_id required'); return null; }
      const r = await http('/modules/run', { method:'POST', body: JSON.stringify({ module_id }) });
      if(!r.ok) return null;
      console.log('[AgentTest.run] meta:', r.data && r.data.meta);
      return r.data;
    },

    async fullFlow(query='diabetes control snapshot', patient_id='demo'){
      console.log('[AgentTest.fullFlow] starting…');
      const plan = await this.plan(query, patient_id);
      if(!plan) return null;
      const exec = await this.executePlan(plan);
      if(!exec) return { plan };
      const rend = await this.render(exec.datasets, plan.render_spec);
      if(!rend) return { plan, exec };
      const saved = await this.save(plan, rend.render_code, `Auto ${new Date().toISOString().slice(0,16)}`);
      const module_id = saved && saved.module && saved.module.id;
      const ran = module_id ? await this.run(module_id) : null;
      console.log('[AgentTest.fullFlow] done');
      return { plan, exec, rend, saved, ran };
    },

    async planNotesSearch(query='ACE inhibitor intolerance', patient_id='demo'){
      const plan = {
        schema_version: '1.0.0',
        purpose: `Retrieve supporting note excerpts for: ${query}`,
        budget: { rows: 100, bytes: 150000, timeout_ms: 4000 },
        data_requests: [
          { tool: 'get_notes_search_results', params: { patient_id, query, top_k: 8 } }
        ],
        render_spec: { tables: [], charts: [] },
        acceptance_criteria: [
          'Includes note_id and chunk text for each match',
          'Limit top_k to <= 8',
          'Respects row/byte/time budgets'
        ]
      };
      console.log('[AgentTest.planNotesSearch] plan:', plan);
      return plan;
    },

    async executeNotesSearchPlan(query='ACE inhibitor intolerance', patient_id='demo'){
      const plan = await this.planNotesSearch(query, patient_id);
      const r = await fetch('/api/agent/execute-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ plan })
      });
      const data = await r.json().catch(()=>null);
      if(!r.ok){ console.warn('[AgentTest.executeNotesSearchPlan] HTTP', r.status, data); return null; }
      console.log('[AgentTest.executeNotesSearchPlan] datasets:', data && data.datasets);
      return data;
    }
  };

  global.AgentTest = AgentTest;
  console.log('AgentTest helper ready. Try: await AgentTest.fullFlow()');
})(typeof window !== 'undefined' ? window : (globalThis||{}));

function render({ datasets, container, Tabulator, SimplePlots, Formatter }) {
  container.innerHTML = '';
  const root = document.createElement('div');
  root.style.fontFamily = 'system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif';
  root.style.padding = '8px';
  container.appendChild(root);

  const h = (t) => { const el = document.createElement('h3'); el.textContent = t; el.style.margin = '12px 0 6px'; return el; };
  const sec = (title) => { const s = document.createElement('section'); s.appendChild(h(title)); root.appendChild(s); return s; };

  const labs = Array.isArray(datasets.labs) ? datasets.labs : [];
  const vitals = Array.isArray(datasets.vitals) ? datasets.vitals : [];
  const meds = Array.isArray(datasets.meds) ? datasets.meds : [];
  const problems = Array.isArray(datasets.problems) ? datasets.problems : [];
  const notes = Array.isArray(datasets.notes) ? datasets.notes : [];
  const notesSearch = Array.isArray(datasets.notes_search_results) ? datasets.notes_search_results : [];

  const title = document.createElement('h2');
  title.textContent = 'Patient Snapshot';
  title.style.margin = '0 0 8px';
  root.appendChild(title);

  const a1c = labs
    .filter(r => String(r.code) === '4548-4' || /a1c|hemoglobin a1c/i.test(String(r.display||'')))
    .map(r => ({ x: r.effectiveDateTime, y: parseFloat(r.value) }))
    .filter(p => isFinite(p.y))
    .sort((a,b) => new Date(a.x) - new Date(b.x));
  if (a1c.length) {
    const s = sec('Hemoglobin A1c Trend');
    const mount = document.createElement('div');
    s.appendChild(mount);
    SimplePlots.line(mount, a1c);
  }

  if (labs.length) {
    const s = sec('Recent Labs');
    const mount = document.createElement('div');
    s.appendChild(mount);
    const rows = labs.slice(0, 15).map(r => ({
      Date: Formatter.date(r.effectiveDateTime),
      Test: r.display,
      Value: r.value,
      Unit: r.unit || '',
      Ref: r.referenceRange || '',
      Abn: r.abnormal ? 'Y' : ''
    }));
    Tabulator.createTable(mount, rows);
  }

  const weightPts = vitals
    .filter(v => /weight/i.test(String(v.type||'')) && v.value != null && v.effectiveDateTime)
    .map(v => ({ x: v.effectiveDateTime, y: +v.value }))
    .filter(p => isFinite(p.y))
    .sort((a,b) => new Date(a.x) - new Date(b.x));
  if (weightPts.length) {
    const s = sec('Weight Trend');
    const mount = document.createElement('div');
    s.appendChild(mount);
    SimplePlots.line(mount, weightPts);
  }

  if (meds.length) {
    const s = sec('Medications');
    const mount = document.createElement('div');
    s.appendChild(mount);
    const rows = meds.slice(0, 20).map(m => ({
      Name: m.name,
      Dose: m.dose || '',
      Route: m.route || '',
      Freq: m.frequency || '',
      Start: m.startDate || '',
      Status: m.status || ''
    }));
    Tabulator.createTable(mount, rows);
  }

  if (problems.length) {
    const s = sec('Problem List');
    const mount = document.createElement('div');
    s.appendChild(mount);
    const rows = problems.slice(0, 20).map(p => ({
      Problem: p.text,
      Status: p.status,
      Onset: p.onset || ''
    }));
    Tabulator.createTable(mount, rows);
  }

  if (notes.length) {
    const s = sec('Recent Notes');
    const mount = document.createElement('div');
    s.appendChild(mount);
    const rows = notes.slice(0, 10).map(n => ({
      Date: Formatter.date(n.date),
      Title: n.title || '',
      Service: n.service || ''
    }));
    Tabulator.createTable(mount, rows);
  }

  if (notesSearch.length) {
    const s = sec('Note Excerpts (Search Results)');
    const mount = document.createElement('div');
    s.appendChild(mount);
    const rows = notesSearch.slice(0, 10).map(n => ({
      Rank: n.rank,
      Score: typeof n.score === 'number' ? n.score.toFixed(3) : '',
      Note: n.note_id,
      Chunk: n.chunk_id,
      Text: n.text || ''
    }));
    Tabulator.createTable(mount, rows);
  }

  if (!labs.length && !vitals.length && !meds.length && !problems.length && !notes.length && !notesSearch.length) {
    const p = document.createElement('p');
    p.textContent = 'No datasets available.';
    root.appendChild(p);
  }
}

if (typeof window !== 'undefined') { window.render = render; }
