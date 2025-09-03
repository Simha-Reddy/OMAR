from flask import Blueprint, request, jsonify, session, current_app
from vpr_XML_to_FHIR import vpr_xml_to_fhir_bundle
import time
import datetime  # added for date parsing
import xml.etree.ElementTree as ET  # for lab XML parsing
import threading  # added: global RPC lock
import re as _re  # for regex operations

bp = Blueprint('patient', __name__)

# --- Patient session utilities ---
_DEF_PATIENT_SESSION_KEYS = {
    'vpr_raw_xml',
    'patient_record',
    'patient_meta',
    'fhir_problems',
    'fhir_allergies',
    'fhir_vitals',
    'fhir_labs',
    'fhir_labs_panels',
    'fhir_labs_loinc_index',
    'fhir_labs_summary',
    'fhir_meds',
    'vpr_retrieval_meta'
}

def _clear_patient_session():
    try:
        for k in list(_DEF_PATIENT_SESSION_KEYS):
            try:
                session.pop(k, None)
            except Exception:
                pass
    except Exception:
        pass

# --- Response helpers ---
def _nocache_json(payload: dict):
    """Return a JSON response with no-store cache headers and DFN marker."""
    try:
        dfn = (session.get('patient_meta') or {}).get('dfn')
    except Exception:
        dfn = None
    resp = jsonify(payload)
    try:
        # Strongly prevent caching for patient-scoped data
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        resp.headers['Vary'] = 'Cookie'
        if dfn:
            resp.headers['X-Patient-DFN'] = str(dfn)
    except Exception:
        pass
    return resp

# --- Helper: attempt RPC across context candidates ---
def _invoke_with_context(vista_client, rpc_name, params, context_candidates):
    """Invoke an RPC under one of the provided contexts with strict serialization.
    Ensures a single shared lock is used for all socket operations to avoid concurrent
    context switches and stream desyncs.
    """
    # Establish a process-wide lock and attach to client if missing
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
    ctx_fail_markers = (
        'Application context has not been created',
        'does not exist on server',
        'Context switch failed'
    )
    # Serialize the entire ensure->setContext->invoke/reconnect cycle
    with lock:
        # Ensure base connection alive before attempts
        try:
            if hasattr(vista_client, 'ensure_connected'):
                vista_client.ensure_connected()
        except Exception:
            # If ensure_connected itself fails, force reconnect once
            try:
                vista_client.reconnect()
            except Exception as e:
                raise Exception(f'Pre-invoke reconnect failed: {e}')
        for ctx in context_candidates:
            if not ctx:
                continue
            tries = 0
            while tries < 2:
                try:
                    if hasattr(vista_client, 'call_in_context'):
                        resp = vista_client.call_in_context(rpc_name, params, ctx)
                    else:
                        if getattr(vista_client, 'context', None) != ctx:
                            vista_client.setContext(ctx)
                        resp = vista_client.invokeRPC(rpc_name, params)
                    return resp, ctx
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    if any(m in msg for m in ctx_fail_markers):
                        break  # try next context
                    if tries == 0 and hasattr(vista_client, '_is_reconnectable_error') and vista_client._is_reconnectable_error(e):
                        try:
                            vista_client.reconnect()
                            tries += 1
                            continue
                        except Exception as re:
                            last_err = re
                    break
    raise Exception(f"All contexts failed for {rpc_name}: {context_candidates}. Last error: {last_err}")

# Common context lists (adjust ordering as needed)
CONTEXTS_VPR = [
    'JLV WEB SERVICES',
    'VPR UI CONTEXT',
    'OR CPRS GUI CHART'
]
CONTEXTS_ORWPT = [
    'OR CPRS GUI CHART',
    'JLV WEB SERVICES'
]
CONTEXTS_SDES = ['SDECRPC', 'JLV WEB SERVICES']
# Add TIU contexts for document/note retrieval
CONTEXTS_TIU = [
    'OR CPRS GUI CHART',
    'TIU TEMPLATE',  # may or may not exist; harmless if fails
    'JLV WEB SERVICES'
]

# --- Normalization helpers for granular FHIR endpoints ---
_DEF_MIN_YEAR = 1900

def _first_coding(res_section):
    try:
        codings = (res_section or {}).get('coding') or []
        if codings:
            return codings[0]
    except Exception:
        pass
    return {}

def _parse_date(dt_str):
    if not dt_str:
        return None
    try:
        # fromisoformat handles 'YYYY-MM-DD' and full timestamps
        return datetime.datetime.fromisoformat(dt_str.replace('Z',''))
    except Exception:
        return None

# --- Lab helpers ---

def _fileman_date_to_iso(val: str | None):
    """Convert FileMan date/time (e.g. 3250509.1154) to ISO 8601 Z format.
    FileMan date: YYYMMDD(.HHMM[SS]) where calendar year = YYY + 1700.
    Returns None if cannot parse.
    """
    if not val:
        return None
    try:
        s = str(val)
        if not s or not s.replace('.', '').isdigit():
            return None
        if '.' in s:
            date_part, time_part = s.split('.', 1)
        else:
            date_part, time_part = s, ''
        if len(date_part) != 7:
            return None
        year = 1700 + int(date_part[:3])
        month = int(date_part[3:5])
        day = int(date_part[5:7])
        hour = minute = second = 0
        if time_part:
            # Pad to at least 4 (HHMM). If >=6 use HHMMSS.
            if len(time_part) < 4:
                time_part = time_part.ljust(4, '0')
            if len(time_part) >= 4:
                hour = int(time_part[:2])
                minute = int(time_part[2:4])
            if len(time_part) >= 6:
                second = int(time_part[4:6])
        dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
        return dt.isoformat().replace('+00:00', 'Z')
    except Exception:
        return None


def _index_labs_from_vpr_xml(vpr_xml: str):
    """Parse raw VPR XML <lab> elements into normalized list of dicts.
    Each lab dict includes test, result, unit, low, high, abnormal flag, dates (ISO), and grouping info.
    Sorted descending by resulted (then collected) date.
    """
    if not vpr_xml:
        return []
    try:
        root = ET.fromstring(vpr_xml)
    except Exception:
        return []
    labs = []
    for lab_el in root.findall('.//lab'):
        def attr(tag, attr_name='value'):
            el = lab_el.find(tag)
            if el is None:
                return None
            # Prefer attribute if present, else text
            if attr_name in el.attrib:
                return el.get(attr_name)
            return (el.text or '').strip() or None
        collected_raw = attr('collected')
        resulted_raw = attr('resulted')
        collected_iso = _fileman_date_to_iso(collected_raw)
        resulted_iso = _fileman_date_to_iso(resulted_raw)
        low_s = attr('low')
        high_s = attr('high')
        result_s = attr('result')
        def to_float(x):
            try:
                return float(x)
            except Exception:
                return None
        low = to_float(low_s)
        high = to_float(high_s)
        result_val = to_float(result_s)
        units = attr('units')
        abnormal = False
        if result_val is not None:
            if low is not None and result_val < low:
                abnormal = True
            if high is not None and result_val > high:
                abnormal = True
        test_name = attr('test') or attr('localName')
        loinc = attr('loinc')
        group_name = attr('groupName')
        group_type = (group_name or '')[:2].strip().upper() if group_name else ''
        labs.append({
            'id': attr('id'),
            'orderId': attr('labOrderID'),
            'test': test_name,
            'localName': attr('localName'),
            'loinc': loinc,
            'result': result_val if result_val is not None else result_s,
            'unit': units,
            'low': low,
            'high': high,
            'abnormal': abnormal,
            'collected': collected_iso,
            'resulted': resulted_iso,
            'collectedFileman': collected_raw,
            'resultedFileman': resulted_raw,
            'groupName': group_name,
            'groupType': group_type,
            'status': attr('status'),
            'sample': attr('sample'),
            'specimen': attr('specimen', 'name'),
            'performingLab': attr('performingLab'),
            'provider': attr('provider', 'name'),
            'facility': attr('facility', 'name'),
            'comment': attr('comment')  # now captures element text
        })
    def _sort_key(r):
        dt_str = r.get('resulted') or r.get('collected')
        dt = _parse_date(dt_str) or datetime.datetime(1900,1,1)
        return dt.timestamp()
    labs.sort(key=_sort_key, reverse=True)
    # Add broadCategory + panelKey (same as groupName) post-sort
    for lab in labs:
        gt = lab.get('groupType') or ''
        if gt == 'HE':
            lab['broadCategory'] = 'Hematology'
        elif gt == 'CH':
            lab['broadCategory'] = 'Chemistry'
        else:
            lab['broadCategory'] = 'Other'
        lab['panelKey'] = lab.get('groupName')  # full groupName acts as panel identifier
    return labs


