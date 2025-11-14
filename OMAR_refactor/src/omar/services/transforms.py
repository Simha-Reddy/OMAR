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
    """Return (DOB_ISO, DOB_MMM_DD_YYYY) from common VPR DOB representations."""
    try:
        raw = str(date_of_birth or '').strip()
        if not raw:
            return None, None

        # Prefer ISO-style inputs first (yyyy-mm-dd[Thh:mm:ssZ])
        try:
            if '-' in raw or 'T' in raw:
                iso_candidate = raw.replace('Z', '+00:00')
                dt_obj = dt.datetime.fromisoformat(iso_candidate)
                dob_date = dt_obj.date()
            else:
                raise ValueError('not ISO')
        except Exception:
            # Fall back to numeric representations (yyyymmdd or FileMan yyyMMdd)
            digits = ''.join(ch for ch in raw if ch.isdigit())
            if not digits:
                return None, None

            dob_date = None
            if len(digits) >= 8:
                possible_year = int(digits[0:4])
                if possible_year >= 1700:
                    month = int(digits[4:6])
                    day = int(digits[6:8])
                    dob_date = dt.date(possible_year, month, day)
            if dob_date is None and len(digits) >= 7:
                # Treat as FileMan (YYYMMDD[HHMMSS])
                year_offset = int(digits[0:3])
                month = int(digits[3:5])
                day = int(digits[5:7])
                dob_date = dt.date(year_offset + 1700, month, day)
            if dob_date is None:
                return None, None

        iso = dob_date.isoformat()
        mon = dob_date.strftime('%b').upper()
        pretty = f"{mon} {dob_date.day}, {dob_date.year}"
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


