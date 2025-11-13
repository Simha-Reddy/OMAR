from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Set
import os
import time
import threading

import numpy as np

from .rag import (
    build_bm25_index,
    hybrid_search,
    sliding_window_chunk,
    remove_boilerplate_phrases,
    clean_chunks_remove_duplicates_and_boilerplate,
)
from omar.ai_tools import embeddings as emb_api
from omar.services.document_search_service import DocumentSearchIndex

# Very light-weight in-memory patient RAG store.
# - Per-DFN cache with simple TTL and generation counter
# - Lexical-first: always builds BM25; embeddings are optional and can be added later
# - No external deps (FAISS/Sklearn) to keep install minimal

class _PatientIndex:
    def __init__(self, dfn: str, model: str):
        self.dfn = dfn
        self.model = model
        self.chunks: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None
        self.bm25: Optional[Dict[str, Any]] = None
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at
        self.generation: int = 1
        self.lexical_only: bool = True
        self.source_generation: Optional[int] = None
        self.document_manifest: Dict[str, Any] = {}

    def manifest(self) -> Dict[str, Any]:
        return {
            'dfn': self.dfn,
            'model': self.model,
            'chunks': len(self.chunks or []),
            'has_vectors': bool(self.vectors is not None and getattr(self.vectors, 'shape', (0,))[0] > 0),
            'lexical_only': bool(self.lexical_only),
            'generation': int(self.generation),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'source_generation': self.source_generation,
        }

