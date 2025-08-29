// Minimal Explore legacy script: chart data chunking, indexing, querying, modal & citations only
// Removed unrelated modules (labs, vitals, patient selection, RPC, dynamic modules, etc.)

// --- State ---
let chartPages = [];
let chartPageSections = [];
let chartChunks = [];
let currentModalPage = 0;
let highlightSection = null;
let keywordHighlight = "";

// Modal keyword match state
let modalMatches = []; // {page, index, length}
let modalCurrentIdx = 0;

// --- Utilities ---
function escapeHtml(text) {
  return text.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[m]));
}
function escapeRegExp(str){return str.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}
function chunkId(section, page){return `chunk-${section.replace(/[^a-zA-Z0-9]/g,'')}-${page}`;}

// --- Parse chart text into pages & sections ---
function parseChartPages(text){
  const pageRegex = /Page\s+\d+\s+of\s+\d+/gi;
  let positions=[]; let m; while((m=pageRegex.exec(text))!==null){positions.push(m.index);} if(positions[0]!==0) positions.unshift(0); positions.push(text.length);
  const pages=[]; const sections=[]; for(let i=0;i<positions.length-1;i++){const start=positions[i];const end=positions[i+1];const pageText=text.slice(start,end);pages.push(pageText);const sectionRegex=/\n([A-Z0-9\s\-\(\)\/,\.]+[:\-])\s*\n/g;let ps=[];let sm;while((sm=sectionRegex.exec(pageText))!==null){ps.push({name:sm[1].trim(),index:sm.index});}sections.push(ps);}return {pages,sections};
}
function updateChartPagesFromChunkText(){
  const text=document.getElementById('chunkText')?.value||'';
  const parsed=parseChartPages(text); chartPages=parsed.pages; chartPageSections=parsed.sections;
}

// --- Modal keyword search helpers ---
function findAllModalMatches(query){modalMatches=[]; if(!query) return; const r=new RegExp(escapeRegExp(query),"gi"); chartPages.forEach((pg,pi)=>{let match; while((match=r.exec(pg))!==null){modalMatches.push({page:pi,index:match.index,length:match[0].length});}});} 
function updateModalMatchLabel(){const lbl=document.getElementById('modalMatchLabel'); if(!lbl) return; if(modalMatches.length) lbl.textContent=`${modalCurrentIdx+1} of ${modalMatches.length} matches`; else lbl.textContent='No matches';}
function scrollToModalMatch(){const marks=document.querySelectorAll('#chartModalContent mark.chart-modal-match'); if(marks.length && marks[modalCurrentIdx]){marks.forEach((m,i)=>m.style.background=i===modalCurrentIdx?'#ffe066':'#ffff99'); marks[modalCurrentIdx].scrollIntoView({behavior:'smooth',block:'center'});} }

