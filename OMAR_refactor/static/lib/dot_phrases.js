// filepath: static/lib/dot_phrases.js
// Shared dot-phrase utility for Workspace, Scribe, Note, Explore/Hey OMAR
// Tokens supported: .name, .dob, .age, .meds, .meds/active, .problems, .problems/active,
// .vitals[/start=YYYY-MM-DD][/end=YYYY-MM-DD][/since=...][/days=N],
// .labs[/<filters comma>][/start=...][/end=...][/since=...][/days=N][/all=1][:last|:all|:days=N|:range=YYYY-MM-DD..YYYY-MM-DD],
// .orders[:status=<current|active|pending|all>,type=<all|labs|meds>,days=N] or .orders/<status>/<type>/<days>
// Behavior:
// - Skips replacement when token is wrapped like {.token}
// - No legacy [[...]] support
// - Uses /quick/patient/* endpoints when available, with /fhir/* fallbacks

(function(){
  const g = (typeof window !== 'undefined') ? window : globalThis;

  function escHtml(s){ return String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]||c)); }

  // Fetch helpers
  async function getJson(url, opts){
    try {
      const r = await fetch(url, Object.assign({ cache:'no-store', credentials:'same-origin' }, opts||{}));
      if (!r.ok) return null;
      return await r.json().catch(()=>null);
    } catch(_e){ return null; }
  }

  // Patient metadata helpers
  async function getPatientMeta(){
    // Use PatientContext only; avoid legacy /get_patient
    try{
      if (g.PatientContext && typeof g.PatientContext.get === 'function'){
        const meta = await g.PatientContext.get();
        if (meta && meta.dfn) return meta;
      }
    }catch(_e){}
    // Fallback to in-memory/session DFN only (no network)
    try{
      const dfn = (g.CURRENT_PATIENT_DFN || (g.sessionStorage && g.sessionStorage.getItem && g.sessionStorage.getItem('CURRENT_PATIENT_DFN')) || '').toString();
      if (dfn) return { dfn };
    }catch(_e){}
    return {};
  }

  // Formatting
  function fmtMeds(meds){
    try{ if(!Array.isArray(meds)||!meds.length) return 'None';
      return meds.map(m=>{
        const name = m && (m.name||m.display||m.text) ? String(m.name||m.display||m.text) : 'Unknown';
        const parts = [];
        if(m && m.dose) parts.push(String(m.dose));
        if(m && m.route) parts.push(String(m.route));
        if(m && m.frequency) parts.push(String(m.frequency));
        const tail = parts.length? ' — '+parts.join(' ') : '';
        return `- ${name}${tail}`;
      }).join('\n');
    }catch(_e){ return 'None'; }
  }
  function fmtProblems(arr, activeOnly){
    try{ const a = Array.isArray(arr)? (activeOnly? arr.filter(p=>p&&p.active):arr) : [];
      if(!a.length) return activeOnly ? 'No active problems' : 'None';
      return a.map(p=> `- ${p && p.name ? String(p.name) : 'Unknown'}${(p && p.active===false)?' (inactive)':''}`).join('\n');
    }catch(_e){ return 'None'; }
  }
  function fmtProblemsDetailed(arr, activeOnly){
    try{
      const a = Array.isArray(arr)? (activeOnly? arr.filter(p=>p&&p.active):arr) : [];
      if(!a.length) return activeOnly ? 'No active problems' : 'None';
      const lines = [];
      for(const p of a){
        const name = p?.name ? String(p.name).trim() : 'Unknown';
        const status = (p?.status || (p?.active===false ? 'inactive' : 'active') || '').toString().toLowerCase();
        const recorded = (p?.recordedDate || p?.enteredDate || p?.onsetDate || '').toString();
        const updated = (p?.updatedDate || '').toString();
        const prov = (p?.provider || '').toString();
        const clinic = (p?.clinic || '').toString();
        const tail = [];
        if(status) tail.push(status);
        if(recorded) tail.push(`recorded ${recorded.slice(0,10)}`);
        else if(updated) tail.push(`updated ${updated.slice(0,10)}`);
        if(prov) tail.push(`provider: ${prov}`);
        if(clinic) tail.push(`clinic: ${clinic}`);
        const header = `- ${name}${tail.length? ' ('+tail.join(', ')+')' : ''}`;
        const cmts = Array.isArray(p?.comments)? p.comments.slice(0,2).map(c=> typeof c==='string'? c : (c?.text||c?.comment||'')).map(s=> String(s||'').trim()).filter(Boolean) : [];
        if(cmts.length){ lines.push(`${header}\n    • comments: ${cmts.join('; ')}`); }
        else { lines.push(header); }
      }
      return lines.join('\n');
    }catch(_e){ return 'None'; }
  }
  function fmtVitalsTable(vitals){
    try{
      const rows=[]; const add=(date,type,value,unit)=>{ const d=date? String(date).slice(0,10):''; rows.push({date:d,type:String(type||''),value:String(value??''),unit:String(unit||'')}); };
      const safe=(x)=> Array.isArray(x)? x:[]; const v=vitals||{};
      safe(v.bloodPressure).forEach(rec=>{ const dt=rec?.effectiveDateTime; const sys=rec?.systolic; const dia=rec?.diastolic; const unit=rec?.unit||'mmHg'; if(sys!=null && dia!=null) add(dt,'BP',`${sys}/${dia}`,unit); });
      [['heartRate','HR'],['pulse','Pulse'],['respiratoryRate','RR'],['oxygenSaturation','SpO2'],['temperature','Temp'],['weight','Weight'],['height','Height'],['bmi','BMI']].forEach(([key,label])=>{
        safe(v[key]).forEach(rec=>{ const dt=rec?.effectiveDateTime; const val=(rec&&(rec.value!=null ? rec.value : rec.latest||rec.reading||rec.val)) ?? ''; const unit=(rec&&(rec.unit||rec.units)); add(dt,label,val,unit); });
      });
      rows.sort((a,b)=> (a.date<b.date?1:(a.date>b.date?-1:0)));
      if(!rows.length) return 'No vitals found';
      const header='| Date | Type | Value | Unit |\n|---|---|---|---|';
      const body=rows.map(r=>`| ${r.date} | ${r.type} | ${r.value} | ${r.unit} |`).join('\n');
      return `${header}\n${body}`;
    }catch(_e){ return 'No vitals found'; }
  }
  function fmtLabsTable(labs){
    try{
      const arr=Array.isArray(labs)? labs.slice():[]; const normDate=(r)=> (r && (r.resulted||r.collected||r.date||''));
      arr.sort((a,b)=> (normDate(a)<normDate(b)?1:(normDate(a)>normDate(b)?-1:0)));
      if(!arr.length) return 'No labs found';
      const header='| Date | Test | Result | Units | Abn |\n|---|---|---|---|---|';
      const rows=arr.map(r=>{
        const date=String(normDate(r)).slice(0,10);
        const test=r.test||r.localName||r.name||r.display||r.code||r.loinc||'';
        let result=''; if(r.result!=null) result=String(r.result); else if(r.value!=null) result=String(r.value);
        const units=r.units||r.unit||'';
        const abn = (r.flag||r.interpretation||r.abnormal)? String(r.flag||r.interpretation||(r.abnormal?'abn':'')) : '';
        return `| ${date} | ${String(test)} | ${String(result)} | ${String(units)} | ${abn} |`;
      }).join('\n');
      return `${header}\n${rows}`;
    }catch(_e){ return 'No labs found'; }
  }
  function fmtOrders(orders){
    try{ if(!Array.isArray(orders)||!orders.length) return 'No orders found';
      return orders.map(o=>{ const d=o?.date? String(o.date).slice(0,10):''; const typ=String(o?.type||''); const nm=String(o?.name||''); const st=String(o?.current_status||o?.status||''); const tail=st?` — ${st}`:''; return `• ${d}${d?': ':''}[${typ}] ${nm}${tail}`.trim(); }).join('\n');
    }catch(_e){ return 'No orders found'; }
  }
  function ordersTypeAlias(s){ const v=String(s||'').trim().toLowerCase(); if(['med','meds','medications','rx','pharmacy'].includes(v)) return 'meds'; if(['lab','labs','laboratory'].includes(v)) return 'labs'; return 'all'; }
  function ordersStatusAlias(s){ const v=String(s||'').trim().toLowerCase(); if(['active','a'].includes(v)) return 'active'; if(['pending','p'].includes(v)) return 'pending'; if(['current','actpend','active+pending','ap','c'].includes(v)) return 'current'; if(['all','*'].includes(v)) return 'all'; return 'current'; }
  function parseOrdersArgs(argStr){ let status='current', type='all', days=7; const s=String(argStr||'').trim(); if(!s) return {status,type,days};
    if(s.includes('=')||s.includes(',')){ const parts=s.split(/[\s,]+/).filter(Boolean); for(const part of parts){ const [kRaw,vRaw]=part.split('='); const k=(kRaw||'').toLowerCase(); const v=(vRaw||'').trim(); if(k==='status') status=ordersStatusAlias(v); else if(k==='type'||k==='category') type=ordersTypeAlias(v); else if(k==='days'){ const n=parseInt(v,10); if(Number.isFinite(n)&&n>0) days=n; } else if(k==='since'||k==='date'){ const dt=new Date(v); if(!isNaN(dt.getTime())){ const now=new Date(); const diffMs=Math.max(0, now-dt); days=Math.max(1, Math.ceil(diffMs/(1000*60*60*24))); } } } return {status,type,days}; }
    const parts=s.split(/[\s/]+/).filter(Boolean); if(parts[0]) status=ordersStatusAlias(parts[0]); if(parts[1]) type=ordersTypeAlias(parts[1]); if(parts[2]){ const d=parts[2].toLowerCase(); const n=parseInt(d,10); if(Number.isFinite(n)&&n>0) days=n; else { const dt=new Date(parts[2]); if(!isNaN(dt.getTime())){ const now=new Date(); const diffMs=Math.max(0, now-dt); days=Math.max(1, Math.ceil(diffMs/(1000*60*60*24))); } } } return {status,type,days}; }

  // Parse natural date-ish tokens seen in commands
  function parseNaturalDate(input, defaultEnd){ try{ let s=String(input||'').trim(); if(!s) return null; const today=new Date(); const ymd=(d)=> d.toISOString().slice(0,10);
    if(/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    if(/^\d{4}-\d{2}$/.test(s)){ const [y,m]=s.split('-').map(n=>parseInt(n,10)); const d=new Date(Date.UTC(y, m-1, defaultEnd? new Date(y, m, 0).getDate():1)); return ymd(d); }
    if(/^\d{4}$/.test(s)){ const y=parseInt(s,10); const d=new Date(Date.UTC(y, defaultEnd?11:0, defaultEnd?31:1)); return ymd(d); }
    const mon=s.match(/^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{4})$/i); if(mon){ const mMap={jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,sept:8,oct:9,nov:10,dec:11}; const key=mon[1].toLowerCase(); const y=parseInt(mon[2],10); const mm=mMap[key]; const d=new Date(Date.UTC(y, mm, defaultEnd? new Date(y, mm+1, 0).getDate():1)); return ymd(d); }
    if(s==='today' || s==='date') return ymd(today);
  }catch(_e){} return null; }

  // Token resolver
  async function resolveToken(tok){
    const t = String(tok||'').trim().toLowerCase();
    try{
      // name
      if (t === 'name' || t === 'patient'){
        const j = await getJson('/quick/patient/demographics');
        let full = '';
        if (j && j.demographics){
          const d = j.demographics;
          // Try multiple shapes: Name, name, first/last
          full = d.Name || d.name || [d.firstName, d.lastName].filter(Boolean).join(' ').trim();
          // If we see LAST,FIRST format, flip to First Last
          if (full && /,/.test(full)){
            const parts = String(full).split(',');
            const last = parts[0].trim();
            const first = parts.slice(1).join(',').trim();
            if (first && last) full = `${first} ${last}`;
          }
        }
        if (!full){
          const s = await getJson('/session_data');
          try{
            const ent = s?.patient_record?.entry || [];
            const pat = ent.find(e=> e?.resource?.resourceType==='Patient');
            const nm = pat?.resource?.name?.[0];
            if(nm){
              const given=(nm.given||[]).join(' ');
              const fam=nm.family||'';
              full=[given,fam].filter(Boolean).join(' ').trim();
            }
            full = full || '';
          }catch(_e){}
        }
        return full || '';
      }
      // dob
      if (t === 'dob'){
        const j = await getJson('/quick/patient/demographics');
        let dob = '';
        try{
          const d = j?.demographics || {};
          dob = d.DOB_ISO || d.DOB || d.dob || '';
        }catch(_e){}
        if (!dob){
          const s = await getJson('/session_data');
          try{ const ent = s?.patient_record?.entry || []; const pat = ent.find(e=> e?.resource?.resourceType==='Patient'); dob = pat?.resource?.birthDate || ''; }catch(_e){}
        }
        // Normalize MMM DD,YYYY to ISO if needed
        if (dob && /[A-Z]{3}\s+\d{1,2},\s?\d{4}/i.test(dob)){
          try{
            const m = dob.match(/([A-Z]{3})\s+(\d{1,2}),\s?(\d{4})/i);
            if (m){
              const mon = m[1].toUpperCase(); const day = parseInt(m[2],10); const year = parseInt(m[3],10);
              const monMap={JAN:1,FEB:2,MAR:3,APR:4,MAY:5,JUN:6,JUL:7,AUG:8,SEP:9,OCT:10,NOV:11,DEC:12};
              const mm = monMap[mon]; if (mm){ const d = new Date(Date.UTC(year, mm-1, day)); dob = d.toISOString().slice(0,10); }
            }
          }catch(_e){}
        }
        return dob || '';
      }
      // age
      if (t === 'age'){
        // Prefer DOB from demographics
        let dob = '';
        try{ const j = await getJson('/quick/patient/demographics'); const d = j?.demographics||{}; dob = d.DOB_ISO || d.DOB || d.dob || ''; }catch(_e){}
        if (!dob){
          const s = await getJson('/session_data');
          try{ const ent = s?.patient_record?.entry || []; const pat = ent.find(e=> e?.resource?.resourceType==='Patient'); dob = pat?.resource?.birthDate || ''; }catch(_e){}
        }
        if (!dob) return '';
        try{
          const today=new Date(); const birth=new Date(dob); let age=today.getFullYear()-birth.getFullYear(); const m=today.getMonth()-birth.getMonth(); if(m<0 || (m===0 && today.getDate()<birth.getDate())) age--; return String(age);
        }catch(_e){ return ''; }
      }
      // phone (mobile preferred)
      if (t === 'phone'){
        const j = await getJson('/quick/patient/demographics');
        const d = j?.demographics || {};
        // Collect possible keys case-insensitively
        const entries = Object.entries(d);
        const byKey = (needleArr)=>{
          const low = (s)=> String(s||'').toLowerCase();
          for (const [k,v] of entries){ if (needleArr.some(n=> low(k).includes(n))) { if (v) return String(v).trim(); } }
          return '';
        };
        // Prefer cell/mobile
        let phone = byKey(['cell','mobile']);
        if (!phone) phone = byKey(['phone (mobile)','mphone']);
        if (!phone) phone = byKey(['home phone','residence phone']);
        if (!phone) phone = byKey(['phone','telephone']);
        return phone || '';
      }
      // medications
      if (t === 'meds/active' || t === 'medications/active'){
        const j = await getJson('/quick/patient/medications?status=ACTIVE+PENDING');
        const meds = j?.medications || j?.items || []; // tolerate alt shapes
        return fmtMeds(meds.filter(m=> String(m.status||'active').toLowerCase()==='active'));
      }
      if (t === 'meds' || t === 'medications'){
        const j = await getJson('/quick/patient/medications');
        const meds = j?.medications || j?.items || [];
        return fmtMeds(meds);
      }
      if (t.startsWith('meds') || t.startsWith('medications')){
        // General handler: .meds[/active][/name or name=<...>][/days][/start=...][/end=...]
        const parts = t.replace(/^medications/, 'meds').split('/').filter(Boolean);
        let status = 'ALL'; // or 'ACTIVE+PENDING'
        let nameFilter = '';
        let start=null, end=null, days=null;
        for (let i=1;i<parts.length;i++){
          const p = parts[i];
          if (!p) continue;
          if (p.toLowerCase()==='active'){ status = 'ACTIVE+PENDING'; continue; }
          if (/^days=\d+$/i.test(p)){ days = parseInt(p.split('=')[1],10); continue; }
          if (/^\d+$/.test(p)){ days = parseInt(p,10); continue; }
          if (/^name=/.test(p)){ nameFilter = p.split('=')[1]; continue; }
          if (p.startsWith('since=')) { start = parseNaturalDate(p.split('=',2)[1], false); continue; }
          if (p.startsWith('start=')) { start = parseNaturalDate(p.split('=',2)[1], false); continue; }
          if (p.startsWith('end='))   { end   = parseNaturalDate(p.split('=',2)[1], true);  continue; }
          // Otherwise treat as part of the drug name
          nameFilter = (nameFilter ? (nameFilter+' ') : '') + p;
        }
        const qs = new URLSearchParams();
        if (status) qs.set('status', status);
        if (days != null) qs.set('days', String(Math.max(0, days)));
        if (start) qs.set('start', start);
        if (end) qs.set('end', end);
        let meds = (await getJson('/quick/patient/medications'+(qs.toString()? ('?'+qs.toString()):'')))?.medications || [];
        // Fallback to FHIR session if quick endpoint unavailable
        if (!Array.isArray(meds) || !meds.length){
          const f = await getJson('/fhir/meds?status='+(status==='ACTIVE+PENDING'?'active':''));
          meds = f?.medications || [];
        }
        const nf = String(nameFilter||'').trim().toLowerCase();
        if (nf){ meds = meds.filter(m => String(m?.name||'').toLowerCase().includes(nf)); }
        return fmtMeds(meds);
      }
      if (t.startsWith('medstarted') || t.startsWith('med_start')){
        // .medstarted/<name>: earliest known start-like date for a medication by substring match
        const parts = t.split('/').filter(Boolean);
        const name = parts.slice(1).join(' ').trim();
        if (!name) return '';
        // Pull wide window from quick endpoint (10 years)
        const j = await getJson('/quick/patient/medications?status=ALL&days=3650');
        let meds = j?.medications || j?.items || [];
        if (!Array.isArray(meds) || !meds.length){
          const f = await getJson('/fhir/meds');
          meds = f?.medications || [];
        }
        const q = name.toLowerCase();
        let best = null, bestLabel = '';
        function asDate(x){ try{ if(!x) return null; const d=new Date(String(x)); return isNaN(d.getTime())? null : d; }catch(_e){ return null; } }
        for (const m of meds){
          const label = String(m?.name||'').trim(); if (!label || !label.toLowerCase().includes(q)) continue;
          const cands = [m?.startDate, m?.writtenDate, m?.orderedDate, m?.firstFilled, m?.lastFilled];
          for (const iso of cands){ const d = asDate(iso); if (!d) continue; if (!best || d < best){ best = d; bestLabel = label; } }
        }
        if (!best) return `No start date found for ${name}.`;
        const ymd = best.toISOString().slice(0,10);
        return `${bestLabel || name} started on ${ymd}.`;
      }
      // problems
      if (t === 'problems' || t === 'problems/active'){
        const j = await getJson(`/quick/patient/problems${t.endsWith('/active')? '?status=active':''}`);
        const probs = j?.problems || [];
        return fmtProblems(probs, t.endsWith('/active'));
      }
      if (t === 'problems/details' || t === 'problems/active/details'){
        const active = t.startsWith('problems/active');
        const qs = active ? '?status=active&detail=1' : '?detail=1';
        const j = await getJson(`/quick/patient/problems${qs}`);
        const probs = j?.problems || [];
        return fmtProblemsDetailed(probs, active);
      }
      // vitals
      if (t.startsWith('vitals')){
        const parts = t.split('/').filter(Boolean); let start=null, end=null, days=null;
        for(let i=1;i<parts.length;i++){ const p=parts[i]; if(/^\d+$/.test(p)) days=parseInt(p,10); else if(p.startsWith('since=')) start=parseNaturalDate(p.split('=',2)[1], false); else if(p.startsWith('start=')) start=parseNaturalDate(p.split('=',2)[1], false); else if(p.startsWith('end=')) end=parseNaturalDate(p.split('=',2)[1], true); }
        if(days != null){ const now=new Date(); const startDt=new Date(now); startDt.setDate(now.getDate()-Math.max(0,days)); start = startDt.toISOString().slice(0,10); end = now.toISOString().slice(0,10); }
        const qs = new URLSearchParams(); if(start) qs.set('start', start); if(end) qs.set('end', end);
        const j = await getJson('/quick/patient/vitals'+(qs.toString()? ('?'+qs.toString()):''));
        const vitals = j?.vitals || {};
        const md = fmtVitalsTable(vitals);
        return { markdown: md, replace: md };
      }
      // labs
      if (t.startsWith('labs')){
        // Support trailing colon modifiers, e.g., labs/a1c:last, labs/a1c:all, labs/a1c:days=30, labs/a1c:range=2024-01-01..2024-12-31
        let base = t, argStr = '';
        if (t.includes(':')){ const split = t.split(':'); base = split.shift(); argStr = split.join(':'); }
        const parts = base.split('/').filter(Boolean); let filters=[], start=null, end=null, since=null, days=null, allParam=null;
        for(let i=1;i<parts.length;i++){
          const p=parts[i];
          if(p.includes('=')){
            const [k,v]=p.split('=');
            if(k==='since') since=parseNaturalDate(v,false); else if(k==='start') start=parseNaturalDate(v,false); else if(k==='end') end=parseNaturalDate(v,true); else if(k==='all') allParam = v;
          } else if(/^\d+$/.test(p)) { days=parseInt(p,10); }
          else { filters = filters.concat(p.split(',').map(x=>x.trim()).filter(Boolean)); }
        }
        // Parse colon args
        let mode = 'all'; // 'all' | 'last'
        if (argStr){
          const items = argStr.split(/[\s,]+/).filter(Boolean);
          for(const item of items){
            const low = item.toLowerCase();
            if (low==='last') mode = 'last';
            else if (low==='all') mode = 'all';
            else if (low.startsWith('days=')){
              const n = parseInt(low.split('=',2)[1],10); if(Number.isFinite(n)) days = n;
            } else if (low.startsWith('range=')){
              const rng = low.split('=',2)[1];
              if (rng){
                const [a,b] = rng.includes('..') ? rng.split('..') : rng.split(',');
                const sParsed = parseNaturalDate(a,false); const eParsed = parseNaturalDate(b,true);
                if (sParsed) start = sParsed; if (eParsed) end = eParsed;
              }
            } else if (low.startsWith('start=')) start = parseNaturalDate(low.split('=',2)[1], false);
            else if (low.startsWith('end=')) end = parseNaturalDate(low.split('=',2)[1], true);
            else if (low.startsWith('since=')) start = parseNaturalDate(low.split('=',2)[1], false);
          }
        }
        // New: if user specified specific tests and no date bounds, default to all results
        if (filters.length && days==null && !start && !end && !since && allParam==null){ allParam = 1; }
        const qs = new URLSearchParams();
        if(filters.length) qs.set('names', filters.join(','));
        if(days != null) qs.set('days', String(Math.max(0,days)));
        if(since && !start) start = since; if(start) qs.set('start', start); if(end) qs.set('end', end);
        if(allParam!=null) qs.set('all', String(allParam));
        const j = await getJson('/quick/patient/labs'+(qs.toString()? ('?'+qs.toString()):''));
        let labs = j?.labs || [];
        // Client-side filter when specific tests requested
        if (filters.length){
          const wants = filters.map(f=> String(f).toLowerCase());
          labs = labs.filter(rec=>{
            const test = String(rec?.test||'').toLowerCase();
            const loinc = String(rec?.loinc||'').toLowerCase();
            return wants.some(w=> test.includes(w) || (loinc && loinc.includes(w)) );
          });
        }
        // If mode is 'last', select the latest per test key
        if (mode === 'last'){
          const normDate=(r)=> (r && (r.resulted||r.collected||r.date||'')) || '';
          const getKey = (r)=>{
            const loinc = (r?.loinc||'').toLowerCase().trim();
            if (loinc) return `loinc:${loinc}`;
            const name = (r?.test||r?.localName||r?.name||r?.display||'').toLowerCase().trim();
            return `name:${name}`;
          };
          const latest = new Map();
          for(const rec of labs){
            const key = getKey(rec);
            const cur = latest.get(key);
            if (!cur) { latest.set(key, rec); continue; }
            const a = normDate(cur); const b = normDate(rec);
            if (a < b) latest.set(key, rec);
          }
          labs = Array.from(latest.values());
        }
        const md = fmtLabsTable(labs);
        return { markdown: md, replace: md };
      }
      // orders
      if (t.startsWith('orders')){
        let status='current', type='all', days=7;
        if(t.includes(':')){ const argStr = t.split(':',2)[1] || ''; const parsed = parseOrdersArgs(argStr); status=parsed.status; type=parsed.type; days=parsed.days; }
        else if(t.includes('/')){ const segs=t.split('/').filter(Boolean); if(segs[1]) status = ordersStatusAlias(segs[1]); if(segs[2]) type = ordersTypeAlias(segs[2]); if(segs[3]){ const n=parseInt(segs[3],10); if(Number.isFinite(n) && n>0) days=n; } }
        const path = `/fhir/orders/${encodeURIComponent(status)}/${encodeURIComponent(type)}/${encodeURIComponent(String(days))}`;
        const j = await getJson(path);
        const arr = j?.orders || [];
        return fmtOrders(arr);
      }
    }catch(_e){ return null; }
    return null;
  }

  function collectDotTokens(s){
    const tokens = [];
    const re = /(^|[^A-Za-z0-9_])\.([A-Za-z][\w]*(?:[\/:=,\-+][\w=+\-]+)*)/g; let m;
    while((m = re.exec(s))){
      const prefix = m[1] || '';
      const body = m[2];
      const start = m.index + prefix.length;
      const end = start + 1 + body.length;
      const isBraced = (start>0 && s[start-1]==='{') && (end < s.length && s[end] === '}');
      if (isBraced) continue; // skip {.token}
      const raw = '.'+body;
      if (!tokens.find(t => t.raw === raw)) tokens.push({ raw, token: body, start, end });
    }
    return tokens;
  }

  async function replace(text){
    const s = String(text ?? '');
    const hasDot = /(^|[^A-Za-z0-9_])\.[A-Za-z]/.test(s);
    if(!hasDot) return s;
    // Ensure patient context exists
    const meta = await getPatientMeta();
    if(!meta || !meta.dfn) return s;
    const tokens = collectDotTokens(s);
    if (!tokens.length) return s;
    const results = await Promise.all(tokens.map(async t => ({ raw: t.raw, val: await resolveToken(t.token) })));
    let out = s;
    for (const { raw, val } of results){
      let rep = '';
      if (val && typeof val === 'object') rep = String(val.replace||val.markdown||val.text||'');
      else if (typeof val === 'string') rep = val;
      if (rep) out = out.split(raw).join(rep);
    }
    return out;
  }

  async function expand(text){
    const s = String(text ?? '');
    const hasDot = /(^|[^A-Za-z0-9_])\.[A-Za-z]/.test(s);
    if(!hasDot) return { replaced: s, replacements: [] };
    const meta = await getPatientMeta();
    if(!meta || !meta.dfn) return { replaced: s, replacements: [] };
    const tokens = collectDotTokens(s);
    if (!tokens.length) return { replaced: s, replacements: [] };
    const results = await Promise.all(tokens.map(async t => ({ raw: t.raw, value: await resolveToken(t.token) })));
    let out = s;
    for (const { raw, value } of results){
      let rep = '';
      if (value && typeof value === 'object') rep = String(value.replace||value.markdown||value.text||'');
      else if (typeof value === 'string') rep = value;
      if (rep) out = out.split(raw).join(rep);
    }
    return { replaced: out, replacements: results };
  }

  const DotPhrases = { resolve: resolveToken, replace, replaceSelective: replace, expand, _fmt: { fmtMeds, fmtProblems, fmtProblemsDetailed, fmtVitalsTable, fmtLabsTable, fmtOrders }, _util: { parseNaturalDate, ordersStatusAlias, ordersTypeAlias, parseOrdersArgs } };
  g.DotPhrases = DotPhrases;
})();