def _build_lab_secondary_indexes(labs):
    """Given list of lab dicts (already sorted desc by date), build:
    panels: list of panel dicts
    loinc_index: mapping loinc -> list(labs)
    summary: per (loinc or test) latest/previous delta
    """
    panels_map = {}
    loinc_index = {}
    # For summary, use codeKey = loinc if present else test name lower
    summary_map = {}
    for lab in labs:
        # Panel grouping
        panel_key = lab.get('panelKey')
        if panel_key:
            p = panels_map.get(panel_key)
            if not p:
                p = {
                    'panelKey': panel_key,
                    'groupName': lab.get('groupName'),
                    'groupType': lab.get('groupType'),
                    'broadCategory': lab.get('broadCategory'),
                    'tests': [],  # list of test names
                    'labIds': [],
                    'loincs': set(),
                    'earliestCollected': None,
                    'latestCollected': None,
                    'earliestResulted': None,
                    'latestResulted': None,
                    'abnormalCount': 0,
                    'total': 0
                }
                panels_map[panel_key] = p
            p['tests'].append(lab.get('test'))
            p['labIds'].append(lab.get('id'))
            if lab.get('loinc'):
                p['loincs'].add(lab.get('loinc'))
            # Dates
            def _upd(date_field, key, mode):
                val = lab.get(key)
                if not val:
                    return
                existing = p[date_field]
                if existing is None:
                    p[date_field] = val
                else:
                    if mode == 'earliest' and val < existing:
                        p[date_field] = val
                    if mode == 'latest' and val > existing:
                        p[date_field] = val
            _upd('earliestCollected', 'collected', 'earliest')
            _upd('latestCollected', 'collected', 'latest')
            _upd('earliestResulted', 'resulted', 'earliest')
            _upd('latestResulted', 'resulted', 'latest')
            if lab.get('abnormal'):
                p['abnormalCount'] += 1
            p['total'] += 1
        # LOINC index
        loinc = lab.get('loinc')
        if loinc:
            loinc_index.setdefault(loinc, []).append(lab)
        # Summary
        code_key = (loinc or (lab.get('test') or '')).strip().lower()
        if not code_key:
            continue
        s = summary_map.get(code_key)
        if not s:
            summary_map[code_key] = {
                'codeKey': code_key,
                'loinc': loinc,
                'testNames': set([lab.get('test')]) if lab.get('test') else set(),
                'latest': lab,
                'previous': None,
                'count': 1
            }
        else:
            # Already have latest; if previous not set and this lab is different instance, set previous
            s['count'] += 1
            if lab.get('test'):
                s['testNames'].add(lab.get('test'))
            if s['previous'] is None:
                s['previous'] = lab
    # Finalize panels list
    panels = []
    for pk, p in panels_map.items():
        p['loincs'] = sorted(p['loincs'])
        panels.append(p)
    # Sort panels by latestResulted (desc) then latestCollected desc
    def _panel_sort_key(p):
        lr = p.get('latestResulted') or ''
        lc = p.get('latestCollected') or ''
        return (lr, lc)
    panels.sort(key=_panel_sort_key, reverse=True)
    # Build summary list
    summary = []
    for ck, s in summary_map.items():
        latest = s['latest']
        prev = s['previous']
        latest_val = latest.get('result') if latest else None
        prev_val = prev.get('result') if prev else None
        delta = None
        if isinstance(latest_val, (int, float)) and isinstance(prev_val, (int, float)):
            delta = latest_val - prev_val
        summary.append({
            'codeKey': ck,
            'loinc': s['loinc'],
            'testNames': sorted(t for t in s['testNames'] if t),
            'latestResult': latest_val,
            'previousResult': prev_val,
            'delta': delta,
            'unit': latest.get('unit') if latest else None,
            'low': latest.get('low') if latest else None,
            'high': latest.get('high') if latest else None,
            'abnormalLatest': latest.get('abnormal') if latest else None,
            'latestDate': latest.get('resulted') or latest.get('collected') if latest else None,
            'previousDate': prev.get('resulted') or prev.get('collected') if prev else None,
            'count': s['count']
        })
    # Sort summary by latestDate desc
    def _sum_sort_key(r):
        return r.get('latestDate') or ''
    summary.sort(key=_sum_sort_key, reverse=True)
    return panels, loinc_index, summary

# --- Patient safety and demographics helpers ---

def _fileman_to_mmddyyyy(val: str | None):
    """Convert FileMan date (YYYMMDD[.time]) to MM/DD/YYYY for display."""
    if not val:
        return None
    try:
        s = str(val).split('.')[0]
        if len(s) != 7 or not s.isdigit():
            return None
        year = 1700 + int(s[:3])
        month = int(s[3:5])
        day = int(s[5:7])
        return f"{month:02d}/{day:02d}/{year:04d}"
    except Exception:
        return None


def _format_ssn(raw: str | None):
    """Normalize SSN to 555-55-5555 if 9 digits; otherwise return as-is."""
    if not raw:
        return None
    s = str(raw).strip()
    digits = ''.join(ch for ch in s if ch.isdigit())
    if len(digits) == 9:
        return f"{digits[0:3]}-{digits[3:5]}-{digits[5:9]}"
    return s


@bp.route('/vista_sensitive_check', methods=['POST'])
def vista_sensitive_check():
    """Pre-check a patient for sensitive record access using DG SENSITIVE RECORD ACCESS.
    Body: { dfn: string }
    Returns: { allowed: bool, raw: string, message: string }
    """
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    data = request.get_json() or {}
    dfn = (data.get('dfn') or '').strip()
    if not dfn:
        return jsonify({'error': 'dfn required'}), 400
    try:
        raw, used_ctx = _invoke_with_context(vista_client, 'DG SENSITIVE RECORD ACCESS', [dfn], CONTEXTS_ORWPT)
        s = (raw or '').strip()
        allowed = False
        msg = s
        # Typical success is "0^OK". Treat 0 at piece 1 or containing "^OK" as allowed
        pieces = s.split('^') if s else []
        if pieces:
            allowed = (pieces[0].strip() == '0') or (len(pieces) > 1 and pieces[1].strip().upper() == 'OK')
        else:
            allowed = False
        if allowed:
            msg = 'OK'
        return _nocache_json({'allowed': bool(allowed), 'raw': s, 'message': msg, 'context': used_ctx})
    except Exception as e:
        return jsonify({'error': f'Sensitive check failed: {e}'}), 500