// --- Render a modal page ---
function renderChartModalPage(pageIdx, highlightSectionName, keyword, offset){
  if(pageIdx<0||pageIdx>=chartPages.length) return; const contentDiv=document.getElementById('chartModalContent'); let pageText=chartPages[pageIdx];
  // normalize page header & add label
  pageText=pageText.replace(/^Page\s+\d+\s+of\s+\d+\s*/i,''); pageText=`**Page ${pageIdx+1}**\n\n`+pageText;
  // insert chunk anchors
  if(chartChunks?.length){let html=escapeHtml(pageText); const pageChunkList=chartChunks.filter(c=>c.page===pageIdx+1).sort((a,b)=>b.start-a.start); for(const ch of pageChunkList){const anchor=`<span id="${ch.chunk_id}" class="chart-chunk-anchor"></span>`; html=html.slice(0,ch.start)+anchor+html.slice(ch.start);} pageText=html;}
  // section formatting
  pageText=pageText.replace(/\n([A-Z0-9\s\-\(\)\/,\.]+[:\-])\s*\n/g,( _ ,hdr)=>`\n\n### ${hdr.trim()}\n\n`);
  pageText=pageText.replace(/(\n\s*)(Signed by[^\n]*)/gi,'\n\n---\n\n$2\n\n---\n\n')
                   .replace(/(\n\s*)(Electronically signed[^\n]*)/gi,'\n\n---\n\n$2\n\n---\n\n')
                   .replace(/(\n\s*)(Attending: [^\n]*)/gi,'\n\n$2\n\n')
                   .replace(/(\n\s*)(Date[:\-][^\n]*)/gi,'\n\n$2\n\n')
                   .replace(/(\n\s*)(DOB[:\-][^\n]*)/gi,'\n\n$2\n\n');
  // highlight section anchor
  if(highlightSectionName){const esc=highlightSectionName.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); const reg=new RegExp('(\\*\\*)'+esc+'(\\*\\*)','i'); pageText=pageText.replace(reg,(m)=>`<span style="background:#ffe066;padding:2px 4px;border-radius:3px;">${m}</span>`);}
  // keyword matches for current page
  const modalKeywordInput=document.getElementById('modalKeywordInput'); const kw=(modalKeywordInput&&modalKeywordInput.value.trim())||''; const pageMatches=modalMatches.filter(m=>m.page===pageIdx); let html=escapeHtml(pageText); if(kw && pageMatches.length){pageMatches.slice().reverse().forEach(m=>{const isCurrent=modalMatches[modalCurrentIdx] && m.index===modalMatches[modalCurrentIdx].index && pageIdx===modalMatches[modalCurrentIdx].page; const markTag=isCurrent?'<mark class="chart-modal-match" style="background:#ffe066;">':'<mark class="chart-modal-match">'; html=html.slice(0,m.index)+markTag+html.slice(m.index,m.index+m.length)+'</mark>'+html.slice(m.index+m.length);});}
  contentDiv.innerHTML= typeof marked!=='undefined'? marked.parse(pageText) : pageText.replace(/\n/g,'<br>');
  document.getElementById('chartModalPageLabel').textContent=`Page ${pageIdx+1} of ${chartPages.length}`; updateModalMatchLabel(); attachChartModalHandlers(); scrollToModalMatch();
  // offset marker
  if(typeof offset==='number' && !isNaN(offset)){ setTimeout(()=>{const node=contentDiv.childNodes[0]; if(node){let charCount=0,found=false; (function walk(n){ if(found)return; if(n.nodeType===Node.TEXT_NODE){ if(charCount+n.length>=offset){const span=document.createElement('span'); span.style.background='#ffe066'; span.id='citation-offset-marker'; const split=offset-charCount; const after=n.splitText(split); n.parentNode.insertBefore(span,after); span.appendChild(after); found=true;} else {charCount+=n.length;} } else if(n.nodeType===Node.ELEMENT_NODE){ for(const c of n.childNodes) walk(c);} })(node); const marker=document.getElementById('citation-offset-marker'); if(marker) marker.scrollIntoView({behavior:'smooth',block:'center'});} },200);} }

function attachChartModalHandlers(){
  const prev=document.getElementById('modalPrevBtn'); if(prev) prev.onclick=()=>gotoChartModalPage(-1);
  const next=document.getElementById('modalNextBtn'); if(next) next.onclick=()=>gotoChartModalPage(1);
  const close=document.getElementById('closeChartModalBtn'); if(close) close.onclick=closeChartModal;
  const input=document.getElementById('modalKeywordInput'); if(input){ input.removeEventListener('input',input._handler||(()=>{})); input._handler=function(){ modalCurrentIdx=0; findAllModalMatches(this.value.trim()); if(modalMatches.length){const m=modalMatches[modalCurrentIdx]; currentModalPage=m.page;} renderChartModalPage(currentModalPage,highlightSection,this.value.trim()); }; input.addEventListener('input',input._handler);} 
  const prevMatch=document.getElementById('prevModalMatchBtn'); if(prevMatch) prevMatch.onclick=function(){ if(!modalMatches.length) return; modalCurrentIdx=(modalCurrentIdx-1+modalMatches.length)%modalMatches.length; const m=modalMatches[modalCurrentIdx]; currentModalPage=m.page; renderChartModalPage(currentModalPage,highlightSection,input.value.trim());};
  const nextMatch=document.getElementById('nextModalMatchBtn'); if(nextMatch) nextMatch.onclick=function(){ if(!modalMatches.length) return; modalCurrentIdx=(modalCurrentIdx+1)%modalMatches.length; const m=modalMatches[modalCurrentIdx]; currentModalPage=m.page; renderChartModalPage(currentModalPage,highlightSection,input.value.trim());};
}

