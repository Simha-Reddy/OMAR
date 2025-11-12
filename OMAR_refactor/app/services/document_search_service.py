from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
import re
import time
from collections import defaultdict
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


def clear_index_for_dfn(dfn: str) -> None:
    """Remove a cached document index for the supplied DFN."""
    key = str(dfn)
    _REGISTRY.pop(key, None)


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
        self.meta: Dict[str, Dict[str, Any]] = {}
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
        # track doc ids whose full text could not be hydrated
        self.missing_text_ids: Set[str] = set()
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
        metadata_rich = any('clinicians' in (m or {}) or 'nationalTitleCode' in (m or {}) for m in self.meta.values())
        return {
            'dfn': self.dfn,
            'documents': len(self.order),
            'has_text': any((txt or '').strip() for txt in self.text.values()),
            'updated_at': self.updated_at,
            'generation': self.generation,
            'station': self.station,
            'duz': self.duz,
            'missing_text': len(self.missing_text_ids),
            'metadata_rich': metadata_rich,
            'text_complete': len(self.missing_text_ids) == 0,
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
        self.missing_text_ids = set()

        gateway = self.gateway or VistaApiXGateway()
        self.set_gateway(gateway)
        try:
            raw_entries = gateway.get_document_index_entries(self.dfn, params={'text': '1'})
        except Exception:
            raw_entries = []
        source_entries = raw_entries if isinstance(raw_entries, list) else []

        normalized_entries: List[Dict[str, Any]] = []
        seen_doc_ids: Set[str] = set()

        for entry in source_entries:
            if not isinstance(entry, dict):
                continue
            doc_id_value = entry.get('doc_id')
            doc_id = str(doc_id_value).strip() if doc_id_value is not None else ''
            if not doc_id:
                quick_candidate = entry.get('quick')
                if isinstance(quick_candidate, dict):
                    for key in ('uid', 'uidLong', 'id', 'localId'):
                        candidate = quick_candidate.get(key)
                        if candidate:
                            doc_id = str(candidate).strip()
                            if doc_id:
                                break
            if not doc_id:
                raw_candidate = entry.get('raw')
                if isinstance(raw_candidate, dict):
                    for key in ('uid', 'uidLong', 'id', 'localId'):
                        candidate = raw_candidate.get(key)
                        if candidate:
                            doc_id = str(candidate).strip()
                            if doc_id:
                                break
            if not doc_id or doc_id in seen_doc_ids:
                continue
            normalized_entries.append({
                'doc_id': doc_id,
                'quick': entry.get('quick'),
                'raw': entry.get('raw'),
                'text': entry.get('text'),
                'rpc_id': entry.get('rpc_id'),
            })
            seen_doc_ids.add(doc_id)

        def _entry_date_value(entry: Dict[str, Any]) -> str:
            date_val = ''
            quick_block = entry.get('quick') if isinstance(entry.get('quick'), dict) else {}
            if isinstance(quick_block, dict):
                raw_date = quick_block.get('date') or quick_block.get('referenceDate')
                if raw_date:
                    date_val = str(raw_date)
            if not date_val:
                raw_block = entry.get('raw') if isinstance(entry.get('raw'), dict) else {}
                if isinstance(raw_block, dict):
                    for key in ('date', 'dateTime', 'referenceDate', 'entered', 'referenceDateTime'):
                        candidate = raw_block.get(key)
                        if candidate:
                            date_val = str(candidate)
                            break
            return date_val

        normalized_entries.sort(key=_entry_date_value, reverse=True)

        documents: Dict[str, Dict[str, Any]] = {}
        doc_sequence: List[str] = []
        hydration_requests: Dict[str, str] = {}
        missing_doc_ids: Set[str] = set()

        for entry in normalized_entries:
            doc_id = entry['doc_id']
            doc_sequence.append(doc_id)

            quick_obj = entry.get('quick')
            quick = quick_obj.copy() if isinstance(quick_obj, dict) else {}
            raw_obj = entry.get('raw')
            raw = raw_obj.copy() if isinstance(raw_obj, dict) else None

            rpc_val = entry.get('rpc_id')
            rpc_id = str(rpc_val).strip() if rpc_val not in (None, '') else None
            if rpc_id:
                self.rpc_ids[doc_id] = rpc_id

            text_val = entry.get('text')
            if isinstance(text_val, list):
                text_str = '\n'.join(str(segment) for segment in text_val if str(segment).strip())
            elif isinstance(text_val, str):
                text_str = text_val
            elif text_val is None:
                text_str = ''
            else:
                text_str = str(text_val)

            if not text_str.strip() and raw:
                try:
                    maybe = self._extract_full_text(raw)
                except Exception:
                    maybe = None
                if maybe:
                    text_str = maybe

            if not text_str.strip():
                missing_doc_ids.add(doc_id)
                if rpc_id:
                    hydration_requests[rpc_id] = doc_id
            else:
                missing_doc_ids.discard(doc_id)

            title = str(quick.get('title') or '')
            author = str(quick.get('author') or '')
            dtype = str(quick.get('documentType') or '')
            dclass = str(quick.get('documentClass') or '')
            date = str(quick.get('date') or quick.get('referenceDate') or '')
            nt = str(quick.get('nationalTitle') or '')

            meta_entry: Dict[str, Any] = {
                'title': title,
                'author': author,
                'type': dtype,
                'class': dclass,
                'date': date,
                'nationalTitle': nt,
            }

            if isinstance(raw, dict):
                if raw.get('uid'):
                    meta_entry['uid'] = str(raw.get('uid'))
                if raw.get('uidLong'):
                    meta_entry['uidLong'] = str(raw.get('uidLong'))
                if raw.get('localTitle'):
                    meta_entry['localTitle'] = str(raw.get('localTitle'))
                elif raw.get('localName'):
                    meta_entry['localTitle'] = str(raw.get('localName'))
                fac_obj = raw.get('facility') if isinstance(raw.get('facility'), dict) else None
                if isinstance(fac_obj, dict):
                    try:
                        fac_name = fac_obj.get('name') or fac_obj.get('displayName') or fac_obj.get('value')
                        if fac_name:
                            meta_entry['facility'] = str(fac_name)
                    except Exception:
                        pass
                elif raw.get('facilityName'):
                    meta_entry['facility'] = str(raw.get('facilityName'))
                nt_obj = raw.get('nationalTitle') if isinstance(raw.get('nationalTitle'), dict) else None
                if isinstance(nt_obj, dict):
                    try:
                        code_val = nt_obj.get('code')
                        name_val = nt_obj.get('name')
                        if code_val:
                            meta_entry['nationalTitleCode'] = str(code_val)
                        if name_val:
                            meta_entry['nationalTitleName'] = str(name_val)
                    except Exception:
                        pass
                for k in ('nationalTitleRole', 'nationalTitleService', 'nationalTitleType', 'nationalTitleSubject'):
                    if not raw.get(k):
                        continue
                    sub = raw.get(k)
                    if isinstance(sub, dict):
                        name_val = sub.get('name') or sub.get('value')
                        if name_val:
                            meta_entry[k] = str(name_val)
                    else:
                        meta_entry[k] = str(sub)
                if raw.get('clinicians'):
                    try:
                        meta_entry['clinicians'] = raw.get('clinicians')
                    except Exception:
                        pass

            if rpc_id:
                meta_entry['rpc_id'] = rpc_id

            documents[doc_id] = {
                'meta': meta_entry,
                'text': text_str,
            }

        if hydration_requests:
            try:
                fallback_map = gateway.get_document_texts(self.dfn, list(hydration_requests.keys()))
            except Exception:
                fallback_map = {}
            for requested_id, lines in (fallback_map or {}).items():
                doc_id = hydration_requests.get(str(requested_id))
                if not doc_id or doc_id not in documents:
                    continue
                if isinstance(lines, list):
                    joined = '\n'.join(str(segment) for segment in lines if str(segment).strip())
                else:
                    joined = str(lines or '')
                if joined.strip():
                    documents[doc_id]['text'] = joined
                    missing_doc_ids.discard(doc_id)

        self.order = doc_sequence

        for doc_id in self.order:
            entry = documents.get(doc_id)
            if not entry:
                continue
            meta_entry = entry.get('meta', {})
            text_value = str(entry.get('text') or '')

            self.meta[doc_id] = dict(meta_entry)
            self.text[doc_id] = text_value

            toks = self._tokenize(text_value)
            self.doc_len[doc_id] = len(toks)
            for token in toks:
                self.postings[token][doc_id] += 1

            title = str(meta_entry.get('title') or '')
            author = str(meta_entry.get('author') or '')
            dtype = str(meta_entry.get('type') or '')
            dclass = str(meta_entry.get('class') or '')
            for field_val, boost in ((title, 3), (author, 2), (dtype, 2), (dclass, 1)):
                if field_val:
                    for token in self._tokenize(field_val):
                        self.postings[token][doc_id] += boost

        self.missing_text_ids = set(missing_doc_ids)
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
