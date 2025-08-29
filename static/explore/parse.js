// Parsing logic for chart text -> pages & sections
import { setChartParsing } from './state.js';

export function parseChartPages(text = '') {
  if(typeof text !== 'string') text = String(text||'');
  const pageRegex = /Page\s+\d+\s+of\s+\d+/gi;
  const matches = [];
  let m; while((m = pageRegex.exec(text)) !== null){ matches.push(m.index); }
  if(matches[0] !== 0) matches.unshift(0);
  matches.push(text.length);
  const pages = []; const sections = [];
  for(let i=0;i<matches.length-1;i++){
    const start = matches[i]; const end = matches[i+1];
    const pageText = text.slice(start,end);
    pages.push(pageText);
    const sectionRegex = /\n([A-Z0-9\s\-\(\)\/,\.]+[:\-])\s*\n/g;
    const pageSections = []; let sm;
    while((sm = sectionRegex.exec(pageText)) !== null){ pageSections.push({ name: sm[1].trim(), index: sm.index }); }
    sections.push(pageSections);
  }
  return { pages, sections };
}

export function updateChartPagesFromChunkText(){
  const ta = document.getElementById('chunkText');
  if(!ta) return setChartParsing({pages:[], sections:[]});
  const parsed = parseChartPages(ta.value||'');
  setChartParsing(parsed);
}
