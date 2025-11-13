from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
from ...contracts import QueryModel
from omar.ai_tools import llm

# Simple, copyable provider that performs a minimal RAG over the current patient's TIU notes.
# It reuses utilities from the default model's RAG services via template_model.services.rag_simple.

class TemplateQueryModelImpl:
    model_id = 'template'
    name = 'Template Query Model (Copy Me)'

    def __init__(self):
        self._prompt_path = Path(__file__).parent / 'PROMPT_answer.md'

    def _build_chunks_from_dfn(self, dfn: str, *, gateway=None) -> List[Dict[str, Any]]:
        """Build simple text chunks from the DocumentSearchIndex for this DFN.
        Each chunk includes text and lightweight metadata for citation building.
        """
        from omar.services.document_search_service import get_or_build_index_for_dfn
        from .services.rag_simple import sliding_window_chunk, remove_boilerplate_phrases
        idx = get_or_build_index_for_dfn(str(dfn), gateway=gateway)
        order = list(getattr(idx, 'order', []) or [])
        text_map = getattr(idx, 'text', {}) or {}
        meta_map = getattr(idx, 'meta', {}) or {}
        doc_ids: List[str] = order[:200] if order else list(text_map.keys())[:200]
        chunks: List[Dict[str, Any]] = []
        for doc_id in doc_ids:
            full = (text_map.get(doc_id) or '').strip()
            if not full:
                continue
            meta = meta_map.get(doc_id, {}) if isinstance(meta_map, dict) else {}
            title = meta.get('title') or ''
            date = meta.get('date') or ''
            text_clean = remove_boilerplate_phrases(full)
            for ch in sliding_window_chunk(text_clean, window_size=1600, step_size=800):
                ch['title'] = title
                ch['date'] = date
                ch['note_id'] = str(doc_id)
                chunks.append(ch)
        return chunks

    def answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Accept new 'query' and legacy 'prompt'
        query = (payload.get('query') or payload.get('prompt') or '').strip()
        patient = payload.get('patient') or {}
        if not query:
            return { 'answer': '', 'citations': [], 'model_id': self.model_id }

        # Resolve DFN (patient local identifier) if present
        try:
            dfn = (patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId') or '').strip()
        except Exception:
            dfn = ''

        # 1) Build chunks and BM25 index (simple keyword search)
        from .services.rag_simple import build_bm25_index, hybrid_search
        gateway = None
        if dfn:
            try:
                sess = payload.get('session') or {}
                station = str(sess.get('station') or '500')
                duz = str(sess.get('duz') or '983')
                from omar.gateways.factory import get_gateway
                gateway = get_gateway(station=station, duz=duz)
            except Exception:
                try:
                    from omar.gateways.factory import get_gateway
                    gateway = get_gateway()
                except Exception:
                    gateway = None
        chunks: List[Dict[str, Any]] = self._build_chunks_from_dfn(dfn, gateway=gateway) if dfn else []
        bm25 = build_bm25_index(chunks) if chunks else None
        if not (chunks and bm25):
            # Nothing to search; answer trivially
            answer_text = llm.chat((self._prompt_path.read_text(encoding='utf-8')).strip() + f"\n\nQuestion: \"{query}\"")
            return { 'answer': answer_text, 'citations': [], 'model_id': self.model_id }

        # 2) Retrieve top excerpts with a small per-note diversity and cap of 12
        top_chunks: List[Dict[str, Any]] = hybrid_search(query, chunks, vectors=None, bm25_index=bm25, top_k=12)

        # 3) Build a simple prompt with numbered excerpts
        system = (self._prompt_path.read_text(encoding='utf-8')).strip()
        # Stable note -> Excerpt number mapping (first appearance order)
        note_order: Dict[str, int] = {}
        order_ctr = 1
        for c in top_chunks:
            nid = str(c.get('note_id') or '')
            if nid and nid not in note_order:
                note_order[nid] = order_ctr
                order_ctr += 1
        context_blobs: List[str] = []
        for c in top_chunks:
            nid = str(c.get('note_id') or '')
            ex = note_order.get(nid, '?')
            dt = c.get('date') or ''
            ttl = c.get('title') or ''
            hdr = f"### Source: (Excerpt {ex}{', Date: ' + dt if dt else ''}{', Title: ' + ttl if ttl else ''})"
            context_blobs.append(hdr + "\n" + (c.get('text') or '')[:1600])
        context = "\n\n".join(context_blobs)
        final_prompt = f"{system}\n\nQuestion: \"{query}\"\n\nBelow are excerpts from the chart:\n{context}"
        answer_text = llm.chat(final_prompt)

        # 4) Prepare citations consumable by the UI
        citations = []
        for c in top_chunks:
            nid = str(c.get('note_id') or '')
            citations.append({
                'excerpt': note_order.get(nid, '?'),
                'note_id': c.get('note_id'),
                'title': c.get('title'),
                'date': c.get('date'),
                'preview': (c.get('text') or '')[:200]
            })

        return { 'answer': answer_text, 'citations': citations, 'model_id': self.model_id }

    def rag_results(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return early RAG results (notes/excerpts) for the given query. If DFN or index not available, return empty list."""
        query = (payload.get('query') or payload.get('prompt') or '').strip()
        patient = payload.get('patient') or {}
        if not query:
            return { 'results': [] }
        try:
            dfn = (patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId') or '').strip()
        except Exception:
            dfn = ''
        if not dfn:
            return { 'results': [] }
        from .services.rag_simple import build_bm25_index, hybrid_search
        gateway = None
        if dfn:
            try:
                sess = payload.get('session') or {}
                station = str(sess.get('station') or '500')
                duz = str(sess.get('duz') or '983')
                from omar.gateways.factory import get_gateway
                gateway = get_gateway(station=station, duz=duz)
            except Exception:
                try:
                    from omar.gateways.factory import get_gateway
                    gateway = get_gateway()
                except Exception:
                    gateway = None
        chunks: List[Dict[str, Any]] = self._build_chunks_from_dfn(dfn, gateway=gateway)
        bm25 = build_bm25_index(chunks) if chunks else None
        if not (chunks and bm25):
            return { 'results': [] }
        top_chunks: List[Dict[str, Any]] = hybrid_search(query, chunks, vectors=None, bm25_index=bm25, top_k=12)
        # Group by note and preserve first-seen order
        by_note: Dict[str, Dict[str, Any]] = {}
        order: List[Dict[str, Any]] = []
        seen = set()
        for ch in top_chunks:
            nid = str(ch.get('note_id') or '')
            if not nid:
                continue
            rec = by_note.get(nid)
            if not rec:
                rec = { 'note_id': nid, 'title': ch.get('title') or '', 'date': ch.get('date') or '', 'excerpts': [] }
                by_note[nid] = rec
            rec['excerpts'].append({ 'page': ch.get('page') or '?', 'text': (ch.get('text') or '')[:300] })
            if nid not in seen:
                seen.add(nid)
                order.append(rec)
        for i, rec in enumerate(order, start=1):
            rec['index'] = i
        return { 'results': order }

# Export symbol for registry
model: QueryModel = TemplateQueryModelImpl()
