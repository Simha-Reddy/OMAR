from datetime import datetime, timedelta
from flask import Blueprint, current_app, jsonify, request, session
import threading
# New imports for lab filtering support
from app.utils import _prepare_lab_filters, _lab_record_matches, _days_ago_cutoff, _in_window, _normalize_term

# Create a single FHIR blueprint and mount under /fhir
bp = Blueprint('fhir', __name__, url_prefix='/fhir')

# --- Small helpers ---

def _parse_date_iso(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z',''))
    except Exception:
        return None

# --------------- ORDERS (live RPC via ORWORR/ORQOR) ---------------

# Connection-safe context invocation (local clone of patient._invoke_with_context minimal)
def _invoke_with_context(vista_client, rpc_name, params, context_candidates):
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
        # Ensure context then invoke
        for ctx in context_candidates:
            try:
                if hasattr(vista_client, 'call_in_context'):
                    raw = vista_client.call_in_context(rpc_name, params, ctx)
                else:
                    if getattr(vista_client, 'context', None) != ctx:
                        vista_client.setContext(ctx)
                    raw = vista_client.invokeRPC(rpc_name, params)
                return raw, ctx
            except Exception as e:
                last_err = e
                # Try next context
                continue
    raise Exception(f"RPC {rpc_name} failed in contexts {context_candidates}: {last_err}")

# Preferred contexts for OR* RPCs
_CONTEXTS_ORDERS = ['OR CPRS GUI CHART', 'JLV WEB SERVICES']

def _orders_status_code(label: str) -> str:
    # Maps to ORWORDG REVSTS codes (see RPC_Orders.txt)
    if not label:
        return '23'  # "Current (Active & Pending)"
    s = label.strip().lower()
    if s in ('active', 'a'):
        return '2'
    if s in ('pending', 'p'):
        return '7'
    if s in ('current', 'active+pending', 'actpend'):
        return '23'
    if s in ('all', '*'):
        return '1'
    return '23'

def _orders_type_label(label: str) -> str:
    if not label:
        return 'all'
    s = label.strip().lower()
    if s in ('med', 'meds', 'medications', 'pharmacy', 'rx'):
        return 'meds'
    if s in ('lab', 'labs', 'laboratory'):
        return 'labs'
    return 'all'

def _dt_to_fileman(dt: datetime) -> float:
    # Fileman date: (year-1700)*10000 + mm*100 + dd, with .HHMM for time
    y = dt.year - 1700
    date_part = y * 10000 + dt.month * 100 + dt.day
    frac = f"{dt.hour:02d}{dt.minute:02d}"
    return float(f"{date_part}.{frac}")

def _fileman_to_iso(fm: str) -> str:
    # Accept "3250819.1146" -> "2025-08-19T11:46:00"
    try:
        s = str(fm)
        if '.' in s:
            d, t = s.split('.', 1)
        else:
            d, t = s, ''
        d = int(d)
        year = 1700 + (d // 10000)
        rem = d % 10000
        month = rem // 100
        day = rem % 100
        hh = 0
        mm = 0
        if t:
            t = t.strip()
            if len(t) >= 2:
                hh = int(t[0:2])
            if len(t) >= 4:
                mm = int(t[2:4])
        return datetime(year, month, day, hh, mm).isoformat()
    except Exception:
        return ""

def _rpc_call(name: str, params):
    vista_client = current_app.config.get('VISTA_CLIENT')
    if not vista_client:
        raise RuntimeError('VistA socket client not available')
    # Choose contexts
    ctxs = _CONTEXTS_ORDERS if name.startswith('OR') else [getattr(vista_client, 'context', None), 'JLV WEB SERVICES']
    raw, used_ctx = _invoke_with_context(vista_client, name, params, ctxs)
    # Normalize lines
    if isinstance(raw, str):
        lines = [ln for ln in raw.splitlines() if ln.strip() != ""]
    elif isinstance(raw, list):
        lines = [str(ln) for ln in raw if str(ln).strip() != ""]
    else:
        lines = []
    return lines

def _parse_orworr_aget(lines):
    # Returns list of dicts with order_id, status_code, fm_date
    out = []
    for ln in lines:
        if ';' not in ln:
            continue
        parts = ln.split('^')
        if len(parts) < 3:
            continue
        order_id = parts[0].strip()  # e.g. "105806961;7"
        status_code = parts[1].strip()
        fm_date = parts[2].strip()
        out.append({'id': order_id, 'status_code': status_code, 'fm_date': fm_date})
    return out

def _detail_order(dfn: str, order_id_with_sub: str):
    # ORQOR DETAIL: Params: orderId;sub, DFN
    lines = _rpc_call('ORQOR DETAIL', [order_id_with_sub, dfn])
    text = "\n".join(lines)
    info = {
        'raw': text,
        'type': 'unknown',
        'name': '',
        'instructions': '',
        'sig': '',
        'indication': '',
        'current_status': ''
    }
    for ln in lines:
        if ln.startswith('Current Status:'):
            info['current_status'] = ln.split(':', 1)[1].strip()
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
                info['name'] = ln.split(':', 1)[1].strip()
            elif s.startswith('Lab Test:'):
                info['type'] = 'labs'
                info['name'] = ln.split(':', 1)[1].strip()
            elif s.startswith('Instructions:'):
                info['instructions'] = ln.split(':', 1)[1].strip()
            elif s.startswith('Sig:'):
                info['sig'] = ln.split(':', 1)[1].strip()
            elif s.startswith('Indication:'):
                info['indication'] = ln.split(':', 1)[1].strip()
    if not info['name'] and lines:
        first = lines[0].strip()
        if first and 'Activity:' not in first and 'Current Data:' not in first:
            info['name'] = first
    return info

def _filter_type(info, want_type: str) -> bool:
    if want_type == 'all':
        return True
    return (info.get('type') == want_type)

def _status_label_for_request(status: str) -> str:
    sc = _orders_status_code(status)
    return f"{sc}^0"

def _within_days(fm_date: str, days: int) -> bool:
    try:
        cutoff = _dt_to_fileman(datetime.now() - timedelta(days=max(0, days)))
        return float(fm_date) >= float(cutoff)
    except Exception:
        return True

def _days_from_segment(seg: str):
    try:
        d = int(seg)
        return max(0, d)
    except Exception:
        return 7

@bp.route('/orders', methods=['GET'])
@bp.route('/orders/<status>', methods=['GET'])
@bp.route('/orders/<status>/<otype>', methods=['GET'])
@bp.route('/orders/<status>/<otype>/<days>', methods=['GET'])
def fhir_orders(status=None, otype=None, days=None):
    meta = session.get('patient_meta') or {}
    dfn = str(meta.get('dfn') or '').strip()
    if not dfn:
        return jsonify({'error': 'No patient selected'}), 400

    status_seg = (status or '').strip()
    type_seg = (otype or '').strip()
    days_val = _days_from_segment(days) if days is not None else 7
    want_type = _orders_type_label(type_seg)

    try:
        status_param = _status_label_for_request(status_seg)  # e.g., "23^0"
        aget_params = [dfn, status_param, '1', '0', '0', '', '0']
        aget_lines = _rpc_call('ORWORR AGET', aget_params)
    except Exception as e:
        return jsonify({'error': f'RPC ORWORR AGET failed: {e}'}), 500

    base = _parse_orworr_aget(aget_lines)
    base = [b for b in base if (not days_val) or _within_days(b.get('fm_date', ''), days_val)]

    limit = 200
    try:
        if 'limit' in request.args:
            limit = max(1, min(1000, int(request.args['limit'])))
    except Exception:
        pass

    results = []
    detail_errors = 0
    for b in base[:limit]:
        oid = b['id']
        fm_date = b['fm_date']
        try:
            info = _detail_order(dfn, oid)
        except Exception:
            detail_errors += 1
            continue
        if not _filter_type(info, want_type):
            continue
        results.append({
            'order_id': oid,
            'status_code': b.get('status_code'),
            'fm_date': fm_date,
            'date': _fileman_to_iso(fm_date),
            'type': info.get('type'),
            'name': info.get('name'),
            'instructions': info.get('instructions'),
            'sig': info.get('sig'),
            'indication': info.get('indication'),
            'current_status': info.get('current_status')
        })

    payload = {
        'patient_id': dfn,
        'status': status_seg or 'current',
        'type': want_type,
        'days': days_val,
        'count': len(results),
        'detail_errors': detail_errors,
        'orders': results
    }
    return jsonify(payload)

# --------------- SESSION-BACKED FHIR VIEWS ---------------

@bp.route('/problems', methods=['GET'])
def fhir_problems():
    problems = session.get('fhir_problems') or []
    status_q = (request.args.get('status') or '').strip().lower()
    active_q = request.args.get('active')
    filtered = problems
    if status_q in ('active', 'inactive'):
        want_active = (status_q == 'active')
        filtered = [p for p in problems if bool(p.get('active')) == want_active]
    elif active_q is not None:
        want_active = str(active_q).strip().lower() in ('1', 'true', 'yes', 'on')
        filtered = [p for p in problems if bool(p.get('active')) == want_active]
    return jsonify({'problems': filtered, 'count': len(filtered)})

@bp.route('/allergies', methods=['GET'])
def fhir_allergies():
    allergies = session.get('fhir_allergies') or []
    return jsonify({'allergies': allergies})

@bp.route('/medications', methods=['GET'])
def fhir_medications():
    meds = session.get('fhir_meds') or []
    status_q = (request.args.get('status') or '').lower().strip()
    q = (request.args.get('q') or '').lower().strip()
    filtered = []
    for m in meds:
        if status_q and (m.get('status') or '').lower() != status_q:
            continue
        if q and q not in (m.get('name') or '').lower():
            continue
        filtered.append(m)
    return jsonify({ 'medications': filtered, 'count': len(filtered) })

# Shorthand alias
@bp.route('/meds', methods=['GET'])
def fhir_meds_alias():
    return fhir_medications()

@bp.route('/labs', methods=['GET'])
def fhir_labs():
    labs = session.get('fhir_labs') or []
    if not labs:
        return jsonify({'labs': []})

    # Existing params
    start_q = request.args.get('start')
    end_q = request.args.get('end')
    test_q = (request.args.get('test') or '').lower().strip()  # legacy name search
    group_q = (request.args.get('groupType') or '').upper().strip()
    abnormal_q = request.args.get('abnormal')

    # New params
    codes_param = (request.args.get('codes') or '').strip()
    names_param = (request.args.get('names') or request.args.get('q') or '').strip()
    days_param = (request.args.get('days') or '').strip()

    # Build filters
    filters = []
    if codes_param:
        filters.extend([t.strip() for t in codes_param.split(',') if t.strip()])
    if names_param:
        filters.extend([t.strip() for t in names_param.split(',') if t.strip()])
    if test_q:
        filters.append(test_q)
    want_codes, want_names = _prepare_lab_filters(filters if filters else None)

    # Time window
    start_dt = _parse_date_iso(start_q) if start_q else None
    end_dt = _parse_date_iso(end_q) if end_q else None

    # If filters provided and no explicit time bounds, return most recent per test
    if (filters and not days_param and not start_dt and not end_dt):
        def _parse_dt(iso: str | None):
            try:
                return datetime.fromisoformat(str(iso).replace('Z','')) if iso else None
            except Exception:
                return None
        def _key(rec: dict) -> str:
            code = (rec.get('loinc') or rec.get('code') or rec.get('loincCode') or '').strip().upper()
            if code:
                return f"CODE:{code}"
            label = (rec.get('test') or rec.get('localName') or '')
            return f"NAME:{_normalize_term(label)}"
        best = {}
        for r in labs:
            # Apply non-time filters first
            if group_q and (r.get('groupType','').upper() != group_q):
                continue
            if abnormal_q and abnormal_q in ('1','true','yes') and not r.get('abnormal'):
                continue
            if not _lab_record_matches(r, want_codes, want_names):
                continue
            dt_iso = r.get('resulted') or r.get('collected')
            dt = _parse_dt(dt_iso)
            if not dt:
                continue
            k = _key(r)
            cur = best.get(k)
            if not cur or dt > cur.get('__dt'):
                cur_copy = dict(r)
                cur_copy['__dt'] = dt
                best[k] = cur_copy
        chosen = sorted(best.values(), key=lambda x: x.get('__dt'), reverse=True)
        for c in chosen:
            c.pop('__dt', None)
        return jsonify({'labs': chosen, 'count': len(chosen)})

    cutoff = None
    try:
        if days_param and (days_param.isdigit() or str(int(days_param)) == days_param):
            cutoff = _days_ago_cutoff(int(days_param))
    except Exception:
        cutoff = None
    if not cutoff and not start_dt and not end_dt:
        cutoff = _days_ago_cutoff(14)

    def _in_range(dt_iso: str | None) -> bool:
        if not dt_iso:
            return False
        if cutoff is not None:
            return _in_window(dt_iso, cutoff)
        dt = _parse_date_iso(dt_iso)
        if start_dt and (not dt or dt < start_dt):
            return False
        if end_dt and (not dt or dt > end_dt):
            return False
        return True

    filtered = []
    for r in labs:
        dt_iso = r.get('resulted') or r.get('collected')
        if not _in_range(dt_iso):
            continue
        if group_q and (r.get('groupType','').upper() != group_q):
            continue
        if abnormal_q and abnormal_q in ('1','true','yes') and not r.get('abnormal'):
            continue
        if not _lab_record_matches(r, want_codes, want_names):
            continue
        filtered.append(r)

    return jsonify({'labs': filtered, 'count': len(filtered)})

@bp.route('/labs/panels', methods=['GET'])
def fhir_labs_panels():
    panels = session.get('fhir_labs_panels') or []
    if not panels:
        return jsonify({'panels': []})
    cat = (request.args.get('category') or '').lower().strip()
    if cat:
        panels_f = [p for p in panels if (p.get('broadCategory') or '').lower() == cat]
    else:
        panels_f = panels
    return jsonify({'panels': panels_f, 'count': len(panels_f)})

@bp.route('/labs/summary', methods=['GET'])
def fhir_labs_summary():
    summary = session.get('fhir_labs_summary') or []
    return jsonify({'summary': summary, 'count': len(summary)})

@bp.route('/labs/loinc/<code>', methods=['GET'])
def fhir_labs_by_loinc(code):
    loinc_index = session.get('fhir_labs_loinc_index') or {}
    labs = loinc_index.get(code) or []
    return jsonify({'loinc': code, 'labs': labs, 'count': len(labs)})

@bp.route('/vitals', methods=['GET'])
def get_vitals():
    meta = session.get('patient_meta') or {}
    dfn = meta.get('dfn')
    if not dfn:
        return jsonify({'error': 'No patient selected'}), 400
    vitals = session.get('fhir_vitals') or {}
    start_q = request.args.get('start')
    end_q = request.args.get('end')
    def _parse(q):
        if not q:
            return None
        try:
            return datetime.fromisoformat(q.replace('Z',''))
        except Exception:
            try:
                return datetime.strptime(q, '%Y-%m-%d')
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
                dt = datetime.fromisoformat(ts.replace('Z','')) if ts else None
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
    return jsonify({
        'vitals': filtered,
        'meta': {
            'patient_dfn': dfn,
            'originalCounts': original_counts,
            'filteredCounts': filtered_counts,
            'start': start_q,
            'end': end_q
        }
    })

@bp.route('/vitals/summary', methods=['GET'])
def vitals_summary():
    meta = session.get('patient_meta') or {}
    dfn = meta.get('dfn')
    if not dfn:
        return jsonify({'error': 'No patient selected'}), 400
    vitals = session.get('fhir_vitals') or {}
    summary = {}
    for k, arr in vitals.items():
        if not arr:
            continue
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
    return jsonify({'patient_dfn': dfn, 'summary': summary})