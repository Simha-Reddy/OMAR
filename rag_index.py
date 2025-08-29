import os, time, json, math
from typing import List, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
import numpy as np
from smart_problems_azureembeddings import build_inverted_index, hybrid_search, build_bm25_index, tag_chunk_with_datetime
import re

# ---------------- LRU cache -----------------
class LRUCache:
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self._data: Dict[str, Any] = {}
        self._order: List[str] = []

    def get(self, key: str):
        if key in self._data:
            self._order.remove(key)
            self._order.append(key)
            return self._data[key]
        return None

    def put(self, key: str, value: Any):
        if key in self._data:
            self._order.remove(key)
        elif len(self._data) >= self.capacity:
            oldest = self._order.pop(0)
            # best-effort zero memory for embeddings
            obj = self._data.pop(oldest)
            try:
                emb = obj.get('embeddings')
                if isinstance(emb, np.ndarray):
                    emb[:] = 0
            except Exception:
                pass
        self._data[key] = value
        self._order.append(key)

_INDEX_CACHE = LRUCache(capacity=5)

# Lightweight registry of indexed note IDs per patient (in-memory)
_NOTE_REGISTRY: Dict[str, Set[str]] = {}

def mark_notes_indexed(patient_id: str, doc_ids: List[str]):
    """Record that the given doc_ids are indexed for the patient."""
    if not patient_id:
        return
    s = _NOTE_REGISTRY.get(patient_id)
    if s is None:
        s = set()
        _NOTE_REGISTRY[patient_id] = s
    for d in doc_ids or []:
        if d:
            s.add(str(d))

def get_indexed_notes(patient_id: str, fallback_to_cache: bool = True) -> List[str]:
    """Return list of indexed doc_ids for patient. If registry empty and fallback enabled,
    derive from cached chunks and populate registry.
    """
    if not patient_id:
        return []
    s = _NOTE_REGISTRY.get(patient_id)
    if (not s) and fallback_to_cache:
        cached = _INDEX_CACHE.get(patient_id)
        if cached:
            chunk_list = cached.get('chunks') or []
            derived = {str(ch.get('note_id')) for ch in chunk_list if ch.get('note_id')}
            _NOTE_REGISTRY[patient_id] = set(derived)
            return list(derived)
        return []
    return list(s)

def clear_patient_registry(patient_id: str) -> bool:
    """Clear the note registry for the patient."""
    if not patient_id:
        return False
    try:
        _NOTE_REGISTRY.pop(patient_id, None)
        return True
    except Exception:
        return False

# --------------- Data classes --------------
@dataclass
class PatientIndex:
    patient_id: str
    chunks: List[Dict[str, Any]]
    embeddings: np.ndarray
    manifest: Dict[str, Any]
    backend: str
    faiss_index: Any = None
    nn: Any = None  # sklearn fallback
    inverted_index: Dict[str, set] = field(default_factory=dict)
    bm25_index: Any = None

# --------------- Chunking ------------------

