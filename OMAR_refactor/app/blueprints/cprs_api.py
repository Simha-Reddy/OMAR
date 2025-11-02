from __future__ import annotations
from flask import Blueprint, jsonify
from ..gateways.vista_api_x_gateway import VistaApiXGateway

bp = Blueprint('cprs_api', __name__)

@bp.get('/sync')
def cprs_sync_top():
    """Return the current CPRS-selected patient, if any.
    Uses ORWPT TOP under OR CPRS GUI CHART context.
    Response: { ok: bool, dfn: str, name: str, raw: str }
    """
    try:
        gw = VistaApiXGateway()
        raw = gw.call_rpc(context='OR CPRS GUI CHART', rpc='ORWPT TOP', parameters=[], json_result=False, timeout=30)
        text = (raw or '').strip()
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
