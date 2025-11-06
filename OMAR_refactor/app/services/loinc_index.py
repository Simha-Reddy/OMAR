import threading
from typing import List, Dict, Tuple, Set, Any

import os

try:
    # Optional: available when called in request context
    from flask import current_app
except Exception:  # pragma: no cover
    current_app = None  # type: ignore


class LoincIndex:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, code_to_name: Dict[str, str], syn_to_codes: Dict[str, Set[str]]):
        self._code_to_name = code_to_name
        self._syn_to_codes = syn_to_codes

    @staticmethod
    def _norm(s: str) -> str:
        return ''.join(ch.lower() if ch.isalnum() else ' ' for ch in (s or '')).strip()

    @classmethod
    def _parse_csv_line(cls, line: str) -> List[str]:
        out: List[str] = []
        cur = ''
        in_q = False
        i = 0
        while i < len(line):
            ch = line[i]
            if in_q:
                if ch == '"':
                    if i + 1 < len(line) and line[i + 1] == '"':
                        cur += '"'
                        i += 1
                    else:
                        in_q = False
                else:
                    cur += ch
            else:
                if ch == '"':
                    in_q = True
                elif ch == ',':
                    out.append(cur)
                    cur = ''
                else:
                    cur += ch
            i += 1
        out.append(cur)
        return out

    @classmethod
    def _default_csv_path(cls) -> str:
        # Prefer Flask static folder if available: <root>/static/lib/LOINC_table.csv
        if current_app is not None:
            folder = getattr(current_app, 'static_folder', None)
            if isinstance(folder, str) and folder:
                return os.path.join(folder, 'lib', 'LOINC_table.csv')
        # Fallback: relative to this file: ../../static/lib/LOINC_table.csv
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, '..', '..', 'static', 'lib', 'LOINC_table.csv'))

    @classmethod
    def load(cls, csv_path: str | None = None) -> 'LoincIndex':
        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            path = csv_path or cls._default_csv_path()
            code_to_name: Dict[str, str] = {}
            syn_to_codes: Dict[str, Set[str]] = {}
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for ln in f:
                        ln = ln.strip('\r\n')
                        if not ln:
                            continue
                        cols = cls._parse_csv_line(ln)
                        if len(cols) < 2:
                            continue
                        code = (cols[0] or '').strip()
                        short_name = (cols[1] or '').strip()
                        syn_col = (cols[3] if len(cols) > 3 else '') or ''
                        if not code:
                            continue
                        if short_name:
                            code_to_name[code] = short_name
                        # Build synonyms: short name + semicolon-separated synonyms (strip bracketed or parenthetical notes)
                        def _clean(s: str) -> str:
                            # crude strip of [..] and (..)
                            import re
                            s2 = re.sub(r'\[[^\]]+\]', '', s or '')
                            s2 = re.sub(r'\([^\)]+\)', '', s2)
                            return s2.strip()

                        syns = [short_name] + [ _clean(x) for x in (syn_col.split(';') if syn_col else []) ]
                        for s in syns:
                            key = cls._norm(s)
                            if not key:
                                continue
                            syn_to_codes.setdefault(key, set()).add(code)
            except Exception:
                # If load fails, leave maps empty
                pass

            cls._instance = LoincIndex(code_to_name, syn_to_codes)
            return cls._instance

    # API
    def resolve_tokens(self, tokens: List[str]) -> Tuple[Set[str], Set[str]]:
        codes: Set[str] = set()
        substrings: Set[str] = set()
        for raw in (tokens or []):
            s = (raw or '').strip()
            if not s:
                continue
            low = s.lower()
            # Direct LOINC code pattern ####-#
            import re
            if re.match(r'^[0-9]+-[0-9]+$', low):
                codes.add(low)
                continue
            key = self._norm(s)
            if key in self._syn_to_codes:
                for c in self._syn_to_codes[key]:
                    codes.add(c.lower())
            if key and len(key) >= 2:
                substrings.add(key)
        return codes, substrings

    def annotate_labs(self, labs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for rec in (labs or []):
            try:
                r = dict(rec)
                if not r.get('loinc'):
                    label = (r.get('test') or r.get('name') or r.get('display') or '').strip()
                    key = self._norm(label)
                    if key and key in self._syn_to_codes:
                        # pick first code
                        code = next(iter(self._syn_to_codes[key]))
                        if code:
                            r['loinc'] = code
                out.append(r)
            except Exception:
                out.append(rec)
        return out