def _split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs separated by one or more blank lines. Preserve inner newlines."""
    # Normalize newlines and strip trailing spaces per line
    text = re.sub(r"\r\n?", "\n", text)
    # Split on two or more newlines (blank line separators)
    parts = re.split(r"\n\s*\n+", text.strip())
    # Remove leading/trailing whitespace of each paragraph but keep internal newlines
    return [p.strip("\n ") for p in parts if p.strip()]

def _split_sentences(paragraph: str) -> List[str]:
    """Naive sentence splitter that tries to avoid common abbreviations and keeps punctuation.
    Clinical notes can be telegraphic; use punctuation and capitalization heuristics.
    """
    if not paragraph:
        return []
    # Common abbreviations that should not end a sentence
    abbr = {
        'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'vs', 'st', 'mt', 'no', 'dept',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
        'e.g', 'i.e', 'etc', 'u.s', 'u.k', 'va', 'pt', 'hx', 'dx', 'sx', 'tx', 'cc', 'hpi', 'ros', 'pmh', 'psh', 'fhx', 'shx'
    }
    sentences: List[str] = []
    buf = []
    i = 0
    n = len(paragraph)
    while i < n:
        ch = paragraph[i]
        buf.append(ch)
        if ch in '.!?':
            # Look back for the token before punctuation
            # Get last word (letters only) before the punctuation
            j = len(buf) - 2
            while j >= 0 and not buf[j].isalnum():
                j -= 1
            k = j
            while k >= 0 and (buf[k].isalnum() or buf[k] in "-'"):
                k -= 1
            token = ''.join(buf[k+1:j+1]).lower()
            is_abbrev = token in abbr or (len(token) == 1)  # single-letter initials
            # Peek next non-space char
            m = i + 1
            while m < n and paragraph[m].isspace():
                m += 1
            next_is_cap_or_eol = (m >= n) or (paragraph[m].isupper() or paragraph[m].isdigit())
            if (not is_abbrev) and next_is_cap_or_eol:
                # End of sentence
                sentences.append(''.join(buf).strip())
                buf = []
        i += 1
    rest = ''.join(buf).strip()
    if rest:
        sentences.append(rest)
    return sentences

def _split_long_sentence(sent: str, max_len: int) -> List[str]:
    """Split a very long sentence into subparts on spaces/commas before max_len."""
    s = sent.strip()
    if len(s) <= max_len:
        return [s]
    parts: List[str] = []
    start = 0
    n = len(s)
    while start < n:
        end = min(start + max_len, n)
        if end < n:
            # try to break at last space or comma before end
            cut = s.rfind(' ', start, end)
            if cut == -1:
                cut = s.rfind(',', start, end)
            if cut == -1 or cut <= start + max_len // 3:
                cut = end
        else:
            cut = end
        parts.append(s[start:cut].strip())
        start = cut
    return [p for p in parts if p]

def _tail_overlap_by_sentences(prev_chunk: str, max_overlap: int) -> str:
    if max_overlap <= 0 or not prev_chunk:
        return ''
    sents = _split_sentences(prev_chunk)
    out: List[str] = []
    total = 0
    # add from the end until reaching max_overlap
    for s in reversed(sents):
        if total + len(s) + (1 if out else 0) > max_overlap and out:
            break
        out.append(s)
        total += len(s) + (1 if out else 0)
    return (' ' .join(reversed(out))).strip()

def simple_chunk_text(text: str, target_chars: int = 1600, overlap: int = 600) -> List[str]:
    """Paragraph- and sentence-aware chunking.
    - Respects blank lines: prefers to keep paragraphs intact.
    - Does not split sentences; splits overly long sentences at spaces/commas.
    - Provides sentence-aligned overlap between adjacent chunks.
    """
    text = (text or '').strip()
    if not text:
        return []
    paragraphs = _split_paragraphs(text)
    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0
    last_chunk_text = ''

    def flush_buffer():
        nonlocal buf, buf_len, last_chunk_text
        if not buf:
            return
        chunk_body = '\n\n'.join(buf).strip()
        if not chunk_body:
            buf = []
            buf_len = 0
            return
        # prepend overlap from previous chunk if any
        ov = _tail_overlap_by_sentences(last_chunk_text, overlap)
        chunk_text = (ov + ('\n\n' if ov else '') + chunk_body).strip()
        chunks.append(chunk_text)
        last_chunk_text = chunk_text
        buf = []
        buf_len = 0

    for para in paragraphs:
        if not para:
            continue
        # If paragraph itself is small, try to add it
        if len(para) <= target_chars:
            projected = buf_len + (2 if buf_len > 0 else 0) + len(para)  # account for \n\n
            if projected <= target_chars:
                buf.append(para)
                buf_len = projected
            else:
                flush_buffer()
                # start new buffer with overlap handled in flush
                buf.append(para)
                buf_len = len(para)
        else:
            # Paragraph too big: split into sentences then pack
            sents = _split_sentences(para)
            # further split very long sentences
            expanded: List[str] = []
            for s in sents:
                expanded.extend(_split_long_sentence(s, max_len=target_chars))
            # pack sentences
            cur_para_buf: List[str] = []
            cur_len = 0
            def flush_para_buf():
                nonlocal cur_para_buf, cur_len
                if cur_para_buf:
                    joined = ' '.join(cur_para_buf).strip()
                    if joined:
                        # treat this as a paragraph unit for the outer buffer
                        nonlocal buf, buf_len
                        if buf_len and (buf_len + 2 + len(joined) > target_chars):
                            flush_buffer()
                        buf.append(joined)
                        buf_len = (len(joined) if not buf_len else buf_len + 2 + len(joined))
                    cur_para_buf = []
                    cur_len = 0
            for s in expanded:
                if s == '':
                    continue
                added = len(s) + (1 if cur_len > 0 else 0)  # space between sentences
                if cur_len + added <= target_chars:
                    cur_para_buf.append(s)
                    cur_len += added
                else:
                    # flush current packed sentences as a paragraph-sized piece
                    flush_para_buf()
                    # If even single sentence > target, place it alone (it has been split above)
                    cur_para_buf.append(s)
                    cur_len = len(s)
            flush_para_buf()

    flush_buffer()
    return [c for c in chunks if c]

def _section_starts_ignored(text: str) -> bool:
    """Return True if the given text begins with one of the ignored section headers.
    We check only the beginning of the chunk (before any blank line) and match case-insensitively
    for robustness. Headers to ignore until a blank line:
      - Common boilerplate or list sections (meds, allergies, immunizations, problems, labs, vitals, imaging)
    """
    if not text:
        return False
    # Normalize newlines and strip leading whitespace
    t = re.sub(r"\r\n?", "\n", text).lstrip()
    # Consider only the first contiguous block up to the first blank line
    first_block = t.split("\n\n", 1)[0]
    fb_lower = first_block.lower()
    # Straight prefix matches
    headers = [
        "full reconciliation",
        "/es/",
        "active problems",
        "problem list",
        "allergies",
        "immunizations",
        "immunization",
        "active inpatient medications",
        "inpatient medications",
        "medications",
        "medication list",
        "vitals",
        "vital signs",
        "laboratory data",
        "labs",
        "imaging",
        "radiology",
    ]
    for h in headers:
        if fb_lower.startswith(h):
            return True
    # Special underline style for Outpatient Medications
    lines = first_block.split("\n")
    if len(lines) >= 2:
        if lines[0].strip().lower().startswith("outpatient medications") and re.fullmatch(r"=+\s*", lines[1].strip() or ""):
            return True
    # Also allow a single-line start match
    if fb_lower.startswith("outpatient medications"):
        return True
    return False

def _detect_section_label(text: str) -> str:
    """Detect common clinical section headers and return a canonical label.
    Returns '' if not detected. Canonical labels:
      - assessment_plan
      - history_present_illness
      - subjective
      - objective
      - hospital_course
    """
    if not text:
        return ''
    t = re.sub(r"\r\n?", "\n", text).lstrip()
    # consider first block (until blank line) and first line
    first_block = t.split("\n\n", 1)[0]
    first_line = (first_block.split("\n", 1)[0] or '').strip().lower()
    # strip trailing ':' or '-' or whitespace
    first_line = re.sub(r"[:\-\s]+$", "", first_line)
    patterns = [
        (r"^(a/p|assessment\s*/\s*plan|assessment\s+and\s+plan|plan|assessment)$", 'assessment_plan'),
        (r"^(hpi|history\s+of\s+present\s+illness|history\s+present\s+illness)$", 'history_present_illness'),
        (r"^(subjective)$", 'subjective'),
        (r"^(objective)$", 'objective'),
        (r"^(hospital\s+course|hospitalization\s+course)$", 'hospital_course'),
    ]
    for pat, label in patterns:
        if re.match(pat, first_line, re.I):
            return label
    return ''

# --------------- Embedding helpers ---------

def embed_texts(client, deploy: str, texts: List[str], batch: int = 256) -> np.ndarray:
    vectors: List[List[float]] = []
    for i in range(0, len(texts), batch):
        batch_texts = texts[i:i+batch]
        resp = client.embeddings.create(model=deploy, input=batch_texts)
        # Azure returns data list preserving order
        for d in resp.data:
            vectors.append(d.embedding)
    arr = np.array(vectors, dtype='float32')
    # normalize in-place for cosine similarity
    norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-8
    arr /= norms
    return arr

# --------------- Ingestion -----------------

def ingest_patient_notes(patient_id: str, notes: List[Dict[str, Any]], client, embed_deploy: str, append: bool = False) -> Dict[str, Any]:
    start_total = time.time()
    timings = {}

    # Normalize notes
    t0 = time.time()
    prepared = []
    for n in notes:
        nid = str(n.get('id') or n.get('note_id') or len(prepared))
        text = (n.get('text') or '').strip()
        note_date = n.get('date')  # may be ISO string from DocumentReference.date
        prepared.append({'id': nid, 'text': text, 'date': note_date})
    timings['normalize'] = time.time() - t0

    # If append, add to existing index
    if append and _INDEX_CACHE.get(patient_id):
        prev = _INDEX_CACHE.get(patient_id)
        prev_chunks = prev['chunks']
        prev_embeddings = prev['embeddings']
        prev_inv = prev.get('inverted', {})
        prev_bm25 = prev.get('bm25')

        # Skip notes already indexed for this patient (idempotent append)
        already = set(get_indexed_notes(patient_id) or [])
        prepared_new = [n for n in prepared if n['id'] not in already]

        # Only add new notes/chunks
        new_chunks = []
        chunk_id = len(prev_chunks)
        for note in prepared_new:
            # Reduce chunk size, moderate overlap
            ctexts = simple_chunk_text(note['text'], target_chars=1200, overlap=350)
            for ct in ctexts:
                ch = {'chunk_id': f'c{chunk_id}', 'note_id': note['id'], 'text': ct, 'skip_semantic': _section_starts_ignored(ct), 'section': _detect_section_label(ct)}
                # Prefer explicit note date if provided
                if note.get('date'):
                    ch['date'] = note.get('date')
                # Try to tag date/time from text when available
                try:
                    dt_tag = tag_chunk_with_datetime({'text': ct})
                    if 'date' in dt_tag and not ch.get('date'):
                        ch['date'] = dt_tag['date']
                    if 'time' in dt_tag:
                        ch['time'] = dt_tag['time']
                except Exception:
                    pass
                new_chunks.append(ch)
                chunk_id += 1
        texts = [c['text'] for c in new_chunks]
        if texts:
            new_embeddings = embed_texts(client, embed_deploy, texts)
            embeddings = np.vstack([prev_embeddings, new_embeddings])
            chunks = prev_chunks + new_chunks
            # Rebuild indexes for simplicity and correctness
            inv = build_inverted_index(chunks)
            bm25 = build_bm25_index(chunks)
            # Update registry with newly added ids
            mark_notes_indexed(patient_id, [n['id'] for n in prepared_new])
        else:
            embeddings = prev_embeddings
            chunks = prev_chunks
            inv = prev_inv
            bm25 = prev_bm25
    else:
        # Chunking (rebuild all if reembed_all)
        t0 = time.time()
        chunks: List[Dict[str, Any]] = []
        chunk_id = 0
        for note in prepared:
            # Reduce chunk size, moderate overlap
            ctexts = simple_chunk_text(note['text'], target_chars=1200, overlap=350)
            for ct in ctexts:
                ch = {
                    'chunk_id': f'c{chunk_id}',
                    'note_id': note['id'],
                    'text': ct,
                    'skip_semantic': _section_starts_ignored(ct),
                    'section': _detect_section_label(ct)
                }
                # Prefer explicit note date if provided
                if note.get('date'):
                    ch['date'] = note.get('date')
                try:
                    dt_tag = tag_chunk_with_datetime({'text': ct})
                    if 'date' in dt_tag and not ch.get('date'):
                        ch['date'] = dt_tag['date']
                    if 'time' in dt_tag:
                        ch['time'] = dt_tag['time']
                except Exception:
                    pass
                chunks.append(ch)
                chunk_id += 1
        timings['chunk'] = time.time() - t0

        # Deduplicate identical chunk text (keep first occurrence)
        t0 = time.time()
        seen = set()
        dedup_chunks = []
        for ch in chunks:
            h = ch['text']
            if h in seen:
                continue
            seen.add(h)
            dedup_chunks.append(ch)
        timings['deduplicate'] = time.time() - t0

        # Embeddings
        t0 = time.time()
        texts = [c['text'] for c in dedup_chunks]
        if texts:
            embeddings = embed_texts(client, embed_deploy, texts)
        else:
            embeddings = np.zeros((0, 1536), dtype='float32')
        timings['embed'] = time.time() - t0
        chunks = dedup_chunks
    # Inverted index
    t0 = time.time()
    inv = build_inverted_index(chunks)
    bm25 = build_bm25_index(chunks)
    timings['invert'] = time.time() - t0

    # Build search index
    t0 = time.time()
    backend = 'none'
    faiss_index = None
    nn = None
    if embeddings.shape[0] > 0:
        try:
            import faiss
            dim = embeddings.shape[1]
            faiss_index = faiss.IndexFlatIP(dim)
            faiss_index.add(embeddings)
            backend = 'faiss'
        except Exception:
            try:
                from sklearn.neighbors import NearestNeighbors
                nn = NearestNeighbors(metric='cosine')
                nn.fit(embeddings)
                backend = 'sklearn'
            except Exception:
                backend = 'numpy'
    timings['index'] = time.time() - t0

    manifest = {
        'patient_id': patient_id,
        'note_count': len(chunks),
        'chunk_count': len(chunks),
        'embedding_dim': int(embeddings.shape[1]) if embeddings.size else 0,
        'backend': backend,
        'updated': time.time(),
        'timings': timings,
        'total_time': time.time() - start_total,
        'version': 1
    }
    _INDEX_CACHE.put(patient_id, {
        'chunks': chunks,
        'embeddings': embeddings,
        'backend': backend,
        'faiss': faiss_index,
        'nn': nn,
        'manifest': manifest,
        'inverted': inv,
        'bm25': bm25,
    })

    # Update registry with indexed note IDs (full rebuild path)
    if not append:
        mark_notes_indexed(patient_id, [n['id'] for n in prepared])

    return manifest

# --------------- Load for query ------------

def _load_index(patient_id: str) -> PatientIndex | None:
    cached = _INDEX_CACHE.get(patient_id)
    if cached:
        c = cached
        return PatientIndex(
            patient_id,
            c['chunks'],
            c['embeddings'],
            c['manifest'],
            c['backend'],
            c.get('faiss'),
            c.get('nn'),
            c.get('inverted', {}),
            c.get('bm25')
        )
    return None

# --------------- Maintenance -------------

def clear_patient_index(patient_id: str) -> bool:
    """Remove a patient's index from the in-memory LRU cache."""
    try:
        # Access internal structures carefully
        cache = _INDEX_CACHE
        if patient_id in cache._data:
            # Zero embeddings to help GC
            try:
                emb = cache._data[patient_id].get('embeddings')
                if hasattr(emb, 'shape'):
                    emb[:] = 0
            except Exception:
                pass
            cache._data.pop(patient_id, None)
            try:
                cache._order.remove(patient_id)
            except ValueError:
                pass
            # Clear registry for the patient
            clear_patient_registry(patient_id)
            return True
        return False
    except Exception:
        return False

