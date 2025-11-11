from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
import re
import time
from collections import defaultdict
from . import transforms as T
from ..services.patient_service import PatientService
from ..gateways.data_gateway import DataGateway
from ..gateways.vista_api_x_gateway import VistaApiXGateway

try:
    from ..gateways.factory import get_gateway as _get_active_gateway
except Exception:
    _get_active_gateway = None

# In-memory per-DFN index registry
_REGISTRY: Dict[str, 'DocumentSearchIndex'] = {}

INDEX_TTL_SECONDS = 3 * 60 * 60  # 3 hours per DFN cache lifecycle

_term_split_re = re.compile(r'\w+|"[^"]+"')
_word_re = re.compile(r"[A-Za-z0-9']+")
_stop = set([ 'the','and','of','to','in','a','for','on','with','as','at','by','is','it','or','an','be','are','from','this','that','was','were','but' ])


def _resolve_gateway(gateway: Optional[DataGateway]) -> Optional[DataGateway]:
    if gateway is not None:
        return gateway
    if callable(_get_active_gateway):
        try:
            return _get_active_gateway()
        except Exception:
            return None
    return None


def get_or_build_index_for_dfn(
    dfn: str,
    *,
    gateway: Optional[DataGateway] = None,
    force: bool = False,
) -> 'DocumentSearchIndex':
    key = str(dfn)
    gw = _resolve_gateway(gateway)
    idx = _REGISTRY.get(key)
    if idx is not None:
        if force or idx.is_stale() or (gw is not None and not idx.matches_gateway(gw)):
            idx = None
        else:
            if gw is not None:
                idx.set_gateway(gw)
    if idx is None:
        idx = DocumentSearchIndex(dfn=key, gateway=gw)
        idx.build()
        _REGISTRY[key] = idx
    return idx