// --- Modal controls ---
window.openChartModal=function(pageIdx,sectionName,keyword,offset){ if(!chartPages.length){alert('No chart data loaded.'); return;} currentModalPage=pageIdx; highlightSection=sectionName||null; const modalKeywordInput=document.getElementById('modalKeywordInput'); if(!keyword && modalKeywordInput){ modalKeywordInput.value=''; findAllModalMatches(''); } else { keywordHighlight= keyword || (modalKeywordInput?modalKeywordInput.value.trim():''); findAllModalMatches(keywordHighlight);} if(modalMatches.length){ const idx=modalMatches.findIndex(m=>m.page===currentModalPage); modalCurrentIdx= idx!==-1?idx:0; currentModalPage=modalMatches[modalCurrentIdx].page; } else { modalCurrentIdx=0; }
  document.getElementById('chartModal').style.display='flex'; renderChartModalPage(currentModalPage,highlightSection,keywordHighlight,offset);
};
window.closeChartModal=function(){ document.getElementById('chartModal').style.display='none'; };
window.gotoChartModalPage=function(delta){ const np=currentModalPage+delta; if(np<0||np>=chartPages.length) return; currentModalPage=np; renderChartModalPage(currentModalPage,highlightSection,keywordHighlight); const kw=document.getElementById('modalKeywordInput'); if(kw && kw.value.trim()) kw.dispatchEvent(new Event('input')); };

