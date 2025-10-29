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


def _pick_phone(telecoms: Any) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = { 'Phone (mobile)': None, 'Phone (work)': None }
    try:
        arr = telecoms if isinstance(telecoms, list) else []
        for t in arr:
            try:
                usage = (t.get('usageCode') or t.get('usageName') or '').upper()
                num = t.get('telecom') or ''
                if not num:
                    continue
                if 'MC' in usage or 'MOBILE' in usage:
                    out['Phone (mobile)'] = out['Phone (mobile)'] or str(num)
                elif 'WORK' in usage or 'WP' in usage:
                    out['Phone (work)'] = out['Phone (work)'] or str(num)
            except Exception:
                continue
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

def _parse_any_datetime_to_iso(val: Any) -> Optional[str]:
    """Best-effort parse of date representations to ISO8601 Z format."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        if not s:
            return None
        # Try ISO
        try:
            if 'T' in s or '-' in s:
                d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
                return d.astimezone(dt.timezone.utc).replace(tzinfo=dt.timezone.utc).isoformat().replace('+00:00', 'Z')
        except Exception:
            pass
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
    Fields: name, result, units, refRange, abnormal, observedDate
    """
    items = _get_nested_items(vpr_payload)
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get('typeName') or it.get('test') or it.get('name') or it.get('display') or ''
        result = it.get('result') or it.get('value') or ''
        units = it.get('units') or it.get('unit') or None
        ref = None
        try:
            rr = it.get('referenceRanges')
            if isinstance(rr, list) and rr:
                r0 = rr[0] or {}
                lo = r0.get('low'); hi = r0.get('high')
                if lo is not None or hi is not None:
                    ref = f"{lo or ''}-{hi or ''}"
            elif isinstance(rr, str):
                ref = rr
        except Exception:
            pass
        abnormal = None
        try:
            abn = it.get('interpretationName') or it.get('abnormal')
            if isinstance(abn, str):
                abnormal = abn
        except Exception:
            pass
        obs = it.get('observed') or it.get('resulted') or it.get('collected')
        obs_iso = _parse_any_datetime_to_iso(obs)
        out.append({
            'name': name,
            'result': result,
            'units': units,
            'refRange': ref,
            'abnormal': abnormal,
            'observedDate': obs_iso,
        })
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
        vt = it.get('typeName') or it.get('vitalType') or it.get('name') or ''
        val = it.get('result') or it.get('value') or it.get('measurement') or ''
        units = it.get('units') or it.get('unit') or None
        dt_val = it.get('observed') or it.get('dateTime') or it.get('taken')
        dt_iso = _parse_any_datetime_to_iso(dt_val)
        out.append({
            'type': vt,
            'value': val,
            'units': units,
            'takenDate': dt_iso,
        })
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
            or ''
        )
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
