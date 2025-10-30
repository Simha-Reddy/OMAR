from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import time
import threading

import numpy as np

from .rag import build_bm25_index, hybrid_search
from .rag import RagEngine  # reuse chunk building from VPR payload
from ...ai_tools import embeddings as emb_api

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

# Singleton store for app
store = RagStore()
