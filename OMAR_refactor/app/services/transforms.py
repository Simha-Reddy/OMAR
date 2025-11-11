from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import datetime as dt


# --------------------- Generic helpers for VPR payloads ---------------------

def _get_nested_items(payload: Any) -> List[Dict[str, Any]]:
    """Extract items list from various shapes: payload.data.items, data.items, items, or value."""
    try:
        if isinstance(payload, dict):
            p = payload
            x = p.get("payload")
            if isinstance(x, dict):
                d = x.get("data")
                if isinstance(d, dict) and isinstance(d.get("items"), list):
                    return d["items"]  # type: ignore
            d = p.get("data")
            if isinstance(d, dict) and isinstance(d.get("items"), list):
                return d["items"]  # type: ignore
            if isinstance(p.get("items"), list):
                return p["items"]  # type: ignore
            if isinstance(p.get("value"), list):
                return p["value"]  # type: ignore
        if isinstance(payload, list):
            return payload  # already a list
    except Exception:
        pass
    return []


def _first_item(payload: Any) -> Dict[str, Any]:
    items = _get_nested_items(payload)
    if items and isinstance(items[0], dict):
        return items[0]
    if isinstance(payload, dict):
        keys = {k.lower() for k in payload.keys()}
        if any(k in keys for k in ("fullname", "localid", "dateofbirth", "ssn", "telecoms")):
            return payload
    return {}