class RagStore:
    def __init__(self, ttl_seconds: int = 3*60*60, capacity: int = 10):
        self._store: Dict[Tuple[str, str], _PatientIndex] = {}
        self._locks: Dict[Tuple[str, str], threading.Lock] = {}
        self._ttl = max(0, int(ttl_seconds))
        self._capacity = max(1, int(capacity))

    @staticmethod
    def _embed_text_batch(texts: List[str]) -> List[List[float]]:
        batch_size = max(1, int(os.getenv('RAG_EMBED_BATCH_SIZE', '32') or 32))
        max_attempts = max(1, int(os.getenv('RAG_EMBED_MAX_ATTEMPTS', '3') or 3))
        backoff_base = float(os.getenv('RAG_EMBED_BACKOFF_SECONDS', '1.5') or 1.5)
        combined: List[List[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start+batch_size]
            if not batch:
                continue
            attempt = 0
            while True:
                try:
                    combined.extend(emb_api.get_embeddings(batch))
                    break
                except Exception:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    sleep_for = backoff_base * (2 ** (attempt - 1))
                    time.sleep(sleep_for)
        return combined

    def _normalize_model(self, model: str | None) -> str:
        text = (model or 'default').strip()
        return text or 'default'

    def _key(self, dfn: str, model: str | None) -> Tuple[str, str]:
        return (str(dfn), self._normalize_model(model))

    def _lock(self, dfn: str, model: str | None) -> threading.Lock:
        key = self._key(dfn, model)
        if key not in self._locks:
            self._locks[key] = threading.Lock()
        return self._locks[key]

    def _prune(self):
        if self._ttl <= 0:
            return
        now = time.time()
        to_del: List[Tuple[str, str]] = []
        for k, v in list(self._store.items()):
            if (now - v.updated_at) > self._ttl:
                to_del.append(k)
        for k in to_del:
            try:
                del self._store[k]
            except Exception:
                pass
            try:
                del self._locks[k]
            except Exception:
                pass
        # capacity control (LRU-ish by updated_at)
        if len(self._store) > self._capacity:
            victims = sorted(self._store.items(), key=lambda kv: kv[1].updated_at)[: max(0, len(self._store)-self._capacity)]
            for key, _ in victims:
                try:
                    del self._store[key]
                except Exception:
                    pass
                try:
                    del self._locks[key]
                except Exception:
                    pass

    def _chunks_from_document_index(self, doc_index: DocumentSearchIndex) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        try:
            doc_index.ensure_priority_texts()
        except Exception:
            pass
        for doc_id, meta, full_text in doc_index.iter_documents():
            text = (full_text or '').strip()
            if not text:
                continue
            cleaned = remove_boilerplate_phrases(text)
            if not cleaned:
                continue
            window = sliding_window_chunk(cleaned, window_size=1600, step_size=800)
            title = meta.get('title') or ''
            nat = meta.get('nationalTitle') or ''
            date = meta.get('date') or ''
            note_id = (
                meta.get('uid')
                or meta.get('uidLong')
                or meta.get('rpc_id')
                or doc_id
            )
            doc_class = meta.get('class') or ''
            doc_type = meta.get('type') or ''
            for ch in window:
                ch['title'] = title
                if nat:
                    ch['title_nat'] = nat
                ch['date'] = date
                ch['note_id'] = note_id
                ch['source_doc_id'] = doc_id
                if doc_class:
                    ch['documentClass'] = doc_class
                if doc_type:
                    ch['documentType'] = doc_type
            chunks.extend(window)
        return clean_chunks_remove_duplicates_and_boilerplate(chunks)

    def ensure_index(self, dfn: str, doc_index: DocumentSearchIndex, force: bool = False, *, model: str = 'default') -> Dict[str, Any]:
        """Build chunks and BM25 for patient if not present. Always returns manifest."""
        self._prune()
        key = self._key(dfn, model)
        with self._lock(dfn, model):
            idx = self._store.get(key)
            if idx is None:
                idx = _PatientIndex(key[0], key[1])
                self._store[key] = idx
            source_generation = getattr(doc_index, 'generation', None)
            needs_rebuild = force or not idx.chunks or idx.source_generation != source_generation
            if not needs_rebuild and doc_index.is_stale():
                needs_rebuild = True
            if needs_rebuild:
                chunks = self._chunks_from_document_index(doc_index)
                idx.chunks = chunks
                idx.bm25 = build_bm25_index(idx.chunks) if idx.chunks else None
                idx.vectors = None
                idx.lexical_only = True
                idx.generation += 1
                idx.updated_at = time.time()
                idx.source_generation = source_generation
                idx.document_manifest = doc_index.manifest()
            return idx.manifest()

    def embed_now(self, dfn: str, *, model: str = 'default') -> Dict[str, Any]:
        """Embed existing chunks if Azure OpenAI is configured; no-op otherwise."""
        self._prune()
        key = self._key(dfn, model)
        with self._lock(dfn, model):
            idx = self._store.get(key)
            if idx is None or not idx.chunks:
                return {'error': 'patient not indexed'}
            # If no Azure key, keep lexical-only (skip dev placeholder vectors)
            use_azure = bool(os.getenv('AZURE_OPENAI_API_KEY'))
            if not use_azure:
                # remain lexical-only
                idx.vectors = None
                idx.lexical_only = True
                return idx.manifest()
            texts = [c.get('text') or '' for c in idx.chunks]
            try:
                vecs_list = self._embed_text_batch(texts)
                # Heuristic: treat tiny vectors as placeholders
                if vecs_list and len(vecs_list[0]) > 3:
                    idx.vectors = np.array(vecs_list, dtype=np.float32)
                    idx.lexical_only = False
                    idx.generation += 1
                    idx.updated_at = time.time()
            except Exception:
                idx.vectors = None
                idx.lexical_only = True
            return idx.manifest()

    # --- Selective embedding helpers ---

    def embed_subset(self, dfn: str, note_ids: Set[str], *, model: str = 'default') -> Dict[str, Any]:
        """Embed only chunks whose note_id is in the provided set.
        Creates a zero-vector matrix for others so hybrid search remains aligned.
        No-ops to lexical-only when Azure isn't configured.
        """
        self._prune()
        key = self._key(dfn, model)
        with self._lock(dfn, model):
            idx = self._store.get(key)
            if idx is None or not idx.chunks:
                return {'error': 'patient not indexed'}
            use_azure = bool(os.getenv('AZURE_OPENAI_API_KEY'))
            if not use_azure:
                idx.vectors = None
                idx.lexical_only = True
                return idx.manifest()
            # Collect selection
            texts: List[str] = []
            pos: List[int] = []
            for i, ch in enumerate(idx.chunks):
                nid = str(ch.get('note_id') or '')
                if nid and nid in note_ids:
                    texts.append(ch.get('text') or '')
                    pos.append(i)
            if not texts:
                return idx.manifest()
            try:
                vecs_list = self._embed_text_batch(texts)
                if not vecs_list:
                    return idx.manifest()
                import numpy as _np
                D = len(vecs_list[0]) if vecs_list else 0
                if D <= 0:
                    return idx.manifest()
                # Initialize zero-matrix for all chunks; fill selected positions
                V = _np.zeros((len(idx.chunks), D), dtype=_np.float32)
                for j, i in enumerate(pos):
                    if 0 <= i < V.shape[0]:
                        try:
                            V[i, :] = _np.array(vecs_list[j], dtype=_np.float32)
                        except Exception:
                            pass
                idx.vectors = V
                idx.lexical_only = False
                idx.generation += 1
                idx.updated_at = time.time()
            except Exception:
                # Leave vectors unchanged on failure
                pass
            return idx.manifest()

    def embed_docs_policy(self, dfn: str, doc_index: DocumentSearchIndex, *, model: str = 'default') -> Dict[str, Any]:
        """Embed per policy:
        - First 100 most recent Progress Notes
        - All Discharge Summaries, Consults, and Radiology documents
        """
        note_candidates: List[Tuple[str, str, str, str]] = []
        for doc_id, meta, _ in doc_index.iter_documents():
            note_id = (
                meta.get('uid')
                or meta.get('uidLong')
                or meta.get('rpc_id')
                or doc_id
            )
            doc_class = (meta.get('class') or '').lower()
            doc_type = (meta.get('type') or '').lower()
            date = meta.get('date') or ''
            if note_id:
                note_candidates.append((note_id, doc_class, doc_type, date))
        if not note_candidates:
            return self.status(dfn, model=model)
        progress: List[Tuple[str, str]] = []
        others: Set[str] = set()
        for note_id, doc_class, doc_type, date in note_candidates:
            is_progress = ('progress' in doc_class) or ('progress' in doc_type)
            is_discharge = ('discharge' in doc_class) or ('discharge' in doc_type)
            is_consult = ('consult' in doc_class) or ('consult' in doc_type)
            is_radiology = ('radiology' in doc_class) or ('radiology' in doc_type) or ('imaging' in doc_class)
            if is_progress:
                progress.append((date, note_id))
            if is_discharge or is_consult or is_radiology:
                others.add(note_id)
        # Sort progress by date desc and take top 100
        try:
            progress.sort(key=lambda t: t[0], reverse=True)
        except Exception:
            pass
        top_prog = [nid for _, nid in progress[:100]]
        selection = set(top_prog) | others
        if not selection:
            return self.status(dfn, model=model)
        return self.embed_subset(dfn, selection, model=model)

    def retrieve(self, dfn: str, query: str, top_k: int = 12, *, model: str = 'default') -> List[Dict[str, Any]]:
        self._prune()
        idx = self._store.get(self._key(dfn, model))
        if idx is None or not idx.chunks:
            return []
        return hybrid_search(query, idx.chunks, idx.vectors, bm25_index=idx.bm25, top_k=top_k)

    def status(self, dfn: str, *, model: str = 'default') -> Dict[str, Any]:
        self._prune()
        key = self._key(dfn, model)
        idx = self._store.get(key)
        if idx is None:
            return {'dfn': key[0], 'model': key[1], 'indexed': False}
        m = idx.manifest()
        m['indexed'] = True
        return m

    # --- Ingestion of raw note texts (fallback path) ---
    def ingest_texts(self, dfn: str, items: List[Dict[str, Any]], *, model: str = 'default') -> Dict[str, Any]:
        """Ingest a list of note texts into the patient index.
        items: [{ id: str, text: str, date?: str, title?: str }]
        Rebuilds BM25; vectors are left as-is and will be re-embedded on demand.
        """
        self._prune()
        key = self._key(dfn, model)
        with self._lock(dfn, model):
            idx = self._store.get(key)
            if idx is None:
                idx = _PatientIndex(key[0], key[1])
                self._store[key] = idx
            # Build chunks and append
            from .rag import sliding_window_chunk, remove_boilerplate_phrases
            new_chunks: List[Dict[str, Any]] = []
            for it in (items or []):
                try:
                    nid = str(it.get('id') or '')
                    txt = str(it.get('text') or '')
                    if not nid or not txt.strip():
                        continue
                    ttl = str(it.get('title') or '')
                    dt = it.get('date') or ''
                    text_clean = remove_boilerplate_phrases(txt)
                    chunks = sliding_window_chunk(text_clean, window_size=1600, step_size=800)
                    for ch in chunks:
                        ch['title'] = ttl
                        ch['date'] = dt
                        ch['note_id'] = nid
                    new_chunks.extend(chunks)
                except Exception:
                    continue
            if new_chunks:
                # Append and refresh BM25; vectors remain None until embed
                idx.chunks = (idx.chunks or []) + new_chunks
                idx.bm25 = build_bm25_index(idx.chunks)
                idx.vectors = None if idx.vectors is None else idx.vectors
                idx.lexical_only = True
                idx.generation += 1
                idx.updated_at = time.time()
            return idx.manifest()

    def clear(self, dfn: str, *, model: str | None = None) -> None:
        """Remove cached RAG indexes for a patient (optionally scoped to a model)."""
        keys = [k for k in list(self._store.keys()) if k[0] == str(dfn) and (model is None or k[1] == self._normalize_model(model))]
        for key in keys:
            try:
                del self._store[key]
            except Exception:
                pass
            try:
                del self._locks[key]
            except Exception:
                pass


# Singleton store for app
store = RagStore()
