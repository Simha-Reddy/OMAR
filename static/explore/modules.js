// Module loading & execution logic
import { exploreState } from './state.js';
import { escapeHtml, logWarn, logInfo, ensureSpinnerFn } from './utilities.js';

export async function loadModules(){
  let response; try { response = await fetch('/modules/all'); } catch(e){ logWarn('Module fetch failed', e); return; }
  if(!response?.ok){ logWarn('Module fetch HTTP error'); return; }
  let modules; try { modules = await response.json(); } catch(e){ logWarn('Bad JSON for modules', e); return; }
  if(!Array.isArray(modules)){ logWarn('Modules payload not array'); return; }
  const container = document.getElementById('dynamicModules'); if(!container){ logWarn('dynamicModules container missing'); return; }
  container.innerHTML = '';
  let row = document.createElement('div'); row.className = 'side-by-side';
  modules.forEach((m,i)=>{ const data = parseModuleContent(m.content||''); const el = createModuleElement(data); row.appendChild(el); if((i+1)%2===0 || i===modules.length-1){ container.appendChild(row); row = document.createElement('div'); row.className='side-by-side'; } });
}

export function parseModuleContent(content=''){ const lines = content.split('\n').map(l=>l.trim()); const d={ title:'', fields:[], query:'', prompt:'', output:'', chain:[]}; lines.forEach(line=>{ if(line.startsWith('Title:')) d.title=line.slice(6).trim(); else if(line.startsWith('Output:')) d.output=line.slice(7).trim(); else if(line.startsWith('Chain:')) d.chain=line.slice(6).split(',').map(s=>s.trim()).filter(Boolean); else if(line.startsWith('Query:')) d.query=line.slice(6).trim(); else if(line.startsWith('AI Prompt:')) d.prompt=line.slice(10).trim(); else if(/^\[\s*[Xx ]\s*]/.test(line)){ const checked=/^\[\s*[Xx]\s*]/.test(line); const name=line.replace(/^\[\s*[Xx ]\s*]/,'').trim(); d.fields.push({name, checked}); } }); if(!d.output) d.output = d.title.replace(/\s+/g,'').toLowerCase(); return d; }

function createModuleElement(data){ const el=document.createElement('div'); el.classList.add('panel'); const header=document.createElement('div'); header.style.display='flex'; header.style.alignItems='center'; header.style.justifyContent='space-between'; header.style.marginBottom='8px'; const title=document.createElement('h2'); title.textContent=data.title; title.style.fontSize='1.2em'; title.style.margin='0'; header.appendChild(title); const btn=document.createElement('button'); btn.textContent='Run'; btn.className='run-panel-btn'; btn.style.fontSize='1.05em'; btn.onclick=()=>runModule(data, el, btn); header.appendChild(btn); el.appendChild(header); const out=document.createElement('div'); out.classList.add('markdown-box','module-output'); out.style.minHeight='120px'; el.appendChild(out); return el; }

export async function runModule(data, moduleEl, button){ ensureSpinnerFn(); if(button) { button.disabled = true; button.dataset._origText = button.textContent; button.textContent='Running...'; }
  if(window.SessionManager?.saveToSession){ try { await window.SessionManager.saveToSession(); await window.SessionManager.loadFromSession(); } catch(e){ logWarn('Session sync failed', e); } }
  const sessionData = window.SessionManager?.lastLoadedData || {}; const scribe = sessionData.scribe||{}; const explore = sessionData.explore||{};
  const inputs={}; data.fields.forEach(f=>{ if(!f.checked) return; if(f.name==='chunkText'){ inputs.chunkText = scribe.chunkText || explore.chunkText || ''; } else if(scribe[f.name]!==undefined) inputs[f.name]=scribe[f.name]; else if(explore[f.name]!==undefined) inputs[f.name]=explore[f.name]; else inputs[f.name]=''; });
  if(data.fields.some(f=>f.checked && f.name==='chunkText')){ const ct = inputs.chunkText||''; if(!ct.trim()){ alert('Enter and prepare chart data before running this module.'); restoreButton(); return; } }
  const body = { module: data.output, prompt: data.prompt, query: data.query, selected_fields: [data.output], ...inputs };
  const out = moduleEl.querySelector('.module-output'); if(out) out.innerHTML = window.showThinkingSpinner? window.showThinkingSpinner() : '<em>Running...</em>';
  let res; try { res = await fetch('/run_module', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }); } catch(e){ logWarn('Module network error', e); if(out) out.textContent='Error: network failure'; restoreButton(); return; }
  if(!res.ok){ if(out) out.textContent = 'Error running module'; restoreButton(); return; }
  let json; try { json = await res.json(); } catch(e){ if(out) out.textContent='Bad JSON response'; restoreButton(); return; }
  const result = json?.results?.[data.output]; if(out) out.innerHTML = result ? renderModuleResult(result, data.output) : '<em>No result.</em>';
  if(window.SessionManager?.saveToSession){ try { await window.SessionManager.saveToSession(); } catch(e){ logWarn('Post-run session save failed', e); } }
  restoreButton();
  function restoreButton(){ if(button){ button.disabled=false; if(button.dataset._origText) button.textContent = button.dataset._origText; } }
}

// Result renderer (simplified & defensive)
export function renderModuleResult(result){ if(result==null) return '<em>(empty)</em>'; if(Array.isArray(result)){ if(result.length && typeof result[0]==='object'){ const keys = Object.keys(result[0]); const uniform = result.every(r=>r && typeof r==='object' && Object.keys(r).join()===keys.join()); if(uniform){ let html='<table class="module-table"><thead><tr>'+keys.map(k=>`<th>${escapeHtml(k)}</th>`).join('')+'</tr></thead><tbody>'; result.forEach(r=>{ html+='<tr>'+keys.map(k=>`<td>${escapeHtml(r[k])}</td>`).join('')+'</tr>'; }); html+='</tbody></table>'; return html; } }
  return '<ul>'+result.map(r=>'<li>'+ (typeof r==='string'? escapeHtml(r): renderModuleResult(r)) +'</li>').join('')+'</ul>'; }
  if(typeof result === 'object'){ let html='<dl>'; Object.entries(result).forEach(([k,v])=>{ html+=`<dt>${escapeHtml(k)}</dt><dd>${renderModuleResult(v)}</dd>`; }); return html+'</dl>'; }
  if(typeof result === 'string'){ if(window.marked){ try { return window.marked.parse(result); } catch { /* ignore */ } } return escapeHtml(result); }
  return escapeHtml(String(result)); }

// Legacy global hooks for backward compatibility
window.loadModules = loadModules;
window.runModule = (...a)=>runModule(...a);
