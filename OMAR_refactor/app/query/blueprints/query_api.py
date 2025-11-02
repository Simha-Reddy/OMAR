from __future__ import annotations
from flask import Blueprint, request, jsonify
from ..registry import ModelRegistry

bp = Blueprint('query_api', __name__)
_registry = ModelRegistry()

@bp.post('/ask')
def ask():
    try:
        data = request.get_json(force=True, silent=True) or {}
        prompt = (data.get('prompt') or '').strip()
        model_id = (data.get('model_id') or 'default').strip()
        patient = data.get('patient')
        if not prompt:
            return jsonify({ 'error': 'Missing prompt' }), 400
        provider = _registry.get(model_id)
        result = provider.answer({ 'prompt': prompt, 'patient': patient })
        # Ensure provider_id is present
        result['provider_id'] = getattr(provider, 'provider_id', model_id) or model_id
        return jsonify(result)
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500
