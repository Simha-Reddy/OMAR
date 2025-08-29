// filepath: static/explore/right_sidebar.js
(function(){
  const MOUNT_ID = 'patientRightSidebar';

  function $(id){ return document.getElementById(id); }

  function toDate(s){ try{ return s ? new Date(s) : null; }catch(_e){ return null; } }
  function fmtDateOnly(s){ try{ const d = toDate(s); return d ? d.toLocaleDateString() : ''; }catch(_e){ return ''; } }
  function fmtDateTime(s){ try{ const d = toDate(s); return d ? d.toLocaleString() : ''; }catch(_e){ return ''; } }
  function daysAgo(n){ const d = new Date(); d.setDate(d.getDate()-n); return d; }
  function bust(url){ try{ const dfn = (window.CURRENT_PATIENT_DFN||''); const sep = url.includes('?') ? '&' : '?'; return url+sep+'_pt=' + encodeURIComponent(dfn) + '&_ts=' + Date.now(); }catch(_e){ return url; } }

  function isRecent(dtStr, cutoff){ const d = toDate(dtStr); return d && d >= cutoff; }

  async function jget(url){ const r = await fetch(bust(url), { cache: 'no-store' }); if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }

  function section(title){
    const wrap = document.createElement('div');
    const head = document.createElement('div');
    head.className = 'vital-line';
    head.textContent = title;
    const list = document.createElement('ul');
    list.className = 'vital-reads';
    wrap.appendChild(head);
    wrap.appendChild(list);
    return { wrap, list, head };
  }

  function titleCase(str){
    if(!str || typeof str !== 'string') return str;
    return str.toLowerCase().replace(/\b([a-z])(\w*)/g, (m, a, b) => a.toUpperCase()+b);
  }

  // Simple popover manager (toggle on repeat click)
  let activePopover = null;
  let activeAnchor = null;
  function closePopover(){
    if(activePopover){ activePopover.remove(); activePopover = null; activeAnchor = null; document.removeEventListener('click', onDocClick, true);} }
  function onDocClick(_e){ if(activePopover){ closePopover(); } }
  function showPopover(anchorEl, title, rows){
    if(activeAnchor === anchorEl){ closePopover(); return; }
    closePopover();
    const pop = document.createElement('div');
    pop.className = 'vital-popover';
    const h = document.createElement('h4'); h.textContent = title; pop.appendChild(h);
    (rows||[]).forEach(r => {
      const div = document.createElement('div'); div.className = 'row';
      if(r && typeof r === 'object' && 'text' in r){
        div.textContent = r.text;
        if(r.severity === 'abnormal') div.classList.add('abnormal');
        if(r.severity === 'critical') div.classList.add('critical');
      } else {
        div.textContent = String(r);
      }
      pop.appendChild(div);
    });
    document.body.appendChild(pop);
    pop.addEventListener('click', e => e.stopPropagation());
    // Base position below-left of anchor
    const rect = anchorEl.getBoundingClientRect();
    let top = window.scrollY + rect.bottom + 6;
    let left = window.scrollX + rect.left;
    // Constrain within viewport
    const pad = 8;
    const vw = window.innerWidth; const vh = window.innerHeight;
    const pr = pop.getBoundingClientRect();
    if(left + pr.width > window.scrollX + vw - pad){
      left = window.scrollX + vw - pad - pr.width;
    }
    if(left < window.scrollX + pad){ left = window.scrollX + pad; }
    if(top + pr.height > window.scrollY + vh - pad){
      // place above
      top = window.scrollY + rect.top - pr.height - 6;
      if(top < window.scrollY + pad){ top = window.scrollY + pad; }
    }
    pop.style.top = `${top}px`;
    pop.style.left = `${left}px`;
    activePopover = pop; activeAnchor = anchorEl;
    setTimeout(()=> document.addEventListener('click', onDocClick, true), 0);
  }

  // Labs helpers for diabetes problem expansion
  function _norm(s){ return (s||'').toString().trim().toLowerCase(); }
  const LAB_SPECS = {
    a1c:        { loinc:['4548-4'], patterns:[/\b(hb)?a1c\b/i, /hemoglobin a1c/i, /glyco.?hemoglobin/i] },
    creat:      { loinc:['2160-0'], patterns:[/\bcreatinine\b/i] },
    microalb:   { loinc:['14959-1','9318-7','30000-0'], patterns:[/micro.*albumin/i, /albumin\s*\/\s*creatinine/i, /\balb\/?\s*creat/i, /\bacr\b/i, /\buacr\b/i] },
    egfr:       { loinc:['33914-3','48643-1','62238-1'], patterns:[/\begfr\b/i, /glomerular filtration rate/i] },
    chol:       { loinc:['2093-3'], patterns:[/\bchol(esterol)?\b/i] },
    ldl:        { loinc:['2089-1'], patterns:[/\bldl\b/i] },
    hdl:        { loinc:['2085-9'], patterns:[/\bhdl\b/i] },
    tg:         { loinc:['2571-8'], patterns:[/\btrig(lycerides?)?\b/i] }
  };
  function _matchesSpec(lab, spec){
    const loinc = _norm(lab.loinc);
    const name = _norm(lab.test || lab.localName);
    if(loinc && spec.loinc && spec.loinc.includes(loinc)) return true;
    if(name && spec.patterns){ for(const p of spec.patterns){ if(p.test(name)) return true; } }
    return false;
  }
  function _latestSeries(labs, spec){
    const rows = (labs||[])
      .filter(r => _matchesSpec(r, spec))
      .map(r => ({ v: (typeof r.result === 'number'? r.result : parseFloat(r.result)), u: r.unit, d: new Date(r.resulted || r.collected || 0), name: r.test || r.localName }))
      .filter(x => !Number.isNaN(x.v) && !isNaN(x.d));
    rows.sort((a,b)=> a.d - b.d);
    return rows;
  }

  function renderAllergies(listEl, allergies){
    if(!allergies || !allergies.length){ listEl.innerHTML = '<li class="vital-empty">No allergies on file</li>'; return; }
    for(const a of allergies){
      const li = document.createElement('li');
      li.style.cursor = 'pointer';
      const name = titleCase(a.substance || 'Allergy');
      const crit = a.criticality ? ` (${titleCase(String(a.criticality))})` : '';
      li.textContent = name + crit;
      li.addEventListener('click', (e)=>{
        e.stopPropagation();
        const rows = [];
        if(a.recordedDate) rows.push(`Recorded: ${fmtDateOnly(a.recordedDate)}`);
        if(a.onsetDateTime) rows.push(`Onset: ${fmtDateOnly(a.onsetDateTime)}`);
        if(a.lastOccurrence) rows.push(`Last Occurrence: ${fmtDateTime(a.lastOccurrence)}`);
        if(a.clinicalStatus) rows.push(`Status: ${a.clinicalStatus}`);
        if(a.verificationStatus) rows.push(`Verification: ${a.verificationStatus}`);
        const cats = ((a.category||[]).join(', ')); if(cats) rows.push(`Category: ${cats}`);
        const rx = (a.reactions||[]).flatMap(r => (r.manifestations||[]));
        if(rx && rx.length){ rows.push('Reactions: ' + rx.join('; ')); }
        showPopover(li, name, rows);
      });
      listEl.appendChild(li);
    }
  }

  function medStatusBucket(m){
    const s = (m.status || '').toLowerCase();
    if(s.includes('discont') || s.includes('stopp')) return 'discontinued';
    const now = new Date();
    if(s.includes('expired')) return 'expired';
    if(m.endDate){ const ed = toDate(m.endDate); if(ed && ed < now) return 'expired'; }
    if(s.includes('active')) return 'active';
    return 'other';
  }

  function medDetailRows(m){
    const rows = [];
    if(m.medClass) rows.push(`Class: ${m.medClass}`);
    if(m.status) rows.push(`Status: ${titleCase(m.status)}`);
    if(m.dose) rows.push(`Dose: ${m.dose}`);
    if(m.route) rows.push(`Route: ${m.route}`);
    if(m.frequency) rows.push(`Frequency: ${m.frequency}`);
    if(m.sig) rows.push(`Sig: ${m.sig}`);
    if(m.startDate) rows.push(`Start: ${fmtDateOnly(m.startDate)}`);
    if(m.lastFilled) rows.push(`Last Filled: ${fmtDateOnly(m.lastFilled)}`);
    if(m.endDate) rows.push(`End: ${fmtDateOnly(m.endDate)}`);
    return rows;
  }

  function renderMeds(listEl, meds, opts){
    opts = opts || {}; const activeOnly = !!opts.activeOnly;
    if(!Array.isArray(meds)){ listEl.innerHTML = '<li class="vital-empty">No recent medications</li>'; return { count: 0 }; }
    const cutoff = daysAgo(90);
    let recent = meds.filter(m => {
      const sdt = m.startDate || m.lastFilled || (m.source||{}).updated || m.endDate;
      return isRecent(sdt, cutoff) || (m.status||'').toLowerCase()==='active';
    });
    if(activeOnly){ recent = recent.filter(m => (m.status||'').toLowerCase()==='active'); }
    if(!recent.length){ listEl.innerHTML = '<li class="vital-empty">No medications in the current view</li>'; return { count: 0 }; }

    const groups = { active: [], expired: [], discontinued: [], other: [] };
    for(const m of recent){ groups[medStatusBucket(m)].push(m); }

    function appendGroup(arr, cls){
      arr.sort((a,b)=> String(b.startDate||b.lastFilled||'').localeCompare(String(a.startDate||a.lastFilled||'')));
      for(const m of arr){
        const li = document.createElement('li');
        li.className = cls;
        li.style.cursor = 'pointer';
        const name = titleCase(m.name || 'Medication');
        const dose = m.dose ? ` — ${m.dose}` : '';
        li.textContent = name + dose;
        li.addEventListener('click', (e)=>{
          e.stopPropagation();
          showPopover(li, name, medDetailRows(m));
        });
        listEl.appendChild(li);
      }
    }

    appendGroup(groups.active, 'med-active');
    if(!activeOnly){
      appendGroup(groups.expired, 'med-expired');
      appendGroup(groups.discontinued, 'med-discontinued');
      appendGroup(groups.other, '');
    }
    return { count: recent.length };
  }

  // Cache labs for problem expansion on demand
  let _labsCache = null;
  async function loadLabs(){
    if(_labsCache) return _labsCache;
    try {
      const res = await jget('/fhir/labs?days=365');
      _labsCache = (res && res.labs) || [];
      return _labsCache;
    } catch(_e){ _labsCache = []; return _labsCache; }
  }

  function isDiabetesProblem(p){ return /diabetes/i.test(p.name || ''); }

  function buildDiabetesRows(labs, meds){
    const rows = [];
    // A1c last 3
    const a1cSer = _latestSeries(labs, LAB_SPECS.a1c);
    if(a1cSer.length){
      rows.push('A1c (last 3):');
      a1cSer.slice(-3).reverse().forEach(x => rows.push(`  ${x.v}${x.u?(' '+x.u):'%'} — ${fmtDateOnly(x.d)}`));
    } else {
      rows.push('A1c (last 3):');
    }
    // Creatinine last
    const crSer = _latestSeries(labs, LAB_SPECS.creat);
    if(crSer.length){ const last = crSer[crSer.length-1]; rows.push(`Creatinine: ${last.v}${last.u?(' '+last.u):''} — ${fmtDateOnly(last.d)}`); }
    else { rows.push('Creatinine:'); }
    // eGFR last
    const egfrSer = _latestSeries(labs, LAB_SPECS.egfr);
    if(egfrSer.length){ const last = egfrSer[egfrSer.length-1]; rows.push(`eGFR: ${last.v}${last.u?(' '+last.u):''} — ${fmtDateOnly(last.d)}`); }
    else { rows.push('eGFR:'); }
    // Albumin/Creatinine Ratio (UACR) last
    const maSer = _latestSeries(labs, LAB_SPECS.microalb);
    if(maSer.length){ const last = maSer[maSer.length-1]; rows.push(`Albumin/Creatinine Ratio (UACR): ${last.v}${last.u?(' '+last.u):''} — ${fmtDateOnly(last.d)}`); }
    else { rows.push('Albumin/Creatinine Ratio (UACR):'); }
    // Lipid panel last
    const lipids = {};
    ['chol','ldl','hdl','tg'].forEach(k => { const ser = _latestSeries(labs, LAB_SPECS[k]); if(ser.length) lipids[k] = ser[ser.length-1]; });
    if(Object.keys(lipids).length){
      const parts = [];
      if(lipids.chol) parts.push(`CHOL ${lipids.chol.v}${lipids.chol.u?(' '+lipids.chol.u):''}`);
      if(lipids.ldl) parts.push(`LDL ${lipids.ldl.v}${lipids.ldl.u?(' '+lipids.ldl.u):''}`);
      if(lipids.hdl) parts.push(`HDL ${lipids.hdl.v}${lipids.hdl.u?(' '+lipids.hdl.u):''}`);
      if(lipids.tg)  parts.push(`TG ${lipids.tg.v}${lipids.tg.u?(' '+lipids.tg.u):''}`);
      const dates = Object.values(lipids).map(x => x.d);
      const mostRecent = dates.length? new Date(Math.max.apply(null, dates)) : null;
      rows.push(`Lipid Panel: ${parts.join('  ')}${mostRecent?(' — '+fmtDateOnly(mostRecent)) : ''}`);
    } else {
      rows.push('Lipid Panel:');
    }
    // Active medications by classes
    const actives = (meds||[]).filter(m => (m.status||'').toLowerCase()==='active');
    const low = s => (s||'').toLowerCase();
    const group = {
      diabetes: actives.filter(m => {
        const c = low(m.medClass);
        return c.includes('insulin') || c.includes('hypoglyc') || c.includes('glp-1') || c.includes('glp1') || c.includes('sglt2');
      }),
      statin: actives.filter(m => low(m.medClass).includes('statin')),
      acearb: actives.filter(m => { const c=low(m.medClass); return c.includes('arb') || c.includes('ace inhibitor') || c.includes('angiotensin'); })
    };
    rows.push('Medications:');
    rows.push('  Diabetes: ' + (group.diabetes.length? group.diabetes.map(m => m.name + (m.dose?(' '+m.dose):'')).join('; ') : ''));
    rows.push('  Statin: ' + (group.statin.length? group.statin.map(m => m.name + (m.dose?(' '+m.dose):'')).join('; ') : ''));
    rows.push('  ACE/ARB: ' + (group.acearb.length? group.acearb.map(m => m.name + (m.dose?(' '+m.dose):'')).join('; ') : ''));
    return rows;
  }

  function renderProblems(listEl, problems, meds, opts){
    opts = opts || {}; const pf = opts.filter || 'all';
    if(!problems || !problems.length){ listEl.innerHTML = '<li class="vital-empty">No problems listed</li>'; return { count: 0 }; }
    let source = problems;
    if(pf === 'active') source = problems.filter(p => !!p.active);
    if(pf === 'inactive') source = problems.filter(p => !p.active);
    const active = [], inactive = [];
    for(const p of source){ (p.active ? active : inactive).push(p); }
    const ordered = active.concat(inactive);
    for(const p of ordered){
      const li = document.createElement('li');
      li.style.cursor = 'pointer';
      const name = titleCase(p.name || 'Problem');
      const status = p.active ? '' : ' (Inactive)';
      li.textContent = name + status;
      li.addEventListener('click', async (e)=>{
        e.stopPropagation();
        const rows = [];
        if(p.clinicalStatus) rows.push(`Status: ${p.clinicalStatus}`);
        if(p.severity) rows.push(`Severity: ${p.severity}`);
        if(p.onsetDateTime) rows.push(`Onset: ${fmtDateOnly(p.onsetDateTime)}`);
        if(p.recordedDate) rows.push(`Recorded: ${fmtDateOnly(p.recordedDate)}`);
        if(p.commentText) rows.push(`Notes: ${p.commentText}`);
        if(isDiabetesProblem(p)){
          try { const labs = await loadLabs(); rows.push('—'); rows.push(...buildDiabetesRows(labs, meds)); } catch(_e){}
        }
        showPopover(li, name, rows);
      });
      listEl.appendChild(li);
    }
    return { count: ordered.length };
  }

  // Sidebar controls state
  const state = { medsActiveOnly: false };
  let _lastData = null;

  function buildControls(){
    const bar = document.createElement('div');
    bar.style.display = 'flex';
    bar.style.gap = '8px';
    bar.style.alignItems = 'center';
    bar.style.flexWrap = 'wrap';
    bar.style.margin = '4px 0 8px 0';

    // Meds: Active only checkbox
    const medWrap = document.createElement('label');
    medWrap.style.fontSize = '0.9em';
    const medCb = document.createElement('input'); medCb.type = 'checkbox'; medCb.checked = state.medsActiveOnly; medCb.style.marginRight = '6px';
    medCb.addEventListener('change', () => { state.medsActiveOnly = !!medCb.checked; if(_lastData) renderSidebar(_lastData); });
    medWrap.appendChild(medCb);
    medWrap.appendChild(document.createTextNode('Active meds only'));

    bar.appendChild(medWrap);
    return bar;
  }

  function renderSidebar(data){
    const mount = $(MOUNT_ID);
    if(!mount) return;
    mount.innerHTML = '';
    mount.appendChild(buildControls());

    // Problems (Active only) — move to top
    const s3 = section('Active Problems');
    const probRes = renderProblems(s3.list, (data && data.problems) || [], (data && data.medications) || [], { filter: 'active' });
    s3.head.textContent = `Active Problems (${probRes.count})`;
    mount.appendChild(s3.wrap);

    // Allergies
    const s1 = section('Allergies');
    renderAllergies(s1.list, (data && data.allergies) || []);
    s1.head.textContent = `Allergies (${((data && data.allergies) || []).length})`;
    mount.appendChild(s1.wrap);

    // Meds
    const s2 = section('Medications');
    const medRes = renderMeds(s2.list, (data && data.medications) || [], { activeOnly: state.medsActiveOnly });
    s2.head.textContent = `${state.medsActiveOnly ? 'Active Medications' : 'Medications'} (${medRes.count})`;
    mount.appendChild(s2.wrap);
  }

  async function refresh(){
    const mount = $(MOUNT_ID);
    if(!mount) return;
    mount.innerHTML = '<div class="vital-loading">Loading summary…</div>';
    try{
      const [alg, meds, probs] = await Promise.all([
        jget('/fhir/allergies').catch(()=>({allergies:[]})),
        jget('/fhir/medications').catch(()=>({medications:[]})),
        jget('/fhir/problems').catch(()=>({problems:[]}))
      ]);
      _lastData = { allergies: (alg && alg.allergies) || [], medications: (meds && meds.medications) || [], problems: (probs && probs.problems) || [] };
      renderSidebar(_lastData);
    }catch(e){
      mount.innerHTML = '<div class="vital-error">Failed to load sidebar</div>';
    }
  }

  function init(){
    if(document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', refresh);
    } else {
      refresh();
    }
  }

  window.RightSidebar = { refresh, init };
  init();
})();