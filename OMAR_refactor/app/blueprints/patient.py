from __future__ import annotations
import json
import os
from typing import Any, Dict
from flask import Blueprint, jsonify, current_app, request, g
from ..services.patient_service import PatientService
from ..gateways.factory import get_gateway
from ..services import transforms as T
from ..utils.context import merge_context
from app.services.loinc_index import LoincIndex
from app.query.query_models.default.services.rag_store import store as rag_store
try:
    # Prefer absolute-style import first to satisfy some analyzers
    from app.services.document_search_service import get_or_build_index_for_dfn  # type: ignore
except Exception:
    from ..services.document_search_service import get_or_build_index_for_dfn  # type: ignore

bp = Blueprint('patient_api', __name__)

# Very small composition for now; later use DI container


def _update_gateway_context(**values: Any) -> None:
    try:
        ctx = dict(getattr(g, 'gateway_context', {}) or {})
    except RuntimeError:
        return
    updated = False
    for key, value in values.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if ctx.get(key) == text:
            continue
        ctx[key] = text
        updated = True
    if updated:
        g.gateway_context = ctx


@bp.url_value_preprocessor
def _capture_dfn(_: str | None, values: dict[str, Any] | None) -> None:
    if not values:
        return
    dfn = values.get('dfn')
    if dfn is not None:
        _update_gateway_context(dfn=dfn)