def _iso_to_mmddyyyy(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    try:
        text = str(val).strip()
        if not text:
            return None
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        dt_obj = dt.datetime.fromisoformat(text)
        return dt_obj.strftime('%m/%d/%Y')
    except Exception:
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
        def _measurement_entries(container: Dict[str, Any]) -> List[Dict[str, Any]]:
            entries: List[Dict[str, Any]] = []
            block = container.get('measurements')
            if isinstance(block, dict):
                candidates = (
                    block.get('measurement')
                    or block.get('measurements')
                    or block.get('items')
                    or block.get('value')
                )
                if isinstance(candidates, list):
                    entries.extend([c for c in candidates if isinstance(c, dict)])
            elif isinstance(block, list):
                entries.extend([c for c in block if isinstance(c, dict)])
            single = container.get('measurement')
            if isinstance(single, dict):
                entries.append(single)
            elif isinstance(single, list):
                entries.extend([c for c in single if isinstance(c, dict)])
            if not entries:
                entries.append(container)
            return entries

        parent_location = it.get('location') or it.get('facility')
        parent_dt_val = (
            it.get('observed')
            or it.get('observationDateTime')
            or it.get('dateTime')
            or it.get('taken')
            or it.get('when')
            or it.get('entered')
        )
        parent_dt_iso = _parse_any_datetime_to_iso(parent_dt_val)

        for entry in _measurement_entries(it):
            if not isinstance(entry, dict):
                continue
            vt_raw = (
                entry.get('typeCode')
                or entry.get('type')
                or entry.get('typeName')
                or entry.get('vitalType')
                or entry.get('name')
                or entry.get('label')
                or it.get('typeCode')
                or it.get('type')
                or it.get('name')
                or ''
            )
            val = (
                entry.get('result')
                or entry.get('value')
                or entry.get('measurement')
                or entry.get('reading')
                or ''
            )
            # Skip entries with no identifying type and no value
            if not str(vt_raw).strip() and not str(val).strip():
                continue

            code = _normalize_vital_code(vt_raw)
            display = None
            default_unit = None
            if code and code in _VITAL_TYPE_MAP:
                display, default_unit = _VITAL_TYPE_MAP[code]
            if not display:
                display = (
                    entry.get('typeName')
                    or entry.get('name')
                    or entry.get('label')
                    or str(vt_raw)
                    or code
                    or ''
                ).strip()

            units_raw = entry.get('units') or entry.get('unit') or entry.get('ucumUnits')
            units = _sanitize_vital_unit(units_raw, val)
            if not units and isinstance(units_raw, str) and units_raw.strip():
                units = units_raw.strip()
            if not units:
                units = default_unit

            dt_val = (
                entry.get('observed')
                or entry.get('observationDateTime')
                or entry.get('dateTime')
                or entry.get('taken')
                or parent_dt_val
            )
            dt_iso = _parse_any_datetime_to_iso(dt_val) or parent_dt_iso

            record: Dict[str, Any] = {
                'type': display,
                'value': val,
                'units': units,
                'takenDate': dt_iso,
            }
            if code:
                record['code'] = code
            location = entry.get('location') or parent_location
            if location:
                record['location'] = location
            measurement_id = entry.get('id') or entry.get('measurementId')
            if measurement_id is not None:
                record['measurementId'] = str(measurement_id)
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
            # Some feeds use 'name' instead of 'title'
            national_title = None
            if isinstance(nt, dict):
                national_title = nt.get('title') or nt.get('name') or None
        except Exception:
            national_title = None
        status = it.get('statusName') or it.get('status') or None
        # Prefer referenceDateTime for display; it appears as Fileman-like yyyymmddhhmmss and is converted to ISO
        date = it.get('referenceDateTime') or it.get('dateTime') or it.get('entered')
        date_iso = _parse_any_datetime_to_iso(date)
        facility = it.get('facilityName') or None
        if not facility:
            try:
                fac_obj = it.get('facility')
                if isinstance(fac_obj, dict):
                    facility = fac_obj.get('name') or fac_obj.get('displayName') or fac_obj.get('value') or None
            except Exception:
                facility = facility
        encounter_name = it.get('encounterName') or None
        if not encounter_name:
            try:
                enc_obj = it.get('encounter')
                if isinstance(enc_obj, dict):
                    encounter_name = enc_obj.get('name') or enc_obj.get('displayName') or enc_obj.get('value') or None
            except Exception:
                encounter_name = encounter_name

        def _coerce_author_name(source: Any) -> Optional[str]:
            if source is None:
                return None
            if isinstance(source, dict):
                for key in ('displayName', 'name', 'text', 'value'):
                    val = source.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
                # fall back to joined string if dict has string repr only
                try:
                    # some payloads embed the name under nested 'author' dict
                    nested = source.get('author') if isinstance(source.get('author'), dict) else None
                    if nested:
                        return _coerce_author_name(nested)
                except Exception:
                    pass
                return None
            if isinstance(source, list):
                for entry in source:
                    name = _coerce_author_name(entry)
                    if name:
                        return name
                return None
            if isinstance(source, str):
                s = source.strip()
                return s or None
            try:
                s = str(source).strip()
                return s or None
            except Exception:
                return None

        author_obj = it.get('author') if isinstance(it, dict) else None
        clinicians = None
        def _normalize_clinicians(value: Any) -> Optional[List[Dict[str, Any]]]:
            if isinstance(value, list):
                return [c for c in value if isinstance(c, dict)] or None
            if isinstance(value, dict):
                if 'clinician' in value and isinstance(value['clinician'], list):
                    return [c for c in value['clinician'] if isinstance(c, dict)] or None
                if 'provider' in value and isinstance(value['provider'], list):
                    return [c for c in value['provider'] if isinstance(c, dict)] or None
                return [value] if value else None
            return None

        try:
            clinicians = _normalize_clinicians(it.get('clinicians') or it.get('providers'))
        except Exception:
            clinicians = None
        # Some VPR feeds embed clinician/author info inside the first text block
        # (e.g., items[].text = [ { 'clinicians': [...], 'content': '...' } ]).
        # If top-level clinicians/providers are not present, try to extract from
        # nested text blocks so author/provider fields get propagated.
        if not clinicians:
            try:
                text_blocks = it.get('text') if isinstance(it, dict) else None
                if isinstance(text_blocks, list):
                    for blk in text_blocks:
                        if isinstance(blk, dict):
                            maybe = _normalize_clinicians(blk.get('clinicians') or blk.get('providers'))
                            if maybe:
                                clinicians = maybe
                                break
            except Exception:
                clinicians = clinicians
        author_record = None
        if isinstance(clinicians, list):
            for c in clinicians:
                if not isinstance(c, dict):
                    continue
                role = str(c.get('role') or '').strip().upper()
                if role == 'A':
                    author_record = c
                    break
            if author_record is None:
                author_record = next((c for c in clinicians if isinstance(c, dict)), None)

        author = (
            _coerce_author_name(it.get('authorDisplayName'))
            or _coerce_author_name(it.get('clinician'))
            or _coerce_author_name(author_record.get('name') if isinstance(author_record, dict) else None)
            or _coerce_author_name(it.get('authorName'))
            or _coerce_author_name(author_obj)
        )

        if isinstance(author_obj, dict):
            if not author:
                author = _coerce_author_name(author_obj)
            provider_type = author_obj.get('providerType') or author_obj.get('type') or None
            provider_class = author_obj.get('classification') or author_obj.get('specialization') or None
        else:
            provider_type = None
            provider_class = None

        # When clinician record present, prefer its metadata but keep existing values as fallback
        if isinstance(author_record, dict):
            provider_type = provider_type or author_record.get('providerType') or author_record.get('type') or author_record.get('service') or None
            provider_class = provider_class or author_record.get('classification') or author_record.get('specialization') or None

        # If author arrived as dict on the item itself, preserve it for potential client needs
        if isinstance(author_obj, dict) and author:
            author_obj = dict(author_obj)
            author_obj['name'] = author  # ensure name key aligns with display
        else:
            author_obj = None

        # TIU identifiers needed for downstream viewers/text fetches
        local_id = it.get('localId') or it.get('id') or None
        uid = it.get('uid') or None
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
        if author_obj:
            obj['_author'] = author_obj
        if provider_type:
            pt = str(provider_type).strip()
            if pt:
                obj['authorProviderType'] = pt
        if provider_class:
            pc = str(provider_class).strip()
            if pc:
                obj['authorClassification'] = pc
        if local_id is not None:
            lid = str(local_id).strip()
            if lid:
                obj['docId'] = lid
        if uid is not None:
            uid_val = str(uid).strip()
            if uid_val:
                obj['uid'] = uid_val
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
        status_code = None
        status_val = it.get('statusName')
        if isinstance(status_val, dict):
            status_code = status_val.get('code') or status_val.get('value')
        else:
            status_code = it.get('statusCode') or status_code
        if not status_val:
            status_val = it.get('status')
        if isinstance(status_val, dict):
            status_code = status_code or status_val.get('code') or status_val.get('value')
            status_val = (
                status_val.get('name')
                or status_val.get('displayName')
                or status_val.get('text')
                or status_val.get('status')
            )
        if not status_val:
            status_val = it.get('clinicalStatus')
        clinical_status = it.get('clinicalStatus')
        if isinstance(clinical_status, dict):
            clinical_status = (
                clinical_status.get('name')
                or clinical_status.get('displayName')
                or clinical_status.get('text')
            )
        if isinstance(status_val, dict):
            status_val = (
                status_val.get('name')
                or status_val.get('displayName')
                or status_val.get('text')
                or status_val.get('status')
            )
        if status_val is None:
            status_val = ''
        status = str(status_val).strip() or None
        status_code_out = None
        if status_code is not None:
            status_code_out = str(status_code).strip() or None
        clinical_status_out = None
        if clinical_status is not None:
            clinical_status_out = str(clinical_status).strip() or None
        onset = it.get('onset') or it.get('dateOfOnset') or it.get('entered')
        resolved = it.get('resolved') or it.get('dateResolved')
        icd = it.get('icdCode') or it.get('icd') or None
        snomed = it.get('snomedCode') or it.get('sctid') or None
        comment_entries: List[Dict[str, Any]] = []
        flat_comments: List[str] = []
        try:
            raw_comments = it.get('comments') or []
            if isinstance(raw_comments, list):
                for comment in raw_comments:
                    text_val = None
                    entered_by_val = None
                    entered_val = None
                    if isinstance(comment, dict):
                        text_val = comment.get('commentText') or comment.get('text') or comment.get('comment')
                        entered_by_val = comment.get('enteredBy') or comment.get('user')
                        entered_val = comment.get('entered') or comment.get('date') or comment.get('timestamp')
                    elif isinstance(comment, str):
                        text_val = comment
                    if text_val is None:
                        continue
                    text = str(text_val).strip()
                    if text.startswith('-'):
                        text = text[1:].strip()
                    if not text:
                        continue
                    entry: Dict[str, Any] = { 'text': text }
                    if entered_by_val:
                        entry['enteredBy'] = str(entered_by_val)
                    if entered_val:
                        entered_iso = _parse_any_datetime_to_iso(entered_val)
                        entered_display = _iso_to_mmddyyyy(entered_iso)
                        if entered_display or entered_iso:
                            entry['entered'] = entered_display or entered_iso
                    comment_entries.append(entry)
                    flat_comments.append(text)
        except Exception:
            comment_entries = []
            flat_comments = []
        problem_text = str(problem or '').strip()
        problem_clean = problem_text
        extracted_snomed = None
        if '(SCT' in problem_clean:
            idx = problem_clean.find('(SCT')
            tail = problem_clean[idx:]
            problem_clean = problem_clean[:idx].rstrip(' -')
            code_parts = tail.split()
            if len(code_parts) >= 2:
                extracted = ''.join(ch for ch in code_parts[1] if ch.isdigit())
                if extracted:
                    extracted_snomed = extracted
        onset_iso = _parse_any_datetime_to_iso(onset)
        onset_display = _iso_to_mmddyyyy(onset_iso)
        resolved_iso = _parse_any_datetime_to_iso(resolved)
        resolved_display = _iso_to_mmddyyyy(resolved_iso)
        record = {
            'problem': problem_clean,
            'status': status,
            'statusCode': status_code_out,
            'clinicalStatus': clinical_status_out,
            'onsetDate': onset_display or onset_iso,
            'resolvedDate': resolved_display or resolved_iso,
            'icdCode': icd,
            'snomedCode': extracted_snomed or snomed,
        }
        if comment_entries:
            record['comments'] = comment_entries
        if flat_comments:
            record['commentText'] = ' • '.join(flat_comments)
        out.append(record)
    return out


# ===================== Orders =====================

_ORDER_COMPLETED_TOKENS = (
    'complete', 'completed', 'comp', 'resulted', 'done', 'finished', 'final', 'finalized'
)
_ORDER_DISCONTINUED_TOKENS = (
    'discontinue', 'discontinued', 'cancel', 'cancelled', 'canceled', 'void', 'voided',
    'stopped', 'stop', 'expired', 'exp', 'lapsed'
)
_ORDER_PENDING_TOKENS = (
    'pending', 'pend', 'hold', 'draft', 'unsigned', 'pre-release', 'prerelease',
    'in process', 'inprocess', 'in-progress', 'new', 'not signed', 'requires signature'
)
_ORDER_ACTIVE_TOKENS = (
    'active', 'current', 'released', 'processing', 'in effect', 'in-effect', 'in force',
    'inforce'
)


def _order_extract_value(node: Any) -> Optional[Any]:
    if node is None:
        return None
    if isinstance(node, dict):
        # Prefer common attribute-style keys (supports xmltodict-style '@' keys as well)
        preferred = ('value', 'name', 'text', 'content', 'string', 'code', 'id', 'number', '#text')
        for cand_key in preferred:
            for key, val in node.items():
                try:
                    norm = str(key).lstrip('@').lower()
                except Exception:
                    norm = ''
                if norm == cand_key.lstrip('@').lower():
                    if isinstance(val, (list, dict)):
                        extracted = _order_extract_value(val)
                    else:
                        extracted = val
                    if extracted not in (None, ''):
                        return extracted
        # Fallback: inspect remaining nested values
        for candidate in node.values():
            extracted = _order_extract_value(candidate)
            if extracted not in (None, ''):
                return extracted
        return None
    if isinstance(node, list):
        for item in node:
            extracted = _order_extract_value(item)
            if extracted not in (None, ''):
                return extracted
        return None
    return node


def _order_extract_string(node: Any) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, list):
        pieces = [ _order_extract_string(item) for item in node ]
        pieces = [p for p in pieces if p]
        if pieces:
            return '\n'.join(pieces)
        return None
    if isinstance(node, dict):
        value = _order_extract_value(node)
    else:
        value = node
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _order_extract_datetime(node: Any) -> tuple[Optional[str], Optional[str]]:
    raw_val = _order_extract_value(node)
    if raw_val is None:
        return None, None
    raw_str = str(raw_val).strip()
    if not raw_str:
        return None, None
    iso = _parse_any_datetime_to_iso(raw_str)
    return raw_str, iso