@bp.route('/vista_patient_demographics', methods=['POST'])
def vista_patient_demographics():
    """Fetch patient demographics using ORWPT SELECT for confirmation prior to loading.
    Body: { dfn: string }
    Returns: { name, sex, dobFileman, dob, ssn, ssnFormatted, raw }
    """
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    data = request.get_json() or {}
    dfn = (data.get('dfn') or '').strip()
    if not dfn:
        return jsonify({'error': 'dfn required'}), 400
    try:
        raw, used_ctx = _invoke_with_context(vista_client, 'ORWPT SELECT', [dfn], CONTEXTS_ORWPT)
        line = (raw.split('\n')[0] if isinstance(raw, str) else '')
        parts = line.split('^') if line else []
        # Heuristic mapping: default positions commonly NAME^SEX^DOB(FM)^SSN^...
        name = parts[0].strip() if len(parts) >= 1 else ''
        sex = parts[1].strip() if len(parts) >= 2 else ''
        dob_fm = parts[2].strip() if len(parts) >= 3 else ''
        ssn_raw = parts[3].strip() if len(parts) >= 4 else ''
        # Fallback scans if fields missing
        if not dob_fm:
            # look for a piece that looks like 7-digit FM date
            for p in parts:
                ps = p.strip()
                if len(ps.split('.')[0]) == 7 and ps.split('.')[0].isdigit():
                    dob_fm = ps
                    break
        if not ssn_raw:
            for p in parts:
                pd = ''.join(ch for ch in p if ch.isdigit())
                if len(pd) == 9:
                    ssn_raw = pd
                    break
        dob_fmt = _fileman_to_mmddyyyy(dob_fm)
        ssn_fmt = _format_ssn(ssn_raw)
        return _nocache_json({
            'dfn': dfn,
            'name': name,
            'sex': sex,
            'dobFileman': dob_fm,
            'dob': dob_fmt,
            'ssn': ssn_raw,
            'ssnFormatted': ssn_fmt,
            'raw': line,
            'context': used_ctx
        })
    except Exception as e:
        return jsonify({'error': f'Demographics retrieval failed: {e}'}), 500

@bp.route('/vista_rpc', methods=['POST'])
def vista_rpc():
    """Generic socket RPC endpoint (diagnostic). parameters: [{"string": "value"}, ...]"""
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    data = request.get_json() or {}
    rpc = data.get('rpc')
    if not rpc:
        return jsonify({'error': 'rpc required'}), 400
    context_override = data.get('context')
    params_in = data.get('parameters', [])
    params = []
    for p in params_in:
        if isinstance(p, dict) and 'string' in p:
            params.append(p['string'])
        elif isinstance(p, str):
            params.append(p)
    # Choose context list
    if context_override:
        context_candidates = [context_override]
    elif rpc.startswith('ORWPT'):
        context_candidates = CONTEXTS_ORWPT
    elif rpc.startswith('SDES'):
        context_candidates = CONTEXTS_SDES
    elif rpc.startswith('VPR'):
        context_candidates = CONTEXTS_VPR
    elif rpc.startswith('TIU'):
        context_candidates = CONTEXTS_TIU
    else:
        # Fallback try current + JLV
        context_candidates = [vista_client.context, 'JLV WEB SERVICES']
    try:
        raw, used_ctx = _invoke_with_context(vista_client, rpc, params, context_candidates)
        return jsonify({'rpc': rpc, 'context': used_ctx, 'raw': raw})
    except Exception as e:
        return jsonify({'error': str(e), 'rpc': rpc, 'contexts_tried': context_candidates}), 500

@bp.route('/select_patient', methods=['POST'])
def select_patient():
    data = request.get_json() or {}
    patient_dfn = data.get('patient_dfn') or data.get('user_id')
    if not patient_dfn:
        return jsonify({'error': 'No patient DFN provided'}), 400
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500

    # Proactively clear any prior patient's session-scoped data to minimize memory
    _clear_patient_session()

    timings = {}
    t0 = time.time()
    try:
        t_rpc = time.time()
        vpr_xml, used_ctx = _invoke_with_context(vista_client, 'VPR GET PATIENT DATA', [patient_dfn], CONTEXTS_VPR)
        timings['vpr_rpc'] = time.time() - t_rpc
    except Exception as e:
        return jsonify({'error': f'VPR retrieval failed: {e}'}), 500

    t_conv = time.time()
    try:
        fhir_bundle = vpr_xml_to_fhir_bundle(vpr_xml)
        timings['xml_to_fhir'] = time.time() - t_conv
    except Exception as e:
        return jsonify({'error': f'Conversion failed: {e}'}), 500

    # Build labs index BEFORE dropping XML, then release XML to free memory
    try:
        session['fhir_labs'] = _index_labs_from_vpr_xml(vpr_xml)
        panels, loinc_index, summary = _build_lab_secondary_indexes(session['fhir_labs'])
        session['fhir_labs_panels'] = panels
        session['fhir_labs_loinc_index'] = loinc_index
        session['fhir_labs_summary'] = summary
    except Exception:
        session['fhir_labs'] = []
        session['fhir_labs_panels'] = []
        session['fhir_labs_loinc_index'] = {}
        session['fhir_labs_summary'] = []

    # Do NOT persist raw XML in session; drop reference ASAP
    try:
        vpr_xml = None  # allow GC
    except Exception:
        pass

    # Store bundle & patient meta
    session['patient_record'] = fhir_bundle
    patient_name = ''
    try:
        for entry in fhir_bundle.get('entry', []):
            res = entry.get('resource', {})
            if res.get('resourceType') == 'Patient':
                n_arr = res.get('name', [])
                if n_arr:
                    n = n_arr[0]
                    if n.get('text'):
                        patient_name = n['text']
                    else:
                        given = ' '.join(n.get('given', []))
                        family = n.get('family', '')
                        patient_name = (given + ' ' + family).strip()
                break
    except Exception:
        pass
    session['patient_meta'] = {'dfn': patient_dfn, 'name': patient_name}
    # Build problems index (Conditions)
    try:
        session['fhir_problems'] = _index_problems(fhir_bundle)
    except Exception as _e:
        session['fhir_problems'] = []
    # Build allergies index
    try:
        session['fhir_allergies'] = _index_allergies(fhir_bundle)
    except Exception:
        session['fhir_allergies'] = []
    # Build vitals index
    try:
        session['fhir_vitals'] = _index_vitals(fhir_bundle)
        # Prune global vitals cache to only keep current patient to limit memory
        try:
            VITALS_CACHE.clear()
        except Exception:
            pass
        if patient_dfn:
            VITALS_CACHE[patient_dfn] = {'updated': time.time(), 'data': session['fhir_vitals']}
    except Exception:
        session['fhir_vitals'] = {}
    # Build medications index
    try:
        session['fhir_meds'] = _index_medications(fhir_bundle)
    except Exception:
        session['fhir_meds'] = []
    timings['total'] = time.time() - t0
    session['vpr_retrieval_meta'] = {'path': 'socket', 'context': used_ctx, 'patient_dfn': patient_dfn, 'timestamp': time.time()}
    print(f"[TIMING] VPR socket ctx={used_ctx} | " + ' '.join(f"{k}:{v:.2f}s" for k,v in timings.items()))
    return jsonify(fhir_bundle)

@bp.route('/get_patient', methods=['GET'])
def get_patient():
    return _nocache_json(session.get('patient_meta', {}))