class DocumentSearchIndex:
    def __init__(self, dfn: str, gateway: Optional[DataGateway] = None):
        self.dfn = str(dfn)
        self.gateway: Optional[DataGateway] = None
        self.station: Optional[str] = None
        self.duz: Optional[str] = None
        self.ttl_seconds = INDEX_TTL_SECONDS
        self.updated_at: float = 0.0
        self.generation: int = 0
        # postings: term -> list[(doc_id, tf)]
        self.postings: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # doc lengths for normalization
        self.doc_len: Dict[str, int] = defaultdict(int)
        # metadata fields: title/author/type/class per doc
        self.meta: Dict[str, Dict[str, str]] = {}
        # rpc identifiers for TIU fetches: doc_id -> rpc_id/localId
        self.rpc_ids: Dict[str, str] = {}
        # text cache: doc_id -> text (full string)
        self.text: Dict[str, str] = {}
        # document order (for viewer prev/next)
        self.order: List[str] = []
        # sorted vocabulary for fast prefix expansion
        self.vocab_sorted: List[str] = []
        # minimum prefix length to trigger expansion
        self.min_prefix_len: int = 3
        self.set_gateway(gateway)

    def set_gateway(self, gateway: Optional[DataGateway]) -> None:
        if gateway is None:
            return
        self.gateway = gateway
        try:
            sta = getattr(gateway, 'station', None)
            self.station = str(sta) if sta is not None else self.station
        except Exception:
            pass
        try:
            duz = getattr(gateway, 'duz', None)
            self.duz = str(duz) if duz is not None else self.duz
        except Exception:
            pass

    def matches_gateway(self, gateway: Optional[DataGateway]) -> bool:
        if gateway is None:
            return True
        try:
            sta = getattr(gateway, 'station', None)
        except Exception:
            sta = None
        try:
            duz = getattr(gateway, 'duz', None)
        except Exception:
            duz = None
        sta = str(sta) if sta is not None else None
        duz = str(duz) if duz is not None else None
        if sta and self.station and sta != self.station:
            return False
        if duz and self.duz and duz != self.duz:
            return False
        return True

    def is_stale(self) -> bool:
        if not self.updated_at:
            return True
        return (time.time() - self.updated_at) > max(60, self.ttl_seconds)

    def manifest(self) -> Dict[str, Any]:
        return {
            'dfn': self.dfn,
            'documents': len(self.order),
            'has_text': any((txt or '').strip() for txt in self.text.values()),
            'updated_at': self.updated_at,
            'generation': self.generation,
            'station': self.station,
            'duz': self.duz,
        }

    def iter_documents(self) -> List[Tuple[str, Dict[str, str], str]]:
        docs: List[Tuple[str, Dict[str, str], str]] = []
        for doc_id in self.order:
            docs.append((doc_id, dict(self.meta.get(doc_id, {})), self.text.get(doc_id, '')))
        return docs

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
        # Reset state before rebuild to avoid carrying stale structures
        self.postings = defaultdict(lambda: defaultdict(int))
        self.doc_len = defaultdict(int)
        self.meta = {}
        self.rpc_ids = {}
        self.text = {}
        self.order = []
        self.vocab_sorted = []

        gateway = self.gateway or VistaApiXGateway()
        self.set_gateway(gateway)
        svc = PatientService(gateway=gateway)
        params = {'text': '1'}
        try:
            vpr = svc.get_vpr_raw(self.dfn, 'document', params=dict(params))
        except Exception:
            vpr = {}
        try:
            quick = svc.get_documents_quick(self.dfn, params=dict(params))
        except Exception:
            quick = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []
        # Align and extract
        docs: List[Tuple[str, Dict[str, Any], Dict[str, Any] | None]] = []
        for idx, q in enumerate(quick if isinstance(quick, list) else []):
            if not isinstance(q, dict):
                continue
            r = raw_items[idx] if idx < len(raw_items) and isinstance(raw_items[idx], dict) else None
            doc_id = None
            rpc_id = None
            uid = None
            if isinstance(r, dict):
                rpc_id = r.get('id') or r.get('localId') or None
                uid = r.get('uid') or r.get('uidLong') or None
            if isinstance(q, dict) and not uid:
                uid = q.get('uid') or q.get('uidLong') or None
            if rpc_id:
                doc_id = str(rpc_id)
            if uid:
                doc_id = str(uid)
            if not doc_id:
                doc_id = str(idx)
            docs.append((str(doc_id), q, r))
            if rpc_id:
                self.rpc_ids[str(doc_id)] = str(rpc_id)
        # Sort by date desc for consistent order
        docs.sort(key=lambda t: (t[1].get('date') or ''), reverse=True)
        self.order = [d for d,_,_ in docs]
        # Index
        missing_rpc_ids: List[str] = []
        rpc_to_doc: Dict[str, str] = {}
        for doc_id, q, r in docs:
            title = str(q.get('title') or '')
            author = str(q.get('author') or '')
            dtype = str(q.get('documentType') or '')
            dclass = str(q.get('documentClass') or '')
            date = str(q.get('date') or '')
            # national title from quick if present
            nt = str(q.get('nationalTitle') or '')
            full = ''
            if isinstance(r, dict):
                try:
                    txt = self._extract_full_text(r)
                    full = txt or ''
                except Exception:
                    full = ''
            if not full and self.rpc_ids.get(doc_id):
                missing_rpc_ids.append(self.rpc_ids[doc_id])
                rpc_to_doc[self.rpc_ids[doc_id]] = doc_id
            # store
            meta_entry: Dict[str, str] = {
                'title': title,
                'author': author,
                'type': dtype,
                'class': dclass,
                'date': date,
                'nationalTitle': nt,
            }
            if isinstance(r, dict):
                if r.get('uid'):
                    meta_entry['uid'] = str(r.get('uid'))
                if r.get('uidLong'):
                    meta_entry['uidLong'] = str(r.get('uidLong'))
            if self.rpc_ids.get(doc_id):
                meta_entry['rpc_id'] = self.rpc_ids[doc_id]
            self.meta[doc_id] = meta_entry
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
        if missing_rpc_ids:
            try:
                texts_map = svc.get_document_texts(self.dfn, missing_rpc_ids)
            except Exception:
                texts_map = {}
            for rpc_id, lines in (texts_map or {}).items():
                doc_id = rpc_to_doc.get(str(rpc_id))
                if not doc_id:
                    continue
                try:
                    joined = '\n'.join(lines) if isinstance(lines, list) else str(lines)
                except Exception:
                    joined = ''
                if joined.strip():
                    self.text[doc_id] = joined
                    toks = self._tokenize(joined)
                    self.doc_len[doc_id] = len(toks)
                    for t in toks:
                        self.postings[t][doc_id] += 1
        # build sorted vocabulary
        try:
            self.vocab_sorted = sorted(self.postings.keys())
        except Exception:
            self.vocab_sorted = list(self.postings.keys())
        self.updated_at = time.time()
        self.generation += 1

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
