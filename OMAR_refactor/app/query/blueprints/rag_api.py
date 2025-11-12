from __future__ import annotations
import os
from typing import Any, Mapping
from flask import Blueprint, request, jsonify, session as flask_session
from ...services.patient_service import PatientService
from ...services.document_search_service import get_or_build_index_for_dfn
from ...gateways.factory import get_gateway
from ..query_models.default.services.rag_store import store

bp = Blueprint('documents_api', __name__)


def _get_patient_service() -> PatientService:
    station = str(flask_session.get('station') or os.getenv('DEFAULT_STATION', '500'))
    duz = str(flask_session.get('duz') or os.getenv('DEFAULT_DUZ', '983'))
    gw = get_gateway(station=station, duz=duz)
    return PatientService(gateway=gw)


def _extract_model(data: Mapping[str, Any] | None) -> str:
    if not data:
        return 'default'
    for key in ('model', 'queryModel', 'query_model', 'ragModel'):
        if not hasattr(data, 'get'):
            break
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, list) and value:
            candidate = value[0]
        else:
            candidate = value
        if isinstance(candidate, str):
            candidate = candidate.strip()
        else:
            candidate = str(candidate).strip()
        if candidate:
            return candidate
    return 'default'

@bp.post('/index/start')
def start_index():
    try:
        data = request.get_json(force=True, silent=True) or {}
        dfn = (data.get('dfn') or data.get('patientId') or data.get('localId') or '').strip()
        if not dfn:
            return jsonify({'error': 'dfn is required'}), 400
        model = _extract_model(data)
        st = store.status(dfn, model=model)
        svc = _get_patient_service()
        doc_index = get_or_build_index_for_dfn(dfn, gateway=svc.gateway, force=not (st.get('indexed') and int(st.get('chunks', 0)) > 0))
        manifest = store.ensure_index(dfn, doc_index, force=not (st.get('indexed') and int(st.get('chunks', 0)) > 0), model=model)
        try:
            if manifest.get('lexical_only', True):
                store.embed_docs_policy(dfn, doc_index, model=model)
        except Exception:
            pass
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
        model = _extract_model(data)
        manifest = store.embed_now(dfn, model=model)
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
        model = _extract_model(data)
        st = store.status(dfn, model=model)
        svc = _get_patient_service()
        doc_index = get_or_build_index_for_dfn(dfn, gateway=svc.gateway, force=not (st.get('indexed') and int(st.get('chunks', 0)) > 0))
        manifest = store.ensure_index(dfn, doc_index, force=not (st.get('indexed') and int(st.get('chunks', 0)) > 0), model=model)
        if manifest.get('chunks', 0) == 0:
            try:
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
                    store.ingest_texts(dfn, items, model=model)
            except Exception:
                pass
        manifest = store.embed_subset(dfn, ids_set, model=model)
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
        model = _extract_model(request.args)
        st = store.status(dfn, model=model)
        return jsonify(st)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