def _order_attr(node: Any, key: str) -> Optional[str]:
    if not isinstance(node, dict):
        return None
    target = key.lower()
    for cand, value in node.items():
        try:
            norm = str(cand).lstrip('@').lower()
        except Exception:
            norm = ''
        if norm == target:
            if isinstance(value, (dict, list)):
                extracted = _order_extract_value(value)
            else:
                extracted = value
            if extracted in (None, ''):
                continue
            text = str(extracted).strip()
            if text:
                return text
    return None


def _order_status_bucket(name: Optional[str], code: Optional[str]) -> str:
    tokens: list[str] = []
    for raw in (name, code):
        if raw is None:
            continue
        norm = str(raw).strip().lower()
        if norm:
            tokens.append(norm)
    for token in tokens:
        if any(marker in token for marker in _ORDER_DISCONTINUED_TOKENS):
            return 'discontinued'
    for token in tokens:
        if any(marker in token for marker in _ORDER_COMPLETED_TOKENS):
            return 'completed'
    for token in tokens:
        if any(marker in token for marker in _ORDER_PENDING_TOKENS):
            return 'pending'
    for token in tokens:
        if any(marker in token for marker in _ORDER_ACTIVE_TOKENS):
            return 'active'
    if tokens:
        return 'other'
    return 'unknown'


