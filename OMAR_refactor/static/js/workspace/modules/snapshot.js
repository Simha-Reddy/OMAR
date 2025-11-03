// filepath: static/workspace/modules/snapshot.js
// Snapshot module: Combined view with Vitals + Labs on the left and collapsible Allergies, Meds, Problems on the right
(function(){
  const MODULE_NAME = 'Snapshot';

  // Simple state and helpers
  const state = { data: null, labs: null, right: null };
  const activeControllers = new Set();
  // Add lightweight per-URL promise cache to collapse near-simultaneous calls within this module
  const requestCache = new Map(); // url -> { t:number, p:Promise }
  const REQUEST_TTL_MS = 5000;
  // Cache brand color once per module to avoid repeated style lookups
  let BRAND_BLUE = null;
  function brandBlue(){
    if(!BRAND_BLUE){
      try{
        BRAND_BLUE = getComputedStyle(document.documentElement).getPropertyValue('--brand-blue') || '#3498db';
      }catch(_e){ BRAND_BLUE = '#3498db'; }
    }
    return BRAND_BLUE;
  }
  try { document.addEventListener('visibilitychange', ()=>{ if(!document.hidden) BRAND_BLUE=null; }, { passive:true }); } catch(_e){}
  let containerRef = null;
  let popover = { el: null, anchor: null, onDocClick: null };
  let lastPopoverClose = { anchor: null, time: 0 };

  // Ensure module-scoped styles are present once (unified scroll, responsive flow, hover-only scrollbar)
  function ensureSnapshotStyles(){
    try{
      const id = 'snapshot-module-styles';
      if(document.getElementById(id)) return;
      const style = document.createElement('style');
      style.id = id;
      style.textContent = `
        /* Snapshot: make the whole tab a single scroll surface */
        .snapshot-layout { overflow: auto; }
        /* Hide scrollbar until hover (Chromium/WebKit) */
        .snapshot-layout::-webkit-scrollbar { width: 0; height: 0; }
        .snapshot-layout:hover::-webkit-scrollbar { width: 10px; height: 10px; }
        .snapshot-layout:hover::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.35); border-radius: 8px; }
        .snapshot-layout:hover::-webkit-scrollbar-track { background: transparent; }
        /* Firefox scrollbar behavior */
        .snapshot-layout { scrollbar-width: none; }
        .snapshot-layout:hover { scrollbar-width: thin; scrollbar-color: rgba(0,0,0,0.35) transparent; }

        /* Vitals grid: responsive auto-fit columns that stack gracefully. Use wider min to prefer single column when narrow */
        .snapshot-layout .vitals-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; align-items: baseline; }
        .snapshot-layout .vital-cell { padding: 6px 4px; }

        /* Fishbone SVGs should shrink to fit container */
        .snapshot-layout .labs-fishbone svg { width: 100%; max-width: 100%; height: auto; display: block; }
      `;
      document.head.appendChild(style);
    }catch(_e){}
  }

  function cancelAll(){
    for(const c of Array.from(activeControllers)){
      try{ c.abort(); }catch(_e){}
    }
    activeControllers.clear();
  }
  function jget(url){
    // Serve from in-module cache if fresh
    const now = Date.now();
    const hit = requestCache.get(url);
    if (hit && (now - hit.t) < REQUEST_TTL_MS) return hit.p;
    const ctrl = new AbortController();
    activeControllers.add(ctrl);
    const p = fetch(url, { headers: { 'Accept':'application/json', 'X-Caller':'Snapshot' }, credentials:'same-origin', signal: ctrl.signal })
      .finally(()=> activeControllers.delete(ctrl))
      .then(r => { if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); });
    requestCache.set(url, { t: now, p });
    // On rejection, clear cache entry so a later call can retry
    p.catch(()=>{ if(requestCache.get(url)?.p === p) requestCache.delete(url); });
    return p;
  }
  function toNum(v){ const n = Number(v); return isFinite(n)? n : null; }
  function fmtShortDate(d){ try{ const dd = (d instanceof Date)? d : new Date(d); if(isNaN(dd)) return ''; const m=dd.getMonth()+1; const day=dd.getDate(); const yy=String(dd.getFullYear()).slice(-2); return `${m}/${day}/${yy}`; }catch(_e){ return ''; } }
  function fmtDate(s){ return fmtShortDate(s); }
  function fmtDateOnly(s){ return fmtShortDate(s); }
  function latest(arr){ return Array.isArray(arr) && arr.length? arr[arr.length-1] : null; }
  function calcPctDelta(a,b){ const A=toNum(a), B=toNum(b); if(A==null||B==null||B===0) return null; return ((A-B)/Math.abs(B))*100; }
  function buildDeltaIndicator(pct){ if(pct==null) return null; const ap=Math.abs(pct); if(ap<5) return null; const up=pct>0; const wrap=document.createElement('span'); wrap.className='delta-wrap'; const tri=document.createElement('span'); tri.className='delta-tri'; tri.textContent = up? '▲':'▼'; wrap.appendChild(tri); if(ap>10){ const tri2=document.createElement('span'); tri2.className='delta-tri'; tri2.textContent = up? '▲':'▼'; wrap.appendChild(tri2);} wrap.title=`${up?'+':''}${pct.toFixed(1)}%`; try{ wrap.style.pointerEvents='none'; }catch(_e){} return wrap; }
  function calcMAP(bp){ if(!bp) return null; const s=toNum(bp.systolic), d=toNum(bp.diastolic); if(s==null||d==null) return null; return d + (s-d)/3; }

  // Popover
  function closePopover(){
    if(popover.el){
      try{ popover.el.remove(); }catch(_e){}
      popover.el=null; popover.anchor=null;
      if(popover.onDocClick){ document.removeEventListener('click', popover.onDocClick, true); popover.onDocClick=null; }
      if(popover.onEsc){ document.removeEventListener('keydown', popover.onEsc, true); popover.onEsc=null; }
    }
  }
  function showPopover(anchorEl, title, rows){
    closePopover(); // Always close any existing popover first
    const el = document.createElement('div'); el.className='vital-popover';
    const h = document.createElement('h4'); h.textContent = title; el.appendChild(h);
    (rows||[]).forEach(r=>{ const d=document.createElement('div'); d.className='row'; if(r && typeof r==='object' && 'text' in r){ d.textContent=r.text; if(r.severity==='abnormal') d.classList.add('abnormal'); if(r.severity==='critical') d.classList.add('critical'); } else { d.textContent=String(r); } el.appendChild(d); });
    document.body.appendChild(el);
    const rect = anchorEl.getBoundingClientRect();
    let top = window.scrollY + rect.bottom + 6; let left = window.scrollX + rect.left;
    const pad=8, vw=window.innerWidth, vh=window.innerHeight, pr=el.getBoundingClientRect();
    if(left+pr.width > window.scrollX+vw-pad) left = window.scrollX+vw-pad-pr.width;
    if(left < window.scrollX+pad) left = window.scrollX+pad;
    if(top+pr.height > window.scrollY+vh-pad){ top = window.scrollY + rect.top - pr.height - 6; if(top < window.scrollY+pad) top = window.scrollY+pad; }
    el.style.top = `${top}px`; el.style.left = `${left}px`;
    popover.el = el; popover.anchor = anchorEl;
    popover.onDocClick = (e)=>{
      // Only close if click is outside both popover and anchor
      if (popover.el && !popover.el.contains(e.target) && popover.anchor && !popover.anchor.contains(e.target)) {
        closePopover();
      }
    };
    popover.onEsc = (e)=>{ if(e.key==='Escape'){ closePopover(); } };
    setTimeout(()=> {
      document.addEventListener('click', popover.onDocClick, true);
      document.addEventListener('keydown', popover.onEsc, true);
    }, 0);
  }
  function togglePopover(anchorEl, title, rows) {
    if (popover.el && popover.anchor === anchorEl) {
      closePopover();
      return;
    }
    showPopover(anchorEl, title, rows);
  }

  // Labs fishbone helpers (compact subset from explore/vitals_sidebar.js)
  const ANALYTES = {
    na:{ loinc:['2951-2','2947-0'], patterns:[/\bna\+?\b/i, /\bsodium\b/i] },
    k:{ loinc:['2823-3'], patterns:[/\bk\+?\b/i, /\bpotassium\b/i] },
    cl:{ loinc:['2075-0'], patterns:[/\bcl-?\b/i, /\bchloride\b/i] },
    hco3:{ loinc:['2028-9'], patterns:[/\bhco3\b/i, /\bco2\b/i, /\bbicarbonate\b/i] },
    bun:{ loinc:['3094-0'], patterns:[/\bbun\b/i, /\burea nitrogen\b/i] },
    cr:{ loinc:['2160-0'], patterns:[/\bcreatinine\b/i, /\bcr\b/i] },
    glu:{ loinc:['2345-7'], patterns:[/\bglu(cose)?\b/i] },
    wbc:{ loinc:['6690-2','26464-8'], patterns:[/\bwbc\b/i, /\bwhite blood\b/i] },
    hgb:{ loinc:['718-7'], patterns:[/\bhgb\b(?![^a-z0-9]*a1c)/i, /\bhemoglobin\b(?![^a-z0-9]*a1c)/i] },
    hct:{ loinc:['4544-3'], patterns:[/\bhct\b/i, /\bhematocrit\b/i] },
    plt:{ loinc:['777-3'], patterns:[/\bplt\b/i, /\bplatelets?\b/i] }
  };
  function _norm(s){ return (s||'').toString().trim().toLowerCase(); }
  function keyForLab(lab){ const loinc=_norm(lab.loinc); const name=_norm(lab.test||lab.localName); for(const [key,spec] of Object.entries(ANALYTES)){ if(loinc && spec.loinc && spec.loinc.includes(loinc)) return key; if(key==='hgb' && name && (name.includes('a1c')||name.includes('glyco'))) continue; if(name && spec.patterns){ for(const p of spec.patterns){ if(p.test(name)) return key; } } } return null; }
  const MAX_LAB_POINTS = 60; // cap per analyte to reduce render work
  // Helper to detect if lab specimen is serum/plasma vs urine, etc.
  function isSerumLike(r){
    try{
      const spec = _norm(r.specimen || r.specimenType || r.sample || r.source || r.bodySite);
      const name = _norm(r.test || r.localName || r.display || r.observation || r.name);
      const sys = _norm(r.system || r.category);
      // Favor serum/plasma for chemistry; exclude urine when explicitly stated
      const mentionsUrine = /\burine\b|\burinalys(i|e)s\b|\bur\b/.test(spec) || /\burine\b|\burinalys(i|e)s\b|\bur\b/.test(name);
      const mentionsSerum = /\bserum\b/.test(spec) || /\bserum\b/.test(name);
      const mentionsPlasma = /\bplasma\b/.test(spec) || /\bplasma\b/.test(name);
      // If specimen explicitly urine, reject; else if serum/plasma or specimen unspecified, allow
      if (mentionsUrine) return false;
      if (mentionsSerum || mentionsPlasma) return true;
      // If no specimen info but it's a core chemistry, default allow; others fall back to allow
      return true;
    }catch(_e){ return true; }
  }
  function buildLabSeries(labs){
    const series={}; Object.keys(ANALYTES).forEach(k=>series[k]=[]);
    (labs||[]).forEach(r=>{
      const key=keyForLab(r); if(!key) return;
      // Enforce serum/plasma-only for BMP (chemistry); CBC components unaffected
      const isChem = (key==='na'||key==='k'||key==='cl'||key==='hco3'||key==='bun'||key==='cr'||key==='glu');
      if (isChem && !isSerumLike(r)) return;
      const val=toNum(r.result); if(val==null) return;
      const date=r.resulted||r.collected;
      series[key].push({ value: val, unit: r.unit, date, raw: r });
    });
    for(const k of Object.keys(series)){
      const arr = series[k];
      arr.sort((a,b)=> new Date(a.date||0)-new Date(b.date||0));
      if(arr.length>MAX_LAB_POINTS){ series[k] = arr.slice(-MAX_LAB_POINTS); }
    }
    return series;
  }

  // Parse per-result reference range from raw lab data
  function refRangeBounds(raw){
    try{
      let low=null, high=null;
      const toNum = (x)=>{ if(x==null) return null; const n=parseFloat(String(x).replace(/[^0-9.+-]/g,'')); return isFinite(n)? n : null; };
      const rr = raw && raw.referenceRange;
      if(typeof rr === 'string'){
        const m = rr.match(/-?\d+(?:\.\d+)?/g);
        if(m && m.length>=2){ low = toNum(m[0]); high = toNum(m[1]); }
      } else if (rr && typeof rr === 'object'){
        low = toNum(rr.low ?? rr.min);
        high = toNum(rr.high ?? rr.max);
      }
      if(low==null) low = toNum(raw && (raw.refLow ?? raw.low ?? raw.normalLow ?? raw.reference_low));
      if(high==null) high = toNum(raw && (raw.refHigh ?? raw.high ?? raw.normalHigh ?? raw.reference_high));
      return { low, high };
    }catch(_e){ return { low:null, high:null }; }
  }
  function abnormalByRef(value, raw){
    const v = toNum(value); if(v==null) return null;
    const { low, high } = refRangeBounds(raw||{});
    if(low==null && high==null) return null;
    if(low!=null && v<low) return true;
    if(high!=null && v>high) return true;
    return false;
  }

  // Generic lab finders for non-fishbone items
  function findLabs(labs, loincs, patterns){
    const out = [];
    const lc = (loincs||[]).map(_norm);
    const pats = (patterns||[]);
    (labs||[]).forEach(r=>{
      try{
        const l = _norm(r.loinc);
        const n = _norm(r.test||r.localName||r.name||'');
        const byLoinc = l && lc.includes(l);
        const byName = pats.some(p=>p.test(n));
        if (!byLoinc && !byName) return;
        const d = new Date(r.resulted||r.collected||0);
        if (!r.result || isNaN(d)) return;
        out.push({ v: String(r.result), u: r.unit || '', d, raw: r });
      }catch(_e){}
    });
    out.sort((a,b)=> a.d-b.d);
    return out;
  }
  function lastN(arr, n){ return (arr||[]).slice(-n).reverse(); }
  function fmtVal(v,u){
    const vv = (v==null)? '' : String(v).trim();
    const uu = (u==null)? '' : String(u).trim();
    return vv + (uu? (' '+uu):'');
  }
  function summarizeLatest(results){
    const last = results && results.length? results[results.length-1] : null;
    return last ? `${fmtVal(last.v,last.u)} — ${fmtDateOnly(last.d)}` : '';
  }
  function latestLab(series,key){ const arr=series[key]||[]; return arr.length? arr[arr.length-1] : null; }
  function pctDeltaForKey(series,key){ const arr=series[key]||[]; if(arr.length<2) return null; const a=arr[arr.length-1], b=arr[arr.length-2]; return calcPctDelta(a.value,b.value); }
  function rowsLast3(series,key){ const arr=series[key]||[]; return arr.slice(-3).reverse().map(x=>`${x.value}${x.unit?(' '+x.unit):''} — ${fmtDate(x.date)}`); }
  function createSVG(w,h){ const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'); svg.setAttribute('width',w); svg.setAttribute('height',h); svg.setAttribute('viewBox',`0 0 ${w} ${h}`); return svg; }
  function line(svg,x1,y1,x2,y2){ const el=document.createElementNS('http://www.w3.org/2000/svg','line'); el.setAttribute('x1',x1); el.setAttribute('y1',y1); el.setAttribute('x2',x2); el.setAttribute('y2',y2); el.setAttribute('stroke', brandBlue()); el.setAttribute('stroke-width',2); svg.appendChild(el); return el; }
  function text(svg, txt, x, y, opts){ const el=document.createElementNS('http://www.w3.org/2000/svg','text'); el.setAttribute('x',x); el.setAttribute('y',y); el.textContent=txt; el.setAttribute('fill', opts&&opts.fill?opts.fill:brandBlue()); el.setAttribute('font-size', (opts&&opts.size)||14); el.setAttribute('font-weight',(opts&&opts.weight)||400); if(opts&&opts.anchor) el.setAttribute('text-anchor',opts.anchor); if(opts&&opts.baseline) el.setAttribute('dominant-baseline',opts.baseline); svg.appendChild(el); return el; }
  function severityFor(key,value){ const v=toNum(value); if(v==null) return 'normal'; const R={ na:{low:135,high:145,critLow:120,critHigh:160}, k:{low:3.5,high:5.1,critLow:2.5,critHigh:6.5}, cl:{low:98,high:107,critLow:85,critHigh:115}, hco3:{low:22,high:29,critLow:12,critHigh:40}, bun:{low:7,high:20,critLow:3,critHigh:100}, cr:{low:0.6,high:1.3,critLow:0.2,critHigh:6}, glu:{low:70,high:99,critLow:40,critHigh:500}, wbc:{low:4,high:11,critLow:1,critHigh:30}, hgb:{low:12,high:17.5,critLow:7,critHigh:20}, hct:{low:36,high:52,critLow:21,critHigh:60}, plt:{low:150,high:400,critLow:25,critHigh:1000} }; const r=R[key]; if(!r) return 'normal'; if(v<r.critLow||v>r.critHigh) return 'critical'; if(v<r.low||v>r.high) return 'abnormal'; return 'normal'; }
  // Simplified ranges for additional labs
  function severityForExtra(type, value){
    const v = toNum(value);
    if(v==null) return 'normal';
    switch((type||'').toLowerCase()){
      case 'a1c':
        // Diabetes >= 6.5%; flag as abnormal when >= 6.5
        return v >= 6.5 ? 'abnormal' : 'normal';
      case 'tsh':
        // Typical 0.4 - 4.5
        return (v < 0.4 || v > 4.5) ? 'abnormal' : 'normal';
      case 'tc':
        // Total Cholesterol: normal < 200
        return v >= 200 ? 'abnormal' : 'normal';
      case 'tg':
        // Triglycerides: normal < 150
        return v >= 150 ? 'abnormal' : 'normal';
      case 'hdl':
        // HDL: low < 40
        return v < 40 ? 'abnormal' : 'normal';
      case 'ldl':
        // LDL: abnormal >= 130 (simple rule)
        return v >= 130 ? 'abnormal' : 'normal';
      default:
        return 'normal';
    }
  }
  function placeTrianglesByText(svg, valueTextEl, pct){ if(pct==null) return; const ap=Math.abs(pct); if(ap<5) return; const tri = pct>0? '▲':'▼'; const margin=6, gap=8; const tryPlace=(n)=>{ try{ const b=valueTextEl.getBBox(); if(!b || (!b.width && n>0)){ requestAnimationFrame(()=>tryPlace(n-1)); return; } const x = b.x - margin; const y = b.y + b.height/2; text(svg, tri, x, y, { size: 12, fill:'#DAA520', anchor:'end', baseline:'middle' }); if(ap>10){ text(svg, tri, x, y+gap/2, { size: 12, fill:'#DAA520', anchor:'end', baseline:'middle' }); } }catch(_e){ if(n>0) requestAnimationFrame(()=>tryPlace(n-1)); } }; requestAnimationFrame(()=>tryPlace(4)); }
  function renderBMP(series){ const svg=createSVG(260,80); line(svg,10,40,200,40); line(svg,70,21,70,59); line(svg,140,21,140,59); line(svg,200,40,238,24); line(svg,200,40,238,56); const mid={ s0:(10+70)/2, s1:(70+140)/2, s2:(140+200)/2 }; const yTop=24, yBot=58; const spots={ na:{x:mid.s0,y:yTop,anchor:'middle'}, k:{x:mid.s0,y:yBot,anchor:'middle'}, cl:{x:mid.s1,y:yTop,anchor:'middle'}, hco3:{x:mid.s1,y:yBot,anchor:'middle'}, bun:{x:mid.s2,y:yTop,anchor:'middle'}, cr:{x:mid.s2,y:yBot,anchor:'middle'}, glu:{x:224,y:44,anchor:'start'} }; Object.entries(spots).forEach(([key,pos])=>{ const cur=latestLab(series,key); const pct=pctDeltaForKey(series,key); const label=cur? String(cur.value) : '--'; const t=text(svg,label,pos.x,pos.y,{anchor:pos.anchor,baseline:'middle'}); t.classList.add('lab-value'); t.style.cursor='pointer'; if(cur){ let sev='normal'; const ab=abnormalByRef(cur.value, cur.raw); if(ab===true) sev='abnormal'; else if(ab===null) sev=severityFor(key,cur.value); if(sev==='abnormal') t.setAttribute('fill','#ef5350'); if(sev==='critical') t.setAttribute('fill','#b71c1c'); } placeTrianglesByText(svg,t,pct); const rows=rowsLast3(series,key); t.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(t, key.toUpperCase()+' (last 3)', rows); }); if(cur){ t.setAttribute('title', `${key.toUpperCase()}: ${cur.value}${cur.unit?(' '+cur.unit):''}`); } }); return svg; }
  function renderCBC(series){ const svg=createSVG(260,80); line(svg,46,9,214,71); line(svg,46,71,214,9); const spots={ wbc:{x:84,y:40,anchor:'end'}, hgb:{x:130,y:18,anchor:'middle'}, hct:{x:142,y:66,anchor:'end'}, plt:{x:182,y:40,anchor:'start'} }; Object.entries(spots).forEach(([key,pos])=>{ const cur=latestLab(series,key); const pct=pctDeltaForKey(series,key); const label=cur? String(cur.value) : '--'; const t=text(svg,label,pos.x,pos.y,{anchor:pos.anchor,baseline:'middle'}); t.classList.add('lab-value'); t.style.cursor='pointer'; if(cur){ let sev='normal'; const ab=abnormalByRef(cur.value, cur.raw); if(ab===true) sev='abnormal'; else if(ab===null) sev=severityFor(key,cur.value); if(sev==='abnormal') t.setAttribute('fill','#ef5350'); if(sev==='critical') t.setAttribute('fill','#b71c1c'); } placeTrianglesByText(svg,t,pct); const rows=rowsLast3(series,key); t.addEventListener('click', (e)=>{ e.stopPropagation(); togglePopover(t, key.toUpperCase()+' (last 3)', rows); }); if(cur){ t.setAttribute('title', `${key.toUpperCase()}: ${cur.value}${cur.unit?(' '+cur.unit):''}`); } }); return svg; }

  // Right side helpers (from explore/right_sidebar.js)
  function titleCase(str){ if(!str||typeof str!=='string') return str; return str.toLowerCase().replace(/\b([a-z])(\w*)/g,(m,a,b)=>a.toUpperCase()+b); }
  function renderAllergies(listEl, allergies){ if(!allergies||!allergies.length){ listEl.innerHTML='<li class="vital-empty">No allergies on file</li>'; return; } for(const a of allergies){ const li=document.createElement('li'); li.style.cursor='pointer'; const name=titleCase(a.substance||'Allergy'); const crit=a.criticality? ` (${titleCase(String(a.criticality))})` : ''; li.textContent = name + crit; li.addEventListener('click', (e)=>{ e.stopPropagation(); const rows=[]; if(a.recordedDate) rows.push(`Recorded: ${fmtDateOnly(a.recordedDate)}`); if(a.onsetDateTime) rows.push(`Onset: ${fmtDateOnly(a.onsetDateTime)}`); if(a.lastOccurrence) rows.push(`Last Occurrence: ${fmtDate(a.lastOccurrence)}`); if(a.clinicalStatus) rows.push(`Status: ${a.clinicalStatus}`); if(a.verificationStatus) rows.push(`Verification: ${a.verificationStatus}`); const cats=((a.category||[]).join(', ')); if(cats) rows.push(`Category: ${cats}`); const rx=(a.reactions||[]).flatMap(r=> (r.manifestations||[])); if(rx&&rx.length){ rows.push('Reactions: '+rx.join('; ')); } togglePopover(li, name, rows); }); listEl.appendChild(li); } }
  function medStatusBucket(m){ const s=(m.status||'').toLowerCase(); if(s.includes('discont')||s.includes('stopp')) return 'discontinued'; const now=new Date(); if(s.includes('expired')) return 'expired'; if(m.endDate){ const ed=new Date(m.endDate); if(ed && ed<now) return 'expired'; } if(s.includes('active')) return 'active'; if(s.includes('pending')) return 'pending'; return 'other'; }
  function medDetailRows(m){ const rows=[]; if(m.medClass) rows.push(`Class: ${m.medClass}`); if(m.status) rows.push(`Status: ${titleCase(m.status)}`); if(m.dose) rows.push(`Dose: ${m.dose}`); if(m.route) rows.push(`Route: ${m.route}`); if(m.frequency) rows.push(`Frequency: ${m.frequency}`); if(m.sig) rows.push(`Sig: ${m.sig}`); if(m.startDate) rows.push(`Start: ${fmtDateOnly(m.startDate)}`); if(m.lastFilled) rows.push(`Last Filled: ${fmtDateOnly(m.lastFilled)}`); if(m.endDate) rows.push(`End: ${fmtDateOnly(m.endDate)}`); return rows; }
  function renderMeds(listEl, meds, opts){ opts=opts||{}; const activeOnly=!!opts.activeOnly; if(!Array.isArray(meds)){ listEl.innerHTML='<li class="vital-empty">No recent medications</li>'; return { count:0 }; } const cutoff=new Date(); cutoff.setDate(cutoff.getDate()-90); let recent=meds.filter(m=>{ const sdt=m.startDate||m.lastFilled||(m.source||{}).updated||m.endDate; const d = sdt? new Date(sdt) : null; const s=(m.status||'').toLowerCase(); const act=s==='active' || s.includes('active'); const pend=s==='pending' || s.includes('pending'); return (d && d>=cutoff) || act || pend; }); if(activeOnly) recent=recent.filter(m => { const s=(m.status||'').toLowerCase(); return s.includes('active') || s.includes('pending'); }); if(!recent.length){ listEl.innerHTML='<li class="vital-empty">No medications in the current view</li>'; return { count:0 }; }
    const groups={ active:[], pending:[], expired:[], discontinued:[], other:[] }; for(const m of recent){ groups[medStatusBucket(m)].push(m); }
    function appendGroup(arr, cls){ arr.sort((a,b)=> String(b.startDate||b.lastFilled||'').localeCompare(String(a.startDate||a.lastFilled||''))); for(const m of arr){ const li=document.createElement('li'); li.className=cls; li.style.cursor='pointer'; const name=titleCase(m.name||'Medication'); const dose=m.dose? ` — ${m.dose}`:''; li.textContent = name + dose; li.addEventListener('click', (e)=>{ e.stopPropagation(); togglePopover(li, name, medDetailRows(m)); }); listEl.appendChild(li); } }
    appendGroup(groups.active,'med-active'); appendGroup(groups.pending,'med-pending'); if(!activeOnly){ appendGroup(groups.expired,'med-expired'); appendGroup(groups.discontinued,'med-discontinued'); appendGroup(groups.other,''); }
    return { count: recent.length };
  }
  function isDiabetesProblem(p){ return /diabetes/i.test(p.name||''); }
  async function renderProblems(listEl, problems, meds){
    if(!problems||!problems.length){
      listEl.innerHTML='<li class="vital-empty">No problems listed</li>';
      return { count:0 };
    }
    const active=[], inactive=[];
    for(const p of problems){ (p.active? active:inactive).push(p); }
    const ordered=active.concat(inactive);
    for(const p of ordered){
      const li=document.createElement('li');
      li.style.cursor='pointer';
      const name=titleCase(p.name||'Problem');
      const status=p.active? '':' (Inactive)';
      li.textContent = name + status;
      li.addEventListener('click', async (e)=>{
        e.stopPropagation();
        const rows=[];
        if(p.clinicalStatus) rows.push(`Status: ${p.clinicalStatus}`);
        if(p.severity) rows.push(`Severity: ${p.severity}`);
        if(p.onsetDateTime) rows.push(`Onset: ${fmtDateOnly(p.onsetDateTime)}`);
        if(p.recordedDate) rows.push(`Recorded: ${fmtDateOnly(p.recordedDate)}`);
        if(Array.isArray(p.comments) && p.comments.length){
          rows.push('Comments:');
          p.comments.forEach(c => {
            const text = (typeof c === 'object' && c && 'text' in c) ? c.text : String(c);
            if(text && text.trim()) rows.push(text);
          });
        } else if(p.commentText) {
          if(p.commentText && String(p.commentText).trim()) rows.push(String(p.commentText));
        }
        if(isDiabetesProblem(p)){
          try{
            // Reuse already-fetched labs from state to avoid refetch
            const labs = (state && state.labs && Array.isArray(state.labs.labs)) ? state.labs.labs : [];
            const a1c = labs.filter(r=>{ const n=_norm(r.test||r.localName); const l=_norm(r.loinc); return (l&&l==='4548-4') || /\b(hb)?a1c\b/i.test(n) || /hemoglobin a1c/i.test(n) || /glyco.?hemoglobin/i.test(n); })
              .map(r=>({ v: toNum(r.result), u:r.unit, d: new Date(r.resulted||r.collected||0) })).filter(x=>x.v!=null && !isNaN(x.d)).sort((a,b)=>a.d-b.d);
            rows.push('—'); rows.push('A1c (last 3):');
            a1c.slice(-3).reverse().forEach(x=> rows.push(`  ${x.v}${x.u?(' '+x.u):'%'} — ${fmtDateOnly(x.d)}`));
          }catch(_e){}
        }
        togglePopover(li, name, rows);
      });
      listEl.appendChild(li);
    }
    return { count: ordered.length };
  }

  function renderVitalsAndLabs(mount){
    const vitals = (state.data && state.data.vitals) || {};
    const bpArr = vitals.bloodPressure||[]; const hrArr=vitals.heartRate||[]; const rrArr=vitals.respiratoryRate||[]; const spArr=vitals.oxygenSaturation||[]; const tArr=vitals.temperature||[]; const wArr=vitals.weight||[];
    const bp=latest(bpArr), hr=latest(hrArr), rr=latest(rrArr), spo2=latest(spArr), temp=latest(tArr), weight=latest(wArr);    const grid=document.createElement('div'); grid.className='vitals-grid'; grid.setAttribute('role','group'); grid.setAttribute('aria-label','Recent vitals');
    // ...existing vitals grid uses full container width by default; no inline width cap

    function cell(){ const d=document.createElement('div'); d.className='vital-cell vital-item'; d.style.display='flex'; d.style.justifyContent='flex-end'; d.style.alignItems='baseline'; d.style.textAlign='right'; return d; }
    function addDateAndStaleness(el, dtStr){
      try{
        const dt = dtStr ? new Date(dtStr) : null;
        const dateEl = document.createElement('span');
        dateEl.className = 'vital-date-mini';
        dateEl.textContent = dt ? ' ' + fmtDateOnly(dt) : '';
        dateEl.style.fontSize = '0.8em';
        dateEl.style.color = '#777';
        dateEl.style.marginLeft = '6px';
        el.appendChild(dateEl);
        if (dt && (Date.now() - dt.getTime() > 24*60*60*1000)) {
          el.style.fontStyle = 'italic';
        }
      }catch(_e){}
    }
    
    // HR - keep as reference pattern
  const hrCell=cell(); if(hr && hr.value!=null){ const wrap=document.createElement('div'); wrap.className='hr-readout'; wrap.style.display='inline-flex'; wrap.style.gap='4px'; wrap.style.alignItems='baseline'; wrap.style.justifyContent='flex-end'; const vEl=document.createElement('span'); vEl.className='hr-value'; vEl.textContent=String(hr.value); const uEl=document.createElement('span'); uEl.className='hr-bpm'; uEl.textContent='BPM'; wrap.appendChild(vEl); wrap.appendChild(uEl); let hrPct=null; if(hrArr.length>=2){ const a=hrArr[hrArr.length-1], b=hrArr[hrArr.length-2]; hrPct=calcPctDelta(a.value,b.value);} const ind=buildDeltaIndicator(hrPct); if(ind) hrCell.appendChild(ind); hrCell.appendChild(wrap); addDateAndStaleness(hrCell, hr.effectiveDateTime); const rows=(hrArr||[]).slice(-3).reverse().map(x=>`${x.value} bpm — ${fmtDate(x.effectiveDateTime)}`); hrCell.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(hrCell,'Heart Rate (last 3)',rows); }); } grid.appendChild(hrCell);
    
    // BP - simplified to SBP/DBP format like HR
  const bpCell=cell(); if(bp && (bp.systolic!=null||bp.diastolic!=null)){ const wrap=document.createElement('div'); wrap.className='hr-readout'; wrap.style.display='inline-flex'; wrap.style.gap='4px'; wrap.style.alignItems='baseline'; wrap.style.justifyContent='flex-end'; const vEl=document.createElement('span'); vEl.className='hr-value'; vEl.textContent=`${bp.systolic??''}/${bp.diastolic??''}`; const uEl=document.createElement('span'); uEl.className='hr-bpm'; uEl.textContent='mmHg'; wrap.appendChild(vEl); wrap.appendChild(uEl); let bpPct=null; if(bpArr.length>=2){ const [b0,b1]=bpArr.slice(-2); const m0=calcMAP(b0), m1=calcMAP(b1); if(m0!=null&&m1!=null) bpPct=calcPctDelta(m1,m0);} const ind=buildDeltaIndicator(bpPct); if(ind) bpCell.appendChild(ind); bpCell.appendChild(wrap); addDateAndStaleness(bpCell, bp.effectiveDateTime); const rows=(bpArr||[]).slice(-3).reverse().map(x=>`${(x.systolic??'')}/${(x.diastolic??'')} — ${fmtDate(x.effectiveDateTime)}`); bpCell.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(bpCell,'Blood Pressure (last 3)',rows); }); } grid.appendChild(bpCell);
    
    // RR - changed to HR pattern
  const rrCell=cell(); if(rr && rr.value!=null){ let rrPct=null; if(rrArr.length>=2){ const a=rrArr[rrArr.length-1], b=rrArr[rrArr.length-2]; rrPct=calcPctDelta(a.value,b.value);} const ind=buildDeltaIndicator(rrPct); if(ind) rrCell.appendChild(ind); const wrap=document.createElement('div'); wrap.className='hr-readout'; wrap.style.display='inline-flex'; wrap.style.gap='4px'; wrap.style.alignItems='baseline'; wrap.style.justifyContent='flex-end'; const vEl=document.createElement('span'); vEl.className='hr-value'; vEl.textContent=String(rr.value); const uEl=document.createElement('span'); uEl.className='hr-bpm'; uEl.textContent='/min'; wrap.appendChild(vEl); wrap.appendChild(uEl); rrCell.appendChild(wrap); addDateAndStaleness(rrCell, rr.effectiveDateTime); const rows=(rrArr||[]).slice(-3).reverse().map(x=>`${x.value} — ${fmtDate(x.effectiveDateTime)}`); rrCell.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(rrCell,'Respiratory Rate (last 3)',rows); }); } grid.appendChild(rrCell);
    
    // SpO2 - changed to HR pattern
  const spCell=cell(); if(spo2 && spo2.value!=null){ let spPct=null; if(spArr.length>=2){ const a=spArr[spArr.length-1], b=spArr[spArr.length-2]; spPct=calcPctDelta(a.value,b.value);} const ind=buildDeltaIndicator(spPct); if(ind) spCell.appendChild(ind); const wrap=document.createElement('div'); wrap.className='hr-readout'; wrap.style.display='inline-flex'; wrap.style.gap='4px'; wrap.style.alignItems='baseline'; wrap.style.justifyContent='flex-end'; const vEl=document.createElement('span'); vEl.className='hr-value'; vEl.textContent=String(spo2.value); const uEl=document.createElement('span'); uEl.className='hr-bpm'; uEl.textContent='%'; wrap.appendChild(vEl); wrap.appendChild(uEl); spCell.appendChild(wrap); addDateAndStaleness(spCell, spo2.effectiveDateTime); const rows=(spArr||[]).slice(-3).reverse().map(x=>`${x.value}% — ${fmtDate(x.effectiveDateTime)}`); spCell.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(spCell,'SpO₂ (last 3)',rows); }); } grid.appendChild(spCell);
    
    // Temp (F) - changed to HR pattern
    function fmtF(v,u){ const ul=(u||'').toLowerCase(); if(ul.includes('f')) return { val: toNum(v)!=null? Math.round(toNum(v)*10)/10 : null, unit:'°F' }; const c=toNum(v); if(c==null) return { val:null, unit:'°F' }; const f=(c*9/5)+32; return { val: Math.round(f*10)/10, unit:'°F' }; }
  const tCell=cell(); if(temp && temp.value!=null){ let pct=null; if(tArr.length>=2){ const a=tArr[tArr.length-1], b=tArr[tArr.length-2]; const va=fmtF(a.value,a.unit).val, vb=fmtF(b.value,b.unit).val; pct=calcPctDelta(va,vb);} const ind=buildDeltaIndicator(pct); if(ind) tCell.appendChild(ind); const conv=fmtF(temp.value,temp.unit); if(conv.val!=null){ const wrap=document.createElement('div'); wrap.className='hr-readout'; wrap.style.display='inline-flex'; wrap.style.gap='4px'; wrap.style.alignItems='baseline'; wrap.style.justifyContent='flex-end'; const vEl=document.createElement('span'); vEl.className='hr-value'; vEl.textContent=String(conv.val); const uEl=document.createElement('span'); uEl.className='hr-bpm'; uEl.textContent=conv.unit; wrap.appendChild(vEl); wrap.appendChild(uEl); tCell.appendChild(wrap); addDateAndStaleness(tCell, temp.effectiveDateTime); const rows=(tArr||[]).slice(-3).reverse().map(x=>{ const c=fmtF(x.value,x.unit); return `${c.val}${c.unit} — ${fmtDate(x.effectiveDateTime)}`; }); tCell.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(tCell,'Temperature (last 3)',rows); }); } }
    grid.appendChild(tCell);
    
    // Weight (lbs) - changed to HR pattern
    function fmtLb(v,u){ const ul=(u||'').toLowerCase(); if(ul.includes('lb')) return { val: toNum(v)!=null? Math.round(toNum(v)*10)/10 : null, unit:'lbs' }; const kg=toNum(v); if(kg==null) return { val:null, unit:'lbs' }; const lbs=kg*2.2046226218; return { val: Math.round(lbs*10)/10, unit:'lbs' }; }
  const wCell=cell(); if(weight && weight.value!=null){ let pct=null; if(wArr.length>=2){ const a=wArr[wArr.length-1], b=wArr[wArr.length-2]; const va=fmtLb(a.value,a.unit).val, vb=fmtLb(b.value,b.unit).val; pct=calcPctDelta(va,vb);} const ind=buildDeltaIndicator(pct); if(ind) wCell.appendChild(ind); const conv=fmtLb(weight.value,weight.unit); if(conv.val!=null){ const wrap=document.createElement('div'); wrap.className='hr-readout'; wrap.style.display='inline-flex'; wrap.style.gap='4px'; wrap.style.alignItems='baseline'; wrap.style.justifyContent='flex-end'; const vEl=document.createElement('span'); vEl.className='hr-value'; vEl.textContent=String(conv.val); const uEl=document.createElement('span'); uEl.className='hr-bpm'; uEl.textContent=conv.unit; wrap.appendChild(vEl); wrap.appendChild(uEl); wCell.appendChild(wrap); addDateAndStaleness(wCell, weight.effectiveDateTime); const rows=(wArr||[]).slice(-3).reverse().map(x=>{ const c=fmtLb(x.value,x.unit); return `${c.val} ${c.unit} — ${fmtDate(x.effectiveDateTime)}`; }); wCell.addEventListener('click',(e)=>{ e.stopPropagation(); togglePopover(wCell,'Weight (last 3)',rows); }); } }
    grid.appendChild(wCell);

    mount.appendChild(grid);

    // Labs fishbones (deferred)
    const labs = state.labs && Array.isArray(state.labs.labs)? state.labs.labs : [];
    if(labs && labs.length){
      const placeholder = document.createElement('div');
      placeholder.className='labs-fishbone';
      placeholder.innerHTML = '<div style="font-size:0.85em;color:#777;margin:8px 0 4px 2px;">Loading labs…</div>';
      mount.appendChild(placeholder);

      const buildAndRender = ()=>{
        try{
          const series=buildLabSeries(labs);
          const wrap=document.createElement('div'); wrap.className='labs-fishbone';
          const latestDateFor=(keys)=>{ let latest=null; keys.forEach(k=>{ const arr=series[k]||[]; if(arr.length){ const d=new Date(arr[arr.length-1].date||0); if(!isNaN(d) && (!latest||d>latest)) latest=d; } }); return latest; };
          const bmpDate=latestDateFor(['na','k','cl','hco3','bun','cr','glu']);
          const cbcDate=latestDateFor(['wbc','hgb','hct','plt']);
          const fishRow=document.createElement('div'); fishRow.style.display='flex'; fishRow.style.gap='16px'; fishRow.style.alignItems='flex-start'; fishRow.style.flexWrap='nowrap';
          const colBMP=document.createElement('div'); colBMP.style.flex='1 1 0'; colBMP.style.minWidth='0'; const bmpT=document.createElement('div'); bmpT.textContent = 'BMP' + (bmpDate? (' '+fmtDateOnly(bmpDate)):''); bmpT.style.fontSize='0.85em'; bmpT.style.color='#555'; bmpT.style.margin='8px 0 4px 2px'; const bmp=renderBMP(series); colBMP.appendChild(bmpT); colBMP.appendChild(bmp);
          const colCBC=document.createElement('div'); colCBC.style.flex='1 1 0'; colCBC.style.minWidth='0'; const cbcT=document.createElement('div'); cbcT.textContent='CBC' + (cbcDate? (' '+fmtDateOnly(cbcDate)):''); cbcT.style.fontSize='0.85em'; cbcT.style.color='#555'; cbcT.style.margin='8px 0 4px 2px'; const cbc=renderCBC(series); colCBC.appendChild(cbcT); colCBC.appendChild(cbc);

          placeholder.replaceWith(wrap);
          fishRow.appendChild(colBMP); fishRow.appendChild(colCBC); wrap.appendChild(fishRow);

          // Additional labs/studies sections (separators removed per UX)
          const sectionHeader = (title, opts) => { const h=document.createElement('div'); h.textContent=title; h.style.fontSize='0.95em'; h.style.color='var(--paper-contrast)'; h.style.margin='6px 0 4px 2px'; h.style.fontWeight = (opts && opts.bold===false) ? '400' : '600'; return h; };
          function makeDateMini(d){ const s=document.createElement('span'); s.className='vital-date-mini'; s.textContent=d? ` (${fmtDateOnly(d)})` : ''; s.style.fontSize='0.85em'; s.style.color='#777'; s.style.marginLeft='6px'; return s; }
          function makeValueSpan(text, abnormal){ const v=document.createElement('span'); v.textContent=text; v.style.marginLeft='6px'; v.style.color = abnormal? '#ef5350' : brandBlue(); v.style.fontWeight='600'; return v; }
          function makeLine(label, results, type, unitFallback){
            const line=document.createElement('div'); line.style.display='flex'; line.style.alignItems='baseline'; line.style.gap='4px'; line.style.padding='2px 2px'; line.style.cursor = (results&&results.length)? 'pointer' : 'default';
            const lab=document.createElement('span'); lab.textContent = label + ':'; lab.style.color='#555'; lab.style.minWidth='64px'; line.appendChild(lab);
            const last = results && results.length? results[results.length-1] : null;
            const unit = (last && last.u) ? last.u : (unitFallback||'');
            const valueText = last? fmtVal(last.v, unit) : '';
            let abnormal = false;
            if(last){
              const ab = abnormalByRef(last.v, last.raw);
              if(ab===true) abnormal = true; else if(ab===null) abnormal = (severityForExtra(type, last.v)==='abnormal');
            }
            const vSpan = makeValueSpan(valueText, abnormal);
            line.appendChild(vSpan);
            line.appendChild(makeDateMini(last? last.d : null));
            if(results && results.length){
              line.addEventListener('click', (e)=>{
                e.stopPropagation();
                const rows = lastN(results,3).map(x=> `${fmtVal(x.v, x.u || unitFallback || '')} — ${fmtDate(x.d)}`);
                togglePopover(line, `${label} (last 3)`, rows);
              });
            }
            return line;
          }
          function makeIndentedLine(label, results, type, unitFallback){ const d=makeLine(label, results, type, unitFallback); d.style.paddingLeft='16px'; return d; }
          // Vertical divider removed; columns will stack or sit side-by-side based on available width

          const labsList = document.createElement('div'); labsList.className='labs-additional-list'; labsList.style.marginTop='8px';

          const allLabs = (state.labs && state.labs.labs) || [];

          // 1) A1c, Lipid, TSH | Vertical | Liver labs (no separators)
          const row1=document.createElement('div'); row1.style.display='flex'; row1.style.gap='12px'; row1.style.alignItems='flex-start'; row1.style.flexWrap='wrap'; row1.style.marginTop='10px';
          const col1=document.createElement('div'); col1.style.minWidth='220px';
          // A1c
          const a1cRes = findLabs(allLabs, ['4548-4'], [/\b(hb)?a1c\b/i, /hemoglobin a1c/i, /glyco.?hemoglobin/i]);
          col1.appendChild(makeLine('A1c', a1cRes, 'a1c', '%'));
          // Lipids
          const cholTot = findLabs(
            allLabs,
            ['2093-3'],
            [
              /^(total\s+)?cholesterol(?!.*hdl)(?!.*ldl)/i,
              /\bcholesterol\b(?!.*\bhdl\b)(?!.*\bldl\b)/i,
              /cholesterol total/i,
              /\btc\b/i
            ]
          );
          const trig = findLabs(allLabs, ['2571-8'], [/triglycerides?/i, /\btg\b/i]);
          const hdl = findLabs(allLabs, ['2085-9'], [/\bhdl\b/i]);
          const ldl = findLabs(allLabs, ['2089-1','13457-7'], [/\bldl\b/i]);
          col1.appendChild(sectionHeader('Lipids', { bold: false }));
          col1.appendChild(makeIndentedLine('Cholesterol', cholTot, 'tc', 'mg/dL'));
          col1.appendChild(makeIndentedLine('TG', trig, 'tg', 'mg/dL'));
          col1.appendChild(makeIndentedLine('HDL', hdl, 'hdl', 'mg/dL'));
          col1.appendChild(makeIndentedLine('LDL', ldl, 'ldl', 'mg/dL'));
          // TSH
          const tshRes = findLabs(allLabs, ['3016-3'], [/\btsh\b/i]);
          col1.appendChild(makeLine('TSH', tshRes, 'tsh', 'mIU/L'));

          // Liver labs in col2
          const col2=document.createElement('div'); col2.style.minWidth='220px';
          col2.appendChild(sectionHeader('Liver'));
          const ast = findLabs(allLabs, ['1920-8'], [/\bast\b/i, /sgot/i, /aspartate aminotransferase/i]);
          const alt = findLabs(allLabs, ['1742-6'], [/\balt\b/i, /sgpt/i, /alanine aminotransferase/i]);
          const alk = findLabs(allLabs, ['6768-6'], [/alk(aline)?\s*phos(phatase)?/i]);
          const tbili = findLabs(allLabs, ['1975-2'], [/total\s+bili(rubin)?/i, /\btbili\b/i]);
          const inr = findLabs(allLabs, ['6301-6','34714-6'], [/\binr\b/i]);
          col2.appendChild(makeLine('AST/SGOT', ast, 'ast', 'U/L'));
          col2.appendChild(makeLine('ALT/SGPT', alt, 'alt', 'U/L'));
          col2.appendChild(makeLine('Alk Phos', alk, 'alkphos', 'U/L'));
          col2.appendChild(makeLine('Total Bili', tbili, 'tbili', 'mg/dL'));
          col2.appendChild(makeLine('INR', inr, 'inr', ''));

          row1.appendChild(col1); row1.appendChild(col2);
          labsList.appendChild(row1);

          // 2) PSA group | Vertical | HIV/Hep C (no separators)
          const row2=document.createElement('div'); row2.style.display='flex'; row2.style.gap='12px'; row2.style.alignItems='flex-start'; row2.style.flexWrap='wrap'; row2.style.marginTop='12px';
          const colL=document.createElement('div'); colL.style.minWidth='220px';
          const psaRes = findLabs(allLabs, ['2857-1'], [/prostate\W?specific\W?antigen/i, /\bpsa\b/i]);
          colL.appendChild(makeLine('PSA', psaRes, 'psa', 'ng/mL'));
          const fitRes = findLabs(allLabs, [], [/\bfit\b/i, /fecal immunochemical/i]);
          colL.appendChild(makeLine('FIT', fitRes, 'fit', ''));
          colL.appendChild(sectionHeader('Colonoscopy', { bold: false }));
          const papRes = findLabs(allLabs, [], [/\bpap\b/i, /papanicolaou/i]);
          const hpvRes = findLabs(allLabs, [], [/\bhpv\b/i]);
          const papHpvCombined = [...papRes, ...hpvRes].sort((a,b)=> a.d - b.d);
          colL.appendChild(makeLine('PAP/HPV', papHpvCombined, 'paphpv', ''));
          colL.appendChild(sectionHeader('Mammogram', { bold: false }));
          colL.appendChild(sectionHeader('LDCT', { bold: false }));

          const colR=document.createElement('div'); colR.style.minWidth='220px';
          const hivRes = findLabs(allLabs, [], [/\bhiv\b/i]);
          colR.appendChild(makeLine('HIV', hivRes, 'hiv', ''));
          const hcvRes = findLabs(allLabs, ['13955-0'], [/hepatitis c/i, /\bhcv\b/i]);
          colR.appendChild(makeLine('Hepatitis C', hcvRes, 'hcv', ''));

          row2.appendChild(colL); row2.appendChild(colR);
          labsList.appendChild(row2);

          wrap.appendChild(labsList);
        }catch(_e){ try{ placeholder.textContent = 'Labs unavailable'; }catch(_ee){} }
      };

      try{
        if('requestIdleCallback' in window){ window.requestIdleCallback(buildAndRender, { timeout: 120 }); }
        else { setTimeout(buildAndRender, 0); }
      }catch(_e){ setTimeout(buildAndRender, 0); }
    }
  }

  function renderRightColumn(mount, data){
    const wrap = document.createElement('div');
    wrap.style.display='flex';
    wrap.style.flexDirection='column';
    wrap.style.gap='10px';

    // Theme Snapshot collapsibles with paper/manila styling
    const style = document.createElement('style');
    style.textContent = `
      .snapshot-collapsible { background: var(--paper-panel); border: 1px solid var(--paper-border); border-radius: 8px; overflow: hidden; }
      .snapshot-collapsible > summary { list-style: none; cursor: pointer; padding: 8px 12px; background: color-mix(in srgb, var(--brand-blue) 6%, var(--paper-panel)); border-bottom: 1px solid var(--paper-border); color: var(--paper-contrast); font-weight: 600; }
      .snapshot-collapsible > summary::-webkit-details-marker { display:none; }
      .snapshot-collapsible .vital-reads { list-style: none; margin: 0; padding: 10px 14px; color: var(--paper-contrast); }
      .snapshot-collapsible .vital-reads li { margin: 4px 0; }
      .snapshot-collapsible .vital-reads li.med-active { color: var(--brand-blue); }
      .snapshot-collapsible .vital-reads li.med-pending { color: #8a6d3b; }
      .snapshot-collapsible .vital-reads li.med-expired,
      .snapshot-collapsible .vital-reads li.med-discontinued { color: #777; font-style: italic; }
    `;
    mount.appendChild(style);

    function makeSection(title){
      const det=document.createElement('details');
      det.open=false;
      det.className='snapshot-collapsible';
      const sum=document.createElement('summary');
      sum.textContent=title;
      const ul=document.createElement('ul');
      ul.className='vital-reads';
      det.appendChild(sum);
      det.appendChild(ul);
      return { det, ul, sum };
    }

  const probs = makeSection('Active Problems'); probs.det.open=true; const pr = (data&&data.problems)||[]; renderProblems(probs.ul, pr, (data&&data.medications)||[]).then(res=>{ probs.sum.textContent = `Active Problems (${(pr||[]).filter(p=>p.active).length})`; }); wrap.appendChild(probs.det);

  const algs = makeSection('Allergies'); algs.det.open=true; renderAllergies(algs.ul, (data&&data.allergies)||[]); algs.sum.textContent = `Allergies (${((data&&data.allergies)||[]).length})`; wrap.appendChild(algs.det);

  const meds = makeSection('Medications'); meds.det.open=true; const medRes = renderMeds(meds.ul, (data&&data.medications)||[], { activeOnly: false }); meds.sum.textContent = `Medications (${medRes.count})`; wrap.appendChild(meds.det);

    mount.appendChild(wrap);
  }

  async function render(container){
    const perfOn = (function(){ try{ return window.__WS_PERF || localStorage.getItem('ws_perf')==='1'; }catch(_e){ return false; } })();
    const tRenderStart = (perfOn && performance && performance.now) ? performance.now() : 0;
    // Ensure CSS is installed for unified scroll and responsive flow
    ensureSnapshotStyles();
    containerRef = container;
    // Abort any in-flight requests from a prior render to prevent overlaps
    try { cancelAll(); } catch(_e){}
    // Clear per-URL cache to avoid cross-patient reuse
    try { requestCache.clear(); } catch(_e){}
    try { if (container && container.dataset) container.dataset.loading = '1'; } catch(_e){}
    container.innerHTML = '';

    // Layout
    const layout = document.createElement('div'); layout.className='snapshot-layout'; layout.style.display='flex'; layout.style.gap='12px'; layout.style.height='100%';
  const left = document.createElement('div'); left.style.flex='1 1 0'; left.style.minWidth='0'; left.style.overflow='visible'; left.style.paddingRight='4px';
  const right = document.createElement('div'); right.style.flex='1 1 0'; right.style.minWidth='0'; right.style.overflow='visible'; right.style.paddingLeft='4px';
    // Removed blue box styling to make text appear directly on the tab

    // Mount points
    const leftMount = document.createElement('div'); leftMount.id='snapshotLeft'; leftMount.innerHTML = '<div class="vital-loading">Loading vitals…</div>';
    const rightMount = document.createElement('div'); rightMount.id='snapshotRight'; rightMount.innerHTML = '<div class="vital-loading">Loading summary…</div>';
    
    left.appendChild(leftMount); right.appendChild(rightMount); layout.appendChild(left); layout.appendChild(right); container.appendChild(layout);

    // Ensure patient selected (no legacy /get_patient)
    let patientMeta = null;
    try {
      if (window.PatientContext && typeof window.PatientContext.get === 'function') {
        patientMeta = await window.PatientContext.get();
      }
    } catch(_e){}
    if(!patientMeta || !patientMeta.dfn){ leftMount.innerHTML='<div class="vital-empty">Select a patient to view snapshot.</div>'; rightMount.innerHTML=''; try { if (container && container.dataset) delete container.dataset.loading; } catch(_e){} return; }

    // Load left + right in parallel
    try{
      const tFetchStart = (perfOn && performance && performance.now) ? performance.now() : 0;
      // Use refactor Api client with DFN-aware endpoints
      const [vRes, lRes, aRes, mRes, pRes] = await Promise.all([
        window.Api && Api.quick ? Api.quick('demographics').then(() => Api.quick('vitals')).catch(()=>null) : Promise.resolve(null),
        (window.Api && Api.quick ? Api.quick('labs', { days: 365, maxPanels: 60 }) : Promise.resolve({ labs: [] })).catch(()=>({ labs: [] })),
        (window.Api && Api.quick ? Api.quick('allergies') : Promise.resolve({ allergies: [] })).catch(()=>({ allergies: [] })),
        (window.Api && Api.quick ? Api.quick('meds', { status: 'ACTIVE+PENDING', days: 365 }) : Promise.resolve({ medications: [] })).catch(()=>({ medications: [] })),
        (window.Api && Api.quick ? Api.quick('problems', { detail: 1 }) : Promise.resolve({ problems: [] })).catch(()=>({ problems: [] }))
      ]);
      if (perfOn && performance && performance.now) {
        try { console.log(`SNAPSHOT:fetch-all took ${(performance.now()-tFetchStart).toFixed(0)}ms`); } catch(_e){}
      }
      state.data = vRes || { vitals: {} };
      state.labs = lRes || { labs: [] };
      state.right = { allergies: (aRes&&aRes.allergies)||[], medications: (mRes&&mRes.medications)||[], problems: (pRes&&pRes.problems)||[] };
      const t0 = (perfOn && performance && performance.now)? performance.now() : 0;
      leftMount.innerHTML=''; renderVitalsAndLabs(leftMount);
      rightMount.innerHTML=''; renderRightColumn(rightMount, state.right);
      if(perfOn && performance && performance.now){ console.log(`SNAPSHOT:paint took ${(performance.now()-t0).toFixed(0)}ms`); }
    }catch(e){ leftMount.innerHTML='<div class="vital-error">Failed to load snapshot.</div>'; rightMount.innerHTML=''; }
    finally { try { if (container && container.dataset) delete container.dataset.loading; } catch(_e){} }
    if (perfOn && performance && performance.now) {
      try { console.log(`SNAPSHOT:render took ${(performance.now()-tRenderStart).toFixed(0)}ms`); } catch(_e){}
    }
  }

  function refresh(){ if(containerRef){ render(containerRef); } }
  function destroy(){ cancelAll(); closePopover(); containerRef=null; }

  window.WorkspaceModules = window.WorkspaceModules || {};
  window.WorkspaceModules[MODULE_NAME] = { render, refresh, destroy };

  // No global event listeners; orchestrator will trigger refresh at correct stage
})();
