// Entry point aggregator for Explore page.
// This file is loaded dynamically by /static/explore.js as an ES module.
// For now, we simply import the legacy implementation so existing globals
// like submitChartChunk() are defined and the Prepare Data button works.
// TODO: Refactor old_explore.js into modular pieces and export needed APIs.
import './old_explore.js';
import './patient_rag.js';
import './documents.js';
import './vitals_sidebar.js';
import './demo_masking.js'; // Add demo masking functionality
import { openDocument as _openDocument } from './state.js';
// New: autosave helpers for Explore
import { wireAutosave } from './session.js';

// Bridge for sandboxed agent citations -> central document open event
try {
  window.AgentOpenDocument = function(payload){
    try {
      const p = payload || {}; const docId = p.docId || p.noteId || p.note_id;
      const excerptText = p.excerptText || p.excerpt || '';
      if(!docId) return;
      _openDocument({ docId: String(docId), excerptText: String(excerptText||'') });
    } catch(_e) {}
  };
  // Fallback alias used by some callers
  window.openDocument = function(payload){ try { window.AgentOpenDocument(payload); } catch(_e){} };
} catch {}

// Wire autosave for Explore fields, including new visitNotes mirror box
try {
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', ()=> wireAutosave(['chunkText','exploreSearchBox','invertedSearchBox','visitNotes']), { once: true });
  } else {
    wireAutosave(['chunkText','exploreSearchBox','invertedSearchBox','visitNotes']);
  }
} catch(_e) {}

console.log('[Explore] index.js loaded (legacy old_explore.js, patient_rag.js, and documents.js imported).');