def _fmt_dob_fields(date_of_birth: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return (DOB_ISO, DOB_MMM_DD_YYYY) from an integer yyyymmdd or string."""
    try:
        s = str(date_of_birth or '').strip()
        if not s:
            return None, None
        y = m = d = None
        if s.isdigit() and len(s) == 8:
            y, m, d = int(s[0:4]), int(s[4:6]), int(s[6:8])
        else:
            try:
                n = int(float(s))
                s2 = f"{n:08d}"
                y, m, d = int(s2[0:4]), int(s2[4:6]), int(s2[6:8])
            except Exception:
                return None, None
        iso = dt.date(y, m, d).isoformat()
        mon = dt.date(y, m, d).strftime('%b').upper()
        pretty = f"{mon} {d},{y}"
        return iso, pretty
    except Exception:
        return None, None


def _fmt_ssn(ssn_val: Any) -> Optional[str]:
    try:
        s = str(ssn_val or '').strip()
        if not s:
            return None
        digits = ''.join(ch for ch in s if ch.isdigit())
        if len(digits) == 9:
            return f"{digits[0:3]}-{digits[3:5]}-{digits[5:9]}"
        return s
    except Exception:
        return None

_VITAL_TYPE_MAP: Dict[str, Tuple[str, Optional[str]]] = {
    'BP': ('Blood Pressure', 'mmHg'),
    'BLOODPRESSURE': ('Blood Pressure', 'mmHg'),
    'T': ('Temperature', 'F'),
    'TEMP': ('Temperature', 'F'),
    'TEMPERATURE': ('Temperature', 'F'),
    'P': ('Pulse', 'bpm'),
    'HR': ('Pulse', 'bpm'),
    'PULSE': ('Pulse', 'bpm'),
    'R': ('Respiratory Rate', 'breaths/min'),
    'RR': ('Respiratory Rate', 'breaths/min'),
    'RESP': ('Respiratory Rate', 'breaths/min'),
    'RESPIRATORYRATE': ('Respiratory Rate', 'breaths/min'),
    'WT': ('Weight', 'lbs'),
    'WEIGHT': ('Weight', 'lbs'),
    'WTKG': ('Weight', 'kg'),
    'HT': ('Height', 'in'),
    'HEIGHT': ('Height', 'in'),
    'HTCM': ('Height', 'cm'),
    'PO2': ('SpO2', '%'),
    'POX': ('SpO2', '%'),
    'SPO2': ('SpO2', '%'),
    'O2': ('SpO2', '%'),
    'OXYGENSATURATION': ('SpO2', '%'),
    'PN': ('Pain', None),
    'PAIN': ('Pain', None),
    'BMI': ('BMI', None),
    'CG': ('Girth', 'cm'),
}


def _normalize_vital_code(raw_type: Any) -> Optional[str]:
    text = (raw_type or '').strip()
    if not text:
        return None
    upper = text.upper()
    if upper in _VITAL_TYPE_MAP:
        return upper
    compact = ''.join(ch for ch in upper if not ch.isspace())
    if compact in _VITAL_TYPE_MAP:
        return compact
    for alias, target in (
        ('TEMPERATURE', 'TEMP'),
        ('PULSE', 'P'),
        ('HEART', 'P'),
        ('RESP', 'RESP'),
        ('WEIGHT', 'WT'),
        ('HEIGHT', 'HT'),
        ('BLOODPRESSURE', 'BP'),
        ('OXYGEN', 'PO2'),
        ('SATURATION', 'PO2'),
    ):
        if alias in upper:
            mapped = target.upper()
            if mapped in _VITAL_TYPE_MAP:
                return mapped
    return None


def _sanitize_vital_unit(unit: Any, value: Any) -> Optional[str]:
    text = (unit or '').strip()
    if not text:
        return None
    value_text = (value or '').strip()
    if text == value_text:
        return None
    if value_text and text.startswith(value_text):
        text = text[len(value_text):].strip()
    if not text:
        return None
    tokens = [tok.strip('() ') for tok in text.split() if tok.strip('() ')]
    if not tokens:
        return None
    cleaned = tokens[-1]
    if cleaned.lower() == 'lb':
        return 'lbs'
    return cleaned


def _pick_phone(telecoms: Any) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {'Phone (mobile)': None, 'Phone (work)': None}
    try:
        arr = telecoms if isinstance(telecoms, list) else []
        for t in arr:
            if not isinstance(t, dict):
                continue
            usage = str(t.get('usageCode') or t.get('usageName') or '').upper()
            num = t.get('telecom') or t.get('value') or ''
            num = str(num).strip()
            if not num:
                continue
            if any(token in usage for token in ('MOB', 'CELL', 'HOME')):
                out['Phone (mobile)'] = out['Phone (mobile)'] or num
            if any(token in usage for token in ('WORK', 'OFFICE', 'WP')):
                out['Phone (work)'] = out['Phone (work)'] or num
    except Exception:
        pass
    return out

# NOTE: FHIR mapping functions removed by request to preserve VA-specific fidelity.


# --------------------- Direct VPR -> quick demographics ---------------------

def map_vpr_patient_to_quick_demographics(vpr_payload: Any) -> Dict[str, Any]:
    """Transform VPR patient domain JSON into the dict used by quick/patient/demographics."""
    it = _first_item(vpr_payload)
    if not it:
        return {}
    name = it.get('fullName') or ''
    dob_iso, dob_pretty = _fmt_dob_fields(it.get('dateOfBirth'))
    ssn_fmt = _fmt_ssn(it.get('ssn'))
    addr_fmt = None
    try:
        addrs = it.get('addresses') or []
        if addrs and isinstance(addrs, list):
            a0 = addrs[0] or {}
            line1 = a0.get('streetLine1') or ''
            city = a0.get('city') or ''
            state = a0.get('stateProvince') or ''
            pc = a0.get('postalCode') or ''
            addr_fmt = ', '.join([p for p in [line1, city, state] if p])
            if pc:
                addr_fmt = f"{addr_fmt} {pc}" if addr_fmt else str(pc)
    except Exception:
        pass
    phones = _pick_phone(it.get('telecoms'))
    out: Dict[str, Any] = {}
    if name:
        out['Name'] = name
    if ssn_fmt:
        out['SSN'] = ssn_fmt
    if dob_pretty:
        out['DOB'] = dob_pretty
    if dob_iso:
        out['DOB_ISO'] = dob_iso
    if it.get('genderName'):
        out['Gender'] = it['genderName']
    if it.get('icn'):
        out['ICN'] = str(it['icn'])
    if it.get('localId'):
        out['DFN'] = str(it['localId'])
    if addr_fmt:
        out['Address'] = addr_fmt
    if phones.get('Phone (mobile)'):
        out['Phone (mobile)'] = phones['Phone (mobile)']
    if phones.get('Phone (work)'):
        out['Phone (work)'] = phones['Phone (work)']
    return out


# ===================== Medications (direct VPR → quick) =====================

def _fileman_to_iso(val: Any) -> Optional[str]:
    """Convert FileMan date/time (YYYMMDD[.HHMM[SS]]) to ISO8601 Z.
    YYY = year - 1700. Example: 3251029.1430 -> 2025-10-29T14:30:00Z
    """
    try:
        s = str(val).strip()
        if not s:
            return None
        # Accept forms: 7 digits or 7 digits + . + time
        head = s
        tail = ''
        if '.' in s:
            head, tail = s.split('.', 1)
        if not head.isdigit() or len(head) != 7:
            return None
        yyy = int(head[0:3])
        y = yyy + 1700
        m = int(head[3:5])
        d = int(head[5:7])
        hh = mm = ss = 0
        if tail:
            tdigits = ''.join(ch for ch in tail if ch.isdigit())
            if len(tdigits) >= 2:
                hh = int(tdigits[0:2])
            if len(tdigits) >= 4:
                mm = int(tdigits[2:4])
            if len(tdigits) >= 6:
                ss = int(tdigits[4:6])
        obj = dt.datetime(y, m, d, hh, mm, ss, tzinfo=dt.timezone.utc)
        return obj.isoformat().replace('+00:00', 'Z')
    except Exception:
        return None


def _parse_any_datetime_to_iso(val: Any) -> Optional[str]:
    """Best-effort parse of date representations to ISO8601 Z format.
    Supports ISO, yyyymmdd[HHMMSS], and FileMan YYYMMDD[.HHMM[SS]].
    """
    if val is None:
        return None
    try:
        s = str(val).strip()
        if not s:
            return None
        # Try ISO first
        try:
            if 'T' in s or '-' in s:
                d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
                return d.astimezone(dt.timezone.utc).replace(tzinfo=dt.timezone.utc).isoformat().replace('+00:00', 'Z')
        except Exception:
            pass
        # Try FileMan
        fm = _fileman_to_iso(s)
        if fm:
            return fm
        # yyyymmdd[hhmmss]
        digits = ''.join(ch for ch in s if ch.isdigit())
        if len(digits) >= 8:
            y = int(digits[0:4]); m = int(digits[4:6]); d = int(digits[6:8])
            hh = int(digits[8:10]) if len(digits) >= 10 else 0
            mm = int(digits[10:12]) if len(digits) >= 12 else 0
            ss = int(digits[12:14]) if len(digits) >= 14 else 0
            dt_obj = dt.datetime(y, m, d, hh, mm, ss, tzinfo=dt.timezone.utc)
            return dt_obj.isoformat().replace('+00:00', 'Z')
    except Exception:
        return None
    return None


def to_fileman_datetime(val: Any) -> Optional[str]:
    """Convert common date/time representations to FileMan date/time string.
    Accepted inputs:
      - ISO date or datetime string (e.g., '2025-10-29' or '2025-10-29T14:30:00Z')
      - Digits 'yyyymmdd' optionally followed by HHMM or HHMMSS
      - Existing FileMan date/time (e.g., '3251029' or '3251029.1430') is returned as-is
    Output:
      - 'YYYMMDD' or 'YYYMMDD.HHMM[SS]' where YYY = year-1700
    """
    try:
        if val is None:
            return None
        s = str(val).strip()
        if not s:
            return None
        # Already looks like FileMan date or date.time
        #  - 7 digits (e.g., 3251029) or 7 digits + . + time
        if s.isdigit() and (len(s) == 7):
            return s
        if '.' in s:
            head, tail = s.split('.', 1)
            if head.isdigit() and len(head) == 7 and tail.replace(':','').isdigit():
                # Accept forms like 3251029.1430 or 3251029.14:30
                return head + '.' + tail.replace(':','')
        # ISO date/time
        try:
            iso = s.replace('Z', '+00:00')
            dt_obj = None
            # fromisoformat works for 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM[:SS][+/-offset]'
            dt_obj = dt.datetime.fromisoformat(iso)
            y = dt_obj.year; m = dt_obj.month; d = dt_obj.day
            hh = dt_obj.hour; mm = dt_obj.minute; ss = dt_obj.second
            yyy = y - 1700
            date_part = f"{yyy:03d}{m:02d}{d:02d}"
            if hh or mm or ss:
                # Emit HHMMSS when seconds present, else HHMM
                if ss:
                    return f"{date_part}.{hh:02d}{mm:02d}{ss:02d}"
                return f"{date_part}.{hh:02d}{mm:02d}"
            return date_part
        except Exception:
            pass
        # Digits yyyymmdd[HHMM[SS]] → convert to FileMan
        digits = ''.join(ch for ch in s if ch.isdigit())
        if len(digits) >= 8:
            y = int(digits[0:4]); m = int(digits[4:6]); d = int(digits[6:8])
            yyy = y - 1700
            date_part = f"{yyy:03d}{m:02d}{d:02d}"
            if len(digits) >= 12:
                hh = int(digits[8:10]); mm = int(digits[10:12])
                if len(digits) >= 14:
                    ss = int(digits[12:14])
                    return f"{date_part}.{hh:02d}{mm:02d}{ss:02d}"
                return f"{date_part}.{hh:02d}{mm:02d}"
            return date_part
        return None
    except Exception:
        return None


# --------------------- Relative date helpers ---------------------

def parse_relative_last_to_iso_range(last: str, now: Optional[dt.datetime] = None) -> Optional[tuple[str, str]]:
    """Parse relative phrase like '14d', '6m', '1y', '2w' into (start_iso, stop_iso).
    Units:
      d=days, w=weeks, m=months, y=years, h=hours. Default unit is days if omitted.
    """
    try:
        if not last:
            return None
        s = str(last).strip().lower()
        if not s:
            return None
        # Extract number and unit
        num_str = ''.join(ch for ch in s if ch.isdigit())
        unit = ''.join(ch for ch in s if ch.isalpha()) or 'd'
        if not num_str:
            return None
        n = int(num_str)
        now = now or dt.datetime.now(dt.timezone.utc)
        # Compute delta
        if unit.startswith('h'):
            delta = dt.timedelta(hours=n)
        elif unit.startswith('w'):
            delta = dt.timedelta(weeks=n)
        elif unit.startswith('m'):
            # months: approximate by 30 days per month
            delta = dt.timedelta(days=30*n)
        elif unit.startswith('y'):
            # years: approximate by 365 days per year
            delta = dt.timedelta(days=365*n)
        else:
            delta = dt.timedelta(days=n)
        start = now - delta
        stop = now
        return (start.isoformat().replace('+00:00', 'Z'), stop.isoformat().replace('+00:00', 'Z'))
    except Exception:
        return None


def _normalize_med_status(s: Any) -> str:
    try:
        txt = (str(s or '')).strip().lower()
        if not txt:
            return ''
        if 'active' in txt and 'inactive' not in txt:
            return 'active'
        if 'pend' in txt or 'hold' in txt or 'new' in txt:
            return 'pending'
        if 'expire' in txt or 'expired' in txt:
            return 'completed'
        if 'discon' in txt or 'dc' in txt or 'stop' in txt or 'discontinu' in txt:
            return 'stopped'
        return txt
    except Exception:
        return ''


# NOTE: FHIR medications mapping removed; keeping direct VPR → quick only.


def vpr_to_quick_medications(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Direct VPR → quick mapping for medications (fallback or comparison)."""
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = (
            it.get('display')
            or it.get('qualifiedName')
            or it.get('name')
            or (lambda p: (p[0].get('name') if p and isinstance(p, list) and isinstance(p[0], dict) else None))(it.get('products') or [])
            or ''
        )
        status = _normalize_med_status(it.get('vaStatus') or it.get('statusName') or it.get('status'))
        start = (
            it.get('overallStart') or it.get('start') or it.get('ordered') or it.get('sigStart')
        )
        stop = (
            it.get('overallStop') or it.get('stop') or it.get('discontinuedDate') or it.get('expires') or it.get('expirationDate')
        )
        start_iso = _parse_any_datetime_to_iso(start)
        stop_iso = _parse_any_datetime_to_iso(stop)
        out.append({
            'name': name,
            'status': status,
            'startDate': start_iso,
            'endDate': stop_iso,
        })
    return out


# ===================== Labs =====================

def vpr_to_quick_labs(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'labs' items to a simplified quick shape.
    Fields (quick):
      - name (prefers displayName), result, units, specimen
      - referenceRange (string "low - high" when both present)
      - abnormal (True/False when reference range present; else None)
      - observed (raw Fileman value if present)
      - observedDate (ISO)
    Also include a few compatibility aliases used by UI modules:
      - test (alias of name), unit (alias of units), resulted (ISO, same as observedDate)
      - refRange (legacy alias of referenceRange)
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        uid = it.get('uid') or None
        local_id = it.get('localId') or None
        panel_id = None
        if isinstance(local_id, str):
            parts = [seg for seg in local_id.split(';') if seg]
            if len(parts) >= 2:
                panel_id = parts[1]
        elif isinstance(uid, str):
            seg = uid.rsplit(':', 1)[-1]
            parts = [p for p in seg.split(';') if p]
            if len(parts) >= 2:
                panel_id = parts[1]
        # Name: prefer displayName when present
        name = (
            it.get('displayName')
            or it.get('typeName')
            or it.get('test')
            or it.get('name')
            or it.get('display')
            or ''
        )
        # Result & units
        result = it.get('result') if it.get('result') is not None else it.get('value')
        units = it.get('units') or it.get('unit') or None
        # Specimen/sample
        specimen = it.get('specimen') or it.get('specimenType') or it.get('sample') or it.get('source') or None
        # Reference range: prefer top-level low/high when present; else use referenceRanges[0]
        low = None
        high = None
        try:
            if it.get('low') is not None or it.get('high') is not None:
                low = it.get('low'); high = it.get('high')
            else:
                rr = it.get('referenceRanges')
                if isinstance(rr, list) and rr:
                    r0 = rr[0] or {}
                    low = r0.get('low'); high = r0.get('high')
        except Exception:
            low = None; high = None
        reference_range = None
        if low is not None or high is not None:
            # Build a human-readable range string
            if low is not None and high is not None:
                reference_range = f"{low} - {high}"
            elif low is not None:
                reference_range = f"> {low}"
            elif high is not None:
                reference_range = f"< {high}"
        # Abnormal calculation: only when both low and high are numeric and result is numeric
        abnormal = None
        try:
            def _to_num(x):
                try:
                    if x is None:
                        return None
                    s = str(x).strip()
                    # tolerate values like "5.2*" or "5.2 H"
                    s = ''.join(ch for ch in s if (ch.isdigit() or ch in '.-'))
                    return float(s) if s not in ('', '.', '-', '-.', '.-') else None
                except Exception:
                    return None
            rv = _to_num(result)
            lo_n = _to_num(low)
            hi_n = _to_num(high)
            if rv is not None and lo_n is not None and hi_n is not None:
                abnormal = (rv < lo_n) or (rv > hi_n)
            elif rv is not None and (lo_n is not None or hi_n is not None):
                # When only one bound exists, mark abnormal if outside the single constraint
                if lo_n is not None:
                    abnormal = rv < lo_n
                if hi_n is not None:
                    abnormal = (rv > hi_n) if abnormal is None else (abnormal or (rv > hi_n))
            else:
                abnormal = None
        except Exception:
            abnormal = None
        # Observed/resulted dates
        observed_fm = it.get('observed')
        obs = observed_fm or it.get('resulted') or it.get('collected')
        obs_iso = _parse_any_datetime_to_iso(obs)
        # Build object with friendly names and aliases for UI compatibility
        obj: Dict[str, Any] = {
            'name': name,
            'test': name,               # alias
            'result': result,
            'units': units,
            'unit': units,              # alias
            'specimen': specimen,
            'referenceRange': reference_range,
            'refRange': reference_range,  # legacy alias
            'abnormal': abnormal,
            'observed': observed_fm,    # raw Fileman
            'observedDate': obs_iso,
            'resulted': obs_iso,        # alias preferred by some UIs
            'uid': uid,
            'localId': local_id,
            'panelId': panel_id,
            'category': it.get('category') or None,
            'groupName': it.get('groupName') or None,
            'source': 'vpr',
        }
        out.append(obj)
    return out


# ===================== Vitals =====================

def vpr_to_quick_vitals(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'vitals' items to quick vitals.
    Fields: type, value, units, takenDate
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        vt_raw = (
            it.get('typeCode')
            or it.get('type')
            or it.get('typeName')
            or it.get('vitalType')
            or it.get('name')
            or ''
        )
        code = _normalize_vital_code(vt_raw)
        display = None
        default_unit = None
        if code and code in _VITAL_TYPE_MAP:
            display, default_unit = _VITAL_TYPE_MAP[code]
        if not display:
            display = (it.get('typeName') or it.get('name') or vt_raw or '').strip() or code or ''
        val = it.get('result') or it.get('value') or it.get('measurement') or ''
        units = _sanitize_vital_unit(it.get('units') or it.get('unit'), val)
        if not units:
            units = default_unit
        dt_val = it.get('observed') or it.get('dateTime') or it.get('taken')
        dt_iso = _parse_any_datetime_to_iso(dt_val)
        record: Dict[str, Any] = {
            'type': display,
            'value': val,
            'units': units,
            'takenDate': dt_iso,
        }
        if code:
            record['code'] = code
        if it.get('location'):
            record['location'] = it.get('location')
        out.append(record)
    return out


# ===================== Notes/Documents =====================

def vpr_to_quick_notes(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'documents' (notes) to quick notes list.
    Fields: title, documentType, nationalTitle, status, date, facility, encounterName, author
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # Title preferences: localTitle for display, fallback to generic title
        title = it.get('localTitle') or it.get('title') or it.get('displayName') or ''
        document_type = it.get('documentTypeName') or None
        document_class = it.get('documentClass') or None
        # National title is nested under nationalTitle.title when present
        try:
            nt = it.get('nationalTitle') or {}
            national_title = (nt.get('title') if isinstance(nt, dict) else None) or None
        except Exception:
            national_title = None
        status = it.get('statusName') or it.get('status') or None
        # Prefer referenceDateTime for display; it appears as Fileman-like yyyymmddhhmmss and is converted to ISO
        date = it.get('referenceDateTime') or it.get('dateTime') or it.get('entered')
        date_iso = _parse_any_datetime_to_iso(date)
        facility = it.get('facilityName') or None
        encounter_name = it.get('encounterName') or None
        author = it.get('authorDisplayName') or it.get('clinician') or None
        obj: Dict[str, Any] = {
            'title': title,
            'status': status,
            'date': date_iso,
        }
        if document_type:
            obj['documentType'] = document_type
        if document_class:
            obj['documentClass'] = document_class
        if national_title:
            obj['nationalTitle'] = national_title
        if facility:
            obj['facility'] = facility
        if encounter_name:
            obj['encounterName'] = encounter_name
        if author:
            obj['author'] = author
        out.append(obj)
    return out


# ===================== Radiology =====================

def vpr_to_quick_radiology(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'radiology' items to a document-oriented quick list.
    Fields include:
      - title (localTitle), documentClass, documentType (documentTypeName)
      - nationalSubject (nationalTitleSubject.subject)
      - status, date (prefer dateTime), facility, encounterName
      - exam (fallback display), impression when present
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # Display title and document metadata
        title = it.get('localTitle') or it.get('name') or it.get('procedure') or ''
        document_class = it.get('documentClass') or None
        document_type = it.get('documentTypeName') or None
        # Modality/subject of study
        national_subject = None
        try:
            ns = it.get('nationalTitleSubject') or {}
            national_subject = (ns.get('subject') if isinstance(ns, dict) else None) or None
        except Exception:
            national_subject = None
        status = it.get('statusName') or it.get('status') or None
        # Prefer dateTime for radiology
        date = it.get('dateTime') or it.get('referenceDateTime') or it.get('performed') or it.get('ordered')
        date_iso = _parse_any_datetime_to_iso(date)
        facility = it.get('facilityName') or None
        encounter_name = it.get('encounterName') or None
        impression = it.get('impression') or it.get('report') or None
        exam = it.get('procedure') or it.get('name') or it.get('typeName') or None
        obj: Dict[str, Any] = {
            'title': title,
            'status': status,
            'date': date_iso,
        }
        if document_class:
            obj['documentClass'] = document_class
        if document_type:
            obj['documentType'] = document_type
        if national_subject:
            obj['nationalSubject'] = national_subject
        if facility:
            obj['facility'] = facility
        if encounter_name:
            obj['encounterName'] = encounter_name
        if exam:
            obj['exam'] = exam
        if impression:
            obj['impression'] = impression
        out.append(obj)
    return out


# ===================== Procedures =====================

def vpr_to_quick_procedures(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'procedures' to quick list.
    Fields: name, date, status
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get('name') or it.get('procedure') or it.get('typeName') or ''
        date = it.get('dateTime') or it.get('performed') or it.get('entered')
        date_iso = _parse_any_datetime_to_iso(date)
        status = it.get('statusName') or it.get('status') or None
        out.append({
            'name': name,
            'date': date_iso,
            'status': status,
        })
    return out


# ===================== Encounters (Visits) =====================

def vpr_to_quick_encounters(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'visits' to quick encounters list.
    Fields: type, location, date, status
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        etype = it.get('typeName') or it.get('category') or it.get('serviceCategoryName') or ''
        loc = None
        try:
            loc = (it.get('location') or {}).get('name') or it.get('clinicName') or it.get('locationName')
        except Exception:
            loc = it.get('locationName')
        date = it.get('dateTime') or it.get('appointment') or it.get('checkInTime') or it.get('admitDateTime')
        date_iso = _parse_any_datetime_to_iso(date)
        status = it.get('statusName') or it.get('status') or None
        out.append({
            'type': etype,
            'location': loc,
            'date': date_iso,
            'status': status,
        })
    return out


# ===================== Problems =====================

def vpr_to_quick_problems(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'problems' to a simplified quick list.
    Fields: problem, status, onsetDate, resolvedDate, icdCode, snomedCode
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        problem = (
            it.get('problemText')
            or it.get('summary')
            or it.get('name')
            or it.get('problem')
            or ''
        )
        status = it.get('statusName') or it.get('status') or it.get('clinicalStatus') or None
        onset = it.get('onset') or it.get('dateOfOnset') or it.get('entered')
        resolved = it.get('resolved') or it.get('dateResolved')
        icd = it.get('icdCode') or it.get('icd') or None
        snomed = it.get('snomedCode') or it.get('sctid') or None
        out.append({
            'problem': problem,
            'status': status,
            'onsetDate': _parse_any_datetime_to_iso(onset),
            'resolvedDate': _parse_any_datetime_to_iso(resolved),
            'icdCode': icd,
            'snomedCode': snomed,
        })
    return out


# ===================== Allergies =====================

def vpr_to_quick_allergies(vpr_payload: Any) -> List[Dict[str, Any]]:
    """Map VPR 'allergies' to a simplified quick list.
    Fields: substance, reactions, severity, status, enteredDate
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # Substance name
        substance = (
            it.get('allergenName')
            or (lambda a: (a.get('name') if isinstance(a, dict) else None))(it.get('allergen') or {})
            or it.get('name')
        )
        # Some VPR payloads provide the allergen under products[0].name
        if not substance:
            try:
                products = it.get('products')
                if isinstance(products, list) and products:
                    p0 = products[0]
                    if isinstance(p0, dict):
                        pname = p0.get('name') or p0.get('product') or p0.get('displayName')
                        if pname:
                            substance = pname
            except Exception:
                pass
        substance = substance or ''
        # Reactions as simple list of names
        reactions: List[str] = []
        try:
            rlist = it.get('reactions') or []
            if isinstance(rlist, list):
                for r in rlist:
                    if isinstance(r, dict):
                        nm = r.get('name') or r.get('reaction') or r.get('displayName')
                        if nm:
                            reactions.append(str(nm))
                    elif isinstance(r, str):
                        reactions.append(r)
        except Exception:
            reactions = []
        severity = it.get('severityName') or it.get('severity') or None
        status = it.get('statusName') or it.get('status') or None
        # Some payloads use a boolean/string flag for historical; reflect that in status if not present
        try:
            if not status:
                hist = it.get('historical')
                if isinstance(hist, bool) and hist:
                    status = 'historical'
                elif isinstance(hist, str) and hist.strip().lower() in ('1','true','yes','y'):
                    status = 'historical'
        except Exception:
            pass
        entered = it.get('entered') or it.get('observed') or it.get('onset')
        out.append({
            'substance': substance,
            'reactions': reactions or None,
            'severity': severity,
            'status': status,
            'enteredDate': _parse_any_datetime_to_iso(entered),
        })
    return out