@bp.after_request
def _inject_context(response):  # type: ignore[override]
    try:
        if not response.is_json:
            return response
        data = response.get_json(silent=True)
        if data is None:
            return response
        wrapped = merge_context(data)
        if wrapped is data:
            return response
        response.set_data(json.dumps(wrapped, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Length'] = str(len(response.get_data()))
    except Exception:
        pass
    return response

def _get_patient_service() -> PatientService:
    """Build PatientService using the active gateway mode.
    - In demo mode, honor station/duz from query or session for vista-api-x.
    - In socket mode, station/duz are ignored; connections are per-session via login.
    """
    from flask import session as flask_session
    sta_arg = request.args.get('station')
    duz_arg = request.args.get('duz')
    if sta_arg:
        flask_session['station'] = str(sta_arg)
    if duz_arg:
        flask_session['duz'] = str(duz_arg)
    station = str(flask_session.get('station') or os.getenv('DEFAULT_STATION','500'))
    duz = str(flask_session.get('duz') or os.getenv('DEFAULT_DUZ','983'))
    gw = get_gateway(station=station, duz=duz)
    return PatientService(gateway=gw)


# ----------------- Maintainability helpers -----------------

# Per-domain allowlists for pass-through filters
_ALLOWED: dict[str, tuple[str, ...]] = {
    'meds': ('start','stop','max','id','uid','vaType','raw'),
    'labs': ('start','stop','max','id','uid','category','nowrap','raw'),
    'vitals': ('start','stop','max','id','uid','raw'),
    'documents': ('start','stop','max','id','uid','status','category','text','nowrap','raw'),
    'radiology': ('start','stop','max','id','uid','raw'),
    'procedures': ('start','stop','max','id','uid','raw'),
    'encounters': ('start','stop','max','id','uid','raw'),
    'problems': ('max','id','uid','status','raw'),
    'allergies': ('start','stop','max','id','uid','raw'),
    # Additional VPR domains
    'appointment': ('start','stop','max','id','uid','raw'),
    'order': ('start','stop','max','id','uid','raw'),
    'consult': ('start','stop','max','id','uid','nowrap','raw'),
    'immunization': ('start','stop','max','id','uid','raw'),
    'cpt': ('start','stop','max','id','uid','raw'),
    'exam': ('start','stop','max','id','uid','raw'),
    'education': ('start','stop','max','id','uid','raw'),
    'factor': ('start','stop','max','id','uid','raw'),
    'pov': ('start','stop','max','id','uid','raw'),
    'skin': ('start','stop','max','id','uid','raw'),
    'obs': ('start','stop','max','id','uid','raw'),
    'ptf': ('start','stop','max','id','uid','raw'),
    'surgery': ('start','stop','max','id','uid','raw'),
    'image': ('start','stop','max','id','uid','raw'),
}

def _collect_for(domain_key: str, *extra: str) -> dict:
    keys = list(_ALLOWED.get(domain_key, ())) + list(extra)
    return _collect_params(*keys)


# ----------------- Helpers to enrich quick results from raw -----------------

def _extract_full_text(raw_item: dict) -> str | None:
    try:
        # Common patterns across documents/radiology/procedures
        # 1) text: [ { content: "..." }, ... ]
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
        # 2) report/impression (radiology)
        rpt = raw_item.get('report') or raw_item.get('impression')
        if isinstance(rpt, str) and rpt.strip():
            return rpt
        # 3) body/content/documentText
        for k in ('body','content','documentText','noteText','clinicalText','details'):
            v = raw_item.get(k)
            if isinstance(v, str) and v.strip():
                return v
        # 4) nested content
        doc = raw_item.get('document')
        if isinstance(doc, dict):
            for k in ('content','text','body'):
                v = doc.get(k)
                if isinstance(v, str) and v.strip():
                    return v
    except Exception:
        pass
    return None


def _extract_encounter_info(raw_item: dict) -> dict | None:
    try:
        enc = None
        # VPR shapes: 'visit' or 'encounter' or 'appointment'
        if isinstance(raw_item.get('visit'), dict):
            enc = raw_item.get('visit')
        elif isinstance(raw_item.get('encounter'), dict):
            enc = raw_item.get('encounter')
        elif isinstance(raw_item.get('appointment'), dict):
            enc = raw_item.get('appointment')
        out = {}
        # visit/encounter identifiers
        uid = None
        if isinstance(enc, dict):
            uid = enc.get('uid') or enc.get('visitUid')
        if not uid:
            uid = raw_item.get('encounterUid') or raw_item.get('visitUid') or raw_item.get('uid')
        if uid:
            out['visitUid'] = uid
        # date/time
        date_val = None
        for k in ('dateTime','referenceDateTime','start','time'):
            if isinstance(enc, dict) and enc.get(k):
                date_val = enc.get(k)
                break
        if not date_val:
            date_val = raw_item.get('dateTime') or raw_item.get('referenceDateTime') or raw_item.get('observed')
        dt_iso = T._parse_any_datetime_to_iso(date_val)  # type: ignore
        if dt_iso:
            out['date'] = dt_iso
        # location
        loc_name = None
        try:
            if isinstance(raw_item.get('location'), dict):
                loc_name = raw_item['location'].get('name') or raw_item['location'].get('displayName')
        except Exception:
            pass
        if not loc_name:
            for k in ('locationName','clinicName','clinic','wardName'):
                v = raw_item.get(k)
                if isinstance(v, str) and v.strip():
                    loc_name = v
                    break
        if loc_name:
            out['location'] = loc_name
        # human-readable encounter name when present
        ename = raw_item.get('encounterName')
        if isinstance(ename, str) and ename.strip():
            out['encounterName'] = ename
        return out or None
    except Exception:
        return None


def _is_problem_active(status_val: str | None) -> bool | None:
    if not status_val:
        return None
    s = status_val.strip().lower()
    # Treat resolved/inactive/historical as inactive
    if 'inactive' in s or 'resolved' in s or 'historical' in s or 'entered in error' in s:
        return False
    if 'active' in s and 'inactive' not in s:
        return True
    return None


def _extract_problem_comments(raw_item: dict) -> list[dict] | None:
    try:
        comments = raw_item.get('comments')
        out = []
        if isinstance(comments, list):
            for c in comments:
                if not isinstance(c, dict):
                    continue
                txt = c.get('comment') or c.get('text')
                when = c.get('entered') or c.get('date') or c.get('enteredDateTime')
                who = c.get('enteredBy') or c.get('author') or c.get('authorDisplayName')
                if txt:
                    out.append({
                        'text': txt,
                        'date': T._parse_any_datetime_to_iso(when),  # type: ignore
                        'author': who
                    })
        return out or None
    except Exception:
        return None


# ----------------- Simple pagination helpers (envelope) -----------------

def _parse_limit(default: int = 50, max_limit: int = 200) -> int:
    try:
        val = int((request.args.get('limit') or '').strip() or default)
        if val < 1:
            return default
        return min(val, max_limit)
    except Exception:
        return default


def _parse_offset() -> int:
    # Supports either explicit offset or opaque next token that is an int
    raw = request.args.get('offset') or request.args.get('next') or '0'
    try:
        off = int(str(raw).strip() or '0')
        return max(0, off)
    except Exception:
        return 0


def _envelope_list(items: list[dict] | list) -> dict:
    """Return a standard list envelope with paging.
    Token is a simple integer offset for now (opaque to clients).
    """
    if not isinstance(items, list):
        items = []
    total = len(items)
    limit = _parse_limit()
    offset = _parse_offset()
    start = min(offset, total)
    end = min(start + limit, total)
    page = items[start:end]
    next_token = str(end) if end < total else None
    return {
        'items': page,
        'next': next_token,
        'total': total,
    }


# ----------------- Sensitive record check -----------------

@bp.get('/<dfn>/sensitive')
def sensitive_check(dfn: str):
    """Best-effort sensitive-record check using a VistA RPC.
    Attempts DG SENSITIVE RECORD ACCESS. If response indicates sensitivity,
    return allowed=False and include the full warning text from VistA; otherwise allowed=True.
    Response: { allowed: bool, message: str, raw: str }
    """
    # Local helper to unwrap possible vista-api-x wrapper
    def _unwrap_vax_raw(raw_val):
        try:
            if isinstance(raw_val, (bytes, bytearray)):
                try:
                    raw_val = raw_val.decode('utf-8', errors='ignore')
                except Exception:
                    return str(raw_val)
            if isinstance(raw_val, str):
                s = raw_val.strip()
                if s.startswith('{') and ('"payload"' in s or "'payload'" in s):
                    import json as _json
                    try:
                        obj = _json.loads(s)
                        pl = obj.get('payload')
                        if isinstance(pl, str):
                            return pl
                        if isinstance(pl, list):
                            return '\n'.join(str(x) for x in pl)
                        return str(pl)
                    except Exception:
                        return s
            return str(raw_val)
        except Exception:
            try:
                return str(raw_val)
            except Exception:
                return ''

    try:
        gw = get_gateway()
        context = 'OR CPRS GUI CHART'
        raw = gw.call_rpc(context=context, rpc='DG SENSITIVE RECORD ACCESS', parameters=[{'string': str(dfn)}], json_result=False, timeout=30)  # type: ignore[attr-defined]
        text = _unwrap_vax_raw(raw).strip()
        # Determine sensitivity and extract human message
        is_sensitive = False
        message = ''
        if text:
            lines = text.splitlines()
            if lines and lines[0].strip().isdigit() and len(lines) == 1:
                is_sensitive = (lines[0].strip() != '0')
            else:
                if lines and lines[0].strip().isdigit():
                    status_code = lines[0].strip()
                    is_sensitive = (status_code != '0')
                    lines = lines[1:]
                low_all = '\n'.join(lines).lower()
                if ('restricted' in low_all or 'warning' in low_all or 'privacy act' in low_all or 'sensitive' in low_all):
                    is_sensitive = True
                message = '\n'.join([ln.rstrip() for ln in lines if ln is not None]).strip()
        if is_sensitive and not message:
            message = 'This patient record is sensitive.'
        return jsonify({ 'allowed': (not is_sensitive), 'message': message, 'raw': text })
    except Exception as e:
        return jsonify({ 'allowed': True, 'message': '', 'error': str(e) })


# ----------------- VPR pass-through param helpers -----------------

def _collect_params(*keys: str) -> dict:
    """Collect allowed params and normalize dates.
    - Converts start/stop to FileMan when provided.
    - Supports relative range via last=14d|2w|6m|1y when start/stop absent; emits start/stop.
    """
    out: dict = {}
    provided_keys = set(keys)
    for k in keys:
        v = request.args.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s == '':
            continue
        if k in ('start','stop'):
            fm = T.to_fileman_datetime(s)
            out[k] = fm or s
        else:
            out[k] = s
    # Relative date convenience: only if endpoint accepts start/stop and not already provided
    if ('start' in provided_keys or 'stop' in provided_keys) and ('start' not in out and 'stop' not in out):
        last = request.args.get('last')
        if last:
            rng = T.parse_relative_last_to_iso_range(last)  # type: ignore
            if rng:
                s_iso, e_iso = rng
                s_fm = T.to_fileman_datetime(s_iso)
                e_fm = T.to_fileman_datetime(e_iso)
                if s_fm:
                    out['start'] = s_fm
                if e_fm:
                    out['stop'] = e_fm
    return out


def _raw_requested() -> bool:
    try:
        return str(request.args.get('raw', '')).strip().lower() in ('1','true','yes','on')
    except Exception:
        return False


def _json_with_optional_raw(payload, vpr_payload, *, list_label: str | None = None):
    if not _raw_requested():
        return jsonify(payload)
    raw_text = None
    if isinstance(vpr_payload, dict):
        raw_text = vpr_payload.get('raw')
    if isinstance(payload, dict):
        body = dict(payload)
        body['raw'] = raw_text
        return jsonify(body)
    key = list_label or 'result'
    return jsonify({key: payload, 'raw': raw_text})

@bp.get('/<dfn>/demographics')
def demographics(dfn: str):
    svc = _get_patient_service()
    try:
        result = svc.get_demographics(dfn)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/demographics')
def demographics_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'patient', params=raw_params)
        quick = svc.get_demographics_quick(dfn)
        if (request.args.get('includeRaw', '0').lower() in ('1', 'true', 'yes', 'on')):
            # Attach first raw item for traceability
            item = None
            try:
                arr = T._get_nested_items(vpr)  # type: ignore
                item = arr[0] if arr else None
            except Exception:
                item = None
            if isinstance(quick, dict):
                quick = dict(quick)
                quick['_raw'] = item
        return _json_with_optional_raw(quick, vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/meds')
@bp.get('/<dfn>/quick/medications')  # alias to match frontend calls
def medications_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'meds', params=raw_params)
        quick = svc.get_medications_quick(dfn, params=raw_params)

        # Optional filtering: status, days/start/end, name
        status_raw = (request.args.get('status') or 'ALL').strip().upper()
        # Normalize status filter to a set of allowed quick statuses
        status_map = {
            'ACTIVE': {'active'},
            'PENDING': {'pending'},
            'ACTIVE+PENDING': {'active', 'pending', 'new', 'hold'},
            'CURRENT': {'active', 'pending'},
            'ALL': None,
        }
        allowed_status = status_map.get(status_raw, None)

        # Date range: support days (relative), start, end in common formats
        from datetime import datetime, timezone, timedelta
        def _to_iso(x):
            try:
                return T._parse_any_datetime_to_iso(x)  # type: ignore
            except Exception:
                return None
        now = datetime.now(timezone.utc)
        start_iso = None
        end_iso = None
        days = None
        try:
            d = request.args.get('days')
            if d is not None:
                di = int(str(d).strip() or '0')
                if di and di > 0:
                    days = di
        except Exception:
            days = None
        if days:
            start_iso = (now - timedelta(days=days)).isoformat().replace('+00:00','Z')
            end_iso = now.isoformat().replace('+00:00','Z')
        s_arg = request.args.get('start')
        e_arg = request.args.get('end')
        if s_arg:
            s_parsed = _to_iso(s_arg)
            if s_parsed:
                start_iso = s_parsed
        if e_arg:
            e_parsed = _to_iso(e_arg)
            if e_parsed:
                end_iso = e_parsed

        name_filter = (request.args.get('name') or '').strip().lower()

        def _in_date_range(item):
            if not (start_iso or end_iso):
                return True
            try:
                sd = item.get('startDate')
                ed = item.get('endDate')
                # Default to startDate when endDate missing
                cand = _to_iso(ed) or _to_iso(sd)
                if not cand:
                    return False
                if start_iso and cand < start_iso:
                    return False
                if end_iso and cand > end_iso:
                    return False
                return True
            except Exception:
                return True

        def _status_ok(item):
            if not allowed_status:
                return True
            s = (item.get('status') or '').strip().lower()
            return s in allowed_status

        def _name_ok(item):
            if not name_filter:
                return True
            n = (item.get('name') or '').strip().lower()
            return name_filter in n

        # Apply filters when requested
        if isinstance(quick, list):
            filtered = [q for q in quick if _status_ok(q) and _in_date_range(q) and _name_ok(q)]
        else:
            filtered = quick

        include_raw_requested = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        if include_raw_requested and isinstance(filtered, list):
            # Best effort: only attach _raw when no filters applied to preserve index alignment
            filters_applied = (allowed_status is not None) or bool(days) or bool(start_iso) or bool(end_iso) or bool(name_filter)
            if not filters_applied:
                raw_items = []
                try:
                    raw_items = T._get_nested_items(vpr)  # type: ignore
                except Exception:
                    raw_items = []
                out = []
                for idx, q in enumerate(filtered):
                    obj = dict(q)
                    if idx < len(raw_items):
                        obj['_raw'] = raw_items[idx]
                    out.append(obj)
                filtered = out
        payload = {'medications': filtered if isinstance(filtered, list) else (filtered or [])}
        return _json_with_optional_raw(payload, vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Quick routes for other domains
@bp.get('/<dfn>/quick/labs')
def labs_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'labs', params=raw_params)

        # Server-side filters: names (comma-separated), days, start, end
        names_raw = (request.args.get('names') or '').strip()
        name_tokens = [s.strip() for s in names_raw.split(',') if s.strip()] if names_raw else []

        from datetime import datetime, timezone, timedelta
        def _to_iso(x):
            try:
                return T._parse_any_datetime_to_iso(x)  # type: ignore
            except Exception:
                return None
        now = datetime.now(timezone.utc)
        start_iso = None
        end_iso = None
        # days → relative range
        days = None
        try:
            d = request.args.get('days')
            if d is not None:
                di = int(str(d).strip() or '0')
                if di and di > 0:
                    days = di
        except Exception:
            days = None
        if days:
            start_iso = (now - timedelta(days=days)).isoformat().replace('+00:00','Z')
            end_iso = now.isoformat().replace('+00:00','Z')
        s_arg = request.args.get('start')
        e_arg = request.args.get('end')
        if s_arg:
            s_parsed = _to_iso(s_arg)
            if s_parsed:
                start_iso = s_parsed
        if e_arg:
            e_parsed = _to_iso(e_arg)
            if e_parsed:
                end_iso = e_parsed

        filters_payload: dict[str, Any] = {'start': start_iso, 'end': end_iso}
        max_panels_arg = request.args.get('maxPanels') or request.args.get('max')
        if max_panels_arg:
            try:
                filters_payload['max_panels'] = int(str(max_panels_arg).strip())
            except Exception:
                pass

        quick = svc.get_labs_quick(dfn, params=raw_params, filters=filters_payload)

        def _date_ok(item):
            if not (start_iso or end_iso):
                return True
            try:
                # quick labs include observedDate/resulted as ISO; fallback to observed/collected
                cand = item.get('observedDate') or item.get('resulted') or item.get('collected') or item.get('date')
                iso = _to_iso(cand) or cand
                if not iso:
                    return False
                if start_iso and iso < start_iso:
                    return False
                if end_iso and iso > end_iso:
                    return False
                return True
            except Exception:
                return True

        # LOINC-aware name/code filtering
        loinc_idx = LoincIndex.load()
        if isinstance(quick, list):
            quick = loinc_idx.annotate_labs(quick)
        codes_set, substrings_set = loinc_idx.resolve_tokens(name_tokens)
        def _name_ok(item):
            if not name_tokens:
                return True
            try:
                test = (item.get('test') or item.get('name') or item.get('display') or '').strip()
                code = (item.get('loinc') or item.get('code') or item.get('typeCode') or '').strip().lower()
                if code and code in codes_set:
                    return True
                key = ''.join(ch.lower() if ch.isalnum() else ' ' for ch in test).strip()
                return any(w in key for w in substrings_set)
            except Exception:
                return True

        filtered = quick
        filters_applied = bool(name_tokens) or bool(days) or bool(start_iso) or bool(end_iso)
        if isinstance(quick, list) and filters_applied:
            filtered = [q for q in quick if _date_ok(q) and _name_ok(q)]

        include_raw_items = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        if include_raw_items and isinstance(filtered, list):
            if not filters_applied:
                raw_items = []
                try:
                    raw_items = T._get_nested_items(vpr)  # type: ignore
                except Exception:
                    raw_items = []
                vpr_index = 0
                out = []
                for q in filtered:
                    obj = dict(q)
                    if q.get('source') != 'rpc' and vpr_index < len(raw_items):
                        obj['_raw'] = raw_items[vpr_index]
                        vpr_index += 1
                    out.append(obj)
                filtered = out
        return _json_with_optional_raw(filtered, vpr, list_label='labs')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/vitals')
def vitals_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'vitals', params=raw_params)
        quick = svc.get_vitals_quick(dfn, params=raw_params)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='vitals')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/notes')
