from __future__ import annotations
import os
import time
from flask import Blueprint, jsonify, request
from ..gateways.factory import get_gateway

# Exposes the classic OMAR patient search endpoints at the root path
# - GET  /vista_default_patient_list
# - POST /vista_patient_search
bp = Blueprint('patient_search', __name__)


def _unwrap_vax_raw(raw_val):
    """Vista-api-x sometimes returns a JSON object with a 'payload' string.
    This helper extracts that payload so downstream parsing sees caret/newline text.
    Accepts bytes/str; returns str.
    """
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


def _get_vista_gateway():
    """Return active gateway (demo or socket). In demo mode, station/duz are passed to vista-api-x.
    Allows optional query overrides (?station=...&duz=...).
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
    return get_gateway(station=station, duz=duz)


@bp.get('/vista_default_patient_list')
def vista_default_patient_list():
    """Return user's default patient list using ORQPT DEFAULT PATIENT LIST and minimal user info via ORWU USERINFO.
    Response shape mirrors original OMAR: { patients: [...], context, count, timestamp, user: {duz,name,division} }
    """
    gw = _get_vista_gateway()
    # Use only CPRS context for patient list in both demo and socket modes
    context_candidates = ['OR CPRS GUI CHART']
    try:
        last_err: Exception | None = None
        for ctx in context_candidates:
            try:
                raw = gw.call_rpc(context=ctx, rpc='ORQPT DEFAULT PATIENT LIST', parameters=[], json_result=False, timeout=40)
                raw_text = _unwrap_vax_raw(raw)
                lines = [ln for ln in str(raw_text).split('\n') if ln.strip()]
                patients = []
                for line in lines:
                    parts = line.split('^')
                    if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                        dfn = parts[0].strip()
                        name = parts[1].strip()
                        item = {'dfn': dfn, 'name': name, 'raw': line}
                        if len(parts) > 2 and parts[2].strip():
                            item['clinic'] = parts[2].strip()
                        if len(parts) > 3 and parts[3].strip():
                            item['date'] = parts[3].strip()
                        patients.append(item)
                # Minimal user info using same working context
                user_duz = None
                user_name = None
                user_division = None
                try:
                    uraw = gw.call_rpc(context=ctx, rpc='ORWU USERINFO', parameters=[], json_result=False, timeout=30)
                    utext = _unwrap_vax_raw(uraw)
                    first = (str(utext).split('\n')[0] if utext else '')
                    p = first.split('^') if first else []
                    if len(p) >= 1 and p[0].strip():
                        user_duz = p[0].strip()
                    if len(p) >= 2 and p[1].strip():
                        user_name = p[1].strip()
                    try:
                        if p:
                            last = p[-1]
                            if ';' in last:
                                user_division = last.split(';')[-1].strip()
                            else:
                                user_division = last.strip()
                    except Exception:
                        user_division = None
                except Exception:
                    pass
                payload = {
                    'patients': patients,
                    'context': ctx,
                    'count': len(patients),
                    'timestamp': time.time(),
                    'user': { 'duz': user_duz, 'name': user_name, 'division': user_division }
                }
                return jsonify(payload)
            except Exception as e:
                last_err = e
                continue
        return jsonify({'error': 'ORQPT DEFAULT PATIENT LIST failed for all contexts', 'contexts_tried': context_candidates, 'detail': str(last_err)}), 500
    except Exception as e:
        return jsonify({'error': str(e), 'rpc': 'ORQPT DEFAULT PATIENT LIST'}), 500


@bp.post('/vista_patient_search')
def vista_patient_search():
    """Patient search identical to original OMAR using vista-api-x.
    LAST5 (A1234) -> ORWPT LAST5; Name prefix -> ORWPT LIST ALL with FROM param.
    Body: { query, pageSize?, cursor? }
    Returns: { matches: [{dfn,name,raw}], context, rpc, hasMore, nextCursor }
    """
    gw = _get_vista_gateway()
    # Use only CPRS context for patient search in both demo and socket modes
    context_candidates = ['OR CPRS GUI CHART']
    data = request.get_json(silent=True) or {}
    raw_q = str(data.get('query') or '')
    # Normalize: remove exactly one space right after the first comma
    if ',' in raw_q:
        head, tail = raw_q.split(',', 1)
        if tail.startswith(' '):
            q = head + ',' + tail[1:]
        else:
            q = raw_q
    else:
        q = raw_q
    search_str = q.strip().upper()
    cursor_name = str(data.get('cursor') or '').strip()
    try:
        page_size = int(data.get('pageSize') or 50)
        if page_size <= 0:
            page_size = 50
        page_size = min(page_size, 200)
    except Exception:
        page_size = 50

    if not search_str:
        return jsonify({'error': 'No search string provided'}), 400

    def _parse_lines(text: str):
        items = []
        for line in str(text or '').split('\n'):
            s = line.strip()
            if not s:
                continue
            parts = s.split('^')
            if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                items.append({'dfn': parts[0].strip(), 'name': parts[1].strip(), 'raw': s})
        return items

    try:
        # LAST5
        if (len(search_str) == 5) and search_str[0].isalpha() and search_str[1:].isdigit():
            rpc = 'ORWPT LAST5'
            last_err: Exception | None = None
            for ctx in context_candidates:
                try:
                    raw = gw.call_rpc(context=ctx, rpc=rpc, parameters=[{'string': search_str}], json_result=False, timeout=40)
                    raw_text = _unwrap_vax_raw(raw)
                    matches = _parse_lines(raw_text)
                    return jsonify({'matches': matches, 'context': ctx, 'rpc': rpc, 'hasMore': False, 'nextCursor': None})
                except Exception as e:
                    last_err = e
                    continue
            return jsonify({'error': f"{rpc} failed for all contexts", 'contexts_tried': context_candidates, 'detail': str(last_err)}), 500

        # LIST ALL name prefix
        if search_str:
            last = search_str[-1]
            if last == 'A':
                new_last = '@'
            elif last.isalpha():
                new_last = chr(ord(last) - 1)
            else:
                new_last = last
            search_mod = search_str[:-1] + new_last + '~'
        else:
            search_mod = '~'
        from_param = (cursor_name + '~') if cursor_name else search_mod
        rpc = 'ORWPT LIST ALL'
        last_err: Exception | None = None
        for ctx in context_candidates:
            try:
                raw = gw.call_rpc(context=ctx, rpc=rpc, parameters=[{'string': from_param}, {'string': '1'}], json_result=False, timeout=60)
                raw_text = _unwrap_vax_raw(raw)
                all_results = _parse_lines(raw_text)
                filtered = [r for r in all_results if r['name'].upper().startswith(search_str)]
                page_matches = filtered[:page_size]
                next_cursor = page_matches[-1]['name'] if len(filtered) > page_size else None
                return jsonify({'matches': page_matches, 'context': ctx, 'rpc': rpc, 'hasMore': bool(next_cursor), 'nextCursor': next_cursor})
            except Exception as e:
                last_err = e
                continue
        return jsonify({'error': f"{rpc} failed for all contexts", 'contexts_tried': context_candidates, 'detail': str(last_err)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
