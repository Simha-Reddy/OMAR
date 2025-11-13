// DocumentService: unified client for Documents list, batched texts, keyword hits, and RAG indexing
// Exposes a singleton-style class attachable to window. No framework deps.
(function(){
  if(window.DocumentService && typeof window.DocumentService === 'function') return; // idempotent only when valid constructor

  class Emitter {
    constructor(){ this._events = new Map(); }
    on(evt, fn){ const a=this._events.get(evt)||[]; a.push(fn); this._events.set(evt,a); return()=>this.off(evt,fn); }
    off(evt, fn){ const a=this._events.get(evt)||[]; const i=a.indexOf(fn); if(i>-1) a.splice(i,1); this._events.set(evt,a); }
    emit(evt, payload){ const a=this._events.get(evt)||[]; for(const fn of a){ try{ fn(payload); }catch(_e){} } }
  }

  function hashString(str){
    // Simple, fast non-crypto hash (FNV-1a-like); sufficient for idempotency checks
    try{
      let h = 2166136261 >>> 0;
      for(let i=0;i<str.length;i++){ h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
      return ('00000000'+h.toString(16)).slice(-8);
    }catch(_e){ return ''; }
  }

  function debounce(fn, wait){ let t=null; return function(...args){ clearTimeout(t); t=setTimeout(()=>fn.apply(this,args), wait); }; }

  class DocumentService {
    constructor(opts){
      const o = opts||{};
      this.batchSize = Number(o.batchSize||24);
      this.maxConcurrency = Math.max(1, Number(o.maxConcurrency||3));
      this.sourceTag = o.source||'workspace';
      this.emitter = new Emitter();
      this._controllers = new Set();
      this._inflightList = null;
      this._inflightTextById = new Map(); // id -> promise
      this._idxInflight = new Set();
      this._destroyed = false;
      this._dfn = null;

      // Caches
      this.docsList = [];              // [{doc_id, title, date, author, ...}]
      this.textCache = new Map();      // id -> { lines: string[], fetchedAt }
      this.textHash = new Map();       // id -> hash string
      this.indexedHash = new Map();    // id -> last hashed value sent to index

      // KW
      this.kwQuery = '';
      this._kwTokens = [];
      this._kwDebounced = debounce(async()=>{ await this._recomputeKwHitsVisible(); }, 150);

      // Visible ids for kw recompute hint
      this._visibleIdsProvider = null; // () => string[]
    }

    on(evt, fn){ return this.emitter.on(evt, fn); }
    off(evt, fn){ return this.emitter.off(evt, fn); }

    setVisibleIdsProvider(fn){ this._visibleIdsProvider = (typeof fn==='function') ? fn : null; }

    setDfn(dfn){
      const next = dfn ? String(dfn) : null;
      if(this._dfn && next && this._dfn !== next){
        // Patient changed: abort inflight and flush patient-specific caches
        try { this.abortAll(); } catch(_e){}
        try { this.docsList = []; this.textCache.clear(); this.textHash.clear(); this.indexedHash.clear(); } catch(_e){}
        try { this.emitter.emit('listLoaded', { docs: [] }); } catch(_e){}
      }
      this._dfn = next;
      try { if(window && window.console) console.debug && console.debug('[DocumentService] setDfn', this._dfn); } catch(_e){}
    }

    abortAll(){ try{ for(const c of Array.from(this._controllers)){ try{ c.abort(); }catch(_e){} } } finally { this._controllers.clear(); }
      this._inflightList = null; this._inflightTextById.clear(); }

    destroy(){ this._destroyed = true; this.abortAll(); this.emitter = new Emitter(); }

    // --- Networking helpers ---
    _csrf(){ try{
      const meta = document.querySelector('meta[name="csrf-token"]'); if(meta) return meta.getAttribute('content');
      const cookie = (document.cookie||'').split('; ').find(s=>s.startsWith('csrf_token=')); if(cookie) return cookie.split('=')[1];
    }catch(_e){} return ''; }

    _fetch(url, init){ const ctrl = new AbortController(); const sig = ctrl.signal; this._controllers.add(ctrl);
      const merged = Object.assign({ credentials:'same-origin', cache:'no-store', referrerPolicy:'no-referrer' }, init||{}, { signal: sig });
      const started = Date.now();
      const p = fetch(url, merged).finally(()=>{ this._controllers.delete(ctrl); const ms=Date.now()-started; if(ms>2000) try{ console.warn(`[DocumentService] slow fetch ${url} ${ms}ms`); }catch(_e){} });
      return { fetchPromise: p, controller: ctrl };
    }

    // --- API ---
    async fetchList(){
      if(this._destroyed) return [];
      if(this._inflightList) return this._inflightList;
      const run = async()=>{
        try{
          const dfn = this._dfn;
          let url = dfn ? `/document_references?dfn=${encodeURIComponent(dfn)}` : '/document_references';
          let { fetchPromise } = this._fetch(url, { method:'GET' });
          let resp = await fetchPromise;
          if(resp.status===400 && dfn){ // try POST body
            const retry = this._fetch('/document_references', { method:'POST', headers:{ 'Content-Type':'application/json', 'X-CSRF-Token': this._csrf() }, body: JSON.stringify({ dfn }) });
            resp = await retry.fetchPromise;
          }
          if(!resp.ok){ throw new Error(`HTTP ${resp.status}`); }
          const data = await resp.json();
          const docs = Array.isArray(data.documents) ? data.documents : [];
          this.docsList = docs;
          this.emitter.emit('listLoaded', { docs });
          try { console.debug && console.debug('[DocumentService] listLoaded', { count: docs.length }); } catch(_e){}
          return docs;
        }catch(err){ this.emitter.emit('error', { stage:'list', error: err }); throw err; }
        finally{ this._inflightList = null; }
      };
      this._inflightList = run();
      return this._inflightList;
    }

    getCachedTextLines(id){ const rec = this.textCache.get(String(id)); return rec && Array.isArray(rec.lines) ? rec.lines : null; }

    async getText(id){ const sid=String(id); const cached = this.getCachedTextLines(sid); if(cached) return cached.join('\n');
      await this.fetchTextsBatch([sid]); const c2=this.getCachedTextLines(sid)||[]; return c2.join('\n'); }

    async fetchTextsBatch(ids){
      if(this._destroyed) return { error:'destroyed' };
      const need = (ids||[]).map(String).filter(Boolean).filter(id=>{
        if(this.textCache.has(id)) return false;
        const inflight = this._inflightTextById.get(id);
        return !inflight;
      });
      if(!need.length) return { data: [] };

      // Split into chunks and limit concurrency
      const chunks = []; for(let i=0;i<need.length;i+=this.batchSize){ chunks.push(need.slice(i, i+this.batchSize)); }
      const results = [];
      let inFlight = 0; let idx = 0;
      const runNext = async()=>{
        if(this._destroyed) return;
        if(idx >= chunks.length) return;
        const chunk = chunks[idx++]; inFlight++;
        try{
          const start = Date.now();
          const payload = { doc_ids: chunk };
          // Mark inflight per id
          const marker = Promise.resolve(); for(const id of chunk){ this._inflightTextById.set(id, marker); }
          const { fetchPromise } = this._fetch('/documents_text_batch', {
            method:'POST', headers:{ 'Content-Type':'application/json', 'X-CSRF-Token': this._csrf() }, body: JSON.stringify(payload)
          });
          const resp = await fetchPromise;
          let j={}; try{ j = await resp.json(); }catch(_e){}
          const notes = Array.isArray(j.notes) ? j.notes : [];
          for(const n of notes){
            const id = n && (n.doc_id!=null ? String(n.doc_id) : ''); if(!id) continue;
            const lines = Array.isArray(n.text) ? n.text : (typeof n.text==='string' ? n.text.split('\n') : []);
            if(lines && lines.length){ this.textCache.set(id, { lines, fetchedAt: Date.now() }); this.textHash.set(id, hashString(lines.join('\n'))); results.push({ id, linesCount: lines.length }); }
          }
          const ms = Date.now()-start; if(ms>1500) try{ console.warn(`[DocumentService] slow batch ${chunk.length} ids in ${ms}ms`); }catch(_e){}
          this.emitter.emit('textsLoaded', { ids: chunk });
          try { console.debug && console.debug('[DocumentService] textsLoaded', { count: chunk.length }); } catch(_e){}
        }catch(err){ this.emitter.emit('error', { stage:'texts', error: err }); }
        finally{ for(const id of chunk){ this._inflightTextById.delete(id); } inFlight--; await pump(); }
      };
      const pump = async()=>{ while(inFlight < this.maxConcurrency && idx < chunks.length){ await runNext(); } };
      await pump();
      return { data: results };
    }

    setKwQuery(q){ this.kwQuery = String(q||''); this._kwTokens = this._parseKw(this.kwQuery); this._kwDebounced(); }

    _parseKw(val){ const s=(val||'').trim(); if(!s) return []; const toks=[]; const re=/\"([^\"]+)\"|([^\s]+)/g; let m; while((m=re.exec(s))){ const t=(m[1]||m[2]||'').trim(); if(t) toks.push(t.toLowerCase()); } return toks; }

    computeHitsForText(full, tokens){ if(!full || !tokens || !tokens.length) return 0; const lower=String(full).toLowerCase(); let total=0; for(const t of tokens){ try{ const esc=t.replace(/[.*+?^${}()|[\\]\\]/g, r=>`\\${r}`); const re=new RegExp(esc,'g'); const matches=lower.match(re); total += matches?matches.length:0; }catch(_e){} } return total; }

    async getKwHitsForIds(ids, query){ const toks = this._parseKw(query==null?this.kwQuery:query); const out=new Map(); if(!toks.length) return out; for(const id of ids){ const lines=this.getCachedTextLines(id)||[]; const full = lines.join('\n'); const hits = this.computeHitsForText(full, toks); out.set(String(id), hits); } return out; }

    async _recomputeKwHitsVisible(){ if(!this._visibleIdsProvider) return; const ids = (this._visibleIdsProvider()||[]).map(String); const map = await this.getKwHitsForIds(ids, this.kwQuery); this.emitter.emit('kwHitsUpdated', { ids, hits: map }); }

    async indexForRag(input){
      const ids = Array.isArray(input) ? (typeof input[0]==='object' ? input.map(d=>String(d.doc_id)) : input.map(String)) : [];
      const unique = Array.from(new Set(ids.filter(Boolean)));
      if(!unique.length) return;
      const toIndex = [];
      for(const id of unique){
        if(this._idxInflight.has(id)) continue;
        const h = this.textHash.get(id); // may be undefined if text not fetched yet
        const prev = this.indexedHash.get(id);
        if(h && prev && prev===h){ continue; } // unchanged -> skip
        toIndex.push({ id, hash: h||'' });
      }
      if(!toIndex.length) return;

      // Mark queued
      for(const {id} of toIndex){ this._idxInflight.add(id); this.emitter.emit('indexProgress', { id, state:'Queued' }); }

      try{
        const payload = { doc_ids: toIndex.map(x=>x.id), append: true, skip_if_indexed: true, content_hashes: toIndex.reduce((m,x)=>{ if(x.hash) m[x.id]=x.hash; return m; }, {}) };
        const { fetchPromise } = this._fetch('/explore/index_notes', { method:'POST', headers:{ 'Content-Type':'application/json', 'X-CSRF-Token': this._csrf() }, body: JSON.stringify(payload) });
        const resp = await fetchPromise;
        let j={}; try{ j = await resp.json(); }catch(_e){}
        const results = Array.isArray(j.results) ? j.results : [];
        for(const r of results){ const id=String(r.doc_id||''); const status=String(r.status||''); if(!id) continue; if(status==='Indexed' || status==='Skipped'){ this.indexedHash.set(id, this.textHash.get(id)||''); this.emitter.emit('indexProgress', { id, state:'Indexed' }); } else if(status==='Error'){ this.emitter.emit('indexProgress', { id, state:'Error' }); } else { this.emitter.emit('indexProgress', { id, state: status || 'Indexed' }); } this._idxInflight.delete(id); }
        // For any ids not returned, assume success to avoid wedging
        const returned = new Set(results.map(r=>String(r.doc_id||'')));
        for(const {id} of toIndex){ if(!returned.has(id)){ this.indexedHash.set(id, this.textHash.get(id)||''); this.emitter.emit('indexProgress', { id, state:'Indexed' }); this._idxInflight.delete(id); } }
      }catch(err){
        console.error('[DocumentService] index error', err);
        for(const {id} of toIndex){ this.emitter.emit('indexProgress', { id, state:'Error' }); this._idxInflight.delete(id); }
      }
    }
  }

  window.DocumentService = DocumentService;
})();