def notes_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'notes', params=raw_params)
        quick = svc.get_notes_quick(dfn, params=raw_params)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        if (include_raw or include_text or include_enc) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    r = raw_items[idx]
                    if include_raw:
                        obj['_raw'] = r
                    if include_text:
                        txt = _extract_full_text(r)
                        if txt:
                            obj['text'] = txt
                    if include_enc:
                        enc = _extract_encounter_info(r)
                        if enc:
                            obj['encounter'] = enc
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='notes')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/documents')
def documents_quick(dfn: str):
    """Unified documents endpoint with filters and enrichment.
    Query params:
      - class: one or more document classes (e.g., PROGRESS NOTES, RADIOLOGY REPORTS, SURGICAL REPORTS, DISCHARGE SUMMARY).
               Accepts comma-separated values. Case-insensitive.
      - type: one or more document type names or codes (e.g., Progress Note or PN, Radiology Report or RA, Surgery Report or SR, Discharge Summary or DS).
               Comma-separated, case-insensitive.
      - includeText=1: include full text under 'text' when available.
      - includeEncounter=1: include encounter details under 'encounter'.
      - includeRaw=1: include _raw payload for each item.
    """
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        # Fetch raw and quick lists
        doc_params: Dict[str, str] = {}
        if include_text or raw_requested:
            doc_params['text'] = '1'
        else:
            doc_params['text'] = '0'
        if raw_requested or include_raw:
            doc_params['raw'] = '1'
        vpr = svc.get_vpr_raw(dfn, 'document', params=doc_params)
        quick_list = svc.get_documents_quick(dfn, params=dict(doc_params))

        # Proactively build keyword index if not present (lazy in search too)
        try:
            _ = get_or_build_index_for_dfn(str(dfn), gateway=svc.gateway, async_build=True)
        except Exception:
            pass

        # Normalize filters
        def _split_params(val: str | None) -> list[str]:
            if not val:
                return []
            parts = []
            for p in str(val).split(','):
                s = p.strip()
                if s:
                    parts.append(s)
            return parts

        class_filters = [s.lower() for s in _split_params(request.args.get('class'))]
        type_filters = [s.lower() for s in _split_params(request.args.get('type'))]

        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []

        # Pair quick with raw by original index to preserve alignment, then filter
        pairs: list[tuple[dict, dict | None]] = []
        if isinstance(quick_list, list):
            for idx, q in enumerate(quick_list):
                r = raw_items[idx] if idx < len(raw_items) else None
                if not isinstance(q, dict):
                    continue
                pairs.append((q, r if isinstance(r, dict) else None))

        # Apply class filter if provided
        if class_filters:
            def _class_matches(q: dict, r: dict | None) -> bool:
                qc = (q.get('documentClass') or '')
                rc = (r.get('documentClass') if isinstance(r, dict) else '')
                s = (qc or rc or '')
                return s.strip().lower() in class_filters
            pairs = [(q, r) for (q, r) in pairs if _class_matches(q, r)]

        # Apply type filter if provided (match by name or code)
        if type_filters:
            def _type_matches(q: dict, r: dict | None) -> bool:
                # Name from quick
                name = (q.get('documentType') or '')
                # Fallbacks from raw
                rname = (r.get('documentTypeName') if isinstance(r, dict) else '')
                rcode = (r.get('documentTypeCode') if isinstance(r, dict) else '')
                vals = [str(name).lower(), str(rname).lower(), str(rcode).lower()]
                return any(v in type_filters for v in vals if v)
            pairs = [(q, r) for (q, r) in pairs if _type_matches(q, r)]

        # Enrichment
        out = []
        for (q, r) in pairs:
            obj = dict(q)
            if include_raw and isinstance(r, dict):
                obj['_raw'] = r
            if include_text and isinstance(r, dict):
                txt = _extract_full_text(r)
                if txt:
                    obj['text'] = txt
            if include_enc and isinstance(r, dict):
                enc = _extract_encounter_info(r)
                if enc:
                    obj['encounter'] = enc
            out.append(obj)

        # No background embedding; RAG uses the keyword index's in-memory texts

        result = out if (include_raw or include_text or include_enc or class_filters or type_filters) else quick_list
        return _json_with_optional_raw(result, vpr, list_label='documents')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.get('/<dfn>/list/documents')
