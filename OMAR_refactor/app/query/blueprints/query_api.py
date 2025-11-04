from __future__ import annotations
from flask import Blueprint, request, jsonify
from ..registry import QueryModelRegistry
from flask import session as flask_session
import os

bp = Blueprint('query_api', __name__)
_registry = QueryModelRegistry()

@bp.post('/ask')
def ask():
    try:
        data = request.get_json(force=True, silent=True) or {}
        # Prefer 'query' over legacy 'prompt'
        query = (data.get('query') or data.get('prompt') or '').strip()
        model_id = (data.get('model_id') or 'default').strip()
        patient = data.get('patient') or {}
        # Normalize DFN in payload and fallback to session when missing
        try:
            dfn = (patient.get('DFN') or patient.get('dfn') or patient.get('localId') or patient.get('patientId') or '').strip()
        except Exception:
            dfn = ''
        if not dfn:
            try:
                meta = flask_session.get('patient_meta') or {}
                dfn = str(meta.get('dfn') or '').strip()
            except Exception:
                dfn = ''
        if dfn:
            patient['DFN'] = dfn
        # Add session vista routing (station/duz) for downstream gateway use
        station = str(flask_session.get('station') or os.getenv('DEFAULT_STATION','500'))
        duz = str(flask_session.get('duz') or os.getenv('DEFAULT_DUZ','983'))
        vista_ctx = { 'station': station, 'duz': duz }
        if not query:
            return jsonify({ 'error': 'Missing query' }), 400
        model = _registry.get(model_id)
        # Pass 'query' to the model; models are responsible for RAG + preface composition
        result = model.answer({ 'query': query, 'patient': patient, 'session': vista_ctx })
        try:
            # Minimal diagnostics for debugging: do not include PHI
            chunks_cnt = len(result.get('citations') or []) if isinstance(result, dict) else -1
            print(f"[ASK] model={model_id} dfn={(patient.get('DFN') or '')} query_len={len(query)} citations={chunks_cnt}")
        except Exception:
            pass
        # Ensure model_id is present
        result['model_id'] = getattr(model, 'model_id', model_id) or model_id
        return jsonify(result)
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500