@bp.route('/lookup_patient', methods=['POST'])
def lookup_patient():
    data = request.get_json() or {}
    search_type = data.get('type', 'name')
    search_value = data.get('value', '').strip()
    if not search_value:
        return jsonify({'error': 'No search value provided'}), 400
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500

    try:
        if search_type == 'icn':
            rpc = 'SDES GET PATIENT DFN BY ICN'
            context_candidates = CONTEXTS_SDES
            params = [search_value]
            raw, used_ctx = _invoke_with_context(vista_client, rpc, params, context_candidates)
            return jsonify({'raw': raw, 'context': used_ctx})
        else:
            # Name lookup via ORWPT NAMELOOKUP (return lines)
            rpc = 'ORWPT NAMELOOKUP'
            context_candidates = CONTEXTS_ORWPT
            raw, used_ctx = _invoke_with_context(vista_client, rpc, [search_value], context_candidates)
            lines = [line for line in raw.split('\n') if line.strip()]
            results = []
            for line in lines:
                parts = line.split('^')
                if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                    results.append({'dfn': parts[0].strip(), 'name': parts[1].strip(), 'raw': line})
            return jsonify({'matches': results, 'context': used_ctx})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/vista_patient_search', methods=['POST'])
def vista_patient_search():
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    # Proactively ensure connection
    try:
        if hasattr(vista_client, 'ensure_connected'):
            vista_client.ensure_connected()
    except Exception as e:
        return jsonify({'error': f'Connection not available: {e}'}), 500
    data = request.get_json() or {}
    # Normalize: remove exactly one space right after the first comma (e.g., 'JONES, BOB' -> 'JONES,BOB')
    raw_q = (data.get('query') or '')
    q = raw_q.strip()
    try:
        comma = q.find(',')
        if comma != -1 and (comma + 1) < len(q) and q[comma + 1] == ' ':
            q = q[:comma+1] + q[comma+2:]
    except Exception:
        pass
    search_str = q.upper()
    # Optional pagination params for All Patients
    cursor_name = (data.get('cursor') or '').strip()  # use last returned name as cursor
    try:
        page_size = int(data.get('pageSize') or 50)
        if page_size <= 0:
            page_size = 50
        page_size = min(page_size, 200)  # hard cap
    except Exception:
        page_size = 50
    if not search_str:
        return jsonify({'error': 'No search string provided'}), 400
    try:
        rpc_params = []
        next_cursor = None
        if len(search_str) == 5 and search_str[0].isalpha() and search_str[1:].isdigit():
            # LAST5 search (not paginated)
            rpc_name = 'ORWPT LAST5'
            rpc_params = [search_str]
            raw, used_ctx = _invoke_with_context(vista_client, rpc_name, rpc_params, CONTEXTS_ORWPT)
            lines = [line for line in raw.strip().split('\n') if line.strip()]
            matches = []
            for line in lines:
                parts = line.split('^')
                if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                    continue
                dfn, name = parts[0].strip(), parts[1].strip()
                matches.append({'dfn': dfn, 'name': name, 'raw': line})
            return _nocache_json({'matches': matches, 'context': used_ctx, 'rpc': rpc_name, 'hasMore': False, 'nextCursor': None})
        else:
            # Name search via LIST ALL with clever FROM manipulation
            if search_str:
                last = search_str[-1]
                if last == 'A':
                    new_last = '@'
                elif last.isalpha():
                    new_last = chr(ord(last) - 1)
                else:
                    new_last = last
                # Prime FROM just before the intended prefix
                search_mod = search_str[:-1] + new_last + '~'
            else:
                search_mod = '~'
            rpc_name = 'ORWPT LIST ALL'
            # If a cursor is provided (the last returned name), continue from there instead
            from_param = cursor_name + '~' if cursor_name else search_mod
            rpc_params = [from_param, '1']
            raw, used_ctx = _invoke_with_context(vista_client, rpc_name, rpc_params, CONTEXTS_ORWPT)
            lines = [line for line in raw.strip().split('\n') if line.strip()]
            # Build results then page/slice on server to reduce network
            results_all = []
            for line in lines:
                parts = line.split('^')
                if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                    continue
                dfn, name = parts[0].strip(), parts[1].strip()
                # Filter by typed prefix when applicable (server should already be close, but ensure here)
                if not name.upper().startswith(search_str):
                    continue
                results_all.append({'dfn': dfn, 'name': name, 'raw': line})
            # Apply page-size window
            page_matches = results_all[:page_size]
            if len(results_all) > page_size:
                next_cursor = page_matches[-1]['name']
            return _nocache_json({'matches': page_matches, 'context': used_ctx, 'rpc': rpc_name, 'hasMore': bool(next_cursor), 'nextCursor': next_cursor})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'rpc': rpc_name, 'params': rpc_params}), 500

@bp.route('/vpr_source', methods=['GET'])
def vpr_source():
    meta = session.get('vpr_retrieval_meta') or {}
    return jsonify(meta)

@bp.route('/last_primary_care_progress_note', methods=['GET'])
def last_primary_care_progress_note():
    """Return text of the most recent Primary Care Progress Note (by DocumentReference date/appearance).
    Optional query param doc_id to fetch a specific TIU document id.
    """
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    # If explicit doc_id provided, skip bundle search
    explicit_doc_id = request.args.get('doc_id')
    doc_id = None
    title = None
    if not explicit_doc_id:
        bundle = session.get('patient_record') or {}
        entries = bundle.get('entry', [])
        # Collect DocumentReferences
        doc_refs = []
        for e in entries:
            res = e.get('resource', {})
            if res.get('resourceType') == 'DocumentReference':
                t = (res.get('description') or res.get('type', {}).get('text') or '').upper()
                date_str = res.get('date')
                # Parse iso date for sorting; fallback epoch 0
                try:
                    dt = datetime.datetime.fromisoformat(date_str) if date_str else datetime.datetime.min
                except Exception:
                    dt = datetime.datetime.min
                doc_refs.append({
                    'resource': res,
                    'title': t,
                    'date': dt,
                    'id': (res.get('masterIdentifier') or {}).get('value')
                })
        # Filter for Primary Care Progress Note variants
        primary_candidates = [d for d in doc_refs if 'PRIMARY CARE PROGRESS' in d['title']]
        target_list = primary_candidates or doc_refs
        if not target_list:
            return jsonify({'error': 'No DocumentReference resources in session bundle'}), 404
        # Sort by date descending, then fallback to original order (already in list order) if dates equal
        target_list.sort(key=lambda d: d['date'], reverse=True)
        chosen = target_list[0]
        doc_id = chosen['id']
        title = chosen['title']
    else:
        doc_id = explicit_doc_id
        title = None
    if not doc_id:
        return jsonify({'error': 'No document id found'}), 404
    # Fetch TIU text
    try:
        text_raw, used_ctx = _invoke_with_context(vista_client, 'TIU GET RECORD TEXT', [doc_id], CONTEXTS_TIU)
        # TIU GET RECORD TEXT typically returns lines separated by \n or ^ depending on broker; normalize
        if '\r\n' in text_raw:
            lines = text_raw.splitlines()
        else:
            # Some implementations return a single string with embedded line breaks
            lines = text_raw.split('\n')
        return _nocache_json({
            'doc_id': doc_id,
            'title': title,
            'context': used_ctx,
            'line_count': len(lines),
            'text': lines
        })
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve TIU text: {e}', 'doc_id': doc_id}), 500