def documents_list_envelope(dfn: str):
    """Paginated list envelope for documents with optional filters.
    Returns: { items: [], next: string|null, total: number }
    Filters via query params `class` and `type` are supported (same as /quick/documents) but
    envelope is always applied to the resulting list. Full text/raw are not included here by default
    to keep payloads small; clients can follow-up on individual items using quick endpoints with
    includeText/includeEncounter when needed.
    """
    svc = _get_patient_service()
    try:
        # Reuse the quick + filters logic to get the full filtered list, then paginate and sort
        vpr = svc.get_vpr_raw(dfn, 'notes')  # alias -> documents
        quick_list = svc.get_documents_quick(dfn)

        def _split_params(val: str | None) -> list[str]:
            if not val:
                return []
            parts = []
            for p in str(val).split(','):
                s = p.strip()
                if s:
                    parts.append(s)
            return parts

        class_filters = [s.lower() for s in _split_params(request.args.get('class'))]
        type_filters = [s.lower() for s in _split_params(request.args.get('type'))]

        if not isinstance(quick_list, list):
            quick_list = []

        # Filter using the same rules as documents_quick (without enrichment)
        items: list[dict] = []
        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []
        for idx, q in enumerate(quick_list):
            if not isinstance(q, dict):
                continue
            r = raw_items[idx] if idx < len(raw_items) else None
            # Class filter
            if class_filters:
                qc = (q.get('documentClass') or '')
                rc = (r.get('documentClass') if isinstance(r, dict) else '')
                s = (qc or rc or '')
                if s.strip().lower() not in class_filters:
                    continue
            # Type filter
            if type_filters:
                name = (q.get('documentType') or '')
                rname = (r.get('documentTypeName') if isinstance(r, dict) else '')
                rcode = (r.get('documentTypeCode') if isinstance(r, dict) else '')
                vals = [str(name).lower(), str(rname).lower(), str(rcode).lower()]
                if not any(v in type_filters for v in vals if v):
                    continue
            # Attach minimal identifiers to support viewer/text-batch on the client
            try:
                if isinstance(r, dict):
                    rid = r.get('id') or r.get('localId') or None
                    if rid is not None:
                        q = dict(q)
                        q['docId'] = str(rid)
                    uid = r.get('uid') or None
                    if uid is not None:
                        if isinstance(q, dict):
                            q = dict(q)
                        q['uid'] = str(uid)
            except Exception:
                pass
            items.append(q)

        # Sorting support: sort=field:dir where field in [date,title,author,type,encounter]
        sort_param = (request.args.get('sort') or '').strip().lower()
        if sort_param:
            try:
                field, direction = (sort_param.split(':', 1) + ['asc'])[:2]
                direction = 'desc' if direction.strip() == 'desc' else 'asc'
                key_map = {
                    'date': lambda o: (o.get('date') or ''),
                    'title': lambda o: (o.get('title') or ''),
                    'author': lambda o: (o.get('author') or ''),
                    'type': lambda o: (o.get('documentType') or ''),
                    'encounter': lambda o: (o.get('encounterName') or ''),
                }
                key_fn = key_map.get(field)
                if key_fn:
                    items.sort(key=lambda o: (key_fn(o) or '').lower(), reverse=(direction=='desc'))
            except Exception:
                pass
        else:
            # Default: date desc
            try:
                items.sort(key=lambda o: (o.get('date') or ''), reverse=True)
            except Exception:
                pass

        # Proactively build keyword index (optional)
        try:
            _ = get_or_build_index_for_dfn(str(dfn), gateway=svc.gateway, async_build=True)
        except Exception:
            pass

        return jsonify(_envelope_list(items))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.post('/<dfn>/documents/text-batch')
