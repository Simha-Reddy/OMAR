// Chart modal handling
import { exploreState } from './state.js';
import { escapeHtml, escapeRegExp, logWarn } from './utilities.js';

export const ChartModal = {
  matches: [],
  currentIdx: 0,
  open(pageIdx = 0, sectionName = null, keyword = '', offset = null){
    if(!Array.isArray(exploreState.chartPages) || !exploreState.chartPages.length){ alert('No chart data loaded.'); return; }
    exploreState.currentModalPage = Math.min(Math.max(pageIdx,0), exploreState.chartPages.length-1);
    exploreState.highlightSection = sectionName;
    exploreState.keywordHighlight = keyword || '';
    this.findAll(exploreState.keywordHighlight);
    if(this.matches.length){
      const firstOnPage = this.matches.findIndex(m=>m.page===exploreState.currentModalPage);
      this.currentIdx = firstOnPage !== -1 ? firstOnPage : 0;
      exploreState.currentModalPage = this.matches[this.currentIdx].page;
    } else { this.currentIdx = 0; }
    const modal = document.getElementById('chartModal'); if(modal) modal.style.display='flex';
    this.renderPage(exploreState.currentModalPage, exploreState.highlightSection, exploreState.keywordHighlight, offset);
  },
  close(){ const modal = document.getElementById('chartModal'); if(modal) modal.style.display='none'; },
  goto(delta){ const newPage = exploreState.currentModalPage + delta; if(newPage<0 || newPage>= exploreState.chartPages.length) return; exploreState.currentModalPage = newPage; this.renderPage(newPage, exploreState.highlightSection, exploreState.keywordHighlight); const kw=document.getElementById('modalKeywordInput'); if(kw?.value.trim()) kw.dispatchEvent(new Event('input')); },
  findAll(query){ this.matches = []; if(!query) return; const regex = new RegExp(escapeRegExp(query), 'gi'); exploreState.chartPages.forEach((txt, idx)=>{ let m; while((m = regex.exec(txt))!==null){ this.matches.push({ page: idx, index: m.index, length: m[0].length }); } }); },
  updateMatchLabel(){ const el = document.getElementById('modalMatchLabel'); if(!el) return; el.textContent = this.matches.length ? `${this.currentIdx+1} of ${this.matches.length} matches` : 'No matches'; },
  scrollToCurrent(){ const marks = document.querySelectorAll('#chartModalContent mark.chart-modal-match'); if(!marks.length) return; marks.forEach((m,i)=> m.style.background = i===this.currentIdx ? '#ffe066':'#ffff99'); marks[this.currentIdx]?.scrollIntoView({behavior:'smooth', block:'center'}); },
  renderPage(pageIdx, highlightSectionName, keyword, offset){
    if(pageIdx < 0 || pageIdx >= exploreState.chartPages.length) return; const contentDiv = document.getElementById('chartModalContent'); if(!contentDiv) return; let pageText = exploreState.chartPages[pageIdx] || '';
    // Page label
    pageText = pageText.replace(/^Page\s+\d+\s+of\s+\d+\s*/i, '');
    pageText = `**Page ${pageIdx+1}**\n\n` + pageText;
    // Insert anchors for chunks
    if(Array.isArray(exploreState.chartChunks) && exploreState.chartChunks.length){ let html = escapeHtml(pageText); const pageChunks = exploreState.chartChunks.filter(c=>c.page === pageIdx+1).sort((a,b)=> b.start - a.start); for(const chunk of pageChunks){ const anchor = `<span id="${chunk.chunk_id}" class="chart-chunk-anchor"></span>`; html = html.slice(0, chunk.start) + anchor + html.slice(chunk.start); } pageText = html; }
    // Bold section headers
    pageText = pageText.replace(/\n([A-Z0-9\s\-\(\)\/.,]+[:\-])\s*\n/g, (_,header)=>`\n\n### ${header.trim()}\n\n`);
    // Signatures & meta formatting
    pageText = pageText.replace(/(\n\s*)(Signed by[^\n]*)/gi, '\n\n---\n\n$2\n\n---\n\n');
    pageText = pageText.replace(/(\n\s*)(Electronically signed[^\n]*)/gi, '\n\n---\n\n$2\n\n---\n\n');
    pageText = pageText.replace(/(\n\s*)(Attending: [^\n]*)/gi, '\n\n$2\n\n');
    // Section highlight (citation)
    if(highlightSectionName){ const esc = highlightSectionName.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); const sectionRegex = new RegExp(`(\*\*)${esc}(\*\*)`, 'i'); pageText = pageText.replace(sectionRegex, '<span style="background:#ffe066; padding:2px 4px; border-radius:3px;">$1'+esc+'$2</span>'); }
    // Keyword matches
    const keywordInput = document.getElementById('modalKeywordInput'); const kw = keywordInput?.value.trim() || keyword || ''; let html = escapeHtml(pageText); if(kw){ const pageMatches = this.matches.filter(m=>m.page===pageIdx).slice().reverse(); pageMatches.forEach(m=>{ const isCurrent = (this.matches[this.currentIdx] && m.index===this.matches[this.currentIdx].index && pageIdx===this.matches[this.currentIdx].page); const markTag = isCurrent? '<mark class="chart-modal-match" style="background:#ffe066;">':'<mark class="chart-modal-match">'; html = html.slice(0,m.index)+ markTag + html.slice(m.index, m.index+m.length) + '</mark>' + html.slice(m.index+m.length); }); }
    contentDiv.innerHTML = window.marked ? window.marked.parse(pageText) : pageText.replace(/\n/g,'<br>');
    const pageLabel = document.getElementById('chartModalPageLabel'); if(pageLabel) pageLabel.textContent = `Page ${pageIdx+1} of ${exploreState.chartPages.length}`;
    this.updateMatchLabel(); this.attachHandlers(); this.scrollToCurrent();
    if(typeof offset === 'number' && !isNaN(offset)){ setTimeout(()=>{ const marker = document.getElementById('citation-offset-marker'); if(marker) marker.scrollIntoView({behavior:'smooth', block:'center'}); }, 150); }
  },
  attachHandlers(){ // Keyword search
    const input = document.getElementById('modalKeywordInput'); if(input && !input.dataset._wired){ input.dataset._wired='1'; input.addEventListener('input', ()=>{ this.findAll(input.value.trim()); this.currentIdx = 0; this.renderPage(exploreState.currentModalPage, exploreState.highlightSection, input.value.trim()); }); }
    const prev = document.getElementById('prevModalMatchBtn'); if(prev && !prev.dataset._wired){ prev.dataset._wired='1'; prev.addEventListener('click', ()=>{ if(!this.matches.length) return; this.currentIdx = (this.currentIdx - 1 + this.matches.length) % this.matches.length; exploreState.currentModalPage = this.matches[this.currentIdx].page; this.renderPage(exploreState.currentModalPage, exploreState.highlightSection, exploreState.keywordHighlight); }); }
    const next = document.getElementById('nextModalMatchBtn'); if(next && !next.dataset._wired){ next.dataset._wired='1'; next.addEventListener('click', ()=>{ if(!this.matches.length) return; this.currentIdx = (this.currentIdx + 1) % this.matches.length; exploreState.currentModalPage = this.matches[this.currentIdx].page; this.renderPage(exploreState.currentModalPage, exploreState.highlightSection, exploreState.keywordHighlight); }); }
    const closeBtn = document.getElementById('closeChartModalBtn'); if(closeBtn && !closeBtn.dataset._wired){ closeBtn.dataset._wired='1'; closeBtn.addEventListener('click', ()=>this.close()); }
    const prevPage = document.getElementById('modalPrevBtn'); if(prevPage && !prevPage.dataset._wired){ prevPage.dataset._wired='1'; prevPage.addEventListener('click', ()=>this.goto(-1)); }
    const nextPage = document.getElementById('modalNextBtn'); if(nextPage && !nextPage.dataset._wired){ nextPage.dataset._wired='1'; nextPage.addEventListener('click', ()=>this.goto(1)); }
  },
  initGlobals(){ window.openChartModal = (...a)=>this.open(...a); window.closeChartModal = ()=>this.close(); window.gotoChartModalPage = d=>this.goto(d); }
};

ChartModal.initGlobals();
