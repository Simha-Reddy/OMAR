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
            # preserve history if existed
            'history': (self._patient_cache.get(str(dfn)) or {}).get('history', []),
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
                # Prefer nationalTitle for tagging; keep local title for display
                title_local = meta.get('title') or ''
                title_nat = meta.get('nationalTitle') or ''
                title = title_local
                date = meta.get('date') or ''
                text_clean = remove_boilerplate_phrases(full)
                chunks = sliding_window_chunk(text_clean, window_size=1600, step_size=800)
                for ch in chunks:
                    ch['title'] = title
                    if title_nat:
                        ch['title_nat'] = title_nat
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
        mode = str(payload.get('mode') or '').strip().lower()
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
                # Precompute tag boosts per chunk if a policy is provided (or summary mode)
                try:
                    from .services.title_tagging import score_for_title, DEFAULT_TAG_POLICY
                    tag_policy = payload.get('tag_policy') or ({**DEFAULT_TAG_POLICY} if mode == 'summary' else None)
                    if tag_policy:
                        for ch in chunks:
                            ttl = ch.get('title_nat') or ch.get('title') or ''
                            try:
                                ch['tag_boost'] = float(score_for_title(ttl, tag_policy))
                            except Exception:
                                ch['tag_boost'] = 0.0
                except Exception:
                    pass
                top_chunks = hybrid_search(query, chunks, vectors=None, bm25_index=bm25, top_k=12)
            else:
                top_chunks = []
        else:
            # Fallback: ad-hoc RAG on provided documents (empty by default)
            vpr_docs = {'data': {'items': []}}
            rag = RagEngine(window_size=1600, step_size=800)
            rag.build_chunks_from_vpr_documents(vpr_docs)
            rag.index()
            top_chunks = rag.retrieve(query, top_k=12)

        # Optional: re-rank by title tags (deprioritize nursing/admin/education for summaries by default)
        try:
            from .services.title_tagging import score_for_title, DEFAULT_TAG_POLICY
            tag_policy = payload.get('tag_policy') or ({**DEFAULT_TAG_POLICY} if mode == 'summary' else None)
            if tag_policy and isinstance(top_chunks, list) and top_chunks:
                # Stable sort by tag score (higher is better), preserving prior ordering on ties
                def _tag_score(ch):
                    ttl = ch.get('title') or ''
                    try:
                        return float(score_for_title(ttl, tag_policy))
                    except Exception:
                        return 0.0
                top_chunks = sorted(top_chunks, key=_tag_score, reverse=True)
        except Exception:
            pass

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
        # Select system prompt: summary mode override, explicit override, else default
        system = ''
        try:
            mode = str(payload.get('mode') or '').strip().lower()
            override = (payload.get('prompt_override') or '').strip()
            template_name = (payload.get('prompt_template') or '').strip() or 'health_summary_prompt.txt'
            if override:
                system = override
            elif mode == 'summary':
                # Load from OMAR_refactor/templates
                from pathlib import Path as _P
                try:
                    templates_dir = _P(__file__).resolve().parents[4] / 'templates'
                    system = (templates_dir / template_name).read_text(encoding='utf-8')
                except Exception:
                    system = ''
            if not system:
                system = (self._prompt_path.read_text(encoding='utf-8')).strip()
        except Exception:
            system = (
                'You are a clinical assistant. Use the provided excerpts to answer succinctly. '
                'Cite each fact with (Excerpt N) matching the excerpt number shown.'
            )
        # Build a stable note -> Excerpt number mapping based on first appearance order
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
        # Include short chat history (prior Q&A) for continuity
        prior_block = ''
        try:
            if dfn:
                entry = self._patient_cache.get(str(dfn)) or {}
                hist = entry.get('history') or []
                if isinstance(hist, list) and hist:
                    lines = ["Prior questions and answers (most recent first):"]
                    for qa in reversed(hist[-4:]):
                        qh = str(qa.get('q') or '').strip()
                        ah = str(qa.get('a') or '').strip()
                        if qh and ah:
                            lines.append(f"Q: {qh}")
                            lines.append(f"A: {ah}")
                            lines.append("")
                    prior_block = "\n".join(lines).strip()
        except Exception:
            prior_block = ''

        augmented_query = (preface + query) if preface else query
        final_prompt = f"{system}\n\nQuestion: \"{augmented_query}\"\n\n{(prior_block + '\n\n') if prior_block else ''}Below are excerpts from the chart:\n{context}"
        answer_text = llm.chat(final_prompt)

        # 4) Prepare citations list
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

        # Persist chat history per DFN and include prior Q&A in future prompts
        try:
            if dfn:
                entry = self._patient_cache.get(str(dfn)) or {}
                hist = entry.get('history') or []
                if isinstance(hist, list):
                    # Simple append; cap to last 10
                    hist.append({'q': query, 'a': answer_text})
                    if len(hist) > 10:
                        hist[:] = hist[-10:]
                else:
                    hist = [{'q': query, 'a': answer_text}]
                entry['history'] = hist
                self._patient_cache[str(dfn)] = { **entry }
        except Exception:
            pass

        return { 'answer': answer_text, 'citations': citations, 'model_id': self.model_id }

    def rag_results(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return early RAG results (notes/excerpts) for the given query. If DFN or index not available, return empty list.
        Response: { results: [ { note_id, title, date, excerpts: [ { page, text } ] } ] }
        """
        query = (payload.get('query') or payload.get('prompt') or '').strip()
        patient = payload.get('patient') or {}
        if not query:
            return { 'results': [] }
        dfn = ''
        try:
            dfn = (patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId') or '').strip()
        except Exception:
            dfn = ''
        if not dfn:
            return { 'results': [] }
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
        if not (chunks and bm25):
            return { 'results': [] }
        top_chunks = hybrid_search(query, chunks, vectors=None, bm25_index=bm25, top_k=12)
        # Group by note
        by_note: Dict[str, Dict[str, Any]] = {}
        for ch in top_chunks:
            nid = str(ch.get('note_id') or '')
            if not nid:
                continue
            rec = by_note.get(nid)
            if not rec:
                rec = { 'note_id': nid, 'title': ch.get('title') or '', 'date': ch.get('date') or '', 'excerpts': [] }
                by_note[nid] = rec
            rec['excerpts'].append({ 'page': ch.get('page') or '?', 'text': (ch.get('text') or '')[:300] })
        # Order by first appearance in top_chunks
        order: List[Dict[str, Any]] = []
        seen = set()
        for ch in top_chunks:
            nid = str(ch.get('note_id') or '')
            if not nid or nid in seen:
                continue
            seen.add(nid)
            if nid in by_note:
                order.append(by_note[nid])
        # Attach stable 1-based index (Excerpt number) for UI and server consistency
        for i, rec in enumerate(order, start=1):
            rec['index'] = i
        return { 'results': order }

    def reset_history(self, dfn: str | None = None):
        try:
            if not dfn:
                return
            key = str(dfn)
            if key in self._patient_cache:
                entry = self._patient_cache.get(key) or {}
                entry['history'] = []
                self._patient_cache[key] = { **entry }
        except Exception:
            pass

# Export symbol for registry
model: QueryModel = DefaultQueryModelImpl()