def get_patient_manifest(patient_id: str) -> dict | None:
    idx = _load_index(patient_id)
    return idx.manifest if idx else None

# --------------- Query helpers ---------------------

def _best_snippet(text: str, query: str, max_len: int = 140) -> str:
    t = (text or '').strip()
    if not t:
        return ''
    q = (query or '').strip().lower()
    if not q:
        return t[:max_len]
    # Token-based find
    terms = re.findall(r"\b[\w'-]+\b", q)
    # Find earliest occurrence of any term
    idx = -1
    term_len = 0
    lower = t.lower()
    for term in terms:
        j = lower.find(term)
        if j != -1 and (idx == -1 or j < idx):
            idx = j
            term_len = len(term)
    if idx == -1:
        # Fallback to first sentence
        m = re.search(r'[.!?]', t)
        return (t[:m.end()] if m else t)[:max_len]
    # Center window around match
    half = max_len // 2
    start = max(0, idx - half)
    end = min(len(t), idx + term_len + half)
    snippet = t[start:end].strip()
    # Add ellipses if trimmed
    if start > 0:
        snippet = '…' + snippet
    if end < len(t):
        snippet = snippet + '…'
    return snippet[:max_len]

# --------------- Query ---------------------

def query_patient(patient_id: str, query: str, client, embed_deploy: str, top_k: int = 5) -> Dict[str, Any]:
    idx = _load_index(patient_id)
    if not idx:
        return {'error': 'patient not indexed'}
    if idx.embeddings.shape[0] == 0:
        return {'matches': [], 'manifest': idx.manifest}
    # Compute cosine sims directly so we can mask ignored sections
    q_emb = embed_texts(client, embed_deploy, [query], batch=1)[0]
    sims = (idx.embeddings @ q_emb)
    # Mask out chunks marked to skip from semantic-only search
    mask = np.array([0.0 if (c.get('skip_semantic')) else 1.0 for c in idx.chunks], dtype=np.float32)
    sims = sims * mask + (-1e9) * (1 - mask)  # push masked to very low score
    inds = np.argsort(-sims)[:top_k]
    scores = sims[inds].tolist()
    results = []
    for rank, (i, sc) in enumerate(zip(inds, scores)):
        if i >= len(idx.chunks):
            continue
        ch = idx.chunks[i]
        results.append({
            'rank': rank + 1,
            'score': float(sc),
            'chunk_id': ch['chunk_id'],
            'note_id': ch['note_id'],
            'text': ch['text']  # no truncation
        })
    return {'matches': results, 'manifest': idx.manifest}

