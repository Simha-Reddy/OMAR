from __future__ import annotations
from flask import Blueprint, request, jsonify
from ...services.patient_service import PatientService
from ...gateways.vista_api_x_gateway import VistaApiXGateway
from ..services.rag_store import store

bp = Blueprint('rag_api', __name__)


def _get_patient_service() -> PatientService:
    from flask import session as flask_session
    import os
    station = str(flask_session.get('station') or os.getenv('DEFAULT_STATION','500'))
    duz = str(flask_session.get('duz') or os.getenv('DEFAULT_DUZ','983'))
    gw = VistaApiXGateway(station=station, duz=duz)
    return PatientService(gateway=gw)


@bp.post('/index/start')
def start_index():
    try:
        data = request.get_json(force=True, silent=True) or {}
        dfn = (data.get('dfn') or data.get('patientId') or data.get('localId') or '').strip()
        if not dfn:
            return jsonify({'error': 'dfn is required'}), 400
        svc = _get_patient_service()
        vpr_docs = svc.get_vpr_raw(dfn, 'document')
        manifest = store.ensure_index(dfn, vpr_docs)
        return jsonify({'status': 'ok', 'manifest': manifest})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.post('/index/embed')
def embed_index():
    try:
        data = request.get_json(force=True, silent=True) or {}
        dfn = (data.get('dfn') or data.get('patientId') or data.get('localId') or '').strip()
        if not dfn:
            return jsonify({'error': 'dfn is required'}), 400
        manifest = store.embed_now(dfn)
        if 'error' in manifest:
            return jsonify(manifest), 400
        return jsonify({'status': 'ok', 'manifest': manifest})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.get('/index/status')
def index_status():
    try:
        dfn = (request.args.get('dfn') or request.args.get('patientId') or request.args.get('localId') or '').strip()
        if not dfn:
            return jsonify({'error': 'dfn is required'}), 400
        st = store.status(dfn)
        return jsonify(st)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