def documents_text_batch_api(dfn: str):
    """Return full text for a batch of document ids.
    Body: { ids: ["123","456", ...] }
    Response: { notes: [{ doc_id: "123", text: [lines] }, ...] }
    """
    svc = _get_patient_service()
    try:
        data = request.get_json(force=True, silent=True) or {}
        ids = data.get('ids') or data.get('doc_ids') or []
        if not isinstance(ids, list) or not ids:
            return jsonify({'notes': []})
        ids = [str(x) for x in ids if x is not None]
        try:
            texts = svc.get_document_texts(dfn, ids)
        except Exception:
            texts = {}

        notes_out = []
        for doc_id in ids:
            lines = texts.get(doc_id)
            if lines:
                notes_out.append({'doc_id': doc_id, 'text': list(lines)})
        return jsonify({'notes': notes_out})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/documents/search')
def documents_search(dfn: str):
    """Keyword search across a patient's documents (full text + metadata).
    Query: q, fields (comma list from full,title,author,type,class), limit, offset
    Returns: { items: [{ doc_id, score, snippet?, fields_hits? }], next, total }
    """
    try:
        q = (request.args.get('q') or '').strip()
        fields = (request.args.get('fields') or 'full,title,author,type').strip()
        limit = _parse_limit(default=50, max_limit=200)
        offset = _parse_offset()
        if not q:
            return jsonify({'items': [], 'next': None, 'total': 0})
        field_set = set([s.strip().lower() for s in fields.split(',') if s.strip()])
        index = get_or_build_index_for_dfn(dfn)
        results = index.search(q, fields=field_set)
        total = len(results)
        start = min(offset, total)
        end = min(start + limit, total)
        page = results[start:end]
        next_token = str(end) if end < total else None
        return jsonify({ 'items': page, 'next': next_token, 'total': total })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/radiology')
