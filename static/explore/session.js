// Session persistence helpers
import { debounce, logWarn } from './utilities.js';
import { exploreState } from './state.js';

async function guardedSessionSave(){
  if(exploreState.savingSession){ exploreState.pendingSessionSave = true; return; }
  exploreState.savingSession = true;
  try { if(window.SessionManager?.saveToSession) await window.SessionManager.saveToSession(); }
  catch(e){ logWarn('Session save failed', e); }
  finally {
    exploreState.savingSession = false;
    if(exploreState.pendingSessionSave){ exploreState.pendingSessionSave = false; guardedSessionSave(); }
  }
}

export const debouncedSessionSave = debounce(guardedSessionSave, 600);

export async function restoreSession(){
  if(!window.SessionManager?.loadFromSession) return;
  try { await window.SessionManager.loadFromSession(); }
  catch(e){ logWarn('Session restore failed', e); }
}

export function wireAutosave(ids = ['chunkText','exploreSearchBox','invertedSearchBox']){
  ids.forEach(id=>{ const el = document.getElementById(id); if(!el) return; el.addEventListener('input', ()=>debouncedSessionSave()); });
}