def _order_categorize(service: Optional[str], group: Optional[str], order_type: Optional[str], name: Optional[str]) -> str:
    service_low = (service or '').strip().lower()
    group_low = (group or '').strip().lower()
    type_low = (order_type or '').strip().lower()
    name_low = (name or '').strip().lower()

    def contains_any(text: str, needles: tuple[str, ...]) -> bool:
        return any(needle in text for needle in needles if needle)

    if (
        service_low.startswith('lr')
        or group_low in {'ch', 'mi', 'sp', 'cy', 'ap', 'lab'}
        or contains_any(type_low, ('lab', 'chem', 'hemat', 'micro', 'path', 'specimen', 'culture'))
        or contains_any(name_low, ('lab', 'panel', 'cbc', 'chem', 'culture', 'pathology', 'specimen'))
    ):
        return 'labs'
    if (
        service_low.startswith('ps')
        or service_low in {'pha', 'pharm', 'pharmacy'}
        or group_low in {'med', 'rx', 'ps', 'psj', 'pharm', 'unit dose', 'clinicmed'}
        or contains_any(type_low, ('med', 'pharm', 'prescription', 'drug', 'dose'))
        or contains_any(name_low, ('med', 'pharm', 'tablet', 'capsule', 'dose', 'rx'))
    ):
        return 'meds'
    if (
        service_low.startswith('ra')
        or 'radiology' in service_low
        or 'imaging' in service_low
        or group_low in {'imaging', 'rad', 'ra'}
        or contains_any(type_low, ('imaging', 'radiology', 'x-ray', 'xray', 'ct', 'mri', 'ultrasound', 'nuclear'))
        or contains_any(name_low, ('imaging', 'radiology', 'x-ray', 'xray', 'ct ', ' mri', 'ultrasound', 'nuclear', 'pet'))
    ):
        return 'imaging'
    if (
        service_low in {'gmrc', 'consult', 'con'}
        or contains_any(type_low, ('consult', 'referral'))
        or contains_any(name_low, ('consult', 'referral'))
    ):
        return 'consults'
    if (
        'nurs' in service_low
        or 'nurse' in group_low
        or contains_any(type_low, ('nurs', 'nursing'))
        or contains_any(name_low, ('nurs', 'nursing'))
    ):
        return 'nursing'
    return 'other'