def radiology_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'radiology', params=raw_params)
        quick = svc.get_radiology_quick(dfn, params=raw_params)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        if (include_raw or include_text or include_enc) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    r = raw_items[idx]
                    if include_raw:
                        obj['_raw'] = r
                    if include_text:
                        txt = _extract_full_text(r)
                        if txt:
                            obj['text'] = txt
                    if include_enc:
                        enc = _extract_encounter_info(r)
                        if enc:
                            obj['encounter'] = enc
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='radiology')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/list/labs')
def labs_list_envelope(dfn: str):
    """Paginated list envelope for labs (quick shape), with optional filters converted to FileMan.
    Returns: { items: [], next: string|null, total: number }
    Supported params: start, stop, max, id, uid, category (CH|MI|AP), nowrap
    """
    svc = _get_patient_service()
    try:
        params = _collect_params('start','stop','max','id','uid','category','nowrap')
        vpr = svc.get_vpr_raw(dfn, 'labs', params=params)
        quick = svc.get_labs_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []
        items = []
        if isinstance(quick, list):
            vpr_index = 0
            for q in quick:
                obj = dict(q)
                if include_raw and q.get('source') != 'rpc' and vpr_index < len(raw_items):
                    obj['_raw'] = raw_items[vpr_index]
                    vpr_index += 1
                items.append(obj)
        return jsonify(_envelope_list(items))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@bp.get('/<dfn>/list/radiology')
def radiology_list_envelope(dfn: str):
    """Paginated list envelope for radiology (quick shape), with optional filters converted to FileMan.
    Returns: { items: [], next: string|null, total: number }
    Supported params: start, stop, max, id, uid
    """
    svc = _get_patient_service()
    try:
        params = _collect_params('start','stop','max','id','uid')
        vpr = svc.get_vpr_raw(dfn, 'radiology', params=params)
        quick = svc.get_radiology_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []
        items = []
        if isinstance(quick, list):
            for idx, q in enumerate(quick):
                obj = dict(q)
                if include_raw and idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                items.append(obj)
        return jsonify(_envelope_list(items))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/list/meds')
def meds_list_envelope(dfn: str):
    """Paginated list envelope for medications (quick shape).
    Returns: { items: [], next: string|null, total: number }
    Supported params: start, stop, max, id, uid, vaType
    Supports relative range via last=14d|2w|6m|1y.
    """
    svc = _get_patient_service()
    try:
        params = _collect_params('start','stop','max','id','uid','vaType')
        vpr = svc.get_vpr_raw(dfn, 'meds', params=params)
        quick = svc.get_medications_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []
        items = []
        if isinstance(quick, list):
            for idx, q in enumerate(quick):
                obj = dict(q)
                if include_raw and idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                items.append(obj)
        return jsonify(_envelope_list(items))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/list/vitals')