# --------------- Hybrid query (keyword + semantic) -------------

def hybrid_query_patient(patient_id: str, query: str, client, embed_deploy: str, top_k: int = 8) -> Dict[str, Any]:
    idx = _load_index(patient_id)
    if not idx:
        return {'error': 'patient not indexed'}
    if idx.embeddings.shape[0] == 0:
        return {'matches': [], 'manifest': idx.manifest}
    chunks = idx.chunks
    vectors = idx.embeddings  # already L2-normalized
    inv = idx.inverted_index or {}
    bm25 = getattr(idx, 'bm25_index', None) or getattr(idx, 'bm25_index', None)
    bm25 = bm25 if bm25 is not None else (getattr(idx, 'bm25', None) if hasattr(idx, 'bm25') else None)
    # Fallback to cached dict key if present
    if bm25 is None:
        try:
            bm25 = _INDEX_CACHE.get(patient_id).get('bm25')
        except Exception:
            bm25 = None
    faiss_idx = idx.faiss_index
    # Prepare excluded indices for semantic portion only
    excluded_indices = {i for i, c in enumerate(chunks) if c.get('skip_semantic')}
    # Use hybrid_search with BM25 and diversity cap
    cands = hybrid_search(client, embed_deploy, query, chunks, vectors, inv, top_k=top_k, faiss_index=faiss_idx, normalized_vectors=vectors, semantic_exclude_indices=excluded_indices, bm25_index=bm25, per_note_cap=2)
    # Score with cosine against the normalized embeddings for display
    q = embed_texts(client, embed_deploy, [query], batch=1)[0]
    sims = vectors @ q
    id_to_index = {c['chunk_id']: i for i, c in enumerate(chunks)}
    results = []
    for rank, ch in enumerate(cands, start=1):
        i = id_to_index.get(ch.get('chunk_id'))
        score = float(sims[i]) if i is not None else 0.0
        results.append({
            'rank': rank,
            'score': score,
            'chunk_id': ch.get('chunk_id'),
            'note_id': ch.get('note_id'),
            'text': (ch.get('text') or ''),
            'section': ch.get('section') or '',
            'snippet': _best_snippet(ch.get('text') or '', query),
            'date': ch.get('date')
        })
    return {'matches': results, 'manifest': idx.manifest}
