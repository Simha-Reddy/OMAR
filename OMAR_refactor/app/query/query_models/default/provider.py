from __future__ import annotations
from typing import Dict, Any, List
from ...contracts import QueryModel
from app.ai_tools import llm
from pathlib import Path
from app.gateways.vista_api_x_gateway import VistaApiXGateway
from .services.rag import (
    RagEngine,
    sliding_window_chunk,
    remove_boilerplate_phrases,
    build_bm25_index,
    hybrid_search,
)

class DefaultQueryModelImpl:
    model_id = 'default'
    name = 'Default Hey OMAR Model'

    def __init__(self):
        self._prompt_path = Path(__file__).parent / 'PROMPT_answer.md'
        # Simple in-model cache keyed by DFN; avoids global RagStore.
        # Structure: { dfn: { 'chunks': [...], 'bm25': obj, 'vectors': None, 'updated_at': float } }
        self._patient_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 3 * 60 * 60  # 3 hours

    def _get_cached(self, dfn: str) -> Dict[str, Any] | None:
        try:
            entry = self._patient_cache.get(str(dfn))
            if not entry:
                return None
            import time
            if (time.time() - float(entry.get('updated_at') or 0)) > self._cache_ttl_seconds:
                return None
            return entry
        except Exception:
            return None

    def _set_cached(self, dfn: str, chunks: List[Dict[str, Any]], bm25: Dict[str, Any], vectors: Any = None):
        import time
        self._patient_cache[str(dfn)] = {
            'chunks': chunks or [],
            'bm25': bm25,
            'vectors': vectors,
            'updated_at': time.time(),
        }

    def _build_chunks_from_document_index(self, dfn: str) -> List[Dict[str, Any]]:
        """Bridge DocumentSearchIndex full texts into chunk list."""
        try:
            from app.services.document_search_service import get_or_build_index_for_dfn
            idx = get_or_build_index_for_dfn(str(dfn))
        except Exception:
            return []
        try:
            order = list(getattr(idx, 'order', []) or [])
            text_map = getattr(idx, 'text', {}) or {}
            meta_map = getattr(idx, 'meta', {}) or {}
        except Exception:
            return []
        # Limit documents to keep memory reasonable
        doc_ids: List[str] = order[:200] if order else list(text_map.keys())[:200]
        all_chunks: List[Dict[str, Any]] = []
        for doc_id in doc_ids:
            try:
                full = (text_map.get(doc_id) or '').strip()
                if not full:
                    continue
                meta = meta_map.get(doc_id, {}) if isinstance(meta_map, dict) else {}
                title = meta.get('title') or ''
                date = meta.get('date') or ''
                text_clean = remove_boilerplate_phrases(full)
                chunks = sliding_window_chunk(text_clean, window_size=1600, step_size=800)
                for ch in chunks:
                    ch['title'] = title
                    ch['date'] = date
                    ch['note_id'] = str(doc_id)
                all_chunks.extend(chunks)
            except Exception:
                continue
        return all_chunks

    def answer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Accept new 'query' (preferred) and fall back to legacy 'prompt'
        query = (payload.get('query') or payload.get('prompt') or '').strip()
        patient = payload.get('patient')  # optional dict expected to contain DFN/localId
        sess = payload.get('session') or {}
        if not query:
            return { 'answer': '', 'citations': [], 'model_id': self.model_id }

        # 1) Build/obtain chunked index from existing DocumentSearchIndex (keyword index)
        dfn = None
        try:
            if isinstance(patient, dict):
                dfn = patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId')
        except Exception:
            dfn = None
        # Prefer session-provided station/duz if present
        try:
            station = str(sess.get('station') or '500')
            duz = str(sess.get('duz') or '983')
        except Exception:
            station, duz = '500', '983'
        gateway = VistaApiXGateway(station=station, duz=duz)
        top_chunks: List[Dict[str, Any]] = []
        if dfn:
            cached = self._get_cached(str(dfn))
            chunks: List[Dict[str, Any]] = []
            bm25: Dict[str, Any] | None = None
            if cached and (cached.get('chunks')):
                chunks = list(cached.get('chunks') or [])
                bm25 = cached.get('bm25')  # type: ignore
            else:
                chunks = self._build_chunks_from_document_index(str(dfn))
                bm25 = build_bm25_index(chunks) if chunks else None
                if chunks and bm25:
                    self._set_cached(str(dfn), chunks, bm25)
            # Retrieval uses raw user query
            if chunks and bm25:
                top_chunks = hybrid_search(query, chunks, vectors=None, bm25_index=bm25, top_k=10)
            else:
                top_chunks = []
        else:
            # Fallback: ad-hoc RAG on provided documents (empty by default)
            vpr_docs = {'data': {'items': []}}
            rag = RagEngine(window_size=1600, step_size=800)
            rag.build_chunks_from_vpr_documents(vpr_docs)
            rag.index()
            top_chunks = rag.retrieve(query, top_k=10)

        # 3) Build clinical preface (demographics, active problems/meds, and today's DOS), then compose LLM prompt
        # Best-effort extraction via VPR domains; silent on errors
        preface = ''
        try:
            nm = ''
            ag = ''
            probs_line = ''
            meds_line = ''
            # Demographics for name/age
            try:
                if dfn:
                    demo = gateway.get_vpr_domain(str(dfn), domain='patient') or {}
                    # Try common paths
                    def _first_str(*paths):
                        for p in paths:
                            try:
                                v = p(demo)
                                if isinstance(v, str) and v.strip():
                                    return v.strip()
                            except Exception:
                                continue
                        return ''
                    items = ((demo.get('data') or {}).get('items') or [])
                    name = ''
                    if items:
                        it0 = items[0] or {}
                        name = (
                            it0.get('fullName') or it0.get('name') or it0.get('displayName') or
                            (f"{(it0.get('givenNames') or '').strip()} {(it0.get('familyName') or '').strip()}" if (it0.get('givenNames') or it0.get('familyName')) else '')
                        ) or ''
                        dob = it0.get('birthDate') or it0.get('dob') or ''
                    else:
                        name = _first_str(lambda d: d['data']['items'][0]['fullName'])
                        dob = _first_str(lambda d: d['data']['items'][0]['birthDate'])
                    nm = (name or '').strip()
                    if nm and ',' in nm:
                        try:
                            last, first = nm.split(',', 1)
                            nm = f"{first.strip()} {last.strip()}"
                        except Exception:
                            pass
                    # Compute age
                    if dob:
                        from datetime import datetime as _dt
                        try:
                            b = _dt.fromisoformat(str(dob).replace('Z','').replace('T',' ').split(' ')[0]).date()
                            today = _dt.now().date()
                            ag = str(max(0, today.year - b.year - ((today.month, today.day) < (b.month, b.day))))
                        except Exception:
                            ag = ''
            except Exception:
                pass
            # Active problems
            try:
                if dfn:
                    probs = gateway.get_vpr_domain(str(dfn), domain='problems') or {}
                    names = []
                    seen = set()
                    for it in ((probs.get('data') or {}).get('items') or []):
                        status = str(it.get('status') or '').strip().lower()
                        active = (status == 'active') or (status == 'a') or bool(it.get('active'))
                        if not active:
                            continue
                        nm_p = (it.get('problem') or it.get('name') or it.get('desc') or '').strip()
                        if nm_p and nm_p not in seen:
                            seen.add(nm_p)
                            names.append(nm_p)
                        if len(names) >= 12:
                            break
                    probs_line = ', '.join(names) if names else 'none'
            except Exception:
                pass
            # Active medications
            try:
                if dfn:
                    meds = gateway.get_vpr_domain(str(dfn), domain='meds') or {}
                    mnames = []
                    mseen = set()
                    for it in ((meds.get('data') or {}).get('items') or []):
                        status = str(it.get('status') or '').strip().lower()
                        active_flag = (status == 'active') or bool(it.get('active'))
                        if not active_flag:
                            continue
                        label = (it.get('name') or it.get('med') or it.get('product') or it.get('drug') or '').strip()
                        if label and label not in mseen:
                            mseen.add(label)
                            mnames.append(label)
                        if len(mnames) >= 12:
                            break
                    meds_line = ', '.join(mnames) if mnames else 'none'
            except Exception:
                pass

            from datetime import datetime
            now = datetime.now()
            dos_human = now.strftime('%B %d, %Y')
            dos_iso = now.date().isoformat()
            if nm and ag:
                lead = f"{nm} is a {ag} year old Veteran with the following conditions and active medications."
            elif nm:
                lead = f"{nm} is a Veteran with the following conditions and active medications."
            elif ag:
                lead = f"{ag} year old Veteran with the following conditions and active medications."
            else:
                lead = "The patient has the following conditions and active medications."
            probs_line = probs_line or 'none'
            meds_line = meds_line or 'none'
            preface = (
                f"{lead}\n"
                f"Problems (active): {probs_line}\n"
                f"Medications (active): {meds_line}\n"
                f"Today's date of service: {dos_human} ({dos_iso}).\n\n"
            )
        except Exception:
            preface = ''

        # 3b) Compose compact system instruction and final prompt with context excerpts
        try:
            system = (self._prompt_path.read_text(encoding='utf-8')).strip()
        except Exception:
            system = (
                'You are a clinical assistant. Use the provided excerpts to answer succinctly. '
                'Cite each fact with (Excerpt N) matching the excerpt number shown.'
            )
        context_blobs: List[str] = []
        for c in top_chunks:
            pg = c.get('page', '?')
            dt = c.get('date') or ''
            ttl = c.get('title') or ''
            hdr = f"### Source: (Excerpt {pg}{', Date: ' + dt if dt else ''}{', Title: ' + ttl if ttl else ''})"
            context_blobs.append(hdr + "\n" + (c.get('text') or '')[:1600])
        context = "\n\n".join(context_blobs)
        augmented_query = (preface + query) if preface else query
        final_prompt = f"{system}\n\nQuestion: \"{augmented_query}\"\n\nBelow are excerpts from the chart:\n{context}"
        answer_text = llm.chat(final_prompt)

        # 4) Prepare citations list
        citations = []
        for c in top_chunks:
            citations.append({
                'excerpt': c.get('page', '?'),
                'note_id': c.get('note_id'),
                'title': c.get('title'),
                'date': c.get('date'),
                'preview': (c.get('text') or '')[:200]
            })

        return { 'answer': answer_text, 'citations': citations, 'model_id': self.model_id }

# Export symbol for registry
model: QueryModel = DefaultQueryModelImpl()