def vitals_list_envelope(dfn: str):
    """Paginated list envelope for vitals (quick shape).
    Returns: { items: [], next: string|null, total: number }
    Supported params: start, stop, max, id, uid
    Supports relative range via last=14d|2w|6m|1y.
    """
    svc = _get_patient_service()
    try:
        params = _collect_params('start','stop','max','id','uid')
        vpr = svc.get_vpr_raw(dfn, 'vitals', params=params)
        quick = svc.get_vitals_quick(dfn)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        raw_items = []
        try:
            raw_items = T._get_nested_items(vpr)  # type: ignore
        except Exception:
            raw_items = []
        items = []
        if isinstance(quick, list):
            for idx, q in enumerate(quick):
                obj = dict(q)
                if include_raw and idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                items.append(obj)
        return jsonify(_envelope_list(items))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/procedures')
def procedures_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'procedures', params=raw_params)
        quick = svc.get_procedures_quick(dfn, params=raw_params)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        include_text = request.args.get('includeText','0').lower() in ('1','true','yes','on')
        include_enc = request.args.get('includeEncounter','0').lower() in ('1','true','yes','on')
        if (include_raw or include_text or include_enc) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    r = raw_items[idx]
                    if include_raw:
                        obj['_raw'] = r
                    if include_text:
                        txt = _extract_full_text(r)
                        if txt:
                            obj['text'] = txt
                    if include_enc:
                        enc = _extract_encounter_info(r)
                        if enc:
                            obj['encounter'] = enc
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='procedures')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/encounters')
def encounters_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'encounters', params=raw_params)
        quick = svc.get_encounters_quick(dfn, params=raw_params)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='encounters')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Raw VPR domain passthrough
