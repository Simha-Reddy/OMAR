from __future__ import annotations
from typing import Any, Dict, List, Set, Tuple
import re
from collections import defaultdict
from . import transforms as T
from ..services.patient_service import PatientService
from ..gateways.vista_api_x_gateway import VistaApiXGateway

# In-memory per-DFN index registry
_REGISTRY: Dict[str, 'DocumentSearchIndex'] = {}

_term_split_re = re.compile(r'\w+|"[^"]+"')
_word_re = re.compile(r"[A-Za-z0-9']+")
_stop = set([ 'the','and','of','to','in','a','for','on','with','as','at','by','is','it','or','an','be','are','from','this','that','was','were','but' ])


def get_or_build_index_for_dfn(dfn: str) -> 'DocumentSearchIndex':
    key = str(dfn)
    idx = _REGISTRY.get(key)
    if idx is None:
        idx = DocumentSearchIndex(dfn=key)
        idx.build()
        _REGISTRY[key] = idx
    return idx


class DocumentSearchIndex:
    def __init__(self, dfn: str):
        self.dfn = str(dfn)
        # postings: term -> list[(doc_id, tf)]
        self.postings: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # doc lengths for normalization
        self.doc_len: Dict[str, int] = defaultdict(int)
        # metadata fields: title/author/type/class per doc
        self.meta: Dict[str, Dict[str, str]] = {}
        # text cache: doc_id -> text (full string)
        self.text: Dict[str, str] = {}
        # document order (for viewer prev/next)
        self.order: List[str] = []
        # sorted vocabulary for fast prefix expansion
        self.vocab_sorted: List[str] = []
        # minimum prefix length to trigger expansion
        self.min_prefix_len: int = 3

    def _tokenize(self, text: str) -> List[str]:
        tokens: List[str] = []
        for m in _word_re.finditer(text.lower()):
            w = m.group(0)
            if w and w not in _stop:
                tokens.append(w)
        return tokens

    def _iter_terms(self, q: str) -> Tuple[List[str], List[str]]:
        # returns (phrases, terms)
        phrases: List[str] = []
        terms: List[str] = []
        for m in _term_split_re.finditer(q):
            s = m.group(0)
            if not s:
                continue
            if s.startswith('"') and s.endswith('"') and len(s) >= 2:
                phr = s[1:-1].strip()
                if phr:
                    phrases.append(phr.lower())
            else:
                for t in self._tokenize(s):
                    terms.append(t)
        return phrases, terms

    def build(self):
        # Build from quick documents + includeText
        svc = PatientService(gateway=VistaApiXGateway())
        vpr = svc.get_vpr_raw(self.dfn, 'document')
        quick = svc.get_documents_quick(self.dfn)
        raw_items = T._get_nested_items(vpr)  # type: ignore
        # Align and extract
        docs: List[Tuple[str, Dict[str, Any], Dict[str, Any] | None]] = []
        for idx, q in enumerate(quick if isinstance(quick, list) else []):
            if not isinstance(q, dict):
                continue
            r = raw_items[idx] if idx < len(raw_items) and isinstance(raw_items[idx], dict) else None
            # doc id from raw or quick (best effort)
            doc_id = None
            if isinstance(r, dict):
                doc_id = r.get('id') or r.get('localId') or r.get('uid')
            if not doc_id:
                # fallback to index-based id
                doc_id = str(idx)
            doc_id = str(doc_id)
            docs.append((doc_id, q, r))
        # Sort by date desc for consistent order
        docs.sort(key=lambda t: (t[1].get('date') or ''), reverse=True)
        self.order = [d for d,_,_ in docs]
        # Index
        for doc_id, q, r in docs:
            title = str(q.get('title') or '')
            author = str(q.get('author') or '')
            dtype = str(q.get('documentType') or '')
            dclass = str(q.get('documentClass') or '')
            date = str(q.get('date') or '')
            full = ''
            if isinstance(r, dict):
                try:
                    txt = self._extract_full_text(r)
                    full = txt or ''
                except Exception:
                    full = ''
            # store
            self.meta[doc_id] = { 'title': title, 'author': author, 'type': dtype, 'class': dclass, 'date': date }
            self.text[doc_id] = full
            # index tokens
            toks = self._tokenize(full)
            self.doc_len[doc_id] = len(toks)
            for t in toks:
                self.postings[t][doc_id] += 1
            # also index metadata with small boosts via term frequency
            for field_val, boost in ((title, 3), (author, 2), (dtype, 2), (dclass, 1)):
                if field_val:
                    for t in self._tokenize(field_val):
                        self.postings[t][doc_id] += boost
        # build sorted vocabulary
        try:
            self.vocab_sorted = sorted(self.postings.keys())
        except Exception:
            self.vocab_sorted = list(self.postings.keys())

    def _extract_full_text(self, raw_item: Dict[str, Any]) -> str | None:
        try:
            # Mirror helper from patient blueprint to reduce import cycles
            txt = raw_item.get('text')
            if isinstance(txt, list) and txt:
                pieces = []
                for block in txt:
                    if isinstance(block, dict):
                        c = block.get('content') or block.get('text') or block.get('summary')
                        if isinstance(c, str) and c.strip():
                            pieces.append(c)
                    elif isinstance(block, str) and block.strip():
                        pieces.append(block)
                if pieces:
                    return "\n".join(pieces)
            rpt = raw_item.get('report') or raw_item.get('impression')
            if isinstance(rpt, str) and rpt.strip():
                return rpt
            for k in ('body','content','documentText','noteText','clinicalText','details'):
                v = raw_item.get(k)
                if isinstance(v, str) and v.strip():
                    return v
            doc = raw_item.get('document')
            if isinstance(doc, dict):
                for k in ('content','text','body'):
                    v = doc.get(k)
                    if isinstance(v, str) and v.strip():
                        return v
        except Exception:
            pass
        return None

    def search(self, q: str, fields: Set[str] | None = None) -> List[Dict[str, Any]]:
        fields = fields or set(['full','title','author','type'])
        phrases, terms = self._iter_terms(q)
        # Collect candidate docs from terms
        candidate_scores: Dict[str, float] = defaultdict(float)
        df: Dict[str, int] = {}
        N = max(1, len(self.doc_len))
        avg_len = max(1.0, self._avg_len())
        for t in terms:
            expanded_terms = self._expand_prefix(t)
            # Use a set to avoid duplicate terms
            seen_terms: Set[str] = set(expanded_terms)
            for et in seen_terms:
                postings = self.postings.get(et) or {}
                df[et] = len(postings)
                if not df[et]:
                    continue
                idf = max(0.0, __import__('math').log((N - df[et] + 0.5) / (df[et] + 0.5) + 1.0))
                for doc_id, tf in postings.items():
                    # Normalize by doc length (BM25-lite style). Treat prefix-expanded terms the same
                    score_inc = (tf / (0.5 + 1.5 * (self.doc_len.get(doc_id, 0) / avg_len))) * idf
                    candidate_scores[doc_id] += score_inc
        # Phrase boosts
        for phr in phrases:
            # Simple contains for now; can be improved with positional index later
            phr_l = phr.lower()
            for doc_id, full in self.text.items():
                if 'full' in fields and full and phr_l in full.lower():
                    candidate_scores[doc_id] += 3.0
            if 'title' in fields:
                for doc_id, m in self.meta.items():
                    if (m.get('title') or '').lower().find(phr_l) != -1:
                        candidate_scores[doc_id] += 2.0
        # Build results
        ordered = sorted(candidate_scores.items(), key=lambda kv: kv[1], reverse=True)
        items: List[Dict[str, Any]] = []
        for doc_id, score in ordered:
            meta = self.meta.get(doc_id, {})
            snip = self._snippet(self.text.get(doc_id, ''), phrases or terms)
            # include light metadata so UI can render meaningful rows without extra calls
            items.append({
                'doc_id': doc_id,
                'score': float(score),
                'snippet': snip,
                'fields_hits': None,
                'title': meta.get('title') or None,
                'author': meta.get('author') or None,
                'type': meta.get('type') or None,
                'class': meta.get('class') or None,
                'date': meta.get('date') or None,
            })
        return items

    def _expand_prefix(self, token: str) -> List[str]:
        """Return a list of vocabulary terms to consider for a query token.
        - If token length >= min_prefix_len, include all vocab terms starting with token (case-insensitive).
        - Always include the exact token if present.
        """
        try:
            s = (token or '').strip().lower()
            if not s:
                return []
            # exact term path
            out: List[str] = []
            if s in self.postings:
                out.append(s)
            if len(s) < self.min_prefix_len or not self.vocab_sorted:
                return out or [s]
            # binary search for prefix range in sorted vocab
            import bisect
            lo = bisect.bisect_left(self.vocab_sorted, s)
            # compute an upper bound string for the prefix (e.g., 'card' -> 'card\uffff')
            hi_prefix = s + "\uffff"
            hi = bisect.bisect_right(self.vocab_sorted, hi_prefix)
            # extend with all matching terms
            for i in range(lo, hi):
                term = self.vocab_sorted[i]
                if term.startswith(s):
                    out.append(term)
                else:
                    break
            # ensure unique and preserve order
            seen: Set[str] = set()
            uniq = []
            for t in out:
                if t not in seen:
                    seen.add(t)
                    uniq.append(t)
            return uniq or [s]
        except Exception:
            return [token]

    def _avg_len(self) -> float:
        if not self.doc_len:
            return 1.0
        return sum(self.doc_len.values()) / max(1, len(self.doc_len))

    def _snippet(self, text: str, cues: List[str], width: int = 180) -> str:
        if not text or not cues:
            return ''
        low = text.lower()
        for c in cues:
            c = c.strip().lower()
            if not c:
                continue
            i = low.find(c)
            if i != -1:
                start = max(0, i - width//2)
                end = min(len(text), i + len(c) + width//2)
                prefix = '...' if start > 0 else ''
                suffix = '...' if end < len(text) else ''
                return prefix + text[start:end].replace('\n',' ') + suffix
        return text[:width] + ('...' if len(text) > width else '')
