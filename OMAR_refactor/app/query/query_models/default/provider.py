from __future__ import annotations
import json
from typing import Dict, Any, List
from ...contracts import QueryModel
from app.ai_tools import llm
from pathlib import Path
from app.gateways.factory import get_gateway
from .services.rag import (
    RagEngine,
    sliding_window_chunk,
    remove_boilerplate_phrases,
    build_bm25_index,
    hybrid_search,
)
from .services.rag_store import store as rag_store

class DefaultQueryModelImpl:
    model_id = 'default'
    name = 'Default Hey OMAR Model'

    def __init__(self):
        self._prompt_path = Path(__file__).parent / 'PROMPT_answer.md'
        # Simple in-model cache keyed by DFN; avoids global RagStore.
        # Structure: { dfn: { 'chunks': [...], 'bm25': obj, 'vectors': None, 'updated_at': float } }
        self._patient_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 3 * 60 * 60  # 3 hours

    def _trim_ascii(self, text: str, limit: int = 1800) -> str:
        try:
            raw = str(text or '')
        except Exception:
            raw = ''
        try:
            ascii_text = raw.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            ascii_text = raw
        if limit and len(ascii_text) > limit:
            excess = len(ascii_text) - limit
            return ascii_text[:limit] + f"... (truncated {excess} chars)"
        return ascii_text

    def _debug(self, message: str, payload: Any | None = None, limit: int = 1800) -> None:
        try:
            prefix = '[HeyOMAR][DefaultQM] '
            if payload is None:
                print(prefix + str(message))
                return
            if isinstance(payload, str):
                body = self._trim_ascii(payload, limit)
            else:
                try:
                    serialized = json.dumps(payload, ensure_ascii=True, default=str)
                except Exception:
                    serialized = str(payload)
                body = self._trim_ascii(serialized, limit)
            print(prefix + str(message) + ': ' + body)
        except Exception:
            pass

    def _summarize_chunks(self, chunks: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        try:
            for ch in chunks[:limit]:
                preview = self._trim_ascii(ch.get('text') or '', 160)
                entry: Dict[str, Any] = {
                    'note_id': ch.get('note_id'),
                    'title': ch.get('title'),
                    'date': ch.get('date'),
                }
                score = ch.get('score')
                if score is None:
                    score = ch.get('bm25_score')
                if isinstance(score, (int, float)):
                    entry['score'] = round(float(score), 4)
                if preview:
                    entry['preview'] = preview
                summary.append(entry)
        except Exception:
            return []
        return summary

    def _generate_rewrites(self, query: str, tag: str) -> List[str]:
        base = [query]
        try:
            prompt = (
                "Rewrite the following clinical question into 3 to 4 diverse retrieval queries that capture synonyms, abbreviations, and alternative phrasings.\n"
                "Return each on its own line without numbering.\n\nQuestion: " + query
            )
            txt = llm.chat(prompt) or ''
            lines = [s.strip('- ').strip() for s in str(txt).splitlines() if s.strip()]
            uniq: List[str] = []
            seen: set[str] = set()
            for s in lines:
                key = s.lower()
                if key and key not in seen:
                    seen.add(key)
                    uniq.append(s)
                if len(uniq) >= 4:
                    break
            base = [query]
            for s in uniq:
                if s.lower() != query.lower():
                    base.append(s)
        except Exception as err:
            self._debug('answer.rewrite_error', {'tag': tag, 'error': str(err)})
        self._debug('answer.rewrites', {'tag': tag, 'queries': base})
        return base

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

    def _build_chunks_from_document_index(
        self,
        dfn: str,
        *,
        gateway=None,
        doc_index: Any | None = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Bridge DocumentSearchIndex full texts into chunk list."""
        try:
            if doc_index is None:
                from app.services.document_search_service import get_or_build_index_for_dfn
                doc_index = get_or_build_index_for_dfn(str(dfn), gateway=gateway)
        except Exception:
            doc_index = None
        if doc_index is None:
            return []
        try:
            order = list(getattr(doc_index, 'order', []) or [])
            text_map = getattr(doc_index, 'text', {}) or {}
            meta_map = getattr(doc_index, 'meta', {}) or {}
        except Exception:
            return []
        doc_ids: List[str] = order[:limit] if order else list(text_map.keys())[:limit]
        all_chunks: List[Dict[str, Any]] = []
        for doc_id in doc_ids:
            try:
                full = (text_map.get(doc_id) or '').strip()
                if not full:
                    continue
                meta = meta_map.get(doc_id, {}) if isinstance(meta_map, dict) else {}
                title_local = meta.get('title') or ''
                title_nat = meta.get('nationalTitle') or ''
                date = meta.get('date') or ''
                note_id = (
                    meta.get('uid')
                    or meta.get('uidLong')
                    or meta.get('rpc_id')
                    or str(doc_id)
                )
                text_clean = remove_boilerplate_phrases(full)
                chunks = sliding_window_chunk(text_clean, window_size=1600, step_size=800)
                for ch in chunks:
                    ch['title'] = title_local
                    if title_nat:
                        ch['title_nat'] = title_nat
                    ch['date'] = date
                    ch['note_id'] = str(note_id)
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
        structured_sections = (payload.get('structured_sections') or '').strip()
        debug_enabled = bool(payload.get('debug'))
        debug_data: Dict[str, Any] = {}
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
        self._debug('answer.start', {'query': query, 'dfn': dfn, 'station': station, 'mode': mode})
        gateway = get_gateway(station=station, duz=duz)
        top_chunks: List[Dict[str, Any]] = []
        rewrites_used: List[str] = []
        rag_source = 'none'
        if dfn:
            doc_index = None
            try:
                from app.services.document_search_service import get_or_build_index_for_dfn
                doc_index = get_or_build_index_for_dfn(str(dfn), gateway=gateway)
            except Exception:
                doc_index = None

            # Prefer the RagStore path, which supports optional embeddings and the embedding policy (recent 100 progress + all DS/consult/radiology)
            used_rag_store = False
            if doc_index is not None:
                try:
                    manifest = rag_store.ensure_index(str(dfn), doc_index)
                    try:
                        if manifest.get('lexical_only', True):
                            rag_store.embed_docs_policy(str(dfn), doc_index)
                    except Exception:
                        pass
                    if mode != 'summary':
                        rewrites = self._generate_rewrites(query, 'rag_store')
                    else:
                        rewrites = [query]
                        self._debug('answer.rewrites', {'tag': 'rag_store_summary', 'queries': rewrites})
                    rewrites_used = list(rewrites)
                    runs: list[list[Dict[str, Any]]] = []
                    K_PER = 12
                    for rq in rewrites:
                        try:
                            res = rag_store.retrieve(str(dfn), rq, top_k=K_PER)
                            if res:
                                runs.append(res)
                        except Exception:
                            continue
                    if not runs:
                        top_chunks = []
                    elif len(runs) == 1:
                        top_chunks = runs[0][:12]
                    else:
                        k_rrf = 60.0
                        scores: dict[int, float] = {}
                        idx_map: dict[int, Dict[str, Any]] = {}
                        for run in runs:
                            for r, m in enumerate(run, start=1):
                                try:
                                    key = id(m)
                                    if key not in idx_map:
                                        idx_map[key] = m
                                    scores[key] = scores.get(key, 0.0) + 1.0 / (k_rrf + r)
                                except Exception:
                                    continue
                        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
                        fused = [idx_map[k] for k, _ in ordered]
                        top_chunks = fused[:12]
                    used_rag_store = True
                    rag_source = 'rag_store'
                except Exception:
                    used_rag_store = False
            self._debug('answer.rag_store_used', {'enabled': used_rag_store})

            if not used_rag_store:
                # Fallback to in-model cache + keyword-only DocumentSearchIndex
                cached = self._get_cached(str(dfn))
                chunks: List[Dict[str, Any]] = []
                bm25: Dict[str, Any] | None = None
                if cached and (cached.get('chunks')):
                    chunks = list(cached.get('chunks') or [])
                    bm25 = cached.get('bm25')  # type: ignore
                else:
                    chunks = self._build_chunks_from_document_index(str(dfn), gateway=gateway, doc_index=doc_index)
                    bm25 = build_bm25_index(chunks) if chunks else None
                    if chunks and bm25:
                        self._set_cached(str(dfn), chunks, bm25)
                if chunks and bm25:
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
                    if mode != 'summary':
                        rewrites = self._generate_rewrites(query, 'fallback_bm25')
                    else:
                        rewrites = [query]
                        self._debug('answer.rewrites', {'tag': 'fallback_summary', 'queries': rewrites})
                    rewrites_used = list(rewrites)
                    runs: list[list[Dict[str, Any]]] = []
                    K_PER = 12
                    for rq in rewrites:
                        try:
                            res = hybrid_search(rq, chunks, vectors=None, bm25_index=bm25, top_k=K_PER)
                            if res:
                                runs.append(res)
                        except Exception:
                            continue
                    if not runs:
                        top_chunks = []
                    elif len(runs) == 1:
                        top_chunks = runs[0][:12]
                    else:
                        k_rrf = 60.0
                        scores: dict[int, float] = {}
                        idx_map: dict[int, Dict[str, Any]] = {}
                        for run in runs:
                            for r, m in enumerate(run, start=1):
                                try:
                                    key = id(m)
                                    if key not in idx_map:
                                        idx_map[key] = m
                                    scores[key] = scores.get(key, 0.0) + 1.0 / (k_rrf + r)
                                except Exception:
                                    continue
                        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
                        fused = [idx_map[k] for k, _ in ordered]
                        top_chunks = fused[:12]
                else:
                    top_chunks = []
                rag_source = 'fallback_bm25'
            self._debug('answer.rag_results', {'count': len(top_chunks), 'samples': self._summarize_chunks(top_chunks)})
        else:
            # Fallback: ad-hoc RAG on provided documents (empty by default)
            vpr_docs = {'data': {'items': []}}
            rag = RagEngine(window_size=1600, step_size=800)
            rag.build_chunks_from_vpr_documents(vpr_docs)
            rag.index()
            top_chunks = rag.retrieve(query, top_k=12)
            self._debug('answer.rag_results', {'count': len(top_chunks), 'samples': self._summarize_chunks(top_chunks)})
            rewrites_used = [query]
            rag_source = 'adhoc'

        if debug_enabled:
            patient_dfn = ''
            if isinstance(patient, dict):
                try:
                    patient_dfn = str(patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId') or '')
                except Exception:
                    patient_dfn = ''
            debug_data['client'] = {
                'query': query,
                'mode': mode,
                'patient': {'DFN': patient_dfn},
                'station': station,
                'duz': duz,
                'structured_sections_length': len(structured_sections),
                'structured_sections_preview': structured_sections[:800],
            }
            debug_data['rag'] = {
                'source': rag_source,
                'used_rag_store': rag_source == 'rag_store',
                'rewrites': rewrites_used,
                'chunk_count': len(top_chunks),
                'chunks': self._summarize_chunks(top_chunks, limit=12),
            }

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
                # Prefer static/prompts first; fall back to legacy templates/
                from pathlib import Path as _P
                try:
                    root_dir = _P(__file__).resolve().parents[4]
                    prompts_dir = root_dir / 'static' / 'prompts'
                    templates_dir = root_dir / 'templates'
                    # Try static prompts location
                    p1 = prompts_dir / template_name
                    if p1.exists():
                        system = p1.read_text(encoding='utf-8')
                    else:
                        # Fallback to legacy templates
                        p2 = templates_dir / template_name
                        if p2.exists():
                            system = p2.read_text(encoding='utf-8')
                        else:
                            system = ''
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
        # Attach optional structured sections (e.g., DotPhrases expansions) similar to original pipeline
        structured_block = ''
        try:
            if structured_sections:
                structured_block = "\n\nStructured data (requested):\n" + structured_sections
        except Exception:
            structured_block = ''
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
        final_prompt = (
            f"{system}\n\nQuestion: \"{augmented_query}\"\n\n"
            f"{(prior_block + '\n\n') if prior_block else ''}Below are excerpts from the chart:\n{context}"
            f"{structured_block}"
        )
        self._debug('answer.prompt', {'length': len(final_prompt), 'body': self._trim_ascii(final_prompt, 1800)})
        if debug_enabled:
            debug_data['prompt'] = {
                'system_prompt': system,
                'preface': preface,
                'structured_sections': structured_sections,
                'prior_block': prior_block,
                'final_prompt_length': len(final_prompt),
                'final_prompt_preview': self._trim_ascii(final_prompt, 6000),
                'note_order': note_order,
            }
        answer_text = llm.chat(final_prompt)
        self._debug('answer.response', {'length': len(answer_text or ''), 'body': self._trim_ascii(answer_text or '', 1000)})
        if debug_enabled:
            debug_data['llm'] = {
                'response': answer_text,
            }

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
        if debug_enabled:
            debug_data['response'] = {
                'citations': citations,
            }

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

        result = { 'answer': answer_text, 'citations': citations, 'model_id': self.model_id }
        if debug_enabled:
            result['debug'] = debug_data
        return result

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
        # Prefer RagStore retrieval (uses embeddings when available)
        top_chunks: List[Dict[str, Any]] = []
        used_rag_store = False
        doc_index = None
        gw = None
        try:
            sess = payload.get('session') or {}
            station = str(sess.get('station') or '500')
            duz = str(sess.get('duz') or '983')
            gw = get_gateway(station=station, duz=duz)
        except Exception:
            gw = get_gateway()
        try:
            from app.services.document_search_service import get_or_build_index_for_dfn
            doc_index = get_or_build_index_for_dfn(str(dfn), gateway=gw)
        except Exception:
            doc_index = None
        if doc_index is not None:
            try:
                manifest = rag_store.ensure_index(str(dfn), doc_index)
                try:
                    if manifest.get('lexical_only', True):
                        rag_store.embed_docs_policy(str(dfn), doc_index)
                except Exception:
                    pass
                top_chunks = rag_store.retrieve(str(dfn), query, top_k=12) or []
                used_rag_store = True
            except Exception:
                used_rag_store = False

        if not used_rag_store:
            cached = self._get_cached(str(dfn))
            chunks: List[Dict[str, Any]] = []
            bm25: Dict[str, Any] | None = None
            if cached and (cached.get('chunks')):
                chunks = list(cached.get('chunks') or [])
                bm25 = cached.get('bm25')  # type: ignore
            else:
                chunks = self._build_chunks_from_document_index(str(dfn), gateway=gw, doc_index=doc_index)
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
