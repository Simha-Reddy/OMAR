from __future__ import annotations
from flask import Blueprint, jsonify

bp = Blueprint('scribe_api', __name__)

@bp.post('/transcribe')
def transcribe():
    # Placeholder: implement Speech-to-Text and return a transcript
    return jsonify({ 'error': 'Not implemented yet' }), 501