@bp.route('/documents_text_batch', methods=['POST'])
def documents_text_batch():
    """Batch-fetch TIU note text for multiple document IDs in one socket session.
    Body: { "doc_ids": ["805...", ...] }
    Returns: { "context": "...", "notes": [ { "doc_id": "...", "text": [lines] } | { "doc_id": "...", "error": "..." } ] }
    """
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    data = request.get_json() or {}
    doc_ids = data.get('doc_ids') or []
    if not isinstance(doc_ids, list) or not doc_ids:
        return jsonify({'error': 'doc_ids must be a non-empty list'}), 400
    # Soft cap to protect server
    max_batch = 25
    if len(doc_ids) > max_batch:
        doc_ids = doc_ids[:max_batch]

    # Ensure connection alive
    try:
        if hasattr(vista_client, 'ensure_connected'):
            vista_client.ensure_connected()
    except Exception as e:
        return jsonify({'error': f'Connection not available: {e}'}), 500

    # Determine a working TIU context by trying the first id
    ctx_used = None
    first_text = None
    first_id = str(doc_ids[0])
    last_err = None
    for ctx in CONTEXTS_TIU:
        try:
            # Use atomic helper to both set context and fetch first record
            raw = vista_client.call_in_context('TIU GET RECORD TEXT', [first_id], ctx) if hasattr(vista_client, 'call_in_context') else None
            if raw is None:
                if vista_client.context != ctx:
                    vista_client.setContext(ctx)
                raw = vista_client.invokeRPC('TIU GET RECORD TEXT', [first_id])
            ctx_used = ctx
            # Normalize lines
            if '\r\n' in raw:
                first_lines = raw.splitlines()
            else:
                first_lines = raw.split('\n')
            first_text = first_lines
            break
        except Exception as e:
            last_err = e
            continue
    if not ctx_used:
        return jsonify({'error': f'All TIU contexts failed for batch: {last_err}'}), 500

    # With context established, fetch remaining ids under the same connection lock to avoid races
    results = []
    results.append({'doc_id': first_id, 'text': first_text})
    remaining = [str(x) for x in doc_ids[1:]]
    try:
        if hasattr(vista_client, 'conn_lock'):
            # Hold the connection lock to prevent concurrent context switches
            with vista_client.conn_lock:
                # Ensure context is still the same
                if getattr(vista_client, 'context', None) != ctx_used:
                    vista_client.setContext(ctx_used)
                for did in remaining:
                    try:
                        raw = vista_client.invokeRPC('TIU GET RECORD TEXT', [did])
                        if '\r\n' in raw:
                            lines = raw.splitlines()
                        else:
                            lines = raw.split('\n')
                        results.append({'doc_id': did, 'text': lines})
                    except Exception as e:
                        results.append({'doc_id': did, 'error': str(e)})
        else:
            for did in remaining:
                try:
                    raw = vista_client.invokeRPC('TIU GET RECORD TEXT', [did])
                    if '\r\n' in raw:
                        lines = raw.splitlines()
                    else:
                        lines = raw.split('\n')
                    results.append({'doc_id': did, 'text': lines})
                except Exception as e:
                    results.append({'doc_id': did, 'error': str(e)})
    except Exception as e:
        # If a batch fetch fails mid-way, return what we have with an error field
        return _nocache_json({'context': ctx_used, 'notes': results, 'batch_error': str(e)})

    return _nocache_json({'context': ctx_used, 'notes': results})

@bp.route('/vitals', methods=['GET'])
def get_vitals():
    """Return vitals index with optional date filtering (?start=YYYY-MM-DD&end=YYYY-MM-DD or ISO).
    Adds meta counts. Uses server-side cache keyed by patient DFN.
    """
    meta = session.get('patient_meta') or {}
    dfn = meta.get('dfn')
    if not dfn:
        return jsonify({'error': 'No patient selected'}), 400
    vitals = session.get('fhir_vitals') or (VITALS_CACHE.get(dfn, {}) or {}).get('data') or {}
    # Cache populate if missing in global cache
    if dfn not in VITALS_CACHE and vitals:
        VITALS_CACHE[dfn] = {'updated': time.time(), 'data': vitals}
    start_q = request.args.get('start')
    end_q = request.args.get('end')
    def _parse(q):
        if not q:
            return None
        try:
            return datetime.datetime.fromisoformat(q.replace('Z',''))
        except Exception:
            try:
                return datetime.datetime.strptime(q, '%Y-%m-%d')
            except Exception:
                return None
    start_dt = _parse(start_q)
    end_dt = _parse(end_q)
    filtered = {}
    original_counts = {k: len(v) for k,v in vitals.items()}
    for k, arr in vitals.items():
        new_arr = []
        for rec in arr:
            ts = rec.get('effectiveDateTime')
            try:
                dt = datetime.datetime.fromisoformat(ts.replace('Z','')) if ts else None
            except Exception:
                dt = None
            if start_dt and (not dt or dt < start_dt):
                continue
            if end_dt and (not dt or dt > end_dt):
                continue
            new_arr.append(rec)
        if new_arr:
            filtered[k] = new_arr
    filtered_counts = {k: len(v) for k,v in filtered.items()}
    return _nocache_json({
        'vitals': filtered,
        'meta': {
            'patient_dfn': dfn,
            'originalCounts': original_counts,
            'filteredCounts': filtered_counts,
            'start': start_q,
            'end': end_q,
            'cacheTime': (VITALS_CACHE.get(dfn) or {}).get('updated')
        }
    })

@bp.route('/vitals/summary', methods=['GET'])
def vitals_summary():
    """Return summary of most recent and prior readings with deltas and abnormal flags."""
    meta = session.get('patient_meta') or {}
    dfn = meta.get('dfn')
    if not dfn:
        return jsonify({'error': 'No patient selected'}), 400
    vitals = session.get('fhir_vitals') or (VITALS_CACHE.get(dfn, {}) or {}).get('data') or {}
    summary = {}
    for k, arr in vitals.items():
        if not arr:
            continue
        # arr already sorted chronologically
        last = arr[-1]
        prev = arr[-2] if len(arr) > 1 else None
        if k == 'bloodPressure':
            last_sys = last.get('systolic')
            last_dia = last.get('diastolic')
            prev_sys = prev.get('systolic') if prev else None
            prev_dia = prev.get('diastolic') if prev else None
            summary[k] = {
                'latest': last,
                'previous': prev,
                'deltaSystolic': (last_sys - prev_sys) if (isinstance(last_sys,(int,float)) and isinstance(prev_sys,(int,float))) else None,
                'deltaDiastolic': (last_dia - prev_dia) if (isinstance(last_dia,(int,float)) and isinstance(prev_dia,(int,float))) else None,
                'directionSystolic': ('up' if last_sys > prev_sys else 'down' if last_sys < prev_sys else 'same') if (isinstance(last_sys,(int,float)) and isinstance(prev_sys,(int,float))) else None,
                'directionDiastolic': ('up' if last_dia > prev_dia else 'down' if last_dia < prev_dia else 'same') if (isinstance(last_dia,(int,float)) and isinstance(prev_dia,(int,float))) else None,
                'abnormal': last.get('abnormal')
            }
        else:
            last_val = last.get('value')
            prev_val = prev.get('value') if prev else None
            summary[k] = {
                'latest': last,
                'previous': prev,
                'delta': (last_val - prev_val) if (isinstance(last_val,(int,float)) and isinstance(prev_val,(int,float))) else None,
                'direction': ('up' if last_val > prev_val else 'down' if last_val < prev_val else 'same') if (isinstance(last_val,(int,float)) and isinstance(prev_val,(int,float))) else None,
                'abnormal': last.get('abnormal')
            }
    return _nocache_json({'patient_dfn': dfn, 'summary': summary})

# Add minimal stubs for previously referenced indexing helpers after RAG removal.
VITALS_CACHE = {}

# --- Indexers implementation (Problems, Allergies, Vitals, Medications) ---

def _coding_text(codeable):
    try:
        if not codeable:
            return None
        if isinstance(codeable, dict):
            if codeable.get('text'):
                return codeable.get('text')
            codings = codeable.get('coding') or []
            if codings:
                c0 = codings[0] or {}
                return c0.get('display') or c0.get('code')
    except Exception:
        pass
    return None