// --- Submit chart text for chunking / embeddings ---
async function submitChartChunk(){ updateChartPagesFromChunkText(); const chunkText=document.getElementById('chunkText')?.value; const chunkLabel=document.getElementById('chunkLabel')?.value; const status=document.getElementById('chunkStatus'); if(!chunkText||!chunkText.trim()){alert('Please enter chart data before submitting.'); return;} if(status) status.textContent='⏳ Indexing chart data...'; try { const res=await fetch('/explore/process_chart_chunk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:chunkText,label:chunkLabel})}); const data=await res.json(); if(data.chunks) chartChunks=data.chunks; if(status) status.textContent='✅ Chart data indexed successfully.'; } catch(err){ console.error('Error submitting chart chunk:',err); if(status) status.textContent='⚠️ Error processing data.'; } }
if(typeof window!=='undefined') window.submitChartChunk=submitChartChunk;

// --- Run retrieval QA over indexed chunks ---
let exploreQAHistory=[];
window.runExploreSearch=async function(){ const qEl=document.getElementById('exploreSearchBox'); if(!qEl) return; const query=qEl.value; if(!query.trim()) return; const answerBox=document.getElementById('exploreGptAnswer'); if(answerBox) answerBox.innerHTML= (typeof showThinkingSpinner==='function')? showThinkingSpinner() : 'Thinking...'; try { const res=await fetch('/explore/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,qa_history:exploreQAHistory})}); const data=await res.json(); if(data.error){ if(answerBox) answerBox.textContent=data.error; return;} exploreQAHistory.push({question:query,answer:data.answer}); const answerHtml= typeof marked!=='undefined'? marked.parse(data.answer||'') : escapeHtml(data.answer||''); if(answerBox){ answerBox.innerHTML=linkifyCitations(answerHtml); answerBox.scrollIntoView({behavior:'smooth'}); } } catch(err){ if(answerBox) answerBox.textContent='Error: '+err.message; } };

// --- Linkify citations in model answer ---
function linkifyCitations(answerHtml){ return answerHtml.replace(/\(([^)]+)\)/g,(full,inner)=>{ const parts=inner.split(/;\s*|,\s*(?=[Pp]age\s*\d+)/); const linked=parts.map(part=>{ const m=part.match(/^(?:([A-Z0-9\s\-\(\)\/,\.]+?),\s*)?[Pp]age\s*(\d+)(?:,?\s*Offset\s*(\d+))?/i); if(m){ const section=m[1]?m[1].trim():'Page'; const page=m[2]; const offset=m[3]?m[3]:null; const id=chunkId(section,page); return `<a href="#" class="citation-link" data-chunkid="${id}" data-page="${page}"${offset?` data-offset="${offset}"`:''}>${part.trim()}</a>`; } return part; }); return '('+linked.join('; ')+')'; }); }

// --- Citation click handler ---
document.addEventListener('click',e=>{ if(e.target.classList?.contains('citation-link')){ e.preventDefault(); const chunkIdAttr=e.target.getAttribute('data-chunkid'); const page=parseInt(e.target.getAttribute('data-page'),10); const offsetStr=e.target.getAttribute('data-offset'); const offset=offsetStr?parseInt(offsetStr,10):undefined; if(chunkIdAttr){ const chunk=chartChunks.find(c=>c.chunk_id===chunkIdAttr); const pageIdx= chunk? (chunk.page-1) : (!isNaN(page)? page-1 : 0); openChartModal(pageIdx,null,null,offset); setTimeout(()=>{ if(chunk){ const anchor=document.getElementById(chunk.chunk_id); if(anchor) anchor.scrollIntoView({behavior:'smooth',block:'center'}); } else if(typeof offset==='number'){ const marker=document.getElementById('citation-offset-marker'); if(marker) marker.scrollIntoView({behavior:'smooth',block:'center'}); } },300); } } });

// --- PDF Drop Zone & UI wiring ---
document.addEventListener('DOMContentLoaded',()=>{
  const dropZone=document.getElementById('dropZone');
  if(dropZone){ const textArea=document.getElementById('chunkText'); const status=document.getElementById('chunkStatus'); ['dragenter','dragover','dragleave','drop'].forEach(ev=>{dropZone.addEventListener(ev,preventDefaults,false); document.body.addEventListener(ev,preventDefaults,false);}); ['dragenter','dragover'].forEach(ev=>dropZone.addEventListener(ev,highlight,false)); ['dragleave','drop'].forEach(ev=>dropZone.addEventListener(ev,unhighlight,false)); dropZone.addEventListener('drop',handleDrop,false);
    function preventDefaults(e){e.preventDefault(); e.stopPropagation();}
    let dragCounter=0; function highlight(){dragCounter++; dropZone.classList.add('dragging');}
    function unhighlight(e){ if(e.type==='drop'){dragCounter=0; dropZone.classList.remove('dragging'); return;} if(e.type==='dragleave'){ if(!e.relatedTarget || !dropZone.contains(e.relatedTarget)){dragCounter=0; dropZone.classList.remove('dragging');} else { dragCounter=Math.max(0,dragCounter-1); if(dragCounter===0) dropZone.classList.remove('dragging'); } } }
    async function handleDrop(e){ const file=e.dataTransfer.files[0]; if(file && file.type==='application/pdf'){ status.textContent='Processing PDF...'; const fd=new FormData(); fd.append('pdf',file); try { const r=await fetch('/upload_pdf',{method:'POST',body:fd}); const data=await r.json(); if(data.error){ status.textContent='Error: '+data.error; } else { textArea.value=data.text; status.textContent='PDF processed successfully!'; updateChartPagesFromChunkText(); } } catch(err){ status.textContent='Error: '+err.message; } } else { status.textContent='Please drop a PDF file.'; } }
  }
  const openKeywordModalBtn=document.getElementById('openKeywordModalBtn'); if(openKeywordModalBtn){ openKeywordModalBtn.addEventListener('click',()=>{ const input=document.getElementById('modalKeywordInput'); if(input){ input.value=''; input.dispatchEvent(new Event('input')); input.focus(); } openChartModal(0,null,''); }); }
  const exploreSearchBox=document.getElementById('exploreSearchBox'); if(exploreSearchBox){ exploreSearchBox.addEventListener('keypress',e=>{ if(e.key==='Enter') runExploreSearch(); }); }
});