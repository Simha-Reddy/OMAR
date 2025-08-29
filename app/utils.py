import os, sys
from flask import current_app, session
import re
import datetime as _dt
import calendar
import csv
from functools import lru_cache
import threading

def get_resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS  # type: ignore
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    # go one level up (app/ -> project root) for existing relative paths
    return os.path.join(os.path.dirname(base_path), relative_path)

def ask_openai(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
    client = current_app.config.get('OPENAI_CLIENT')
    deploy_chat = current_app.config.get('DEPLOY_CHAT')
    if not client or not deploy_chat:
        return "OpenAI client not configured"
    try:
        resp = client.chat.completions.create(
            model=deploy_chat,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=temperature
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

def _fmt_date_human(iso: str | None) -> str:
    if not iso:
        return ''
    try:
        d = _dt.datetime.fromisoformat(str(iso).replace('Z',''))
    except Exception:
        return str(iso)
    try:
        return d.strftime('%b %d, %Y')
    except Exception:
        return str(iso)

def _days_ago_cutoff(days: int) -> _dt.datetime:
    now = _dt.datetime.now()
    return now - _dt.timedelta(days=max(0, int(days)))

def _phone_pretty(num: str | None) -> str:
    s = ''.join(ch for ch in str(num or '') if ch.isdigit())
    if len(s) == 11 and s.startswith('1'):
        s = s[1:]
    if len(s) == 10:
        return f"({s[0:3]}) {s[3:6]}-{s[6:]}"
    return num or ''

def _name_as_first_last(name: str) -> str:
    """Return patient name with proper casing, preserving middle names and suffixes.
    - If input is 'LAST,FIRST MIDDLE SUFFIX' -> 'First Middle Suffix Last'
    - If input has no comma, keep token order but normalize casing and whitespace
    - Handles Mc/Mac prefixes (e.g., McIntyre, MacArthur), O'/’ (e.g., O'Neill, O’Connor), and hyphenated names
    - Suffixes like JR/SR -> Jr/Sr; roman numerals (II, III, IV, V, VI, VII, VIII, IX, X) stay uppercase
    """
    def _fmt_token(tok: str) -> str:
        s = tok.strip()
        base = s.strip('.')  # allow detecting suffixes like Jr.
        U = base.upper()
        # Suffixes
        if U in {"JR", "SR"}:
            return "Jr" if U == "JR" else "Sr"
        if U in {"II","III","IV","V","VI","VII","VIII","IX","X"}:
            return U

        def _fmt_subword(w: str) -> str:
            if not w:
                return ''
            # Apostrophes (ASCII or Unicode)
            parts = re.split(r"(['’])", w, maxsplit=1)
            if len(parts) == 3:
                left, sep, right = parts
                left_c = (left[:1].upper() + left[1:].lower()) if left else ''
                # Right side after apostrophe: capitalize first letter, rest lower
                right_c = (right[:1].upper() + right[1:].lower()) if right else ''
                return f"{left_c}{sep}{right_c}"
            wl = w.lower()
            # Mc/Mac prefixes
            if wl.startswith('mc') and len(w) >= 3 and w[2].isalpha():
                return 'Mc' + w[2].upper() + w[3:].lower()
            if wl.startswith('mac') and len(w) >= 4 and w[3].isalpha():
                return 'Mac' + w[3].upper() + w[4:].lower()
            # Default title casing for the subword
            return w[:1].upper() + w[1:].lower()

        # Hyphenated names: case each subpart
        hy = base.split('-')
        cased = '-'.join(_fmt_subword(p) for p in hy)
        return cased

    try:
        s = (name or '').strip()
        if not s:
            return ''
        if ',' in s:
            family, given = s.split(',', 1)
            family = re.sub(r"\s+", " ", (family or '').strip())
            given = re.sub(r"\s+", " ", (given or '').strip())
            g_parts = [p for p in given.split(' ') if p]
            if not g_parts:
                fam_fmt = ' '.join(_fmt_token(t) for t in family.split(' ') if t)
                return fam_fmt
            first = _fmt_token(g_parts[0])
            rest = [_fmt_token(t) for t in g_parts[1:]]
            fam_fmt = ' '.join(_fmt_token(t) for t in family.split(' ') if t)
            return ' '.join([p for p in [first] + rest + [fam_fmt] if p]).strip()
        # No comma -> keep order, normalize casing
        tokens = [t for t in re.split(r"\s+", s) if t]
        return ' '.join(_fmt_token(t) for t in tokens)
    except Exception:
        return (name or '').title()

def _get_patient_core():
    bundle = session.get('patient_record') or {}
    meta = session.get('patient_meta') or {}
    name = meta.get('name') or ''
    dob = ''
    phone = ''
    try:
        for e in (bundle.get('entry') or []):
            res = (e or {}).get('resource') or {}
            if res.get('resourceType') == 'Patient':
                dob = res.get('birthDate') or ''
                for t in (res.get('telecom') or []):
                    if (t or {}).get('system') == 'phone':
                        use = (t or {}).get('use') or ''
                        if use.lower() in ('mobile','cell','msisdn') and (t.get('value')):
                            phone = t.get('value')
                            break
                        if not phone and t.get('value'):
                            phone = t.get('value')
                break
    except Exception:
        pass
    return name, dob, _phone_pretty(phone)

def _in_window(date_iso: str | None, cutoff: _dt.datetime) -> bool:
    if not date_iso:
        return False
    try:
        d = _dt.datetime.fromisoformat(str(date_iso).replace('Z',''))
        return d >= cutoff
    except Exception:
        return False

# ---------------- LOINC filters support ----------------

def _normalize_term(s: str) -> str:
    try:
        return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
    except Exception:
        return ''

@lru_cache(maxsize=1)
def _get_loinc_index() -> dict:
    """
    Load and cache LOINC_table.csv into an index with:
      - codes: set of known codes (uppercase)
      - name_to_codes: map of normalized names -> set of codes
    Accepts likely column names: LOINC_NUM, SHORTNAME/SHORT_NAME, LONG_COMMON_NAME, LONGNAME, COMPONENT, PROPERTY
    """
    idx = {
        'codes': set(),
        'name_to_codes': {}
    }
    try:
        csv_path = get_resource_path('LOINC_table.csv')
    except Exception:
        csv_path = None
    if not csv_path or not os.path.exists(csv_path):
        return idx
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get('LOINC_NUM') or row.get('code') or row.get('Code') or '').strip()
                if not code:
                    continue
                code = code.upper()
                idx['codes'].add(code)
                name_fields = [
                    row.get('SHORTNAME'), row.get('SHORT_NAME'),
                    row.get('LONG_COMMON_NAME'), row.get('LONGNAME'),
                    row.get('COMPONENT'), row.get('PROPERTY')
                ]
                for name in name_fields:
                    if not name:
                        continue
                    n = _normalize_term(name)
                    if not n:
                        continue
                    s = idx['name_to_codes'].setdefault(n, set())
                    s.add(code)
        # Seed a few common synonyms to ensure matches even if not exact
        synonyms = {
            'a1c': ['hemoglobin a1c', 'hba1c', 'glycohemoglobin'],
            'ldl': ['ldl cholesterol', 'ldl-c'],
            'hdl': ['hdl cholesterol', 'hdl-c'],
            'cholesterol': ['total cholesterol', 'cholesterol total'],
            'triglycerides': ['triglycerides', 'tg'],
            'creatinine': ['serum creatinine', 'creat'],
            'egfr': ['estimated gfr', 'gfr'],
            'uacr': ['urine albumin creatinine ratio', 'albumin/creatinine ratio'],
            'microalbumin': ['urine microalbumin']
        }
        for base, syns in synonyms.items():
            for s in [base] + syns:
                n = _normalize_term(s)
                idx['name_to_codes'].setdefault(n, set())
    except Exception:
        # If CSV fails to load, return whatever we have (likely empty)
        return idx
    return idx

def _prepare_lab_filters(filters: list[str] | None) -> tuple[set[str], set[str]]:
    """
    From a list of raw filters (names or LOINC codes), return:
      - want_codes: set of codes (uppercase)
      - want_names: set of normalized name substrings
    Also expands names to codes using the LOINC index when available.
    """
    want_codes: set[str] = set()
    want_names: set[str] = set()
    if not filters:
        return want_codes, want_names
    idx = _get_loinc_index()
    code_pat = re.compile(r'^\d{3,5}-\d$', re.IGNORECASE)
    for f in filters:
        tok = (f or '').strip()
        if not tok:
            continue
        if code_pat.match(tok):
            want_codes.add(tok.upper())
            continue
        norm = _normalize_term(tok)
        if not norm:
            continue
        want_names.add(norm)
        codes = idx['name_to_codes'].get(norm)
        if codes:
            want_codes.update(codes)
    return want_codes, want_names

def _lab_record_matches(rec: dict, want_codes: set[str], want_names: set[str]) -> bool:
    if not want_codes and not want_names:
        return True
    code_fields = [
        str(rec.get('loinc') or ''),
        str(rec.get('code') or ''),
        str(rec.get('loincCode') or ''),
    ]
    code_fields = [c.upper() for c in code_fields if c]
    if want_codes and any(c in want_codes for c in code_fields):
        return True
    label = (rec.get('test') or rec.get('localName') or '')
    label_norm = _normalize_term(label)
    return bool(want_names and any(n in label_norm for n in want_names))

def _list_meds(days: int | None, only_active: bool) -> str:
    meds = session.get('fhir_meds') or []
    cutoff = _days_ago_cutoff(days if days is not None else 90)
    out = []
    for m in meds:
        status = (m.get('status') or '').lower()
        if only_active and status != 'active':
            continue
        # choose a relevant date for window: lastFilled, else startDate
        dt = m.get('lastFilled') or m.get('startDate')
        if not _in_window(dt, cutoff):
            continue
        parts = []
        if m.get('name'): parts.append(m.get('name'))
        if m.get('dose'): parts.append(m.get('dose'))
        # Build simple descriptor
        desc = ', '.join(parts)
        extra = []
        if m.get('route'): extra.append(m.get('route'))
        if m.get('frequency'): extra.append(m.get('frequency'))
        if status: extra.append(f"status: {status}")
        when = _fmt_date_human(dt)
        if when: extra.append(f"as of {when}")
        if extra:
            desc += f" ({'; '.join(extra)})"
        if desc:
            out.append(f"- {desc}")
    if not out:
        return "no recent medications found."
    return '\n'.join(out)

def _list_problems(only_active: bool) -> str:
    probs = session.get('fhir_problems') or []
    out = []
    for p in probs:
        if only_active and not bool(p.get('active')):
            continue
        name = p.get('name') or 'problem'
        onset = _fmt_date_human(p.get('onsetDateTime'))
        abate = _fmt_date_human(p.get('abatementDateTime'))
        status = 'active' if p.get('active') else (p.get('clinicalStatus') or '').lower() or 'inactive'
        bits = [name]
        tail = []
        if status: tail.append(status)
        if onset: tail.append(f"since {onset}")
        if abate and not p.get('active'): tail.append(f"ended {abate}")
        if tail:
            bits.append(f"({', '.join(tail)})")
        out.append(f"- {' '.join(bits)}")
    if not out:
        return "no problems recorded."
    return '\n'.join(out)

def _list_allergies() -> str:
    alls = session.get('fhir_allergies') or []
    if not alls:
        return "no allergies recorded."
    out = []
    for a in alls:
        sub = a.get('substance') or 'allergy'
        sev = (a.get('criticality') or '')
        last = _fmt_date_human(a.get('lastOccurrence'))
        bits = [sub]
        tail = []
        if sev: tail.append(sev.lower())
        if last: tail.append(f"last noted {last}")
        if tail:
            bits.append(f"({', '.join(tail)})")
        out.append(f"- {' '.join(bits)}")
    return '\n'.join(out)

# --- Medication start-date helper ---

def _parse_dt_safe(iso: str | None):
    try:
        return _dt.datetime.fromisoformat(str(iso).replace('Z','')) if iso else None
    except Exception:
        return None

def _med_started(name_q: str) -> str:
    """Return earliest known start date for a medication matching name_q.
    Looks across common fields: startDate, writtenDate, orderedDate, firstFilled, lastFilled.
    """
    meds = session.get('fhir_meds') or []
    if not meds:
        return "no medications available."
    q = (name_q or '').strip().lower()
    if not q:
        return "no medication specified."
    best_dt = None
    best_label = None
    for m in meds:
        label = (m.get('name') or '').strip()
        if not label or q not in label.lower():
            continue
        cands = [
            m.get('startDate'), m.get('writtenDate'), m.get('orderedDate'),
            m.get('firstFilled'), m.get('lastFilled')
        ]
        for iso in cands:
            dt = _parse_dt_safe(iso)
            if not dt:
                continue
            if best_dt is None or dt < best_dt:
                best_dt = dt
                best_label = label
    if not best_dt:
        return f"no start date found for {name_q}."
    return f"{best_label or name_q} started on {_fmt_date_human(best_dt.isoformat())}."

def _latest_vitals() -> str:
    vitals = session.get('fhir_vitals') or {}
    if not vitals:
        return "no vitals available."
    # series sorted chronologically; take last
    def last_of(key):
        arr = vitals.get(key) or []
        return arr[-1] if arr else None
    bp = last_of('bloodPressure')
    hr = last_of('heartRate')
    rr = last_of('respiratoryRate')
    temp = last_of('temperature')
    spo2 = last_of('oxygenSaturation')
    wt = last_of('weight')
    out = []
    if bp and (bp.get('systolic') is not None or bp.get('diastolic') is not None):
        d = _fmt_date_human(bp.get('effectiveDateTime'))
        out.append(f"- blood pressure {bp.get('systolic') or ''}/{bp.get('diastolic') or ''} {bp.get('unit') or 'mmHg'} ({d})")
    if hr:
        out.append(f"- heart rate {hr.get('value')} {hr.get('unit') or 'bpm'} ({_fmt_date_human(hr.get('effectiveDateTime'))})")
    if rr:
        out.append(f"- respiratory rate {rr.get('value')} {rr.get('unit') or 'breaths/min'} ({_fmt_date_human(rr.get('effectiveDateTime'))})")
    if temp:
        out.append(f"- temperature {temp.get('value')} {temp.get('unit') or 'F'} ({_fmt_date_human(temp.get('effectiveDateTime'))})")
    if spo2:
        out.append(f"- oxygen saturation {spo2.get('value')}% ({_fmt_date_human(spo2.get('effectiveDateTime'))})")
    if wt:
        out.append(f"- weight {wt.get('value')} {wt.get('unit') or 'kg'} ({_fmt_date_human(wt.get('effectiveDateTime'))})")
    if not out:
        return "no vitals available."
    return '\n'.join(out)

def _vitals_in_days(days: int) -> str:
    vitals = session.get('fhir_vitals') or {}
    if not vitals:
        return "no vitals available."
    cutoff = _days_ago_cutoff(days)
    out = []
    for key, arr in vitals.items():
        for rec in arr:
            if _in_window(rec.get('effectiveDateTime'), cutoff):
                label = key.replace('oxygenSaturation', 'oxygen saturation').replace('bloodPressure','blood pressure')
                val = ''
                if key == 'bloodPressure':
                    val = f"{rec.get('systolic')}/{rec.get('diastolic')} {rec.get('unit') or 'mmHg'}"
                else:
                    unit = rec.get('unit') or ''
                    v = rec.get('value')
                    if v is not None:
                        val = f"{v} {unit}".strip()
                d = _fmt_date_human(rec.get('effectiveDateTime'))
                out.append(f"- {label} {val} ({d})")
    if not out:
        return "no vitals in the selected window."
    # sort by date descending within the text by extracting date again
    def _key(line: str):
        return 0
    return '\n'.join(out)

def _list_labs(days: int | None, filters: list[str] | None = None) -> str:
    labs = session.get('fhir_labs') or []
    if not labs:
        return "no labs available."

    want_codes, want_names = _prepare_lab_filters(filters)

    # If specific filters are provided and no days window, return the most recent per test
    if (filters and days is None):
        best: dict[str, dict] = {}
        def _key(rec: dict) -> str:
            code = (rec.get('loinc') or rec.get('code') or rec.get('loincCode') or '').strip().upper()
            if code:
                return f"CODE:{code}"
            label = (rec.get('test') or rec.get('localName') or '')
            return f"NAME:{_normalize_term(label)}"
        def _parse_dt(iso: str | None):
            try:
                return _dt.datetime.fromisoformat(str(iso).replace('Z','')) if iso else None
            except Exception:
                return None
        for r in labs:
            if not _lab_record_matches(r, want_codes, want_names):
                continue
            dt_iso = r.get('resulted') or r.get('collected')
            dt = _parse_dt(dt_iso)
            if not dt:
                continue
            k = _key(r)
            cur = best.get(k)
            if not cur:
                best[k] = {**r, '__dt': dt}
            else:
                if dt > cur.get('__dt'):
                    best[k] = {**r, '__dt': dt}
        if not best:
            return "no labs found."
        # Sort by most recent
        chosen = sorted(best.values(), key=lambda x: x.get('__dt'), reverse=True)
        out = []
        for r in chosen:
            test = r.get('test') or r.get('localName') or 'lab'
            val = r.get('result')
            unit = r.get('unit') or ''
            abn = ' abnormal' if r.get('abnormal') else ''
            when = _fmt_date_human((r.get('resulted') or r.get('collected')))
            val_s = str(val) if val is not None else ''
            out.append(f"- {test}: {val_s} {unit} ({when}){abn}".strip())
        return '\n'.join(out)

    # Otherwise, use time-window listing (default 14 days)
    cutoff = _days_ago_cutoff(days if days is not None else 14)
    out = []
    for r in labs:
        dt_iso = r.get('resulted') or r.get('collected')
        if not _in_window(dt_iso, cutoff):
            continue
        if not _lab_record_matches(r, want_codes, want_names):
            continue
        test = r.get('test') or r.get('localName') or 'lab'
        val = r.get('result')
        unit = r.get('unit') or ''
        abn = ' abnormal' if r.get('abnormal') else ''
        when = _fmt_date_human(dt_iso)
        if isinstance(val, (int,float)):
            val_s = str(val)
        else:
            val_s = str(val) if val is not None else ''
        line = f"- {test}: {val_s} {unit} ({when}){abn}"
        out.append(line.strip())
    if not out:
        return "no labs in the selected window."
    return '\n'.join(out)

def _calc_age_years(dob_iso: str | None) -> str:
    """Return age in years from an ISO DOB like YYYY-MM-DD (empty string if unavailable)."""
    if not dob_iso:
        return ''
    try:
        d = _dt.datetime.fromisoformat(str(dob_iso).replace('Z','')).date()
    except Exception:
        # Try basic YYYY-MM-DD
        try:
            y, m, day = map(int, str(dob_iso)[:10].split('-'))
            d = _dt.date(y, m, day)
        except Exception:
            return ''
    today = _dt.date.today()
    years = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    try:
        return str(max(0, years))
    except Exception:
        return ''

def _to_iso_date(d: _dt.date) -> str:
    try:
        return d.isoformat()
    except Exception:
        return str(d)

def _parse_natural_date(token: str, default_end: bool = False) -> str | None:
    """Parse tokens like '2023', 'May 2019', '2024-02-03' into ISO YYYY-MM-DD.
    If only year or month-year provided, choose first (default_end=False) or last day (default_end=True).
    """
    if not token:
        return None
    s = token.strip()
    # YYYY-MM-DD
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
            y, m, d = map(int, s.split('-'))
            return _to_iso_date(_dt.date(y, m, d))
    except Exception:
        pass
    # Month YYYY
    mth = re.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{4})$', s, re.IGNORECASE)
    if mth:
        y = int(mth.group(2))
        m = [None,'jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].index(mth.group(1)[:3].lower())
        if default_end:
            last_day = calendar.monthrange(y, m)[1]
            return _to_iso_date(_dt.date(y, m, last_day))
        else:
            return _to_iso_date(_dt.date(y, m, 1))
    # YYYY
    yr = re.match(r'^(\d{4})$', s)
    if yr:
        y = int(yr.group(1))
        if default_end:
            return _to_iso_date(_dt.date(y, 12, 31))
        else:
            return _to_iso_date(_dt.date(y, 1, 1))
    return None

def _dt_from_iso(iso: str | None):
    try:
        if not iso: return None
        return _dt.datetime.fromisoformat(str(iso).replace('Z',''))
    except Exception:
        return None

def _within_range(dt_iso: str | None, start_iso: str | None, end_iso: str | None) -> bool:
    d = _dt_from_iso(dt_iso)
    if not d:
        return False
    if start_iso:
        s = _dt_from_iso(start_iso)
        if s and d < s:
            return False
    if end_iso:
        e = _dt_from_iso(end_iso)
        if e and d > e:
            return False
    return True

def _list_labs_range(start_iso: str | None, end_iso: str | None, filters: list[str] | None) -> str:
    labs = session.get('fhir_labs') or []
    if not labs:
        return "no labs available."
    want_codes, want_names = _prepare_lab_filters(filters)
    out = []
    for r in labs:
        dt_iso = r.get('resulted') or r.get('collected')
        if not _within_range(dt_iso, start_iso, end_iso):
            continue
        if not _lab_record_matches(r, want_codes, want_names):
            continue
        test = r.get('test') or r.get('localName') or 'lab'
        val = r.get('result')
        unit = r.get('unit') or ''
        abn = ' abnormal' if r.get('abnormal') else ''
        when = _fmt_date_human(dt_iso)
        val_s = str(val) if val is not None else ''
        out.append(f"- {test}: {val_s} {unit} ({when}){abn}".strip())
    if not out:
        return "no labs in the selected window."
    return '\n'.join(out)

def _vitals_in_range(start_iso: str | None, end_iso: str | None) -> str:
    vitals = session.get('fhir_vitals') or {}
    if not vitals:
        return "no vitals available."
    out = []
    for key, arr in vitals.items():
        for rec in arr:
            if _within_range(rec.get('effectiveDateTime'), start_iso, end_iso):
                label = key.replace('oxygenSaturation', 'oxygen saturation').replace('bloodPressure','blood pressure')
                val = ''
                if key == 'bloodPressure':
                    val = f"{rec.get('systolic')}/{rec.get('diastolic')} {rec.get('unit') or 'mmHg'}"
                else:
                    unit = rec.get('unit') or ''
                    v = rec.get('value')
                    if v is not None:
                        val = f"{v} {unit}".strip()
                d = _fmt_date_human(rec.get('effectiveDateTime'))
                out.append(f"- {label} {val} ({d})")
    if not out:
        return "no vitals in the selected window."
    return '\n'.join(out)

def _list_meds_range(start_iso: str | None, end_iso: str | None, only_active: bool) -> str:
    meds = session.get('fhir_meds') or []
    if not meds:
        return "no medications available."
    out = []
    for m in meds:
        status = (m.get('status') or '').lower()
        if only_active and status != 'active':
            continue
        dt = m.get('lastFilled') or m.get('startDate')
        if not _within_range(dt, start_iso, end_iso):
            continue
        parts = []
        if m.get('name'): parts.append(m.get('name'))
        if m.get('dose'): parts.append(m.get('dose'))
        desc = ', '.join(parts)
        extra = []
        if m.get('route'): extra.append(m.get('route'))
        if m.get('frequency'): extra.append(m.get('frequency'))
        if status: extra.append(f"status: {status}")
        when = _fmt_date_human(dt)
        if when: extra.append(f"as of {when}")
        if extra:
            desc += f" ({'; '.join(extra)})"
        if desc:
            out.append(f"- {desc}")
    if not out:
        return "no medications in the selected window."
    return '\n'.join(out)

# --- Orders (VistA RPC) support for dot-phrases ---

def _orders_status_code(label: str) -> str:
    if not label:
        return '23'  # current (active+pending)
    s = label.strip().lower()
    if s in ('active','a','signed','complete','completed','current'):
        return '2'
    if s in ('pending','p','new','unsigned'):
        return '7'
    if s in ('current','active+pending','actpend'):
        return '23'
    if s in ('all','*'):
        return '1'
    return '23'

def _orders_type_label(label: str) -> str:
    if not label:
        return 'all'
    s = label.strip().lower()
    if s in ('med','meds','medications','pharmacy','rx'):
        return 'meds'
    if s in ('lab','labs','laboratory','lab orders','labs orders'):
        return 'labs'
    return 'all'

def _fileman_now_minus_days(days: int) -> float:
    d = _dt.datetime.now() - _dt.timedelta(days=max(0,int(days)))
    y = d.year - 1700
    date_part = y * 10000 + d.month * 100 + d.day
    frac = f"{d.hour:02d}{d.minute:02d}"
    try:
        return float(f"{date_part}.{frac}")
    except Exception:
        return float(date_part)

def _fileman_to_iso_local(fm: str) -> str:
    try:
        s = str(fm)
        if '.' in s:
            d, t = s.split('.',1)
        else:
            d, t = s, ''
        d = int(d)
        year = 1700 + (d // 10000)
        rem = d % 10000
        month = rem // 100
        day = rem % 100
        hh = int(t[0:2]) if len(t) >= 2 else 0
        mm = int(t[2:4]) if len(t) >= 4 else 0
        return _dt.datetime(year, month, day, hh, mm).isoformat()
    except Exception:
        return ''

def _vista_rpc_call(name: str, params):
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        raise RuntimeError('VistA socket client not available')
    # preferred contexts for orders
    contexts = ['OR CPRS GUI CHART', getattr(vista_client, 'context', None), 'JLV WEB SERVICES']
    lock = getattr(vista_client, 'conn_lock', None)
    if not lock:
        try:
            lock = current_app.config.setdefault('VISTA_LOCK', threading.Lock())
        except Exception:
            lock = threading.Lock()
        try:
            setattr(vista_client, 'conn_lock', lock)
        except Exception:
            pass
    last_err = None
    with lock:
        for ctx in contexts:
            try:
                if hasattr(vista_client, 'call_in_context'):
                    raw = vista_client.call_in_context(name, params, ctx)
                else:
                    if getattr(vista_client, 'context', None) != ctx:
                        vista_client.setContext(ctx)
                    raw = vista_client.invokeRPC(name, params)
                # normalize lines
                if isinstance(raw, str):
                    lines = [ln for ln in raw.splitlines() if ln.strip()]
                elif isinstance(raw, list):
                    lines = [str(ln) for ln in raw if str(ln).strip()]
                else:
                    lines = []
                return lines
            except Exception as e:
                last_err = e
                continue
    raise RuntimeError(f"RPC {name} failed: {last_err}")

def _orders_parse_aget(lines):
    out = []
    for ln in lines:
        if ';' not in ln:
            continue
        parts = ln.split('^')
        if len(parts) < 3:
            continue
        out.append({'id': parts[0].strip(), 'status_code': parts[1].strip(), 'fm_date': parts[2].strip()})
    return out

def _orders_detail(dfn: str, order_id_with_sub: str) -> dict:
    lines = _vista_rpc_call('ORQOR DETAIL', [order_id_with_sub, dfn])
    info = {'type':'unknown','name':'','instructions':'','sig':'','indication':'','current_status':'','raw':'\n'.join(lines)}
    for ln in lines:
        if ln.startswith('Current Status:'):
            info['current_status'] = ln.split(':',1)[1].strip()
            break
    in_order = False
    for ln in lines:
        if ln.strip() == 'Order:':
            in_order = True
            continue
        if in_order and ln.strip() == '':
            break
        if in_order:
            s = ln.strip()
            if s.startswith('Medication:'):
                info['type'] = 'meds'
                info['name'] = ln.split(':',1)[1].strip()
            elif s.startswith('Lab Test:'):
                info['type'] = 'labs'
                info['name'] = ln.split(':',1)[1].strip()
            elif s.startswith('Instructions:'):
                info['instructions'] = ln.split(':',1)[1].strip()
            elif s.startswith('Sig:'):
                info['sig'] = ln.split(':',1)[1].strip()
            elif s.startswith('Indication:'):
                info['indication'] = ln.split(':',1)[1].strip()
    if not info['name'] and lines:
        first = lines[0].strip()
        if first and 'Activity:' not in first and 'Current Data:' not in first:
            info['name'] = first
    return info

def _list_orders(status: str | None, typ: str | None, days: int | None, start_iso: str | None, end_iso: str | None) -> str:
    meta = session.get('patient_meta') or {}
    dfn = str(meta.get('dfn') or '').strip()
    if not dfn:
        return 'no patient selected.'
    try:
        status_param = f"{_orders_status_code(status or '')}^0"
        aget_params = [dfn, status_param, '1', '0', '0', '', '0']
        rows = _orders_parse_aget(_vista_rpc_call('ORWORR AGET', aget_params))
    except Exception as e:
        return f"error retrieving orders: {e}"
    # time filter
    fm_cutoff = None
    if days is not None:
        fm_cutoff = _fileman_now_minus_days(days)
    # Build list with details and apply filters
    want_type = _orders_type_label(typ or '')
    out = []
    limit = 150
    for b in rows[:limit]:
        fm_date = b.get('fm_date') or ''
        if fm_cutoff is not None:
            try:
                if float(fm_date) < float(fm_cutoff):
                    continue
            except Exception:
                pass
        # If start/end in ISO provided, convert fm to iso and compare
        if start_iso or end_iso:
            iso = _fileman_to_iso_local(fm_date)
            d = _dt_from_iso(iso)
            sdt = _dt_from_iso(start_iso) if start_iso else None
            edt = _dt_from_iso(end_iso) if end_iso else None
            if sdt and (not d or d < sdt):
                continue
            if edt and (not d or d > edt):
                continue
        try:
            info = _orders_detail(dfn, b['id'])
        except Exception:
            continue
        if want_type != 'all' and info.get('type') != want_type:
            continue
        when_h = _fmt_date_human(_fileman_to_iso_local(fm_date))
        typ_label = info.get('type') or 'order'
        cur = info.get('current_status') or ''
        name = info.get('name') or '(unnamed)'
        extra = []
        if typ_label == 'meds' and info.get('sig'):
            extra.append(info['sig'])
        if info.get('instructions') and typ_label != 'meds':
            extra.append(info['instructions'])
        if info.get('indication'):
            extra.append(f"for {info['indication']}")
        tail = f" ({'; '.join(extra)})" if extra else ''
        out.append(f"- {typ_label}: {name}{tail} [{cur}] ({when_h})")
    if not out:
        return 'no matching orders.'
    return '\n'.join(out)

def expand_patient_dotphrases(text: str, for_query: bool = False) -> str:
    """Expand [[...]] patient dot-phrases in the given text if a patient is loaded.
    for_query: set True when expanding a user's retrieval query; keeps content concise.
    """
    if not isinstance(text, str) or '[[' not in text:
        return text
    meta = session.get('patient_meta') or {}
    if not meta.get('dfn'):
        return text

    name, dob, phone = _get_patient_core()

    def repl(match: re.Match) -> str:
        raw = (match.group(1) or '').strip().lower()
        if not raw:
            return match.group(0)
        parts = [p for p in raw.split('/') if p]
        if not parts:
            return match.group(0)
        # parse optional numeric days at end
        days = None
        if parts and parts[-1].isdigit():
            try:
                days = int(parts[-1])
                parts = parts[:-1]
            except Exception:
                pass
        key = parts[0]
        # simple fields
        if key == 'name':
            return _name_as_first_last(name)
        if key == 'dob':
            return _fmt_date_human(dob) or (dob or '')
        if key == 'age':
            return _calc_age_years(dob)
        if key == 'phone':
            return phone or ''
        # lists
        if key == 'meds':
            only_active = (len(parts) > 1 and parts[1] == 'active')
            # range tokens for meds
            has_range = any('=' in p for p in parts[1:])
            if has_range:
                start_iso = None
                end_iso = None
                for tok in parts[1:]:
                    if tok.startswith('since='):
                        start_iso = _parse_natural_date(tok.split('=',1)[1], default_end=False)
                    elif tok.startswith('start='):
                        start_iso = _parse_natural_date(tok.split('=',1)[1], default_end=False)
                    elif tok.startswith('end='):
                        end_iso = _parse_natural_date(tok.split('=',1)[1], default_end=True)
                return _list_meds_range(start_iso, end_iso, only_active)
            return _list_meds(days, only_active)
        if key == 'problems':
            only_active = (len(parts) > 1 and parts[1] == 'active')
            return _list_problems(only_active)
        if key == 'allergies':
            return _list_allergies()
        if key == 'vitals':
            # check for range tokens
            range_tokens = {p for p in parts[1:] if '=' in p}
            if range_tokens:
                start_iso = None
                end_iso = None
                for tok in parts[1:]:
                    if tok.startswith('since='):
                        start_iso = _parse_natural_date(tok.split('=',1)[1], default_end=False)
                    elif tok.startswith('start='):
                        start_iso = _parse_natural_date(tok.split('=',1)[1], default_end=False)
                    elif tok.startswith('end='):
                        end_iso = _parse_natural_date(tok.split('=',1)[1], default_end=True)
                return _vitals_in_range(start_iso, end_iso)
            if days is not None:
                return _vitals_in_days(days)
            return _latest_vitals()
        if key == 'labs':
            # Remaining parts are filters and optional range tokens
            filters: list[str] = []
            start_iso = None
            end_iso = None
            for token in parts[1:]:
                if '=' in token:
                    k, v = token.split('=',1)
                    if k == 'since':
                        start_iso = _parse_natural_date(v, default_end=False)
                    elif k == 'start':
                        start_iso = _parse_natural_date(v, default_end=False)
                    elif k == 'end':
                        end_iso = _parse_natural_date(v, default_end=True)
                    continue
                filters.extend([t.strip() for t in token.split(',') if t.strip()])
            if start_iso or end_iso:
                return _list_labs_range(start_iso, end_iso, filters if filters else None)
            return _list_labs(days, filters if filters else None)
        if key in ('meds','medications'):
            only_active = (len(parts) > 1 and parts[1] == 'active')
            return _list_meds(days, only_active)
        if key == 'orders':
            # orders[/type][/days] plus optional range tokens start=, end=, since=
            otype = None
            start_iso = None
            end_iso = None
            status = None
            for token in parts[1:]:
                if '=' in token:
                    k, v = token.split('=',1)
                    if k == 'since' or k == 'start':
                        start_iso = _parse_natural_date(v, default_end=False)
                    elif k == 'end':
                        end_iso = _parse_natural_date(v, default_end=True)
                    elif k == 'status':
                        status = v
                    continue
                # if token is a known type or status word
                if token in ('meds','med','medications','pharmacy','rx','labs','lab','laboratory'):
                    otype = token
                elif token in ('active','pending','current','all','signed','complete','completed','new','unsigned'):
                    status = token
            return _list_orders(status, otype, days, start_iso, end_iso)
        if key in ('medstarted','med_start'):
            # Medication name is the rest joined by spaces or comma-separated
            med_q = ''
            if len(parts) > 1:
                med_q = ' '.join(parts[1:])
            return _med_started(med_q)
        # Unknown -> keep original token
        return match.group(0)

    # Replace all occurrences
    try:
        return re.sub(r"\[\[([^\]]+)\]\]", repl, text)
    except Exception:
        return text

def get_dotphrase_commands() -> list:
    """Return list of supported [[patient]] dot-phrases with explanations."""
    return [
        { 'command': '[[name]]', 'explanation': 'Patient name.' },
        { 'command': '[[dob]]', 'explanation': 'Date of birth.' },
        { 'command': '[[age]]', 'explanation': 'Patient age in years (if DOB available).' },
        { 'command': '[[phone]]', 'explanation': 'Mobile phone if available.' },
        { 'command': '[[meds]]', 'explanation': 'All medications in the last 90 days by default.' },
        { 'command': '[[meds/active]]', 'explanation': 'Active medications in the last 90 days by default.' },
        { 'command': '[[problems]]', 'explanation': 'All problems/conditions.' },
        { 'command': '[[problems/active]]', 'explanation': 'Active problems/conditions.' },
        { 'command': '[[allergies]]', 'explanation': 'Allergy list.' },
        { 'command': '[[vitals]]', 'explanation': 'Most recent vitals.' },
        { 'command': '[[vitals/<days>]]', 'explanation': 'Vitals recorded within the past N days, e.g., [[vitals/7]].' },
        { 'command': '[[labs]]', 'explanation': 'Labs from the past 14 days by default.' },
        { 'command': '[[labs/<days>]]', 'explanation': 'Labs within the past N days, e.g., [[labs/365]].' },
        { 'command': '[[labs/<name-or-code>]]', 'explanation': 'Filter labs by name or LOINC code, e.g., [[labs/a1c]] or [[labs/2089-1]].' },
        { 'command': '[[labs/<name-or-code>/<days>]]', 'explanation': 'Filter labs within past N days, e.g., [[labs/ldl/365]] or [[labs/a1c,creatinine/180]].' },
        { 'command': '[[medstarted/<name>]]', 'explanation': 'Earliest start date for a medication by name, e.g., [[medstarted/empagliflozin]].' },
        { 'command': '[[meds/<days>]]', 'explanation': 'Medications within the past N days, e.g., [[meds/60]].' },
        { 'command': '[[meds/active/<days>]]', 'explanation': 'Active medications within the past N days, e.g., [[meds/active/30]].' },
        { 'command': '[[vitals/start=<date>/end=<date>]]', 'explanation': 'Vitals in a date range. Date can be YYYY, Mon YYYY, or YYYY-MM-DD.' },
        { 'command': '[[labs/start=<date>/end=<date>]]', 'explanation': 'Labs in a date range with optional filters, e.g., [[labs/a1c/start=2024/end=2025-08-29]].' },
        { 'command': '[[labs/since=<date>]]', 'explanation': 'Labs since a date with optional filters, e.g., [[labs/ldl,scr/since=2023]].' },
        { 'command': '[[meds/start=<date>/end=<date>]]', 'explanation': 'Medications in a date range; add /active for active only.' },
        { 'command': '[[orders]]', 'explanation': 'Current (active+pending) orders in the last 7 days.' },
        { 'command': '[[orders/<type>]]', 'explanation': 'Orders filtered by type: meds or labs, e.g., [[orders/meds]].' },
        { 'command': '[[orders/<days>]]', 'explanation': 'Orders within the past N days, e.g., [[orders/30]].' },
        { 'command': '[[orders/status=<status>]]', 'explanation': 'Status: active, pending, current, all.' },
        { 'command': '[[orders/start=<date>/end=<date>]]', 'explanation': 'Orders in a date range.' },
        { 'command': '[[orders/since=<date>]]', 'explanation': 'Orders since a date.' },
    ]