def _clinical_status(res):
    try:
        cs = res.get('clinicalStatus') or {}
        cod = (cs.get('coding') or [{}])[0]
        return cod.get('code') or cod.get('display') or (cs.get('text') or '')
    except Exception:
        return ''

def _verification_status(res):
    try:
        vs = res.get('verificationStatus') or {}
        cod = (vs.get('coding') or [{}])[0]
        return cod.get('code') or cod.get('display') or (vs.get('text') or '')
    except Exception:
        return ''

def _safe_iso(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.datetime.fromisoformat(dt_str.replace('Z','')).isoformat().replace('+00:00','Z')
    except Exception:
        return dt_str

def _index_problems(bundle):
    problems = []
    try:
        entries = (bundle or {}).get('entry', [])
        for e in entries:
            res = (e or {}).get('resource', {})
            if res.get('resourceType') != 'Condition':
                continue
            name = _coding_text(res.get('code')) or ''
            categories = []
            cat = res.get('category') or []
            if isinstance(cat, list):
                for c in cat:
                    t = c.get('text') or _coding_text(c)
                    if t:
                        categories.append(t)
            severity = _coding_text(res.get('severity'))
            onset = res.get('onsetDateTime') or ((res.get('onsetPeriod') or {}).get('start')) or None
            abatement = res.get('abatementDateTime') or ((res.get('abatementPeriod') or {}).get('end')) or None
            recorded = res.get('recordedDate') or None
            asserter = ''
            try:
                asserter_ref = res.get('asserter') or {}
                asserter = asserter_ref.get('display') or ''
            except Exception:
                pass
            notes = []
            commentText = None
            try:
                for n in (res.get('note') or []):
                    note_text = n.get('text')
                    notes.append({
                        'text': note_text,
                        'time': n.get('time'),
                        'author': (n.get('authorReference') or {}).get('display') or n.get('authorString')
                    })
                if notes:
                    commentText = '\n'.join([n.get('text') for n in notes if n.get('text')])
            except Exception:
                pass
            codes = ((res.get('code') or {}).get('coding') or [])
            clinical = _clinical_status(res)
            verify = _verification_status(res)
            active = (clinical.lower() == 'active') and not abatement
            problems.append({
                'id': res.get('id'),
                'name': name,
                'codes': codes,
                'category': categories,
                'clinicalStatus': clinical,
                'verificationStatus': verify,
                'severity': severity,
                'onsetDateTime': onset,
                'abatementDateTime': abatement,
                'recordedDate': recorded,
                'asserter': asserter,
                'notes': notes,
                'commentText': commentText,
                'active': active
            })
        # Sort by onset or recorded desc
        def _key(p):
            return p.get('onsetDateTime') or p.get('recordedDate') or ''
        problems.sort(key=_key, reverse=True)
    except Exception:
        problems = []
    return problems

def _index_allergies(bundle):
    allergies = []
    try:
        entries = (bundle or {}).get('entry', [])
        for e in entries:
            res = (e or {}).get('resource', {})
            if res.get('resourceType') != 'AllergyIntolerance':
                continue
            substance_text = _coding_text(res.get('code')) or ''
            codes = ((res.get('code') or {}).get('coding') or [])
            clinical = _clinical_status(res)
            verify = _verification_status(res)
            criticality = res.get('criticality')
            category = res.get('category') or []
            recordedDate = res.get('recordedDate')
            onset = res.get('onsetDateTime') or ((res.get('onsetPeriod') or {}).get('start')) or None
            lastOccurrence = res.get('lastOccurrence')
            reactions = []
            for r in (res.get('reaction') or []):
                mans = []
                for m in (r.get('manifestation') or []):
                    mans.append(_coding_text(m) or '')
                r_notes = []
                for n in (r.get('note') or []):
                    r_notes.append(n.get('text'))
                reactions.append({
                    'manifestations': [m for m in mans if m],
                    'severity': r.get('severity'),
                    'description': r.get('description'),
                    'notes': [t for t in r_notes if t]
                })
            notes = []
            for n in (res.get('note') or []):
                notes.append({
                    'text': n.get('text'),
                    'time': n.get('time'),
                    'author': (n.get('authorReference') or {}).get('display') or n.get('authorString')
                })
            allergies.append({
                'id': res.get('id'),
                'substance': substance_text,
                'codes': codes,
                'clinicalStatus': clinical,
                'verificationStatus': verify,
                'criticality': criticality,
                'category': category,
                'recordedDate': recordedDate,
                'onsetDateTime': onset,
                'lastOccurrence': lastOccurrence,
                'reactions': reactions,
                'notes': notes
            })
        allergies.sort(key=lambda a: a.get('recordedDate') or a.get('onsetDateTime') or '', reverse=True)
    except Exception:
        allergies = []
    return allergies

# Vital sign code map (LOINC)
_VITALS_CODE_MAP = {
    '85354-9': 'bloodPressure',  # BP panel (components)
    '8867-4': 'heartRate',
    '9279-1': 'respiratoryRate',
    '8310-5': 'temperature',
    '59408-5': 'oxygenSaturation',  # SpO2
    '2708-6': 'oxygenSaturation',
    '8302-2': 'height',
    '29463-7': 'weight',
    '39156-5': 'bmi'
}

# BP component codes
_BP_SYSTOLIC = {'8480-6', 'Systolic Blood Pressure', 'systolic'}
_BP_DIASTOLIC = {'8462-4', 'Diastolic Blood Pressure', 'diastolic'}

def _obs_code_to_key(obs):
    try:
        code = (obs.get('code') or {})
        for c in (code.get('coding') or []):
            code_val = (c or {}).get('code')
            if code_val and code_val in _VITALS_CODE_MAP:
                return _VITALS_CODE_MAP[code_val]
        # Fallback by text
        t = code.get('text') or ''
        for k in set(_VITALS_CODE_MAP.values()):
            if k.replace('oxygen', 'oxygen ').lower() in t.lower():
                return k
    except Exception:
        pass
    return None


def _is_abnormal(value, ref_range):
    try:
        if value is None:
            return False
        if not ref_range:
            return False
        low = None
        high = None
        try:
            rr = ref_range[0] if isinstance(ref_range, list) and ref_range else ref_range
            low = (rr.get('low') or {}).get('value')
            high = (rr.get('high') or {}).get('value')
        except Exception:
            pass
        if isinstance(value, (int, float)):
            if low is not None and value < low:
                return True
            if high is not None and value > high:
                return True
        return False
    except Exception:
        return False


def _index_vitals(bundle):
    vitals = {
        'bloodPressure': [],
        'heartRate': [],
        'respiratoryRate': [],
        'temperature': [],
        'oxygenSaturation': [],
        'height': [],
        'weight': [],
        'bmi': []
    }
    try:
        entries = (bundle or {}).get('entry', [])
        for e in entries:
            res = (e or {}).get('resource', {})
            if res.get('resourceType') != 'Observation':
                continue
            # Effective date
            ts = res.get('effectiveDateTime') or ((res.get('effectivePeriod') or {}).get('start'))
            # BP panel
            key = _obs_code_to_key(res)
            if key == 'bloodPressure' or (res.get('component') and any(((c.get('code') or {}).get('text') or '').lower().find('systolic') >= 0 for c in res.get('component', []))):
                sys_val = None
                dia_val = None
                unit = None
                for comp in (res.get('component') or []):
                    cname = (comp.get('code') or {}).get('text') or ''
                    # Match either by code or text
                    codes = (comp.get('code') or {}).get('coding') or []
                    code_set = { (c or {}).get('code') for c in codes }
                    if (code_set & {'8480-6'}) or any('systolic' in (cname or '').lower() for _ in [0]):
                        q = comp.get('valueQuantity') or {}
                        sys_val = q.get('value')
                        unit = unit or q.get('unit')
                    if (code_set & {'8462-4'}) or any('diastolic' in (cname or '').lower() for _ in [0]):
                        q = comp.get('valueQuantity') or {}
                        dia_val = q.get('value')
                        unit = unit or q.get('unit')
                if sys_val is not None or dia_val is not None:
                    # Abnormal via referenceRange? Fallback simple flags if absent
                    abnormal = False
                    if _is_abnormal(sys_val, res.get('referenceRange')) or _is_abnormal(dia_val, res.get('referenceRange')):
                        abnormal = True
                    bp = {
                        'effectiveDateTime': ts,
                        'systolic': sys_val,
                        'diastolic': dia_val,
                        'unit': unit,
                        'abnormal': abnormal
                    }
                    vitals['bloodPressure'].append(bp)
                continue
            # Other simple quantity observations
            if not key:
                continue
            q = res.get('valueQuantity') or {}
            val = q.get('value')
            unit = q.get('unit')
            abnormal = _is_abnormal(val, res.get('referenceRange'))
            vitals[key].append({
                'effectiveDateTime': ts,
                'value': val,
                'unit': unit,
                'abnormal': abnormal
            })
        # Sort each series chronologically
        def _parse_iso(x):
            try:
                return datetime.datetime.fromisoformat((x or '').replace('Z',''))
            except Exception:
                return None
        for k, arr in list(vitals.items()):
            arr.sort(key=lambda r: _parse_iso(r.get('effectiveDateTime')) or datetime.datetime.min)
            if not arr:
                del vitals[k]
    except Exception:
        pass
    return vitals

# --- Medications indexing ---

def _index_medications(bundle):
    meds = []
    try:
        entries = (bundle or {}).get('entry', [])
        for e in entries:
            res = (e or {}).get('resource', {})
            rtype = res.get('resourceType')
            if rtype not in ('MedicationStatement', 'MedicationRequest'):
                continue
            # Name
            name = _coding_text(res.get('medicationCodeableConcept')) or ''
            status = res.get('status')
            start = None
            end = None
            dose = None
            route = None
            frequency = None
            quantity = None
            last_filled = None
            refills = None
            sig = None
            # Medication Class: prefer note[].text, then category text/coding
            med_class = ''
            try:
                notes = res.get('note') or []
                note_texts = [ (n or {}).get('text', '').strip() for n in notes if (n or {}).get('text') ]
                if note_texts:
                    med_class = '; '.join([t for t in note_texts if t])
            except Exception:
                pass
            if not med_class:
                try:
                    cat = res.get('category')
                    if isinstance(cat, list) and cat:
                        for c in cat:
                            if (c or {}).get('text'):
                                med_class = c.get('text')
                                break
                        if not med_class:
                            for c in cat:
                                codings = (c or {}).get('coding') or []
                                for cd in codings:
                                    disp = (cd or {}).get('display') or (cd or {}).get('code')
                                    if disp:
                                        med_class = disp
                                        break
                                if med_class:
                                    break
                    elif isinstance(cat, dict) and cat:
                        med_class = cat.get('text') or (((cat.get('coding') or [{}])[0]).get('display') or ((cat.get('coding') or [{}])[0]).get('code')) or ''
                except Exception:
                    pass

            def _norm_unit(u):
                try:
                    if not u:
                        return ''
                    m = {
                        'MG': 'mg', 'G': 'g', 'MCG': 'mcg', 'UG': 'mcg', 'ML': 'mL', 'L': 'L',
                        'UNITS': 'units', 'IU': 'IU', 'MEQ': 'mEq', 'MMOL': 'mmol', 'PERCENT': '%'
                    }
                    up = str(u).strip().upper()
                    return m.get(up, u)
                except Exception:
                    return u or ''

            def _fmt_qty(q):
                try:
                    if not isinstance(q, dict):
                        return None
                    v = q.get('value')
                    u = q.get('unit') or q.get('code')
                    if v is None and u is None:
                        return None
                    # Normalize numeric value rendering
                    vs = str(v)
                    try:
                        fv = float(vs)
                        vs = str(int(fv)) if abs(fv - int(fv)) < 1e-6 else str(fv)
                    except Exception:
                        pass
                    us = _norm_unit(u)
                    return f"{vs} {us}".strip()
                except Exception:
                    return None

            def _extract_dose_from_di(di_item):
                # Prefer doseAndRate[].doseQuantity; fallback to top-level doseQuantity or doseRange
                try:
                    drs = (di_item or {}).get('doseAndRate') or []
                    for dr in drs:
                        dq = (dr or {}).get('doseQuantity')
                        if isinstance(dq, dict):
                            s = _fmt_qty(dq)
                            if s:
                                return s
                        # Range
                        rng = (dr or {}).get('doseRange')
                        if isinstance(rng, dict):
                            low = _fmt_qty(rng.get('low') or {})
                            high = _fmt_qty(rng.get('high') or {})
                            if low and high:
                                # Use common unit if possible
                                return f"{low} - {high}"
                            if low:
                                return low
                            if high:
                                return high
                    # Fallbacks
                    dq2 = di_item.get('doseQuantity')
                    if isinstance(dq2, dict):
                        s2 = _fmt_qty(dq2)
                        if s2:
                            return s2
                    # As a last resort, attempt to parse strength from medication text (e.g., 500MG)
                    txt = (di_item.get('text') or '')
                    import re as _re
                    m = _re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|mL|IU|units|mEq)\b", txt, flags=_re.I)
                    if m:
                        return f"{m.group(1)} {m.group(2).lower()}".replace('iu','IU')
                except Exception:
                    pass
                return None

            # Dates and dosage parsing
            if rtype == 'MedicationRequest':
                start = res.get('authoredOn') or ((res.get('dosageInstruction') or [{}])[0].get('timing') or {}).get('repeat', {}).get('boundsPeriod', {}).get('start')
                if not start:
                    start = ((res.get('dispenseRequest') or {}).get('validityPeriod') or {}).get('start')
                end = ((res.get('dispenseRequest') or {}).get('validityPeriod') or {}).get('end')
                di = (res.get('dosageInstruction') or [])
                if di:
                    d0 = di[0] or {}
                    sig = d0.get('text') or d0.get('patientInstruction')
                    # dose from structured fields
                    dose = _extract_dose_from_di(d0)
                    # route
                    route = _coding_text(d0.get('route'))
                    # frequency from timing
                    try:
                        t = d0.get('timing') or {}
                        code = _coding_text((t.get('code') or {}))
                        if code:
                            frequency = code
                        else:
                            rpt = (t.get('repeat') or {})
                            if rpt.get('frequency') and rpt.get('period') and rpt.get('periodUnit'):
                                frequency = f"{rpt.get('frequency')} per {rpt.get('period')} {rpt.get('periodUnit')}"
                    except Exception:
                        pass
                try:
                    quantity = ((((res.get('dispenseRequest') or {}).get('quantity') or {}) or {}).get('value'))
                except Exception:
                    quantity = None
                try:
                    refills = (res.get('dispenseRequest') or {}).get('numberOfRepeatsAllowed')
                except Exception:
                    refills = None
                last_filled = start
            else:  # MedicationStatement
                start = res.get('effectiveDateTime') or ((res.get('effectivePeriod') or {}).get('start'))
                end = ((res.get('effectivePeriod') or {}).get('end'))
                di = (res.get('dosage') or [])
                if di:
                    d0 = di[0] or {}
                    sig = d0.get('text') or d0.get('patientInstruction')
                    dose = _extract_dose_from_di(d0)
                    route = _coding_text(d0.get('route'))
                    try:
                        t = d0.get('timing') or {}
                        code = _coding_text((t.get('code') or {}))
                        if code:
                            frequency = code
                        else:
                            rpt = (t.get('repeat') or {})
                            if rpt.get('frequency') and rpt.get('period') and rpt.get('periodUnit'):
                                frequency = f"{rpt.get('frequency')} per {rpt.get('period')} {rpt.get('periodUnit')}"
                    except Exception:
                        pass
                last_filled = res.get('dateAsserted') or start

            updated = None
            try:
                updated = ((res.get('meta') or {}).get('lastUpdated'))
            except Exception:
                pass
            meds.append({
                'id': res.get('id'),
                'resourceType': rtype,
                'medClass': med_class,
                'name': name,
                'dose': dose,
                'route': route,
                'frequency': frequency,
                'quantity': quantity,
                'lastFilled': last_filled,
                'startDate': start,
                'endDate': end,
                'refills': refills,
                'status': status,
                'sig': sig,
                'source': { 'updated': updated }
            })
        meds.sort(key=lambda m: m.get('startDate') or '', reverse=True)
    except Exception:
        meds = []
    return meds