def vpr_to_quick_orders(vpr_payload: Any) -> List[Dict[str, Any]]:
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        order_id = _order_extract_string(it.get('id'))
        uid_val = _order_extract_string(it.get('uid'))
        result_id = _order_extract_string(it.get('resultID'))

        name_node = it.get('name')
        content_preview = (
            _order_extract_string(it.get('contentPreview'))
            or _order_extract_string(it.get('contentText'))
            or _order_extract_string(it.get('content'))
            or _order_extract_string(it.get('instructionsText'))
            or _order_extract_string(it.get('instructions'))
        )
        order_name = (
            _order_extract_string(name_node)
            or _order_extract_string(it.get('summary'))
            or _order_extract_string(it.get('displayName'))
            or _order_extract_string(it.get('description'))
            or _order_extract_string(it.get('text'))
            or _order_extract_string(it.get('orderName'))
            or ''
        )
        if not order_name and content_preview:
            first_line = content_preview.splitlines()[0].strip()
            order_name = first_line or content_preview.strip()
        if not order_name:
            order_name = (
                _order_extract_string(it.get('displayGroup'))
                or _order_extract_string(it.get('group'))
                or _order_extract_string(it.get('service'))
                or _order_extract_string(it.get('typeName'))
                or _order_extract_string(it.get('type'))
                or ''
            )
        if order_name and len(order_name) > 160:
            order_name = order_name[:160].rstrip()
        name_code = None
        if isinstance(name_node, dict):
            name_code = (
                _order_attr(name_node, 'code')
                or _order_attr(name_node, 'value')
                or _order_attr(name_node, 'id')
            )

        group_val = _order_extract_string(it.get('group'))
        service_val = _order_extract_string(it.get('service'))
        priority_val = _order_extract_string(it.get('priority'))

        type_node = it.get('type')
        order_type_name = _order_extract_string(type_node)
        order_type_code = None
        if isinstance(type_node, dict):
            order_type_code = (
                _order_attr(type_node, 'code')
                or _order_attr(type_node, 'value')
            )

        status_node = it.get('status')
        status_name = _order_extract_string(status_node)
        status_code = None
        status_vuid = None
        if isinstance(status_node, dict):
            status_code = (
                _order_attr(status_node, 'code')
                or _order_attr(status_node, 'value')
            )
            status_vuid = _order_attr(status_node, 'vuid')
            if not status_name:
                status_name = _order_attr(status_node, 'name')

        signature_status = _order_extract_string(it.get('signatureStatus'))

        facility_dict = it.get('facility')
        facility_name = None
        facility_code = None
        if isinstance(facility_dict, dict):
            facility_name = _order_extract_string(facility_dict.get('name')) or _order_extract_string(facility_dict)
            facility_code = _order_attr(facility_dict, 'code')

        location_dict = it.get('location')
        location_name = None
        location_code = None
        if isinstance(location_dict, dict):
            location_name = _order_extract_string(location_dict.get('name')) or _order_extract_string(location_dict)
            location_code = _order_attr(location_dict, 'code')

        provider_dict = it.get('provider')
        provider_obj = None
        if isinstance(provider_dict, dict):
            provider_code = (
                _order_attr(provider_dict, 'code')
                or _order_attr(provider_dict, 'id')
                or _order_extract_string(provider_dict.get('code') or provider_dict.get('id'))
            )
            provider_name = (
                _order_attr(provider_dict, 'name')
                or _order_extract_string(provider_dict.get('name'))
            )
            provider_id = (
                _order_attr(provider_dict, 'id')
                or _order_extract_string(provider_dict.get('id'))
            )
            provider_npi = (
                _order_attr(provider_dict, 'npi')
                or _order_extract_string(provider_dict.get('npi'))
            )
            provider_phone = (
                _order_attr(provider_dict, 'officePhone')
                or _order_attr(provider_dict, 'phone')
                or _order_extract_string(provider_dict.get('officePhone') or provider_dict.get('phone'))
            )
            provider_service = (
                _order_attr(provider_dict, 'service')
                or _order_extract_string(provider_dict.get('service'))
            )
            provider_title = (
                _order_attr(provider_dict, 'title')
                or _order_extract_string(provider_dict.get('title'))
            )
            provider_candidate = {
                'code': provider_code,
                'name': provider_name,
                'id': provider_id,
                'npi': provider_npi,
                'phone': provider_phone,
                'service': provider_service,
                'title': provider_title,
            }
            provider_obj = {k: v for k, v in provider_candidate.items() if v}
            if not provider_obj:
                provider_obj = None

        entered_raw, entered_iso = _order_extract_datetime(it.get('entered'))
        start_raw, start_iso = _order_extract_datetime(it.get('start'))
        stop_raw, stop_iso = _order_extract_datetime(it.get('stop'))
        released_raw, released_iso = _order_extract_datetime(it.get('released'))
        signed_raw, signed_iso = _order_extract_datetime(it.get('signed'))

        signed_dict = it.get('signed') if isinstance(it.get('signed'), dict) else {}
        signed_by = None
        signed_by_name = None
        if isinstance(signed_dict, dict):
            signed_by = (
                _order_attr(signed_dict, 'by')
                or _order_attr(signed_dict, 'byCode')
                or _order_extract_string(signed_dict.get('by') or signed_dict.get('byCode'))
            )
            signed_by_name = (
                _order_attr(signed_dict, 'byName')
                or _order_attr(signed_dict, 'name')
                or _order_extract_string(signed_dict.get('byName') or signed_dict.get('name'))
            )

        discontinued_dict = it.get('discontinued') if isinstance(it.get('discontinued'), dict) else {}
        discontinued_raw = None
        discontinued_iso = None
        discontinued_reason = None
        discontinued_by = None
        discontinued_by_name = None
        if isinstance(discontinued_dict, dict):
            discontinued_raw = (
                _order_attr(discontinued_dict, 'date')
                or _order_attr(discontinued_dict, 'value')
                or _order_extract_string(discontinued_dict.get('date'))
                or _order_extract_string(discontinued_dict.get('value'))
                or _order_extract_string(discontinued_dict)
            )
            if discontinued_raw:
                discontinued_iso = _parse_any_datetime_to_iso(discontinued_raw)
            discontinued_reason = (
                _order_attr(discontinued_dict, 'reason')
                or _order_extract_string(discontinued_dict.get('reason'))
            )
            discontinued_by = (
                _order_attr(discontinued_dict, 'by')
                or _order_extract_string(discontinued_dict.get('by'))
            )
            discontinued_by_name = (
                _order_attr(discontinued_dict, 'byName')
                or _order_extract_string(discontinued_dict.get('byName'))
            )

        instructions_text = (
            _order_extract_string(it.get('content'))
            or _order_extract_string(it.get('comment'))
            or _order_extract_string(it.get('comments'))
        )
        sig_text = _order_extract_string(it.get('sig') or it.get('sigText'))
        indication_text = _order_extract_string(it.get('indication') or it.get('reason') or it.get('diagnosis'))

        category_key = _order_categorize(service_val, group_val, order_type_name, order_name)
        category_title_map = {
            'labs': 'Labs',
            'meds': 'Meds',
            'imaging': 'Imaging',
            'consults': 'Consults',
            'nursing': 'Nursing',
            'other': 'Other',
        }
        type_display = category_title_map.get(category_key, 'Other')

        status_bucket = _order_status_bucket(status_name, status_code)
        current_status_display = (str(status_name).strip() if status_name else '')
        if not current_status_display and status_code:
            current_status_display = str(status_code).upper()

        status_code_disp = str(status_code).upper() if status_code else None

        date_iso = next(
            (ts for ts in (start_iso, released_iso, entered_iso, signed_iso, stop_iso) if ts),
            None
        )
        fm_date = next(
            (ts for ts in (start_raw, entered_raw, released_raw, signed_raw, stop_raw) if ts),
            None
        )

        record: Dict[str, Any] = {
            'uid': uid_val,
            'order_id': order_id,
            'id': order_id,
            'result_id': result_id,
            'name': order_name,
            'code': name_code,
            'group': group_val,
            'service': service_val,
            'priority': priority_val,
            'type': type_display,
            'type_detail': order_type_name,
            'type_code': order_type_code,
            'category': category_key,
            'current_status': current_status_display,
            'status': current_status_display,
            'status_code': status_code_disp,
            'status_bucket': status_bucket,
            'status_vuid': status_vuid,
            'signature_status': signature_status,
            'facility_name': facility_name,
            'facility_code': facility_code,
            'location_name': location_name,
            'location_code': location_code,
            'provider_name': provider_obj.get('name') if provider_obj else None,
            'provider': provider_obj,
            'entered': entered_iso,
            'entered_fm': entered_raw,
            'start': start_iso,
            'start_fm': start_raw,
            'stop': stop_iso,
            'stop_fm': stop_raw,
            'released': released_iso,
            'released_fm': released_raw,
            'signed': signed_iso,
            'signed_fm': signed_raw,
            'signed_by': signed_by_name or signed_by,
            'signed_by_id': signed_by,
            'discontinued_date': discontinued_iso,
            'discontinued_fm': discontinued_raw,
            'discontinued_reason': discontinued_reason,
            'discontinued_by': discontinued_by_name or discontinued_by,
            'instructions': instructions_text,
            'content': instructions_text,
            'sig': sig_text,
            'indication': indication_text,
            'fm_date': fm_date,
            'date': date_iso,
            'source': 'vpr',
        }

        # Drop keys with null/empty values except for a few identifiers
        cleaned: Dict[str, Any] = {}
        for key, value in record.items():
            if value is None:
                continue
            if isinstance(value, str):
                text = value.strip()
                if not text and key not in {'name', 'current_status', 'status', 'status_code', 'category', 'type', 'date', 'fm_date'}:
                    continue
                cleaned[key] = text if text else ''
            else:
                cleaned[key] = value

        if cleaned.get('name') is None:
            cleaned['name'] = ''
        if 'status_code' not in cleaned and status_code_disp:
            cleaned['status_code'] = status_code_disp
        if 'status_bucket' not in cleaned:
            cleaned['status_bucket'] = status_bucket
        if 'provider' not in cleaned and provider_obj:
            cleaned['provider'] = provider_obj

        out.append(cleaned)

    out.sort(key=lambda rec: (rec.get('date') or '', rec.get('fm_date') or ''), reverse=True)
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
