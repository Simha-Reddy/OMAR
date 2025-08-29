// Recent Vitals Sidebar
// Renders into #vitalsSidebar on the Explore page.
(function(){
    const MOUNT_ID = 'vitalsSidebar';
    const state = { data: null, labs: null };
  
    function $(id){ return document.getElementById(id); }
  
    function toNum(v){ const n = Number(v); return isFinite(n) ? n : null; }
  
    // Add cache-busting helper tied to current DFN
    function bust(url){
      try {
        const dfn = (window.CURRENT_PATIENT_DFN || (window.__PATIENT_META__ && window.__PATIENT_META__.dfn) || '');
        const sep = url.includes('?') ? '&' : '?';
        return url + sep + '_pt=' + encodeURIComponent(dfn) + '&_ts=' + Date.now();
      } catch(_e){ return url; }
    }

    function fmtDate(s){
      if(!s) return '';
      try {
        const d = new Date(s);
        if(!isNaN(d.getTime())) return d.toLocaleString();
      } catch(_e){}
      return String(s);
    }
    // Date-only (no time)
    function fmtDateOnly(sOrDate){
      try {
        const d = (sOrDate instanceof Date) ? sOrDate : new Date(sOrDate);
        if(!isNaN(d.getTime())) return d.toLocaleDateString();
      } catch(_e){}
      return '';
    }
  
    function fmtFahrenheit(v, unit){
      const u = (unit||'').toLowerCase();
      let c = null;
      if(u.includes('c')) c = toNum(v);
      else if(u.includes('f')) return { val: toNum(v), unit: '°F' };
      else c = toNum(v); // unknown -> assume C, better than showing wrong symbol
      if(c==null) return { val: null, unit: '°F' };
      const f = (c * 9/5) + 32;
      return { val: Math.round(f*10)/10, unit: '°F' };
    }
  
    function fmtLbs(v, unit){
      const u = (unit||'').toLowerCase();
      if(u.includes('lb')) return { val: toNum(v)!=null? Math.round(toNum(v)*10)/10 : null, unit: 'lbs' };
      const kg = toNum(v);
      if(kg==null) return { val: null, unit: 'lbs' };
      const lbs = kg * 2.2046226218;
      return { val: Math.round(lbs*10)/10, unit: 'lbs' };
    }
  
    function latest(arr){ if(!Array.isArray(arr)||!arr.length) return null; return arr[arr.length-1] || null; }
    function lastN(arr, n){ const a = Array.isArray(arr)? arr : []; if(n<=0) return []; return a.slice(Math.max(0, a.length - n)); }
    // New: last N in reverse chronological order (most recent first)
    function lastNDesc(arr, n){ const a = Array.isArray(arr)? arr : []; if(n<=0) return []; return a.slice(Math.max(0, a.length - n)).reverse(); }
  
    function calcPctDelta(newV, oldV){
      const a = toNum(newV); const b = toNum(oldV);
      if(a==null || b==null || b === 0) return null;
      const pct = ((a - b) / Math.abs(b)) * 100;
      return pct;
    }
  
    function buildDeltaIndicator(pct){
      if(pct==null) return null;
      const ap = Math.abs(pct);
      if(ap < 5) return null;
      const dirUp = pct > 0;
      const wrap = document.createElement('span');
      wrap.className = 'delta-wrap';
      // Prevent triangles from intercepting clicks (so sub-values remain clickable)
      try { wrap.style.pointerEvents = 'none'; } catch(_e){}
      const tri = document.createElement('span');
      tri.className = 'delta-tri';
      tri.textContent = dirUp ? '▲' : '▼';
      wrap.appendChild(tri);
      if(ap > 10){
        const tri2 = document.createElement('span');
        tri2.className = 'delta-tri';
        tri2.textContent = dirUp ? '▲' : '▼';
        wrap.appendChild(tri2);
      }
      wrap.title = `${dirUp?'+':''}${pct.toFixed(1)}%`;
      return wrap;
    }
  
    function calcMAP(bp){
      if(!bp) return null;
      const s = toNum(bp.systolic); const d = toNum(bp.diastolic);
      if(s==null || d==null) return null;
      return d + (s - d)/3;
    }
  
    // Simple popover manager
    let activePopover = null;
    let activeAnchor = null;
    function closePopover(){ if(activePopover){ activePopover.remove(); activePopover = null; activeAnchor = null; document.removeEventListener('click', onDocClick, true);} }
    function onDocClick(_e){ if(activePopover){ closePopover(); } }
    function showPopover(anchorEl, title, rows){
      // Toggle: if clicking same anchor, just close and return
      if(activeAnchor === anchorEl){ closePopover(); return; }
      // Close any open popover from a different anchor
      closePopover();
      const pop = document.createElement('div');
      pop.className = 'vital-popover';
      const h = document.createElement('h4'); h.textContent = title; pop.appendChild(h);
      rows.forEach(r => {
        const div = document.createElement('div');
        div.className = 'row';
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
      // position near anchor
      const rect = anchorEl.getBoundingClientRect();
      const top = window.scrollY + rect.bottom + 6;
      const left = window.scrollX + rect.left;
      pop.style.top = `${top}px`;
      pop.style.left = `${left}px`;
      activePopover = pop;
      activeAnchor = anchorEl;
      setTimeout(()=> document.addEventListener('click', onDocClick, true), 0);
    }
  
    // --- Labs helpers ---
    // Map of analyte keys -> LOINC codes and robust name patterns
    const ANALYTES = {
      na:  { loinc: ['2951-2','2947-0'], patterns:[/\bna\+?\b/, /\bsodium\b/] },
      k:   { loinc: ['2823-3'], patterns:[/\bk\+?\b/, /\bpotassium\b/] },
      cl:  { loinc: ['2075-0'], patterns:[/\bcl-?\b/, /\bchloride\b/] },
      hco3:{ loinc: ['2028-9'], patterns:[/\bhco3\b/, /\bco2\b/, /\bbicarbonate\b/, /\bcarbon dioxide\b/] },
      bun: { loinc: ['3094-0'], patterns:[/\bbun\b/, /\burea nitrogen\b/] },
      cr:  { loinc: ['2160-0'], patterns:[/\bcr\b/, /\bcreatinine\b/] },
      glu: { loinc: ['2345-7'], patterns:[/\bglu(cose)?\b/] },
      wbc: { loinc: ['6690-2','26464-8'], patterns:[/\bwbc\b/, /\bwhite blood\b/] },
      // Tighten Hemoglobin match: exclude Hemoglobin A1c variants even with punctuation
      hgb: { loinc: ['718-7'], patterns:[/\bhgb\b(?![^a-z0-9]*a1c)/, /\bhemoglobin\b(?![^a-z0-9]*a1c)/, /\bhaemoglobin\b(?![^a-z0-9]*a1c)/] },
      hct: { loinc: ['4544-3'], patterns:[/\bhct\b/, /\bhematocrit\b/, /\bhaematocrit\b/] },
      plt: { loinc: ['777-3'], patterns:[/\bplt\b/, /\bplatelets?\b/] }
    };
  
    function _norm(s){ return (s||'').toString().trim().toLowerCase(); }
    function keyForLab(lab){
      const loinc = _norm(lab.loinc);
      const name = _norm(lab.test || lab.localName);
      for(const [key, spec] of Object.entries(ANALYTES)){
        if(loinc && spec.loinc && spec.loinc.includes(loinc)) return key;
        // Defensive: avoid mapping Hemoglobin A1c to Hemoglobin slot
        if(key === 'hgb' && name && (name.includes('a1c') || name.includes('glyco'))){
          continue;
        }
        if(name && spec.patterns){
          for(const p of spec.patterns){ if(p.test(name)) return key; }
        }
      }
      return null;
    }
  
    function buildLabSeries(labs){
      const series = {};
      Object.keys(ANALYTES).forEach(k => series[k] = []);
      (labs||[]).forEach(r => {
        const key = keyForLab(r);
        if(!key) return;
        const val = toNum(r.result);
        if(val==null) return;
        const date = r.resulted || r.collected;
        series[key].push({ value: val, unit: r.unit, date });
      });
      // sort ascending by date for each key
      for(const k of Object.keys(series)){
        series[k].sort((a,b)=> new Date(a.date||0) - new Date(b.date||0));
      }
      return series;
    }
  
    function latestLab(series, key){ const arr = series[key]||[]; return arr.length? arr[arr.length-1] : null; }
  
    function pctDeltaForKey(series, key){
      const arr = series[key]||[];
      if(arr.length < 2) return null;
      const a = arr[arr.length-1];
      const b = arr[arr.length-2];
      return calcPctDelta(a.value, b.value);
    }
  
    function rowsLast3(series, key){
      const arr = series[key]||[];
      // Show most recent first, max 3, do not duplicate
      return lastNDesc(arr,3).map(x => `${x.value}${x.unit?(' '+x.unit):''} — ${fmtDate(x.date)}`);
    }
  
    // Build a compact SVG fishbone (BMP or CBC)
    function createSVG(width, height){
      const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      return svg;
    }
    function line(svg, x1,y1,x2,y2, cls){
      const el = document.createElementNS('http://www.w3.org/2000/svg','line');
      el.setAttribute('x1', x1); el.setAttribute('y1', y1); el.setAttribute('x2', x2); el.setAttribute('y2', y2);
      el.setAttribute('stroke', getComputedStyle(document.documentElement).getPropertyValue('--brand-blue') || '#3498db');
      el.setAttribute('stroke-width', 2);
      el.setAttribute('class', cls||'');
      svg.appendChild(el);
      return el;
    }
    function text(svg, txt, x, y, opts={}){
      const el = document.createElementNS('http://www.w3.org/2000/svg','text');
      el.setAttribute('x', x); el.setAttribute('y', y);
      el.textContent = txt;
      el.setAttribute('fill', opts.fill || getComputedStyle(document.documentElement).getPropertyValue('--brand-blue') || '#3498db');
      el.setAttribute('font-size', opts.size || 14);
      el.setAttribute('font-weight', opts.weight || 400);
      if(opts.anchor) el.setAttribute('text-anchor', opts.anchor);
      if(opts.baseline) el.setAttribute('dominant-baseline', opts.baseline);
      if(opts.class) el.setAttribute('class', opts.class);
      svg.appendChild(el);
      return el;
    }
    function trianglesForPct(pct){
      // Deprecated: kept for backward compatibility if used elsewhere
      if(pct==null) return '';
      const ap = Math.abs(pct);
      if(ap < 5) return '';
      const tri = (pct>0)? '▲' : '▼';
      return (ap>10)? (tri+tri) : tri;
    }
  
    // Return triangle spec for percent change: how many and direction
    function triSpecForPct(pct){
      if(pct==null) return { count: 0, up: null };
      const ap = Math.abs(pct);
      if(ap < 5) return { count: 0, up: null };
      const count = ap>10 ? 2 : 1;
      return { count, up: pct>0 };
    }
  
    function drawStackedTriangles(svg, x, y, anchor, pct){
      const spec = triSpecForPct(pct);
      if(!spec.count) return null;
      const triChar = spec.up ? '▲' : '▼';
      const dx = 14; // increase left offset so triangles are clearly left of value
      const gap = 8; // vertical spacing between stacked triangles
      if(spec.count === 1){
        return text(svg, triChar, x - dx, y - 2, { size: 12, fill:'#DAA520', anchor: anchor==='start'?'end':(anchor||'middle'), baseline: 'middle' });
      }
      // Two triangles stacked vertically around the label center (y)
      const anchorAdj = anchor==='start'?'end':(anchor||'middle');
      text(svg, triChar, x - dx, y - gap/2, { size: 12, fill:'#DAA520', anchor: anchorAdj, baseline: 'middle' });
      text(svg, triChar, x - dx, y + gap/2, { size: 12, fill:'#DAA520', anchor: anchorAdj, baseline: 'middle' });
      return null;
    }
  
    // NEW: Place triangles relative to the value text instead of diagram coordinates
    function placeTrianglesByText(svg, valueTextEl, pct, side='left'){
      const spec = triSpecForPct(pct);
      if(!spec.count) return;
      const triChar = spec.up ? '▲' : '▼';
      const margin = 6; // gap between triangles and value text
      const gap = 8;    // vertical spacing for double triangles
      const tryPlace = (triesLeft) => {
        try {
          // If not attached or not measurable yet, retry on next frame
          const bbox = valueTextEl.getBBox();
          if(!bbox || (!bbox.width && triesLeft>0)){
            requestAnimationFrame(()=> tryPlace(triesLeft-1));
            return;
          }
          const yMid = bbox.y + bbox.height/2;
          let x, anchor;
          if(side === 'left'){
            x = bbox.x - margin;
            anchor = 'end';
          } else {
            x = bbox.x + bbox.width + margin;
            anchor = 'start';
          }
          if(spec.count === 1){
            text(svg, triChar, x, yMid, { size: 12, fill:'#DAA520', anchor, baseline: 'middle' });
          } else {
            text(svg, triChar, x, yMid - gap/2, { size: 12, fill:'#DAA520', anchor, baseline: 'middle' });
            text(svg, triChar, x, yMid + gap/2, { size: 12, fill:'#DAA520', anchor, baseline: 'middle' });
          }
        } catch(_e){
          if(triesLeft>0) requestAnimationFrame(()=> tryPlace(triesLeft-1));
        }
      };
      // Try a few frames to ensure the element is attached and measurable
      requestAnimationFrame(()=> tryPlace(4));
    }
  
    // Normal and critical ranges for lab values (generic adult references)
    const LAB_RANGES = {
      na:  { low:135, high:145, critLow:120, critHigh:160 },
      k:   { low:3.5, high:5.1, critLow:2.5, critHigh:6.5 },
      cl:  { low:98, high:107, critLow:85, critHigh:115 },
      hco3:{ low:22, high:29, critLow:12, critHigh:40 },
      bun: { low:7, high:20, critLow:3, critHigh:100 },
      cr:  { low:0.6, high:1.3, critLow:0.2, critHigh:6 },
      glu: { low:70, high:99, critLow:40, critHigh:500 },
      wbc: { low:4, high:11, critLow:1, critHigh:30 },
      hgb: { low:12, high:17.5, critLow:7, critHigh:20 },
      hct: { low:36, high:52, critLow:21, critHigh:60 },
      plt: { low:150, high:400, critLow:25, critHigh:1000 },
      // Added key labs
      a1c: { low:4.0, high:5.6, critLow:3.0, critHigh:10.0 },
      chol:{ low:0, high:200, critLow:0, critHigh:280 },
      ldl: { low:0, high:160, critLow:0, critHigh:190 },
      hdl: { low:40, high:200, critLow:25, critHigh:200 }, // low HDL is abnormal
      tg:  { low:0, high:150, critLow:0, critHigh:500 },
      psa: { low:0, high:4.0, critLow:0, critHigh:10.0 }
    };
  
    function severityFor(key, value){
      const v = toNum(value);
      if(v==null) return 'normal';
      const r = LAB_RANGES[key];
      if(!r) return 'normal';
      if(v < r.critLow || v > r.critHigh) return 'critical';
      if(v < r.low || v > r.high) return 'abnormal';
      return 'normal';
    }
  
    // Helpers for key labs outside fishbone (uses raw labs list)
    function _labDate(r){ return new Date(r.resulted || r.collected || 0); }
    function _name(r){ return _norm(r.test || r.localName); }
    function matchSpec(r, spec){
      const loinc = _norm(r.loinc);
      const nm = _name(r);
      if(spec.loinc && loinc && spec.loinc.includes(loinc)) return true;
      if(spec.patterns){ for(const p of spec.patterns){ if(p.test(nm)) return true; } }
      return false;
    }
    function latestNumericSeries(labs, spec){
      const rows = (labs||[]).filter(r => matchSpec(r, spec)).map(r => ({ v: toNum(r.result), u: r.unit, d: _labDate(r), raw: r })).filter(x => x.v!=null);
      rows.sort((a,b)=> a.d - b.d);
      return rows;
    }
    function latestMatching(labs, spec){
      const rows = (labs||[]).filter(r => matchSpec(r, spec)).map(r => ({ res: r.result, u: r.unit, d: _labDate(r), raw: r }));
      rows.sort((a,b)=> a.d - b.d);
      return rows.length ? rows[rows.length-1] : null;
    }
    function latestMatchingSeries(labs, spec){
      const rows = (labs||[]).filter(r => matchSpec(r, spec)).map(r => ({ res: r.result, u: r.unit, d: _labDate(r), raw: r }));
      rows.sort((a,b)=> a.d - b.d);
      return rows;
    }
    function qualitativeSeverity(txt){
      const s = _norm(txt);
      if(!s) return 'normal';
      // negatives first to avoid matching 'reactive' inside 'non-reactive'
      if(s.includes('non reactive') || s.includes('non-reactive') || s.includes('negative') || s.includes('not detected')) return 'normal';
      if(s.includes('positive') || s.includes('reactive') || s.includes('detected')) return 'critical';
      if(s.includes('indetermin')) return 'abnormal';
      return 'normal';
    }
  
    function renderBMPFishbone(series){
        const svg = createSVG(280, 90);
        // spine (shortened) and verticals (remove third)
        line(svg, 10, 45, 210, 45);
        line(svg, 75, 24, 75, 66);
        line(svg, 150, 24, 150, 66);
        // right fork starting at 210
        line(svg, 210, 45, 242, 26);
        line(svg, 210, 45, 242, 64);
    
        // Reposition labels to be centered between vertical lines (horizontally) and near the spine (vertically)
        const segMid = {
          s0: (10 + 75) / 2,    // start..first vertical
          s1: (75 + 150) / 2,   // first..second vertical
          s2: (150 + 210) / 2   // second vertical..fork
        };
        // Increase vertical space between value and spine
        const yTop = 26;  // further above spine
        const yBot = 68;  // further below spine
  
      const spots = {
        na:  {x: segMid.s0, y: yTop, anchor:'middle'},
        k:   {x: segMid.s0, y: yBot, anchor:'middle'},
        cl:  {x: segMid.s1, y: yTop, anchor:'middle'},
        hco3:{x: segMid.s1, y: yBot, anchor:'middle'},
        bun: {x: segMid.s2, y: yTop, anchor:'middle'},
        cr:  {x: segMid.s2, y: yBot, anchor:'middle'},
        // Move Glucose closer to the fork
        glu: {x: 228, y: 49, anchor:'start'}
      };
  
      Object.entries(spots).forEach(([key, pos]) => {
        const cur = latestLab(series, key);
        const pct = pctDeltaForKey(series, key);
        const label = cur? String(cur.value) : '--';
        const t = text(svg, label, pos.x, pos.y, { anchor: pos.anchor, baseline: 'middle' });
        t.classList.add('lab-value');
        t.style.cursor = 'pointer';
        t.setAttribute('aria-label', key);
        // severity coloring
        if(cur){
          const sev = severityFor(key, cur.value);
          if(sev === 'abnormal') t.setAttribute('fill', '#ef5350');
          if(sev === 'critical') t.setAttribute('fill', '#b71c1c');
        }
        // Place triangles relative to the rendered value text
        placeTrianglesByText(svg, t, pct, 'left');
        const rows = rowsLast3(series, key);
        t.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(t, key.toUpperCase() + ' (last 3)', rows); });
        if(cur){ t.setAttribute('title', `${key.toUpperCase()}: ${cur.value}${cur.unit?(' '+cur.unit):''}`); }
      });
      return svg;
    }
  
    function renderCBCFishbone(series){
      const svg = createSVG(280, 90);
      // Switch to a simple X instead of a fishbone
      line(svg, 50, 10, 230, 80);
      line(svg, 50, 80, 230, 10);
  
      const spots = {
        wbc: {x: 90, y: 45, anchor:'end'},     // upper-left
        hgb: {x: 140, y: 12, anchor:'middle'}, // top center
        hct: {x: 150, y: 74, anchor:'end'},     // lower-left
        plt: {x: 195, y: 45, anchor:'start'}   // lower-right
      };
  
      Object.entries(spots).forEach(([key, pos]) => {
        const cur = latestLab(series, key);
        const pct = pctDeltaForKey(series, key);
        const label = cur? String(cur.value) : '--';
        const t = text(svg, label, pos.x, pos.y, { anchor: pos.anchor, baseline: 'middle' });
        t.classList.add('lab-value');
        t.style.cursor = 'pointer';
        if(cur){
          const sev = severityFor(key, cur.value);
          if(sev === 'abnormal') t.setAttribute('fill', '#ef5350');
          if(sev === 'critical') t.setAttribute('fill', '#b71c1c');
        }
        // Place triangles relative to the rendered value text
        placeTrianglesByText(svg, t, pct, 'left');
        const rows = rowsLast3(series, key);
        t.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(t, key.toUpperCase() + ' (last 3)', rows); });
        if(cur){ t.setAttribute('title', `${key.toUpperCase()}: ${cur.value}${cur.unit?(' '+cur.unit):''}`); }
      });
      return svg;
    }
    function renderLabsSection(mount){
      console.log('[VitalsSidebar] renderLabsSection called with state.labs:', state.labs);
      if(!state.labs || !Array.isArray(state.labs.labs)) {
        console.log('[VitalsSidebar] Early return - labs data invalid:', { hasLabs: !!state.labs, isArray: Array.isArray(state.labs?.labs), labsType: typeof state.labs?.labs });
        return; // server returns { labs: [] }
      }
      const series = buildLabSeries(state.labs.labs);
      // helper to get latest date across a set of keys
      const latestDateFor = (keys) => {
        let latest = null;
        keys.forEach(k => {
          const arr = series[k] || [];
          if(arr.length){
            const d = new Date(arr[arr.length-1].date || 0);
            if(!isNaN(d) && (!latest || d > latest)) latest = d;
          }
        });
        return latest;
      };
      // Build a wrapper
      const sep = document.createElement('div');
      sep.className = 'vitals-separator';
      sep.setAttribute('role','separator');
  
      const labsWrap = document.createElement('div');
      labsWrap.className = 'labs-fishbone';
      labsWrap.setAttribute('role','group');
      labsWrap.setAttribute('aria-label','Recent labs');
  
      // BMP first row
      const bmpTitle = document.createElement('div');
      const bmpDate = latestDateFor(['na','k','cl','hco3','bun','cr','glu']);
      bmpTitle.textContent = 'BMP' + (bmpDate? (' ' + fmtDateOnly(bmpDate)) : '');
      bmpTitle.style.fontSize = '0.85em'; bmpTitle.style.color = '#555'; bmpTitle.style.margin = '4px 0 4px 2px';
      const bmpSvg = renderBMPFishbone(series);
  
      // CBC second row
      const cbcTitle = document.createElement('div');
      const cbcDate = latestDateFor(['wbc','hgb','hct','plt']);
      cbcTitle.textContent = 'CBC' + (cbcDate? (' ' + fmtDateOnly(cbcDate)) : '');
      cbcTitle.style.fontSize = '0.85em'; cbcTitle.style.color = '#555'; cbcTitle.style.margin = '8px 0 4px 2px';
      const cbcSvg = renderCBCFishbone(series);
  
      labsWrap.appendChild(bmpTitle);
      labsWrap.appendChild(bmpSvg);
      labsWrap.appendChild(cbcTitle);
      labsWrap.appendChild(cbcSvg);
  
      // Key labs list (A1c, Lipids, PSA, HIV, HepB, HepC)
      const keyList = document.createElement('div');
      keyList.className = 'labs-list';
  
      const labsRaw = state.labs.labs || [];
      const SPECS = {
        a1c: { loinc:['4548-4'], patterns:[/\b(hb)?a1c\b/, /\bhemoglobin a1c\b/, /glyco.?hemoglobin/] },
        chol:{ loinc:['2093-3'], patterns:[/\b(chol(esterol)?)\b/] },
        ldl: { loinc:['2089-1'], patterns:[/\bldl\b/] },
        hdl: { loinc:['2085-9'], patterns:[/\bhdl\b/] },
        tg:  { loinc:['2571-8'], patterns:[/\btrig(lycerides?)?\b/] },
        psa: { loinc:['2857-1'], patterns:[/\bpsa\b/, /prostate specific/] },
        hiv: { loinc:[], patterns:[/\bhiv\b/] },
        hepb:{ loinc:[], patterns:[/\bhep(atitis)?\s*b\b|\bhbsag\b|\bhbc(ab)?\b|\bhbs(ab)?\b/i] },
        hepc:{ loinc:[], patterns:[/\bhep(atitis)?\s*c\b|\bhcv\b|\brna\b/i] }
      };
  
      // A1c (always render label; value may be blank)
      const a1cSeries = latestNumericSeries(labsRaw, SPECS.a1c);
      {
        const last = a1cSeries.length ? a1cSeries[a1cSeries.length-1] : null;
        const item = document.createElement('div'); item.className = 'labs-item';
        const label = document.createElement('span'); label.className = 'labs-label'; label.textContent = 'A1c:';
        const valWrap = document.createElement('span'); valWrap.className = 'labs-value-wrap';
        const val = document.createElement('span'); val.className = 'labs-value'; val.textContent = last? String(last.v) : '';
        const unit = document.createElement('span'); unit.className = 'labs-unit'; unit.textContent = last? (last.u ? last.u : '%') : '';
        valWrap.appendChild(val); valWrap.appendChild(unit);
        if(last){ const sev = severityFor('a1c', last.v); if(sev==='abnormal') val.classList.add('abnormal'); if(sev==='critical') val.classList.add('critical'); }
        item.appendChild(label);
        const pct = (a1cSeries.length>=2) ? calcPctDelta(a1cSeries[a1cSeries.length-1].v, a1cSeries[a1cSeries.length-2].v) : null;
        const ind = buildDeltaIndicator(pct); if(ind) item.appendChild(ind);
        item.appendChild(valWrap);
        const dt = document.createElement('span'); dt.className = 'labs-date'; dt.textContent = last? ` ${fmtDateOnly(last.d)}` : ''; item.appendChild(dt);
        // click: show last 3 (most recent -> oldest)
        item.addEventListener('click', (e)=>{
          e.preventDefault(); e.stopPropagation();
          const rows = a1cSeries.slice(-3).reverse().map(x => `${x.v}${x.u?(' '+x.u):'%'} ${fmtDateOnly(x.d)}`);
          showPopover(item, 'A1c (last 3)', rows);
        });
        keyList.appendChild(item);
      }
  
      // Lipids (single line, per-component clickable)
      const lipidKeys = ['chol','ldl','hdl','tg'];
      const lipidParts = [];
      lipidKeys.forEach(k => {
        const ser = latestNumericSeries(labsRaw, SPECS[k]);
        if(ser.length){
          const last = ser[ser.length-1];
          const sev = severityFor(k, last.v);
          lipidParts.push({ key:k, v:last.v, u:last.u||'', sev, pct:(ser.length>=2?calcPctDelta(ser[ser.length-1].v, ser[ser.length-2].v):null), date:last.d });
        }
      });
      {
        const item = document.createElement('div'); item.className = 'labs-item';
        const label = document.createElement('span'); label.className = 'labs-label'; label.textContent = 'Lipids:';
        item.appendChild(label);
        // use date of most recent component
        const recent = lipidParts.length ? lipidParts.reduce((a,b)=> a && a.date>b.date ? a : b, null) : null;
        // Triangles: show if any component has pct; choose LDL's if present else most recent
        const triSource = lipidParts.find(p=>p.key==='ldl' && p.pct!=null) || lipidParts.find(p=>p.pct!=null);
        if(triSource){ const ind = buildDeltaIndicator(triSource.pct); if(ind) item.appendChild(ind); }
        const valuesWrap = document.createElement('span');
        if(lipidParts.length){
          lipidParts.forEach((p,i)=>{
            const group = document.createElement('span'); group.className = 'labs-value-wrap'; group.style.cursor = 'pointer'; group.setAttribute('data-anal', p.key);
            const span = document.createElement('span'); span.className = 'labs-value'; span.textContent = `${p.key.toUpperCase()} ${p.v}`; if(p.sev==='abnormal') span.classList.add('abnormal'); if(p.sev==='critical') span.classList.add('critical');
            const unit = document.createElement('span'); unit.className = 'labs-unit'; unit.textContent = p.u;
            group.appendChild(span); group.appendChild(unit);
            // Per-component click opens that analyte's last 3 (most recent -> oldest)
            group.addEventListener('click', (e)=>{
              e.preventDefault(); e.stopPropagation();
              const key = group.getAttribute('data-anal');
              const ser = latestNumericSeries(labsRaw, SPECS[key]);
              const rows = ser.slice(-3).reverse().map(x => `${x.v}${x.u?(' '+x.u):''} ${fmtDateOnly(x.d)}`);
              const ttl = key.toUpperCase() + ' (last 3)';
              showPopover(group, ttl, rows);
            });
            valuesWrap.appendChild(group);
            if(i < lipidParts.length-1){ const sep = document.createElement('span'); sep.textContent = '  '; valuesWrap.appendChild(sep); }
          });
        }
        item.appendChild(valuesWrap);
        const dt = document.createElement('span'); dt.className='labs-date'; dt.textContent = recent? ` ${fmtDateOnly(recent.date)}` : ''; item.appendChild(dt);
        // Remove item-level click; use per-component clicks instead
        keyList.appendChild(item);
      }
  
      // PSA (always render label; value may be blank)
      const psaSer = latestNumericSeries(labsRaw, SPECS.psa);
      {
        const last = psaSer.length ? psaSer[psaSer.length-1] : null;
        const item = document.createElement('div'); item.className = 'labs-item';
        const label = document.createElement('span'); label.className = 'labs-label'; label.textContent = 'PSA:';
        const valWrap = document.createElement('span'); valWrap.className = 'labs-value-wrap';
        const val = document.createElement('span'); val.className = 'labs-value'; val.textContent = last? String(last.v) : '';
        const unit = document.createElement('span'); unit.className = 'labs-unit'; unit.textContent = last? (last.u || '') : '';
        valWrap.appendChild(val); valWrap.appendChild(unit);
        if(last){ const sev = severityFor('psa', last.v); if(sev==='abnormal') val.classList.add('abnormal'); if(sev==='critical') val.classList.add('critical'); }
        item.appendChild(label);
        const pct = (psaSer.length>=2) ? calcPctDelta(psaSer[psaSer.length-1].v, psaSer[psaSer.length-2].v) : null;
        const ind = buildDeltaIndicator(pct); if(ind) item.appendChild(ind);
        item.appendChild(valWrap);
        const dt = document.createElement('span'); dt.className='labs-date'; dt.textContent = last? ` ${fmtDateOnly(last.d)}` : ''; item.appendChild(dt);
        item.addEventListener('click', (e)=>{
          e.preventDefault(); e.stopPropagation();
          const rows = psaSer.slice(-3).reverse().map(x => `${x.v}${x.u?(' '+x.u):''} ${fmtDateOnly(x.d)}`);
          showPopover(item, 'PSA (last 3)', rows);
        });
        keyList.appendChild(item);
      }
  
      // HIV (qualitative; always render label)
      {
        const hiv = latestMatching(labsRaw, SPECS.hiv);
        const item = document.createElement('div'); item.className = 'labs-item';
        const label = document.createElement('span'); label.className = 'labs-label'; label.textContent = 'HIV:';
        const val = document.createElement('span'); val.className = 'labs-value'; val.textContent = hiv? String(hiv.res) : '';
        if(hiv){ const sev = qualitativeSeverity(hiv.res); if(sev==='abnormal') val.classList.add('abnormal'); if(sev==='critical') val.classList.add('critical'); }
        item.appendChild(label); item.appendChild(val);
        const dt = document.createElement('span'); dt.className='labs-date'; dt.textContent = hiv? ` ${fmtDateOnly(hiv.d)}` : ''; item.appendChild(dt);
        item.addEventListener('click', (e)=>{
          e.preventDefault(); e.stopPropagation();
          const ser = latestMatchingSeries(labsRaw, SPECS.hiv);
          const rows = ser.slice(-3).reverse().map(x => `${String(x.res)} ${fmtDateOnly(x.d)}`);
          showPopover(item, 'HIV (last 3)', rows);
        });
        keyList.appendChild(item);
      }
  
      // Hep B (qualitative; always render label)
      {
        const hepb = latestMatching(labsRaw, SPECS.hepb);
        const item = document.createElement('div'); item.className = 'labs-item';
        const label = document.createElement('span'); label.className = 'labs-label'; label.textContent = 'Hep B:';
        const val = document.createElement('span'); val.className = 'labs-value'; val.textContent = hepb? String(hepb.res) : '';
        if(hepb){ const sev = qualitativeSeverity(hepb.res); if(sev==='abnormal') val.classList.add('abnormal'); if(sev==='critical') val.classList.add('critical'); }
        item.appendChild(label); item.appendChild(val);
        const dt = document.createElement('span'); dt.className='labs-date'; dt.textContent = hepb? ` ${fmtDateOnly(hepb.d)}` : ''; item.appendChild(dt);
        item.addEventListener('click', (e)=>{
          e.preventDefault(); e.stopPropagation();
          const ser = latestMatchingSeries(labsRaw, SPECS.hepb);
          const rows = ser.slice(-3).reverse().map(x => `${String(x.res)} ${fmtDateOnly(x.d)}`);
          showPopover(item, 'Hep B (last 3)', rows);
        });
        keyList.appendChild(item);
      }
  
      // Hep C (qualitative; always render label)
      {
        const hepc = latestMatching(labsRaw, SPECS.hepc);
        const item = document.createElement('div'); item.className = 'labs-item';
        const label = document.createElement('span'); label.className = 'labs-label'; label.textContent = 'Hep C:';
        const val = document.createElement('span'); val.className = 'labs-value'; val.textContent = hepc? String(hepc.res) : '';
        if(hepc){ const sev = qualitativeSeverity(hepc.res); if(sev==='abnormal') val.classList.add('abnormal'); if(sev==='critical') val.classList.add('critical'); }
        item.appendChild(label); item.appendChild(val);
        const dt = document.createElement('span'); dt.className='labs-date'; dt.textContent = hepc? ` ${fmtDateOnly(hepc.d)}` : ''; item.appendChild(dt);
        item.addEventListener('click', (e)=>{
          e.preventDefault(); e.stopPropagation();
          const ser = latestMatchingSeries(labsRaw, SPECS.hepc);
          const rows = ser.slice(-3).reverse().map(x => `${String(x.res)} ${fmtDateOnly(x.d)}`);
          showPopover(item, 'Hep C (last 3)', rows);
        });
        keyList.appendChild(item);
      }
  
      if(keyList.children.length){
        const keyHeader = document.createElement('div'); keyHeader.textContent = 'Key Labs'; keyHeader.style.fontSize='0.85em'; keyHeader.style.color='#555'; keyHeader.style.margin='8px 0 4px 2px';
        labsWrap.appendChild(keyHeader);
        labsWrap.appendChild(keyList);
      }
  
      // Helper to map any lab row to a known key for severity coloring
      const keyFromAny = (r) => {
        const k = keyForLab(r);
        if(k) return k;
        // Check key labs specs
        if(matchSpec(r, SPECS.a1c)) return 'a1c';
        if(matchSpec(r, SPECS.chol)) return 'chol';
        if(matchSpec(r, SPECS.ldl)) return 'ldl';
        if(matchSpec(r, SPECS.hdl)) return 'hdl';
        if(matchSpec(r, SPECS.tg)) return 'tg';
        if(matchSpec(r, SPECS.psa)) return 'psa';
        return null;
      };
  
      // Recent labs (last 90 days) popover link
      const recentLink = document.createElement('a'); recentLink.href = '#'; recentLink.textContent = 'Recent Labs (last 90 days)'; recentLink.className = 'labs-recent-link';
      recentLink.addEventListener('click', (e)=>{
        e.preventDefault(); e.stopPropagation();
        const cutoff = new Date(); cutoff.setDate(cutoff.getDate()-90);
        const rows = (labsRaw||[])
          .map(r=>({ raw:r, name: r.test || r.localName || '', res: r.result, u: r.unit, d: _labDate(r) }))
          .filter(x => x.d && x.d >= cutoff)
          .sort((a,b)=> b.d - a.d)
          .map(x => {
            const key = keyFromAny(x.raw);
            let sev = null;
            if(key){
              const v = toNum(x.res);
              if(v!=null){ sev = severityFor(key, v); }
            }
            return { text: `${fmtDate(x.d)} — ${x.name}: ${x.res}${x.u?(' '+x.u):''}`, severity: sev };
          });
        showPopover(recentLink, 'Recent Labs (last 90 days)', rows.slice(0,200));
      });
      labsWrap.appendChild(recentLink);
  
      // Recent Abnormal labs (last 90 days) popover link (red)
      const abnLink = document.createElement('a'); abnLink.href = '#'; abnLink.textContent = 'Recent Abnormal Labs (last 90 days)'; abnLink.className = 'labs-recent-link labs-recent-abnormal';
      abnLink.style.color = '#b71c1c';
      abnLink.style.display = 'block'; // ensure it appears below the Recent Labs link
      abnLink.style.marginTop = '4px';
      abnLink.addEventListener('click', (e)=>{
        e.preventDefault(); e.stopPropagation();
        const cutoff = new Date(); cutoff.setDate(cutoff.getDate()-90);
        const rows = (labsRaw||[])
          .map(r=>({ raw:r, name: r.test || r.localName || '', res: r.result, u: r.unit, d: _labDate(r) }))
          .filter(x => x.d && x.d >= cutoff)
          .map(x => {
            // Determine severity via numeric mapping or qualitative text
            const key = keyFromAny(x.raw);
            let sev = null;
            if(key){
              const v = toNum(x.res);
              if(v!=null){ sev = severityFor(key, v); }
            }
            if(!sev || sev==='normal'){
              const qsev = qualitativeSeverity(x.res);
              if(qsev !== 'normal') sev = qsev;
            }
            return { ...x, sev };
          })
          .filter(x => x.sev === 'abnormal' || x.sev === 'critical')
          .sort((a,b)=> b.d - a.d)
          .map(x => ({ text: `${fmtDate(x.d)} — ${x.name}: ${x.res}${x.u?(' '+x.u):''}`, severity: x.sev }));
        showPopover(abnLink, 'Abnormal Labs (last 90 days)', rows.slice(0,200));
      });
      labsWrap.appendChild(abnLink);
  
      mount.appendChild(sep);
      mount.appendChild(labsWrap);
    }
  
    function render(){
      const mount = $(MOUNT_ID); if(!mount) return;
      const vitals = (state.data && state.data.vitals) || {};
  
      // Grab latest readings and series
      const bpArr = vitals.bloodPressure || [];
      const hrArr = vitals.heartRate || [];
      const rrArr = vitals.respiratoryRate || [];
      const spArr = vitals.oxygenSaturation || [];
      const tArr = vitals.temperature || [];
      const wArr = vitals.weight || [];
  
      const bp = latest(bpArr);
      const hr = latest(hrArr);
      const rr = latest(rrArr);
      const spo2 = latest(spArr);
      const temp = latest(tArr);
      const weight = latest(wArr);
  
      // Build grid
      const grid = document.createElement('div');
      grid.className = 'vitals-grid';
      grid.setAttribute('role','group');
      grid.setAttribute('aria-label','Recent vitals');
  
      // Row 1, Col 1: Heart Rate (blue value + small black BPM) + delta + popover
      const hrCell = document.createElement('div');
      hrCell.className = 'vital-cell vital-item';
      if(hr && hr.value!=null){
        const wrap = document.createElement('div');
        wrap.className = 'hr-readout';
        const vEl = document.createElement('span');
        vEl.className = 'hr-value';
        vEl.textContent = String(hr.value);
        const uEl = document.createElement('span');
        uEl.className = 'hr-bpm';
        uEl.textContent = 'BPM';
        wrap.setAttribute('aria-label', `Heart Rate ${vEl.textContent} bpm`);
        wrap.appendChild(vEl); wrap.appendChild(uEl);
        // delta (prepend to left)
        let hrPct = null; if(hrArr.length>=2){ const a=hrArr[hrArr.length-1], b=hrArr[hrArr.length-2]; hrPct = calcPctDelta(a.value, b.value); }
        const hrInd = buildDeltaIndicator(hrPct); if(hrInd) hrCell.appendChild(hrInd);
        hrCell.appendChild(wrap);
        // popover (most recent -> oldest)
        const hrRows = (hrArr||[]).slice(-3).reverse().map(x => `${x.value} bpm — ${fmtDate(x.effectiveDateTime)}`);
        hrCell.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(hrCell, 'Heart Rate (last 3)', hrRows); });
      }
      grid.appendChild(hrCell);
  
      // Row 1, Col 2: Blood Pressure with diagonal layout + delta + popover
      const bpCell = document.createElement('div');
      bpCell.className = 'vital-cell vital-item';
      if(bp && (bp.systolic!=null || bp.diastolic!=null)){
        const wrap = document.createElement('div');
        wrap.className = 'bp-readout vital-big';
        const sys = document.createElement('span');
        sys.className = 'bp-sys';
        sys.textContent = (bp.systolic!=null ? String(bp.systolic) : '');
        const slash = document.createElement('span');
        slash.className = 'bp-slash';
        slash.setAttribute('aria-hidden','true');
        const dia = document.createElement('span');
        dia.className = 'bp-dia';
        dia.textContent = (bp.diastolic!=null ? String(bp.diastolic) : '');
        wrap.setAttribute('aria-label', `Blood Pressure ${sys.textContent}${dia.textContent?('/'+dia.textContent):''}`);
        wrap.appendChild(sys); wrap.appendChild(slash); wrap.appendChild(dia);
        // Delta based on MAP comparing last two readings
        let bpPct = null;
        if(bpArr.length >= 2){
          const last2 = bpArr.slice(-2);
          const m1 = calcMAP(last2[1]);
          const m0 = calcMAP(last2[0]);
          bpPct = (m1!=null && m0!=null) ? calcPctDelta(m1, m0) : null;
        }
        // Indicator first (left), then the readout
        const ind = buildDeltaIndicator(bpPct);
        if(ind) bpCell.appendChild(ind);
        bpCell.appendChild(wrap);
        // Popover: last 3 BP values (most recent -> oldest)
        const rows = (bpArr||[]).slice(-3).reverse().map(x => `${(x.systolic??'')}/${(x.diastolic??'')} — ${fmtDate(x.effectiveDateTime)}`);
        bpCell.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(bpCell, 'Blood Pressure (last 3)', rows); });
      }
      grid.appendChild(bpCell);
  
      // Row 2, Col 1: Respiratory Rate (label small, value big blue) + delta + popover
      const rrCell = document.createElement('div');
      rrCell.className = 'vital-cell vital-item';
      if(rr && rr.value!=null){
        const val = document.createElement('span'); val.className = 'vital-large'; val.textContent = String(rr.value);
        const label = document.createElement('span'); label.className = 'vital-label'; label.textContent = 'RR';
        rrCell.setAttribute('aria-label', `Respiratory Rate ${val.textContent}`);
        let rrPct = null; if(rrArr.length>=2){ const a=rrArr[rrArr.length-1], b=rrArr[rrArr.length-2]; rrPct = calcPctDelta(a.value, b.value); }
        const rrInd = buildDeltaIndicator(rrPct); if(rrInd) rrCell.appendChild(rrInd);
        // Value first, then small black label on the right
        rrCell.appendChild(val); rrCell.appendChild(label);
        const rrRows = (rrArr||[]).slice(-3).reverse().map(x => `${x.value} — ${fmtDate(x.effectiveDateTime)}`);
        rrCell.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(rrCell, 'Respiratory Rate (last 3)', rrRows); });
      }
      grid.appendChild(rrCell);
  
      // Row 2, Col 2: SpO2 (value big blue + blue % unit, small black label to the right) + delta + popover
      const spCell = document.createElement('div');
      spCell.className = 'vital-cell vital-item';
      if(spo2 && spo2.value!=null){
        const valWrap = document.createElement('span');
        const val = document.createElement('span'); val.className = 'vital-large'; val.textContent = `${spo2.value}`;
        const unit = document.createElement('span'); unit.className = 'unit-blue'; unit.textContent = '%';
        valWrap.appendChild(val); valWrap.appendChild(unit);
        const label = document.createElement('span'); label.className = 'vital-label'; label.textContent = 'SpO₂';
        spCell.setAttribute('aria-label', `Oxygen Saturation ${spo2.value} percent`);
        let spPct = null; if(spArr.length>=2){ const a=spArr[spArr.length-1], b=spArr[spArr.length-2]; spPct = calcPctDelta(a.value, b.value); }
        const spInd = buildDeltaIndicator(spPct); if(spInd) spCell.appendChild(spInd);
        // Value (+ blue %) first, then small black label on the right
        spCell.appendChild(valWrap); spCell.appendChild(label);
        const spRows = (spArr||[]).slice(-3).reverse().map(x => `${x.value}% — ${fmtDate(x.effectiveDateTime)}`);
        spCell.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(spCell, 'SpO₂ (last 3)', spRows); });
      }
      grid.appendChild(spCell);
  
      // Row 3, Col 1: Temperature (Fahrenheit) + delta + popover
      const tCell = document.createElement('div');
      tCell.className = 'vital-cell vital-item';
      if(temp && temp.value!=null){
        const conv = fmtFahrenheit(temp.value, temp.unit);
        if(conv.val!=null){
          let tPct = null; if(tArr.length>=2){ const a=tArr[tArr.length-1], b=tArr[tArr.length-2]; const va=fmtFahrenheit(a.value,a.unit).val, vb=fmtFahrenheit(b.value,b.unit).val; tPct = calcPctDelta(va, vb); }
          const tInd = buildDeltaIndicator(tPct); if(tInd) tCell.appendChild(tInd);
          const vEl = document.createElement('span'); vEl.className = 'vital-value'; vEl.textContent = String(conv.val);
          const uEl = document.createElement('span'); uEl.className = 'unit-small'; uEl.textContent = conv.unit;
          tCell.setAttribute('aria-label', `Temperature ${conv.val} Fahrenheit`);
          tCell.appendChild(vEl); tCell.appendChild(uEl);
          const tRows = (tArr||[]).slice(-3).reverse().map(x => { const c=fmtFahrenheit(x.value,x.unit); return `${c.val}${c.unit} — ${fmtDate(x.effectiveDateTime)}`; });
          tCell.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(tCell, 'Temperature (last 3)', tRows); });
        }
      }
      grid.appendChild(tCell);
  
      // Row 3, Col 2: Weight (lbs) + delta + popover
      const wCell = document.createElement('div');
      wCell.className = 'vital-cell vital-item';
      if(weight && weight.value!=null){
        const conv = fmtLbs(weight.value, weight.unit);
        if(conv.val!=null){
          let wPct = null; if(wArr.length>=2){ const a=wArr[wArr.length-1], b=wArr[wArr.length-2]; const va=fmtLbs(a.value,a.unit).val, vb=fmtLbs(b.value,b.unit).val; wPct = calcPctDelta(va, vb); }
          const wInd = buildDeltaIndicator(wPct); if(wInd) wCell.appendChild(wInd);
          const vEl = document.createElement('span'); vEl.className = 'vital-value'; vEl.textContent = String(conv.val);
          const uEl = document.createElement('span'); uEl.className = 'unit-small'; uEl.textContent = conv.unit;
          wCell.setAttribute('aria-label', `Weight ${conv.val} pounds`);
          wCell.appendChild(vEl); wCell.appendChild(uEl);
          const wRows = (wArr||[]).slice(-3).reverse().map(x => { const c=fmtLbs(x.value,x.unit); return `${c.val} ${c.unit} — ${fmtDate(x.effectiveDateTime)}`; });
          wCell.addEventListener('click', (e)=>{ e.stopPropagation(); showPopover(wCell, 'Weight (last 3)', wRows); });
        }
      }
      grid.appendChild(wCell);
  
      // Mount
      mount.innerHTML = '';
      mount.classList.add('vitals-sidebar');
      mount.appendChild(grid);
  
      // Labs fishbones below vitals
      try { renderLabsSection(mount); } catch(e){ console.warn('[VitalsSidebar] labs render error', e); }
  
      // If nothing rendered, show empty state
      if(!grid.textContent.trim() && !(mount.querySelector('.labs-fishbone'))){
        mount.innerHTML = '<div class="vital-empty">No vitals available.</div>';
      }
    }
  
    async function refresh(){
      const el = $(MOUNT_ID); if(!el) return;
      try {
        el.innerHTML = '<div class="vital-loading">Loading vitals…</div>';
  
        // Check if a patient is selected first to avoid 400 from /fhir/vitals
        let patientMeta = null;
        try {
          const pm = await fetch('/get_patient', { headers: { 'Accept': 'application/json' }, cache: 'no-store' });
          if (pm.ok) {
            patientMeta = await pm.json();
            // expose for bust()
            try { window.__PATIENT_META__ = patientMeta; } catch(_e){}
          }
        } catch(_e) {}
  
        if(!patientMeta || !patientMeta.dfn){
          el.innerHTML = '<div class="vital-empty">Select a patient to view vitals.</div>';
          return;
        }
  
        // Fetch vitals and labs in parallel (request a longer labs window)
        const [vRes, lRes] = await Promise.all([
          fetch(bust('/fhir/vitals'), { cache: 'no-store' }),
          fetch(bust('/fhir/labs?days=365'), { cache: 'no-store' })
        ]);
  
        if(!vRes.ok){
          try { const errJson = await vRes.json(); const msg = (errJson && (errJson.error || errJson.message)) ? errJson.error || errJson.message : 'Unable to load vitals.'; el.innerHTML = `<div class="vital-error">${msg}</div>`; } catch{ el.innerHTML = '<div class="vital-error">Unable to load vitals.</div>'; }
          return;
        }
        const vJson = await vRes.json();
        state.data = vJson;        if(lRes && lRes.ok){
          try { 
            state.labs = await lRes.json(); 
            console.log('[VitalsSidebar] Labs data received:', state.labs);
          } catch(e){ 
            console.warn('[VitalsSidebar] Failed to parse labs JSON:', e);
            state.labs = { labs: [] }; 
          }
        } else {
          console.warn('[VitalsSidebar] Labs request failed:', lRes?.status, lRes?.statusText);
          state.labs = { labs: [] };
        }
  
        render();
      } catch(err){
        el.innerHTML = '<div class="vital-error">Error loading vitals.</div>';
        console.warn('[VitalsSidebar] load error', err);
      }
    }
  
    // Export
    window.VitalsSidebar = { refresh };
  
    // Auto-init on DOM ready or immediately if DOM already loaded
    function autoInit(){ if($(MOUNT_ID)) refresh(); }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', autoInit, { once: true });
    } else {
      // DOM is already interactive/complete; initialize now
      autoInit();
    }
  })();