@bp.route('/document_references', methods=['GET'])
def document_references():
    """Return list of DocumentReference items for the current patient session.
    Each item contains: id (TIU doc id if available), date (ISO), title/description, type text, status, author, and best-effort encounter display.
    """
    bundle = session.get('patient_record') or {}
    dfn_meta = (session.get('patient_meta') or {}).get('dfn')
    docs = []
    try:
        # Pre-index encounters for encounter display matching
        encounters_idx = []
        for e in (bundle.get('entry', []) or []):
            res_e = e.get('resource', {}) or {}
            if res_e.get('resourceType') != 'Encounter':
                continue
            # Parse date
            try:
                enc_dt = None
                period = res_e.get('period') or {}
                if period.get('start'):
                    enc_dt = _parse_date(period.get('start'))
            except Exception:
                enc_dt = None
            # Build display
            type_txt = ''
            try:
                t = res_e.get('type') or []
                if t and isinstance(t, list):
                    type_txt = (t[0] or {}).get('text') or ''
            except Exception:
                pass
            if not type_txt:
                try:
                    st = res_e.get('serviceType') or {}
                    type_txt = st.get('text') or ''
                except Exception:
                    pass
            facility = ''
            try:
                sp = res_e.get('serviceProvider') or {}
                facility = sp.get('display') or ''
            except Exception:
                pass
            location_txt = ''
            try:
                locs = res_e.get('location') or []
                if locs:
                    location_txt = ((locs[0] or {}).get('location') or {}).get('display') or ''
            except Exception:
                pass
            parts = [p for p in [type_txt or 'Encounter', facility, location_txt] if p]
            enc_display = ' at '.join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else 'Encounter')
            encounters_idx.append({'dt': enc_dt, 'display': enc_display})
        # Process DocumentReferences
        for entry in bundle.get('entry', []) or []:
            res = entry.get('resource', {}) or {}
            if res.get('resourceType') != 'DocumentReference':
                continue
            # Identify a stable id to later request TIU text
            doc_id = None
            try:
                doc_id = ((res.get('masterIdentifier') or {}).get('value')) or res.get('id')
            except Exception:
                doc_id = res.get('id')
            # Title/description/type
            desc = res.get('description') or ''
            type_text = ''
            try:
                typ = res.get('type') or {}
                type_text = typ.get('text') or ''
            except Exception:
                pass
            # Date
            date_str = res.get('date') or ''
            dt = _parse_date(date_str)
            status = res.get('status') or ''
            # Author (first display)
            author_disp = ''
            try:
                auth = res.get('author') or []
                if auth:
                    author_disp = (auth[0] or {}).get('display') or ''
            except Exception:
                pass
            # Best-effort encounter match: nearest encounter on same day or closest by timestamp
            encounter_display = ''
            if dt and encounters_idx:
                best = None
                best_delta = None
                for enc in encounters_idx:
                    enc_dt = enc.get('dt')
                    if not enc_dt:
                        continue
                    delta = abs((dt - enc_dt).total_seconds())
                    if (best_delta is None) or (delta < best_delta):
                        best_delta = delta
                        best = enc
                # Prefer same-day (within 24 hours)
                if best and best_delta is not None and best_delta <= 86400:
                    encounter_display = best.get('display') or ''
            docs.append({
                'doc_id': doc_id,
                'date': date_str,
                'title': desc or type_text or '',
                'type': type_text,
                'status': status,
                'author': author_disp,
                'encounter': encounter_display
            })
        # Sort by date desc (fallback empty string)
        docs.sort(key=lambda d: d.get('date') or '', reverse=True)
    except Exception:
        docs = []
    try:
        print(f"[patient] /document_references dfn={dfn_meta} count={len(docs)}")
    except Exception:
        pass
    return _nocache_json({'documents': docs, 'count': len(docs)})

