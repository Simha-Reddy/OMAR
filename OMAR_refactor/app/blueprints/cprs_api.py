from __future__ import annotations
from flask import Blueprint, jsonify
from ..gateways.factory import get_gateway

bp = Blueprint('cprs_api', __name__)

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

@bp.get('/sync')
def cprs_sync_top():
    """Return the current CPRS-selected patient, if any.
    Uses ORWPT TOP under OR CPRS GUI CHART context.
    Response: { ok: bool, dfn: str, name: str, raw: str }
    """
    try:
        gw = get_gateway()
        raw = gw.call_rpc(context='OR CPRS GUI CHART', rpc='ORWPT TOP', parameters=[], json_result=False, timeout=30)
        text = _unwrap_vax_raw(raw).strip()
        dfn = ''
        name = ''
        if text:
            # Heuristic parse: caret-delimited expected; e.g., "123^DOE,JOHN^..."
            parts = [p.strip() for p in text.split('^')]
            if len(parts) >= 2:
                dfn = parts[0]
                name = parts[1]
            else:
                # Fallback: try comma split
                cparts = [p.strip() for p in text.split(',')]
                if len(cparts) >= 2:
                    name = f"{cparts[0]},{cparts[1]}"
        return jsonify({ 'ok': bool(dfn), 'dfn': dfn, 'name': name, 'raw': text })
    except Exception as e:
        return jsonify({ 'ok': False, 'dfn': '', 'name': '', 'error': str(e) })
