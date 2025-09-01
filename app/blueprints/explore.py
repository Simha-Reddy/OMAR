from flask import Blueprint, render_template, request, jsonify, session, current_app
import uuid
from datetime import datetime
import numpy as np
from smart_problems_azureembeddings import (
    sliding_window_chunk,
    get_embeddings_batched,
    build_inverted_index,
    hybrid_search,
    sentence_density_score,
    get_retrieval_queries,
    ask_gpt,
    build_bm25_index,
)
from module_runner import run_module_by_name
from rag_index import ingest_patient_notes, query_patient, clear_patient_index, get_patient_manifest, hybrid_query_patient, get_indexed_notes
from flask import current_app as app
import math, time
import re
from ..utils import expand_patient_dotphrases, _prepare_lab_filters, _lab_record_matches

bp = Blueprint('explore', __name__, url_prefix='/explore')

# --- In-memory inverted index for whole-note keyword search per patient ---
# Structure: { patient_id: { 'term_to_docs': { term: { doc_id: count } }, 'doc_to_terms': { doc_id: { term: count } }, 'updated_at': float } }
_NOTE_KW_INDEX = {}

def _apply_demo_masking(text):
    """Apply demo masking to text - show only first 2 characters + 6 asterisks for names/dates"""
    if not text or not isinstance(text, str):
        return text
    
    # Mask names (proper case like "John Smith")
    text = re.sub(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    
    # Mask names (all caps with comma like "SMITH,JOHN")
    text = re.sub(r'\b[A-Z]+,[A-Z]+\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    
    # Mask dates (various formats)
    text = re.sub(r'\b\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    text = re.sub(r'\b\d{1,2}\/\d{1,2}\/\d{4}\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    
    return text

@bp.route('')
def explore_home():
    return render_template('explore.html', safe_modules_enabled=current_app.config.get('SAFE_MODULES_ENABLED', False))

@bp.route('/m')
def explore_mobile():
    return render_template('explore_mobile.html', safe_modules_enabled=current_app.config.get('SAFE_MODULES_ENABLED', False))

@bp.route('/process_chart_chunk', methods=['POST'])
def process_chart_chunk():
    data = request.get_json()
    text = data.get('text', '').strip()
    label = data.get('label', '')
    selected_fields = data.get('selected_fields', [])
    timestamp = datetime.now().isoformat()

    if 'chartChunks' not in session:
        session['chartChunks'] = []
    if 'outputs' not in session:
        session['outputs'] = {}

    chunk_obj = {
        'id': str(uuid.uuid4()),
        'label': label,
        'text': text,
        'timestamp': timestamp
    }
    session['chartChunks'].append(chunk_obj)

    if text:
        chunks = sliding_window_chunk(text)
        client = current_app.config.get('OPENAI_CLIENT')
        deploy_embed = current_app.config.get('DEPLOY_EMBED')
        vectors = get_embeddings_batched(client, deploy_embed, [c['text'] for c in chunks])
        inverted_index = build_inverted_index(chunks)
        session['explore_chunks'] = chunks
        session['explore_vectors'] = vectors.tolist()
        session['explore_index'] = {k: list(v) for k, v in inverted_index.items()}
    else:
        chunks = []
        vectors = []
        inverted_index = {}

    client = current_app.config.get('OPENAI_CLIENT')
    deploy_chat = current_app.config.get('DEPLOY_CHAT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')

    for field in selected_fields:
        result = run_module_by_name(
            field, data, chunks, np.array(vectors), {k: set(v) for k, v in inverted_index.items()},
            client, deploy_chat, deploy_embed, hybrid_search
        )
        session['outputs'][field] = result

    response = {'chunks': chunks}
    if len(selected_fields) == 1:
        response[selected_fields[0]] = session['outputs'][selected_fields[0]]
    else:
        response.update(session['outputs'])
    return jsonify(response)

@bp.route('/search', methods=['POST'])
def explore_search():
    data = request.get_json()
    query = data.get('query', '')
    # Expand [[...]] if patient loaded
    try:
        query = expand_patient_dotphrases(query, for_query=True)
    except Exception:
        pass
    qa_history = data.get('qa_history', [])
    all_chunks = session.get('explore_chunks', [])
    vectors = np.array(session.get('explore_vectors', []))
    inverted_index = {k: set(v) for k, v in session.get('explore_index', {}).items()}
    if not all_chunks or not len(vectors):
        return jsonify({'error': 'No chart data loaded.'}), 400

    client = current_app.config.get('OPENAI_CLIENT')
    deploy_chat = current_app.config.get('DEPLOY_CHAT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')

    # Build BM25 once for current chunk set
    bm25 = build_bm25_index(all_chunks)

    queries = get_retrieval_queries(client, deploy_chat, query)
    all_results = []
    for q in queries:
        all_results.extend(hybrid_search(client, deploy_embed, q, all_chunks, vectors, inverted_index, top_k=5, bm25_index=bm25))

    seen = set()
    deduped_chunks = []
    for c in all_results:
        key = (c.get('section', ''), c.get('page', 1), c.get('text', ''))
        if key not in seen:
            deduped_chunks.append(c)
            seen.add(key)

    deduped_chunks.sort(key=sentence_density_score, reverse=True)
    top_chunks = deduped_chunks[:20]

    answer = ask_gpt(client, deploy_chat, top_chunks, query, qa_history=qa_history)
    # Post-process answer for [[...]]
    try:
        answer = expand_patient_dotphrases(answer)
    except Exception:
        pass
    return jsonify({'chunks': all_chunks, 'answer': answer})

@bp.route('/index_notes', methods=['POST'])
def index_notes():
    """Index selected TIU notes (by doc_id) for the current patient into a server-side RAG index.
    Body: { doc_ids: ["..."], append?: bool, skip_if_indexed?: bool }
    Returns: { manifest, count_indexed, results: [{doc_id, status}] }
    """
    data = request.get_json() or {}
    doc_ids = data.get('doc_ids') or []
    append = bool(data.get('append'))
    skip_if_indexed = data.get('skip_if_indexed')
    if skip_if_indexed is None:
        skip_if_indexed = True
    meta = session.get('patient_meta') or {}
    patient_id = meta.get('dfn') or 'unknown'
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    if not isinstance(doc_ids, list) or not doc_ids:
        return jsonify({'error': 'doc_ids must be a non-empty list'}), 400

    # Normalize to strings
    doc_ids = [str(d) for d in doc_ids if d is not None]

    # Build map of DocumentReference dates for these doc_ids from the session bundle
    doc_dates = {}
    try:
        bundle = session.get('patient_record') or {}
        for e in (bundle.get('entry') or []):
            res = (e or {}).get('resource') or {}
            if res.get('resourceType') != 'DocumentReference':
                continue
            did = ((res.get('masterIdentifier') or {}).get('value')) or res.get('id')
            if did:
                doc_dates[str(did)] = res.get('date')
    except Exception:
        doc_dates = {}

    # Determine which to skip based on registry
    existing = set(get_indexed_notes(str(patient_id)) or []) if skip_if_indexed else set()
    to_fetch = []
    results = []
    for did in doc_ids:
        if skip_if_indexed and did in existing:
            results.append({'doc_id': did, 'status': 'Skipped'})
        else:
            to_fetch.append(did)

    # Fetch note texts using the existing batch endpoint in chunks
    texts = []
    CHUNK = 20
    fetched_map = {did: None for did in to_fetch}
    for i in range(0, len(to_fetch), CHUNK):
        part = to_fetch[i:i+CHUNK]
        # Call internal view function to avoid HTTP roundtrip
        with app.test_request_context(json={'doc_ids': part}):
            from .patient import documents_text_batch  # local import to avoid circular at top
            resp = documents_text_batch()
            payload = resp.get_json() if hasattr(resp, 'get_json') else None
        if not payload:
            # Mark all in this part as error if payload missing
            for did in part:
                results.append({'doc_id': did, 'status': 'Error'})
            continue
        for item in (payload.get('notes') or []):
            did = str(item.get('doc_id')) if item.get('doc_id') is not None else None
            if not did:
                continue
            if item.get('error'):
                results.append({'doc_id': did, 'status': 'Error'})
                fetched_map[did] = 'error'
            elif isinstance(item.get('text'), list) and item.get('text'):
                text_blob = '\n'.join(item['text'])
                texts.append({'id': did, 'text': text_blob, 'date': doc_dates.get(did)})
                fetched_map[did] = 'ok'
            else:
                results.append({'doc_id': did, 'status': 'Error'})
                fetched_map[did] = 'error'
    # Any remaining not set in fetched_map were not returned; mark error
    for did, status in fetched_map.items():
        if status is None:
            results.append({'doc_id': did, 'status': 'Error'})

    client = current_app.config.get('OPENAI_CLIENT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')
    if not client or not deploy_embed:
        return jsonify({'error': 'Embeddings client not configured'}), 500

    manifest = None
    if texts:
        manifest = ingest_patient_notes(str(patient_id), texts, client, deploy_embed, append=append)
        # Set status Indexed for those successfully sent to ingestion
        indexed_ids = {t['id'] for t in texts}
        # Update any placeholders for these ids to Indexed if not already present
        # Avoid duplicating entries: only add status if not set yet for that id
        present = {r['doc_id'] for r in results}
        for did in indexed_ids:
            if did not in present:
                results.append({'doc_id': did, 'status': 'Indexed'})
            else:
                # Upgrade any non-error statuses for ingested ids to Indexed
                for r in results:
                    if r['doc_id'] == did and r['status'] != 'Error':
                        r['status'] = 'Indexed'
    # counts
    indexed_count = sum(1 for r in results if r['status'] == 'Indexed')
    skipped_count = sum(1 for r in results if r['status'] == 'Skipped')
    error_count = sum(1 for r in results if r['status'] == 'Error')

    return jsonify({
        'manifest': manifest,
        'requested_count': len(doc_ids),
        'count_indexed': indexed_count,
        'count_skipped': skipped_count,
        'count_error': error_count,
        'results': results
    })

@bp.route('/index_status', methods=['GET'])
def index_status():
    """Return indexed doc_ids for the current patient.
    Response: { indexed_ids: [...], count: number, patient_dfn: string }
    """
    meta = session.get('patient_meta') or {}
    patient_id = meta.get('dfn') or 'unknown'
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    indexed = get_indexed_notes(str(patient_id)) or []
    return jsonify({'indexed_ids': indexed, 'count': len(indexed), 'patient_dfn': str(patient_id)})

@bp.route('/notes_search', methods=['POST'])
def notes_search():
    data = request.get_json() or {}
    query = data.get('query') or ''
    top_k = int(data.get('top_k') or 5)
    meta = session.get('patient_meta') or {}
    patient_id = meta.get('dfn') or 'unknown'
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    client = current_app.config.get('OPENAI_CLIENT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')
    if not client or not deploy_embed:
        return jsonify({'error': 'Embeddings client not configured'}), 500
    # Use hybrid (keyword + semantic) retrieval for notes, consistent with Chart Data
    result = hybrid_query_patient(str(patient_id), query, client, deploy_embed, top_k=top_k)
    return jsonify(result)

@bp.route('/clear_notes_index', methods=['POST'])
def clear_notes_index():
    meta = session.get('patient_meta') or {}
    patient_id = meta.get('dfn') or 'unknown'
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    ok = clear_patient_index(str(patient_id))
    # Also clear per-patient keyword inverted index
    try:
        _NOTE_KW_INDEX.pop(str(patient_id), None)
    except Exception:
        pass
    return jsonify({'cleared': bool(ok), 'patient_id': patient_id})

@bp.route('/notes_qa', methods=['POST'])
def notes_qa():
    """Full RAG -> LLM for notes. Body: { query: str, top_k?: int, qa_history?: [...], demo_mode?: bool }"""
    data = request.get_json() or {}
    query_raw = data.get('query') or ''
    demo_mode = data.get('demo_mode', False)  # Check if demo mode is enabled

    # --- Quick "Show me" natural-language -> dotphrase shortcut ---
    def _parse_last_window_days(text_l: str) -> int | None:
        """
        Parse phrases like "last 6 months", "past 2 weeks", and treat
        "recent/most recent/latest" the same as "last" for numeric/singular windows.
        """
        # handle numeric windows: "last 6 months", "most recent 2 weeks", "latest 14 days"
        m = re.search(r"(?:over\s+)?(?:the\s+)?(?:most\s+recent|latest|recent|last|past)\s+(\d+)\s*(day|days|week|weeks|month|months|year|years)\b", text_l)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit.startswith('day'):
                return max(1, n)
            if unit.startswith('week'):
                return max(1, n*7)
            if unit.startswith('month'):
                return max(1, n*30)
            if unit.startswith('year'):
                return max(1, n*365)
        # singular: "last year", "past month", "recent week", "most recent day", "latest month"
        m2 = re.search(r"(?:over\s+)?(?:the\s+)?(?:most\s+recent|latest|recent|last|past)\s+(year|month|week|day)\b", text_l)
        if m2:
            unit = m2.group(1)
            return 365 if unit=='year' else 30 if unit=='month' else 7 if unit=='week' else 1
        return None

    def _extract_between(text_l: str, start_pat: str, end_pats: list[str]) -> str:
        sidx = re.search(start_pat, text_l)
        if not sidx:
            return text_l
        start = sidx.end()
        end = len(text_l)
        for pat in end_pats:
            m = re.search(pat, text_l[start:])
            if m:
                end = start + m.start()
                break
        return text_l[start:end].strip()

    # --- Helpers for anchor-window behavior ---
    def _parse_dt_safe(iso: str | None):
        try:
            return datetime.fromisoformat(str(iso).replace('Z','')) if iso else None
        except Exception:
            return None

    def _compute_labs_anchor_range(filters: list[str] | None, window_days: int) -> tuple[str, str] | None:
        labs = session.get('fhir_labs') or []
        if not labs:
            return None
        want_codes, want_names = _prepare_lab_filters(filters or [])
        anchor_dt = None
        for r in labs:
            # Respect filters if provided
            if filters and not _lab_record_matches(r, want_codes, want_names):
                continue
            dt_iso = r.get('resulted') or r.get('collected')
            dt = _parse_dt_safe(dt_iso)
            if not dt:
                continue
            if anchor_dt is None or dt > anchor_dt:
                anchor_dt = dt
        if not anchor_dt:
            return None
        start_iso = (anchor_dt.date()).isoformat()
        end_iso = (anchor_dt.date()).isoformat()
        try:
            from datetime import timedelta as _td
            start_iso = (anchor_dt - _td(days=max(0, int(window_days)))).date().isoformat()
            end_iso = (anchor_dt + _td(days=max(0, int(window_days)))).date().isoformat()
        except Exception:
            pass
        return start_iso, end_iso

    def _try_show_me(text: str) -> str | None:
        tl = (text or '').strip()
        tl_l = tl.lower()
        if not tl_l:
            return None
        # trigger if "show me" appears within first 40 chars
        mstart = tl_l.find('show me')
        if mstart < 0 or mstart > 40:
            return None

        # --- common helpers ---
        date_pat = r"(?:\d{4}(?:-\d{2}(?:-\d{2})?)?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4})"
        between = re.search(rf"\b(?:between|from)\s+({date_pat})\s+(?:and|to)\s+({date_pat})", tl_l)
        since = re.search(rf"\bsince\s+({date_pat})", tl_l)
        days = _parse_last_window_days(tl_l)
        # Interpret "today" or "from today" as a 1-day window when no explicit range provided
        if (not between) and (not since) and (days is None):
            if re.search(r"\bfrom\s+today\b", tl_l) or re.search(r"\btoday(?:'s)?\b", tl_l):
                days = 1
        # recency mention without explicit numeric or range -> anchor behavior
        recency_mention = (bool(re.search(r"\b(most\s+recent|latest|recent|last)\b", tl_l)) and not between and not since and days is None)
        anchor_window_days = int(current_app.config.get('ANCHOR_WINDOW_DAYS', 7) or 7)

        def add_range(dp: str) -> str:
            if between:
                a, b = between.group(1), between.group(2)
                return f"{dp}/start={a}/end={b}]]"
            if since:
                a = since.group(1)
                return f"{dp}/since={a}]]"
            if days:
                return f"{dp}/{days}]]"
            return f"{dp}]]"

        dp_parts: list[str] = []
        added: set[str] = set()

        # Map problem synonyms: "problem list" and "past medical history" => problems
        has_problems_syn = bool(re.search(r"\b(problem\s*list|problems?|past\s+medical\s+history)\b", tl_l))

        # 1) Explicit entities: vitals, meds, problems, allergies (single-intent fast paths)
        # Keep these as early returns when they are the sole intent
        if all(kw not in tl_l for kw in [' and ', ' & ', ',']) and (
            'vitals' in tl_l or 'medications' in tl_l or 'meds' in tl_l or has_problems_syn or 'allergies' in tl_l
        ):
            if 'vitals' in tl_l:
                base = '[[vitals'
                return add_range(base)
            if 'medications' in tl_l or 'meds' in tl_l:
                base = '[[meds'
                if re.search(r"\bactive\b", tl_l):
                    base += '/active'
                return add_range(base)
            if has_problems_syn:
                if re.search(r"\bactive\b", tl_l):
                    return '[[problems/active]]'
                return '[[problems]]'
            if 'allergies' in tl_l or 'allergy' in tl_l:
                return '[[allergies]]'

        # 2) Orders expressions (treated as one block)
        if re.search(r"\border(s)?\b", tl_l):
            base = '[[orders'
            otype = ''
            if re.search(r"\b(meds?|medications|pharmacy|rx)\b", tl_l):
                otype = '/meds'
            elif re.search(r"\b(labs?|laborator(?:y|ies))\b", tl_l):
                otype = '/labs'
            status_word = None
            for s in ['active','pending','current','all','signed','complete','completed','new','unsigned']:
                if re.search(rf"\b{s}\b", tl_l):
                    status_word = s
                    break
            dp = base + otype
            if status_word:
                dp += f"/status={status_word}"
            dp_parts.append(add_range(dp)[:-2] + ']]')
            added.add('orders')

        # 3) Labs-focused patterns (extract filters like creatinine, a1c, etc.)
        labs_seg = _extract_between(
            tl_l,
            r"show\s+me\s+",
            [
                r"\bover\s+the\s+last\b", r"\bfor\s+the\s+last\b", r"\bin\s+the\s+last\b",
                r"\bpast\b", r"\bsince\b", r"\bbetween\b", r"\bfrom\b",
                r"\band\s+when\b"
            ]
        )
        labs_seg = re.sub(r"\b(his|her|their|the|latest|most\s+recent|last|recent|labs?)\b", " ", labs_seg).strip()
        labs_list = [s.strip() for part in re.split(r"[,;&]", labs_seg) for s in re.split(r"\band\b", part) if s.strip()]
        if labs_list:
            filt = ','.join(labs_list)
            # If recency mention without explicit window/range -> anchor to most recent matching lab
            if recency_mention and not between and not since and days is None:
                anchor = _compute_labs_anchor_range(labs_list, anchor_window_days)
                if anchor:
                    a, b = anchor
                    dp_parts.append(f"[[labs/{filt}/start={a}/end={b}]]")
                else:
                    dp_parts.append(f"[[labs/{filt}]]")
            else:
                if re.search(r"\b(creatinine|a1c|ldl|hdl|cholesterol|triglycerides|egfr|uacr|microalbumin|scr|bun|potassium|sodium|hemoglobin|platelet|wbc)\b", filt):
                    if between:
                        a, b = between.group(1), between.group(2)
                        dp_parts.append(f"[[labs/{filt}/start={a}/end={b}]]")
                    elif since:
                        a = since.group(1)
                        dp_parts.append(f"[[labs/{filt}/since={a}]]")
                    elif days:
                        dp_parts.append(f"[[labs/{filt}/{days}]]")
                    else:
                        dp_parts.append(f"[[labs/{filt}]]")
            added.add('labs')
        # If user said "labs" generically and we haven't added a labs block yet, add it with range or anchor
        if ('labs' in tl_l or 'laboratory' in tl_l) and ('labs' not in added):
            if recency_mention and not between and not since and days is None:
                anchor = _compute_labs_anchor_range(None, anchor_window_days)
                if anchor:
                    a, b = anchor
                    dp_parts.append(f"[[labs/start={a}/end={b}]]")
                else:
                    dp_parts.append(add_range('[[labs'))
            else:
                dp_parts.append(add_range('[[labs'))
            added.add('labs')

        # 4) Medication started pattern (can coexist with labs)
        m_started = re.search(r"\bwhen\s+(?:did\s+)?(?:he|she|they)\s+(?:start|started)\s+([a-z0-9\-\s]+)", tl_l)
        if not m_started:
            m_started = re.search(r"\b(?:he|she|they)\s+(?:started|start(?:ed)?)\s+([a-z0-9\-\s]+)", tl_l)
        if m_started:
            med = m_started.group(1).strip(" .!?\t\r\n")
            med = re.sub(r"^(his|her|their|the)\s+", "", med)
            if med:
                dp_parts.append(f"[[medstarted/{med}]]")
                added.add('medstarted')

        # 5) Generic entity mentions to combine: vitals, meds, problems, allergies
        if 'vitals' in tl_l and 'vitals' not in added:
            dp_parts.append(add_range('[[vitals'))
            added.add('vitals')
        if (('medications' in tl_l) or ('meds' in tl_l)) and 'meds' not in added:
            base = '[[meds'
            if re.search(r"\bactive\b", tl_l):
                base += '/active'
            dp_parts.append(add_range(base))
            added.add('meds')
        if has_problems_syn and 'problems' not in added:
            if re.search(r"\bactive\b", tl_l):
                dp_parts.append('[[problems/active]]')
            else:
                dp_parts.append('[[problems]]')
            added.add('problems')
        if ('allergies' in tl_l or 'allergy' in tl_l) and 'allergies' not in added:
            dp_parts.append('[[allergies]]')
            added.add('allergies')

        # 6) Simple demographics/contact can be combined
        if re.search(r"\bname\b", tl_l):
            dp_parts.append("[[name]]")
        if re.search(r"\bage\b", tl_l):
            dp_parts.append("[[age]]")
        if re.search(r"\b(dob|date\s+of\s+birth)\b", tl_l):
            dp_parts.append("[[dob]]")
        if re.search(r"\b(phone|phone\s+number|mobile|cell)\b", tl_l):
            dp_parts.append("[[phone]]")

        if dp_parts:
            return "\n".join(dp_parts)
        return None

    show_me_dp = _try_show_me(query_raw)
    if show_me_dp:
        # Build labeled sections for each dotphrase line
        try:
            lines = [l.strip() for l in show_me_dp.splitlines() if l.strip()]
            sections = []
            def title_for(dp: str) -> str:
                s = dp.strip()
                low = s.lower()
                # Range phrase
                range_txt = ''
                m_start_end = re.search(r"/start=([^/\]]+)/end=([^/\]]+)", low)
                m_since = re.search(r"/since=([^/\]]+)", low)
                m_days = re.search(r"/(\d+)\]\]$", low)
                if m_start_end:
                    a, b = m_start_end.group(1), m_start_end.group(2)
                    range_txt = f"between {a} and {b}"
                elif m_since:
                    range_txt = f"since {m_since.group(1)}"
                elif m_days:
                    range_txt = f"over last {m_days.group(1)} days"
                # Entity-specific
                if low.startswith('[[labs'):
                    # Extract filters if present
                    filt = ''
                    m_f = re.search(r"\[\[labs/([^/\]]+)", s, flags=re.IGNORECASE)
                    if m_f:
                        filt = m_f.group(1)
                        # Normalize list "a1c,creatinine" -> "A1c, Creatinine"
                        parts = [p.strip() for p in re.split(r"[,;+]", filt) if p.strip()]
                        if parts:
                            filt = ', '.join([p.strip().capitalize() for p in parts])
                    title = filt if filt else 'Labs'
                    return f"{title} {range_txt}".strip()
                if low.startswith('[[vitals'):
                    return f"Vitals {range_txt}".strip()
                if low.startswith('[[meds'):
                    active = '/active' in low
                    base = 'Active medications' if active else 'Medications'
                    return f"{base} {range_txt}".strip()
                if low.startswith('[[problems'):
                    active = '/active' in low
                    return 'Active problem list' if active else 'Problem list'
                if low.startswith('[[allergies'):
                    return 'Allergies'
                if low.startswith('[[orders'):
                    otype = 'Orders'
                    if '/meds' in low:
                        otype = 'Medication orders'
                    elif '/labs' in low:
                        otype = 'Lab orders'
                    m_status = re.search(r"/status=([a-z]+)", low)
                    status = f" ({m_status.group(1)})" if m_status else ''
                    return f"{otype}{status} {range_txt}".strip()
                if low.startswith('[[medstarted'):
                    m = re.search(r"\[\[medstarted/([^\]]+)\]\]", s, flags=re.IGNORECASE)
                    drug = m.group(1).strip() if m else ''
                    return f"Medication start date: {drug}".strip()
                if low.startswith('[[age'):
                    return 'Age'
                if low.startswith('[[dob'):
                    return 'Date of birth'
                if low.startswith('[[name'):
                    return 'Name'
                if low.startswith('[[phone'):
                    return 'Phone'
                return 'Results'

            for dp in lines:
                try:
                    content = expand_patient_dotphrases(dp)
                except Exception:
                    content = dp
                title = title_for(dp)
                underline = '=' * len(title)
                sections.append(f"{title}\n{underline}\n{content}")
            answer_sm = "\n\n".join(sections)
        except Exception:
            # Fallback to plain expansion
            try:
                answer_sm = expand_patient_dotphrases(show_me_dp)
            except Exception:
                answer_sm = show_me_dp
        return jsonify({'matches': [], 'answer': answer_sm, 'show_me': True, 'dotphrase': show_me_dp})

    # --- Normal QA flow ---
    # Expand [[...]] in user query if patient selected
    try:
        query = expand_patient_dotphrases(query_raw, for_query=True)
    except Exception:
        query = query_raw

    top_k = int(data.get('top_k') or 8)
    qa_history = data.get('qa_history') or []
    meta = session.get('patient_meta') or {}
    patient_id = meta.get('dfn') or 'unknown'
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    client = current_app.config.get('OPENAI_CLIENT')
    deploy_chat = current_app.config.get('DEPLOY_CHAT')
    deploy_embed = current_app.config.get('DEPLOY_EMBED')
    if not client or not deploy_embed or not deploy_chat:
        return jsonify({'error': 'LLM/embedding client not configured'}), 500

    # Multi-query rewrites for better recall (based on user's question, not augmented context)
    rewrites = get_retrieval_queries(client, deploy_chat, query)

    # Retrieve per rewrite using hybrid index and fuse via Reciprocal Rank Fusion (RRF)
    K_PER = max(6, top_k)
    runs = []
    for q in rewrites:
        res = hybrid_query_patient(str(patient_id), q, client, deploy_embed, top_k=K_PER)
        matches = res.get('matches') if isinstance(res, dict) else None
        if matches:
            runs.append(matches)
    # If no runs gathered, fallback to single query
    if not runs:
        res = hybrid_query_patient(str(patient_id), query, client, deploy_embed, top_k=top_k)
        if res.get('error'):
            return jsonify(res), 400
        base_matches = res.get('matches') or []
    else:
        # RRF fusion
        k_rrf = 60.0
        scores = {}
        items = {}
        for run in runs:
            for r, m in enumerate(run, start=1):
                cid = m.get('chunk_id')
                if not cid:
                    continue
                items[cid] = m
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_rrf + r)
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        base_matches = [items[cid] for cid, _ in ordered[:top_k]]

    # Enrich matches with page numbers and a default section label for UI linking
    matches = []
    for i, m in enumerate(base_matches, start=1):
        mm = dict(m)
        mm['page'] = i
        if not mm.get('section'):
            mm['section'] = f"Note {mm.get('note_id', '')}"
        # make sure date is carried forward
        if m.get('date') and not mm.get('date'):
            mm['date'] = m.get('date')
        matches.append(mm)

    top_chunks = []
    for m in matches:
        top_chunks.append({
            'text': m.get('text') or '',
            'page': m.get('page'),
            'section': m.get('section'),
            'note_id': m.get('note_id'),
            'date': m.get('date')  # include date for LLM context
        })

    # Build augmented prompt with demographics, active problems/meds, and today's date of service
    try:
        now = datetime.now()
        dos_human = now.strftime('%B %d, %Y')
        dos_iso = now.date().isoformat()
        preface = (
            "[[name]] is a [[age]] year old Veteran with the following conditions and active medications.\n"
            "Problems (active): [[problems/active]]\n"
            "Medications (active): [[meds/active]]\n"
            f"Today's date of service: {dos_human} ({dos_iso}).\n\n"
        )
        augmented_template = preface + query
        augmented_query = expand_patient_dotphrases(augmented_template, for_query=True)
    except Exception:
        # Fallback to original query if expansion or date formatting fails
        augmented_query = query

    answer = ask_gpt(client, deploy_chat, top_chunks, augmented_query, qa_history=qa_history)
    # Post-process LLM answer to expand [[...]]
    try:
        answer = expand_patient_dotphrases(answer)
    except Exception:
        pass
    
    # Apply demo masking if requested
    if demo_mode:
        answer = _apply_demo_masking(answer)
        
    print("[NOTES QA RESPONSE]", {
        'answer': answer,
        'matches': top_chunks,
        'query': augmented_query,
        'rewrites': rewrites
    })
    return jsonify({'matches': matches, 'answer': answer})

# === Keyword inverted index endpoints for whole-note search ===

def _norm_token(tok: str) -> str:
    if not tok:
        return ''
    # Keep letters and digits; lowercase
    return re.sub(r'[^A-Za-z0-9]+', '', str(tok)).lower()


def _tokenize_counts(text: str) -> dict:
    """Return a dict of token -> count for the given text."""
    if not text:
        return {}
    counts = {}
    # Split on non-alphanumerics, count tokens length >= 2
    for raw in re.split(r'[^A-Za-z0-9]+', text):
        tok = _norm_token(raw)
        if not tok or len(tok) < 2:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    return counts


@bp.route('/index_keyword_batch', methods=['POST'])
def index_keyword_batch():
    """Update per-patient inverted index for a batch of document ids.
    Body: { doc_ids: [str] }
    Response: { indexed: [doc_id], skipped: [doc_id] }
    """
    data = request.get_json() or {}
    doc_ids = [str(d) for d in (data.get('doc_ids') or []) if d is not None]
    meta = session.get('patient_meta') or {}
    patient_id = str(meta.get('dfn') or 'unknown')
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    if not doc_ids:
        return jsonify({'indexed': [], 'skipped': []})

    store = _NOTE_KW_INDEX.setdefault(patient_id, {'term_to_docs': {}, 'doc_to_terms': {}, 'updated_at': 0.0})
    term_to_docs = store['term_to_docs']
    doc_to_terms = store['doc_to_terms']

    # Fetch missing texts via internal batch endpoint
    CHUNK = 24
    indexed = []
    for i in range(0, len(doc_ids), CHUNK):
        part = doc_ids[i:i+CHUNK]
        with app.test_request_context(json={'doc_ids': part}):
            from .patient import documents_text_batch
            resp = documents_text_batch()
            payload = resp.get_json() if hasattr(resp, 'get_json') else None
        items = (payload.get('notes') or []) if payload else []
        for it in items:
            did = str(it.get('doc_id') or '')
            if not did:
                continue
            if isinstance(it.get('text'), list) and it.get('text'):
                blob = '\n'.join(it['text'])
            else:
                blob = ''
            # Remove previous postings for this doc
            prev = doc_to_terms.get(did) or {}
            if prev:
                for t in list(prev.keys()):
                    td = term_to_docs.get(t)
                    if td and did in td:
                        del td[did]
                        if not td:
                            term_to_docs.pop(t, None)
            # Recompute counts and update postings
            counts = _tokenize_counts(blob)
            doc_to_terms[did] = counts
            for t, c in counts.items():
                td = term_to_docs.setdefault(t, {})
                td[did] = int(c)
            indexed.append(did)
    store['updated_at'] = time.time()
    return jsonify({'indexed': indexed, 'skipped': []})


@bp.route('/notes_keyword_counts', methods=['POST'])
def notes_keyword_counts():
    """Return keyword hit counts for a set of doc_ids for the current patient.
    Body: { keyword: str, doc_ids: [str] }
    Response: { scores: [{ doc_id, count }] }
    """
    data = request.get_json() or {}
    raw_kw = (data.get('keyword') or '').strip()
    doc_ids = [str(d) for d in (data.get('doc_ids') or []) if d is not None]
    meta = session.get('patient_meta') or {}
    patient_id = str(meta.get('dfn') or 'unknown')
    
    if not patient_id:
        return jsonify({'error': 'No patient selected'}), 400
    
    if not doc_ids:
        return jsonify({'scores': []})
    
    term = _norm_token(raw_kw)
    if not term:
        return jsonify({'scores': [{'doc_id': did, 'count': 0} for did in doc_ids]})
    store = _NOTE_KW_INDEX.get(patient_id) or {'term_to_docs': {}, 'doc_to_terms': {}}
    term_to_docs = store.get('term_to_docs') or {}
    postings = term_to_docs.get(term) or {}
    out = []
    for did in doc_ids:
        out.append({'doc_id': did, 'count': int(postings.get(did, 0) or 0)})
    return jsonify({'scores': out})


def _apply_demo_masking(text):
    """Apply demo masking to text - show only first 2 characters + 6 asterisks for names/dates"""
    if not text or not isinstance(text, str):
        return text
    
    # Mask names (proper case like "John Smith")
    text = re.sub(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    
    # Mask names (all caps with comma like "SMITH,JOHN")
    text = re.sub(r'\b[A-Z]+,[A-Z]+\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    
    # Mask dates (various formats)
    text = re.sub(r'\b\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    text = re.sub(r'\b\d{1,2}\/\d{1,2}\/\d{4}\b', 
                  lambda m: m.group(0)[:2] + '******' if len(m.group(0)) > 2 else m.group(0), text)
    
    return text