@bp.route('/vista_default_patient_list', methods=['GET'])
def vista_default_patient_list():
    """Fetch user's default patient list using ORQPT DEFAULT PATIENT LIST RPC
    Also returns minimal user identity to allow client cache invalidation on user/site change.
    """
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        return jsonify({'error': 'VistA socket client not available'}), 500
    
    try:
        if hasattr(vista_client, 'ensure_connected'):
            vista_client.ensure_connected()
    except Exception as e:
        return jsonify({'error': f'Connection not available: {e}'}), 500
    
    try:
        # Use ORQPT DEFAULT PATIENT LIST to get user's default patient list
        raw, used_ctx = _invoke_with_context(vista_client, 'ORQPT DEFAULT PATIENT LIST', [], CONTEXTS_ORWPT)
        lines = [line for line in raw.strip().split('\n') if line.strip()]
        patients = []
        
        for line in lines:
            parts = line.split('^')
            if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
                continue
            dfn, name = parts[0].strip(), parts[1].strip()
            patient_data = {
                'dfn': dfn, 
                'name': name, 
                'raw': line
            }
            if len(parts) > 2:
                patient_data['clinic'] = parts[2].strip() if len(parts) > 2 else ''
            if len(parts) > 3:
                patient_data['date'] = parts[3].strip() if len(parts) > 3 else ''
            patients.append(patient_data)
        # Also fetch minimal user identity
        user_duz = None
        user_name = None
        user_division = None
        try:
            info_raw, _ctx2 = _invoke_with_context(vista_client, 'ORWU USERINFO', [], CONTEXTS_ORWPT)
            # Typical return: DUZ^USER NAME^...^DIVISION IEN;DIVISION NAME;STATION
            first_line = (info_raw.split('\n')[0] if info_raw else '')
            p = first_line.split('^') if first_line else []
            if len(p) >= 1 and p[0].strip():
                user_duz = p[0].strip()
            if len(p) >= 2 and p[1].strip():
                user_name = p[1].strip()
            # Try to parse division from remainder
            try:
                if len(p) >= 3:
                    div_part = p[-1]
                    # Example: 500;SOME VA;500
                    if ';' in div_part:
                        user_division = div_part.split(';')[-1].strip()
                    else:
                        user_division = div_part.strip()
            except Exception:
                pass
        except Exception:
            pass
        payload = {
            'patients': patients,
            'context': used_ctx,
            'count': len(patients),
            'timestamp': time.time(),
            'user': {
                'duz': user_duz,
                'name': user_name,
                'division': user_division
            }
        }
        return _nocache_json(payload)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'rpc': 'ORQPT DEFAULT PATIENT LIST'}), 500