@bp.get('/<dfn>/vpr/<domain>')
def vpr_raw(dfn: str, domain: str):
    svc = _get_patient_service()
    try:
        # Best-effort param collection using a union of commonly safe keys
        params = _collect_params('start','stop','max','id','uid','status','category','text','nowrap','vaType')
        vpr = svc.get_vpr_raw(dfn, domain, params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/vpr/<domain>/item')
def vpr_item(dfn: str, domain: str):
    """Fetch a single item by uid or id for any VPR domain.
    Usage: /<dfn>/vpr/<domain>/item?uid=... or ?id=...
    Accepts optional nowrap. If both uid and id provided, both are forwarded.
    """
    svc = _get_patient_service()
    try:
        uid = (request.args.get('uid') or '').strip()
        id_ = (request.args.get('id') or '').strip()
        if not uid and not id_:
            return jsonify({'error': 'one of uid or id is required'}), 400
        params = _collect_params('id','uid','nowrap','start','stop','max')
        vpr = svc.get_vpr_raw(dfn, domain, params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Full VPR chart without domain filtering (large payload)
@bp.get('/<dfn>/fullchart')
def fullchart(dfn: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_fullchart(dfn)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Compare raw vs quick for supported domains
@bp.get('/<dfn>/compare/<domain>')
def compare_domain(dfn: str, domain: str):
    svc = _get_patient_service()
    try:
        vpr = svc.get_vpr_raw(dfn, domain)
        # Support both 'patient' and 'demographics' for convenience
        if domain in ('patient','demographics'):
            quick = svc.get_demographics_quick(dfn)
        elif domain == 'meds':
            quick = svc.get_medications_quick(dfn)
        elif domain == 'labs':
            quick = svc.get_labs_quick(dfn)
        elif domain == 'vitals':
            quick = svc.get_vitals_quick(dfn)
        elif domain == 'notes':
            quick = svc.get_notes_quick(dfn)
        elif domain in ('documents','document'):
            quick = svc.get_documents_quick(dfn)
        elif domain == 'radiology':
            quick = svc.get_radiology_quick(dfn)
        elif domain == 'procedures':
            quick = svc.get_procedures_quick(dfn)
        elif domain == 'encounters':
            quick = svc.get_encounters_quick(dfn)
        elif domain == 'problems':
            quick = svc.get_problems_quick(dfn)
        elif domain == 'allergies':
            quick = svc.get_allergies_quick(dfn)
        else:
            return jsonify({'error': f"compare not implemented for domain '{domain}'"}), 501
        return jsonify({'raw': vpr, 'quick': quick})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Default VPR shortcuts for common domains
@bp.get('/<dfn>/meds')
def meds_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('meds')
        vpr = svc.get_vpr_raw(dfn, 'meds', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Default VPR shortcuts for other domains
@bp.get('/<dfn>/labs')
def labs_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('labs')
        vpr = svc.get_vpr_raw(dfn, 'labs', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/vitals')
def vitals_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('vitals')
        vpr = svc.get_vpr_raw(dfn, 'vitals', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/notes')
def notes_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('documents')
        vpr = svc.get_vpr_raw(dfn, 'notes', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/radiology')
def radiology_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('radiology')
        vpr = svc.get_vpr_raw(dfn, 'radiology', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/procedures')
def procedures_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('procedures')
        vpr = svc.get_vpr_raw(dfn, 'procedures', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/encounters')
def encounters_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('encounters')
        vpr = svc.get_vpr_raw(dfn, 'encounters', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/problems')
def problems_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('problems')
        vpr = svc.get_vpr_raw(dfn, 'problems', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/allergies')
def allergies_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('allergies')
        vpr = svc.get_vpr_raw(dfn, 'allergies', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Default VPR shortcut for unified documents
@bp.get('/<dfn>/documents')
def documents_default_vpr(dfn: str):
    svc = _get_patient_service()
    try:
        params = _collect_for('documents')
        vpr = svc.get_vpr_raw(dfn, 'document', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Quick routes: problems & allergies
@bp.get('/<dfn>/quick/problems')
def problems_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'problems', params=raw_params)
        quick = svc.get_problems_quick(dfn, params=raw_params)
        include_raw = request.args.get('includeRaw','0').lower() in ('1','true','yes','on')
        # Accept detail=1 as alias for includeComments=1 (frontend convenience)
        include_comments = request.args.get('includeComments','0').lower() in ('1','true','yes','on')
        if not include_comments:
            include_comments = request.args.get('detail','0').lower() in ('1','true','yes','on')
        status_filter = (request.args.get('status') or 'all').strip().lower()  # 'active' | 'inactive' | 'all'
        if (include_raw or include_comments or status_filter != 'all') and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                raw = raw_items[idx] if idx < len(raw_items) else None
                # status filtering
                if status_filter != 'all':
                    # Try quick status first
                    is_active = _is_problem_active(obj.get('status'))
                    if is_active is None and isinstance(raw, dict):
                        is_active = _is_problem_active(raw.get('statusName') or raw.get('status'))
                    # If still None, treat as unknown: only include in 'all'
                    if is_active is None:
                        if status_filter in ('active','inactive'):
                            continue
                    else:
                        if status_filter == 'active' and not is_active:
                            continue
                        if status_filter == 'inactive' and is_active:
                            continue
                # enrich
                if include_raw and isinstance(raw, dict):
                    obj['_raw'] = raw
                if include_comments and isinstance(raw, dict):
                    comments = _extract_problem_comments(raw)
                    if comments:
                        obj['comments'] = comments
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='problems')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/quick/allergies')
def allergies_quick(dfn: str):
    svc = _get_patient_service()
    try:
        raw_requested = _raw_requested()
        raw_params = {'raw': '1'} if raw_requested else None
        vpr = svc.get_vpr_raw(dfn, 'allergies', params=raw_params)
        quick = svc.get_allergies_quick(dfn, params=raw_params)
        if (request.args.get('includeRaw','0').lower() in ('1','true','yes','on')) and isinstance(quick, list):
            raw_items = []
            try:
                raw_items = T._get_nested_items(vpr)  # type: ignore
            except Exception:
                raw_items = []
            out = []
            for idx, q in enumerate(quick):
                obj = dict(q)
                if idx < len(raw_items):
                    obj['_raw'] = raw_items[idx]
                out.append(obj)
            quick = out
        return _json_with_optional_raw(quick, vpr, list_label='allergies')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------- Additional VPR domains (raw passthrough) -----------------

@bp.get('/<dfn>/appointments')
def appointments_vpr(dfn: str):
    """Scheduling appointments (VPR domain 'appointment').
    Filters: start (defaults to today), stop (future), max, id, uid
    """
    svc = _get_patient_service()
    try:
        params = _collect_for('appointment')
        vpr = svc.get_vpr_raw(dfn, 'appointment', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/orders')
def orders_vpr(dfn: str):
    """Orders (VPR domain 'order'). Filters: start/stop (date released), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('order')
        vpr = svc.get_vpr_raw(dfn, 'order', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/consults')
def consults_vpr(dfn: str):
    """Consults (VPR domain 'consult'). Filters: start/stop (dateTime), max, id, uid, nowrap"""
    svc = _get_patient_service()
    try:
        params = _collect_for('consult')
        vpr = svc.get_vpr_raw(dfn, 'consult', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/immunizations')
def immunizations_vpr(dfn: str):
    """Immunizations (VPR domain 'immunization'). Filters: start/stop (administeredDateTime), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('immunization')
        vpr = svc.get_vpr_raw(dfn, 'immunization', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/cpt')
def cpt_vpr(dfn: str):
    """CPT procedures (VPR domain 'cpt'). Filters: start/stop (entered), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('cpt')
        vpr = svc.get_vpr_raw(dfn, 'cpt', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/exams')
def exams_vpr(dfn: str):
    """Exams (VPR domain 'exam'). Filters: start/stop (entered), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('exam')
        vpr = svc.get_vpr_raw(dfn, 'exam', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/education')
def education_vpr(dfn: str):
    """Education (VPR domain 'education'). Filters: start/stop (entered), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('education')
        vpr = svc.get_vpr_raw(dfn, 'education', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/factors')
def factors_vpr(dfn: str):
    """Health Factors (VPR domain 'factor'). Filters: start/stop (entered), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('factor')
        vpr = svc.get_vpr_raw(dfn, 'factor', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/pov')
def pov_vpr(dfn: str):
    """Purpose of Visit (VPR domain 'pov'). Filters: start/stop (entered), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('pov')
        vpr = svc.get_vpr_raw(dfn, 'pov', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/skin')
def skin_vpr(dfn: str):
    """Skin Tests (VPR domain 'skin'). Filters: start/stop (entered), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('skin')
        vpr = svc.get_vpr_raw(dfn, 'skin', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/observations')
def observations_vpr(dfn: str):
    """Clinical Observations (VPR domain 'obs'). Filters: start/stop (observed), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('obs')
        vpr = svc.get_vpr_raw(dfn, 'obs', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/ptf')
def ptf_vpr(dfn: str):
    """Patient Treatment File (VPR domain 'ptf'). Filters: start/stop (movement date), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('ptf')
        vpr = svc.get_vpr_raw(dfn, 'ptf', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/surgery')
def surgery_vpr(dfn: str):
    """Surgery (VPR domain 'surgery'). Filters: start/stop (dateTime), max, id, uid"""
    svc = _get_patient_service()
    try:
        params = _collect_for('surgery')
        vpr = svc.get_vpr_raw(dfn, 'surgery', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/<dfn>/image')
def image_vpr(dfn: str):
    """Radiology/Nuclear Medicine images (VPR domain 'image'). Filters: start/stop (dateTime), max, id, uid
    Note: `/radiology` is an alias that uses the same underlying VPR domain.
    """
    svc = _get_patient_service()
    try:
        params = _collect_for('image')
        vpr = svc.get_vpr_raw(dfn, 'image', params=params)
        return jsonify(vpr)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
