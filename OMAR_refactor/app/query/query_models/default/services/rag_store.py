from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Set
import os
import time
import threading

import numpy as np

from .rag import build_bm25_index, hybrid_search
from .rag import RagEngine  # reuse chunk building from VPR payload
from app.ai_tools import embeddings as emb_api

# Very light-weight in-memory patient RAG store.
# - Per-DFN cache with simple TTL and generation counter
# - Lexical-first: always builds BM25; embeddings are optional and can be added later
# - No external deps (FAISS/Sklearn) to keep install minimal

class _PatientIndex:
    def __init__(self, dfn: str):
        self.dfn = dfn
        self.chunks: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None
        self.bm25: Optional[Dict[str, Any]] = None
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at
        self.generation: int = 1
        self.lexical_only: bool = True

    def manifest(self) -> Dict[str, Any]:
        return {
            'dfn': self.dfn,
            'chunks': len(self.chunks or []),
            'has_vectors': bool(self.vectors is not None and getattr(self.vectors, 'shape', (0,))[0] > 0),
            'lexical_only': bool(self.lexical_only),
            'generation': int(self.generation),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

class RagStore:
    def __init__(self, ttl_seconds: int = 3*60*60, capacity: int = 10):
        self._store: Dict[str, _PatientIndex] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._ttl = max(0, int(ttl_seconds))
        self._capacity = max(1, int(capacity))

    def _lock(self, dfn: str) -> threading.Lock:
        if dfn not in self._locks:
            self._locks[dfn] = threading.Lock()
        return self._locks[dfn]

    def _prune(self):
        if self._ttl <= 0:
            return
        now = time.time()
        to_del: List[str] = []
        for k, v in list(self._store.items()):
            if (now - v.updated_at) > self._ttl:
                to_del.append(k)
        for k in to_del:
            try:
                del self._store[k]
            except Exception:
                pass
        # capacity control (LRU-ish by updated_at)
        if len(self._store) > self._capacity:
            victims = sorted(self._store.values(), key=lambda x: x.updated_at)[: max(0, len(self._store)-self._capacity)]
            for v in victims:
                try:
                    del self._store[v.dfn]
                except Exception:
                    pass

    def ensure_index(self, dfn: str, vpr_documents_payload: Any) -> Dict[str, Any]:
        """Build chunks and BM25 for patient if not present. Always returns manifest."""
        self._prune()
        with self._lock(dfn):
            idx = self._store.get(dfn)
            if idx is None:
                idx = _PatientIndex(dfn)
                self._store[dfn] = idx
            # Build chunks (replace fully for now)
            eng = RagEngine(window_size=1600, step_size=800)
            chunks = eng.build_chunks_from_vpr_documents(vpr_documents_payload)
            idx.chunks = chunks
            # BM25
            idx.bm25 = build_bm25_index(idx.chunks)
            # Decide whether to embed now
            idx.vectors = None
            idx.lexical_only = True
            idx.generation += 1
            now = time.time()
            idx.updated_at = now
            return idx.manifest()

    def embed_now(self, dfn: str) -> Dict[str, Any]:
        """Embed existing chunks if Azure OpenAI is configured; no-op otherwise."""
        self._prune()
        with self._lock(dfn):
            idx = self._store.get(dfn)
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
                vecs_list = emb_api.get_embeddings(texts)
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

    def embed_subset(self, dfn: str, note_ids: Set[str]) -> Dict[str, Any]:
        """Embed only chunks whose note_id is in the provided set.
        Creates a zero-vector matrix for others so hybrid search remains aligned.
        No-ops to lexical-only when Azure isn't configured.
        """
        self._prune()
        with self._lock(dfn):
            idx = self._store.get(dfn)
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
                vecs_list = emb_api.get_embeddings(texts)
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

    def embed_docs_policy(self, dfn: str, vpr_documents_payload: Any) -> Dict[str, Any]:
        """Embed per policy:
        - First 100 most recent Progress Notes
        - All Discharge Summaries, Consults, and Radiology documents
        """
        # Build a set of note_ids to embed using raw VPR items
        try:
            items = []
            if isinstance(vpr_documents_payload, dict):
                d = vpr_documents_payload.get('data') or {}
                items = (d.get('items') if isinstance(d, dict) else None) or vpr_documents_payload.get('items') or []
            elif isinstance(vpr_documents_payload, list):
                items = vpr_documents_payload
        except Exception:
            items = []
        def _get_id(it: Dict[str, Any]) -> Optional[str]:
            for k in ('uid','id','localId','uidLong'):
                v = it.get(k)
                if v:
                    return str(v)
            return None
        def _get_doc_class(it: Dict[str, Any]) -> str:
            return str(it.get('documentClass') or '').lower()
        def _get_doc_type(it: Dict[str, Any]) -> str:
            return str(it.get('documentTypeName') or it.get('documentType') or '').lower()
        def _get_date(it: Dict[str, Any]) -> str:
            return str(it.get('referenceDateTime') or it.get('dateTime') or it.get('entered') or '')
        # Collect candidates
        progress: List[Tuple[str, str]] = []  # (date, id)
        others: Set[str] = set()
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            nid = _get_id(it)
            if not nid:
                continue
            dclass = _get_doc_class(it)
            dtype = _get_doc_type(it)
            date = _get_date(it)
            is_progress = ('progress' in dclass) or ('progress' in dtype)
            is_discharge = ('discharge' in dclass) or ('discharge' in dtype)
            is_consult = ('consult' in dclass) or ('consult' in dtype)
            is_radiology = ('radiology' in dclass) or ('radiology' in dtype) or ('imaging' in dclass)
            if is_progress:
                progress.append((date, nid))
            if is_discharge or is_consult or is_radiology:
                others.add(nid)
        # Sort progress by date desc and take top 100
        try:
            progress.sort(key=lambda t: t[0], reverse=True)
        except Exception:
            pass
        top_prog = [nid for _, nid in progress[:100]]
        selection = set(top_prog) | others
        if not selection:
            return self.status(dfn)
        return self.embed_subset(dfn, selection)

    def retrieve(self, dfn: str, query: str, top_k: int = 12) -> List[Dict[str, Any]]:
        self._prune()
        idx = self._store.get(dfn)
        if idx is None or not idx.chunks:
            return []
        return hybrid_search(query, idx.chunks, idx.vectors, bm25_index=idx.bm25, top_k=top_k)

    def status(self, dfn: str) -> Dict[str, Any]:
        self._prune()
        idx = self._store.get(dfn)
        if idx is None:
            return {'dfn': dfn, 'indexed': False}
        m = idx.manifest()
        m['indexed'] = True
        return m

    # --- Ingestion of raw note texts (fallback path) ---
    def ingest_texts(self, dfn: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest a list of note texts into the patient index.
        items: [{ id: str, text: str, date?: str, title?: str }]
        Rebuilds BM25; vectors are left as-is and will be re-embedded on demand.
        """
        self._prune()
        with self._lock(dfn):
            idx = self._store.get(dfn)
            if idx is None:
                idx = _PatientIndex(dfn)
                self._store[dfn] = idx
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


# Singleton store for app
store = RagStore()
