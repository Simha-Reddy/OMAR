from __future__ import annotations
from flask import Blueprint, request, jsonify
from ...services.patient_service import PatientService
from ...gateways.vista_api_x_gateway import VistaApiXGateway
from ..query_models.default.services.rag_store import store

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
        # If already indexed with chunks, avoid re-fetching VPR
        st = store.status(dfn)
        if st.get('indexed') and int(st.get('chunks', 0)) > 0:
            manifest = st
        else:
            svc = _get_patient_service()
            # Request full text when available to ensure chunking produces excerpts
            vpr_docs = svc.get_vpr_raw(dfn, 'documents', params={'text': '1'})
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


@bp.post('/index/embed-docs')
def embed_docs():
    """Embed a specified list of document IDs for the patient according to the active store.
    Body: { dfn: string, ids: [string] }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        dfn = (data.get('dfn') or data.get('patientId') or data.get('localId') or '').strip()
        ids = data.get('ids') or data.get('docIds') or data.get('doc_ids') or []
        if not dfn:
            return jsonify({'error': 'dfn is required'}), 400
        if not isinstance(ids, list) or not ids:
            return jsonify({'error': 'ids is required'}), 400
        ids_set = set(str(x) for x in ids if x is not None)
        # Ensure index exists before embedding; skip network if already present
        st = store.status(dfn)
        if not (st.get('indexed') and int(st.get('chunks', 0)) > 0):
            svc = _get_patient_service()
            # Ensure index with text when possible
            vpr_docs = svc.get_vpr_raw(dfn, 'documents', params={'text': '1'})
            store.ensure_index(dfn, vpr_docs)
            # If still no chunks (e.g., server omitted text), fetch full text for the specified ids and ingest
            st = store.status(dfn)
        if not st.get('indexed') or int(st.get('chunks', 0)) == 0:
            try:
                svc = _get_patient_service()
                params = { 'id': ','.join(list(ids_set)[:50]) }  # cap batch
                vpr_subset = svc.get_vpr_raw(dfn, 'documents', params=params)
                # Extract minimal {id, text, date, title} for ingestion
                from ..query_models.default.services.rag import RagEngine
                items = []
                data_items = (vpr_subset.get('data') or {}).get('items') if isinstance(vpr_subset, dict) else None
                raw_list = data_items if isinstance(data_items, list) else (vpr_subset.get('items') if isinstance(vpr_subset, dict) else [])
                for it in (raw_list or []):
                    if not isinstance(it, dict):
                        continue
                    # Match by id or localId
                    nid = str(it.get('id') or it.get('localId') or it.get('uid') or '')
                    if not nid or nid not in ids_set:
                        continue
                    txt = RagEngine._extract_note_text(it)
                    if not txt:
                        continue
                    title = it.get('localTitle') or it.get('title') or it.get('displayName') or ''
                    date = it.get('referenceDateTime') or it.get('dateTime') or it.get('entered') or ''
                    items.append({ 'id': nid, 'text': txt, 'title': title, 'date': date })
                if items:
                    store.ingest_texts(dfn, items)
            except Exception:
                pass
        manifest = store.embed_subset(dfn, ids_set)
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
