from __future__ import annotations
import io
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from flask import Blueprint, request, jsonify, current_app
from ..scribe.providers import get_transcription_provider, TranscriptionResult

bp = Blueprint('scribe_api', __name__)

# Storage backends: prefer Redis when available; fall back to in-process dict (dev only)
# Data is text transcript only; audio chunks are not persisted.

@dataclass
class ScribeSession:
    session_id: str
    patient_id: str
    user_id: str
    created_at: float
    last_seq: int = -1
    status: str = "active"  # active | stopped
    transcript: str = ""
    meta: Dict[str, Any] = None

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, ensure_ascii=False)

    @staticmethod
    def from_json(s: str) -> "ScribeSession":
        d = json.loads(s)
        return ScribeSession(**d)


def _redis():
    # SESSION_REDIS is set by app factory when Redis/FakeRedis is available
    return current_app.config.get('SESSION_REDIS')


def _session_key(session_id: str) -> str:
    return f"scribe:session:{session_id}"


def _get_user_id() -> str:
    # Placeholder until real auth; keep it non-PII
    # Try to get from session if available, else a fixed dev user
    try:
        from flask import session as flask_session
        uid = flask_session.get('user_id')
        if uid:
            return str(uid)
    except Exception:
        pass
    return "dev-user"


def _load_session(session_id: str) -> Optional[ScribeSession]:
    r = _redis()
    if r is not None:
        raw = r.get(_session_key(session_id))
        if not raw:
            return None
        return ScribeSession.from_json(raw.decode('utf-8'))
    # fallback
    store = current_app.config.setdefault('_SCRIBE_STORE', {})
    sess = store.get(session_id)
    return sess


def _save_session(sess: ScribeSession, ttl_seconds: int = 3600):
    r = _redis()
    if r is not None:
        r.setex(_session_key(sess.session_id), ttl_seconds, sess.to_json().encode('utf-8'))
        return
    # fallback
    store = current_app.config.setdefault('_SCRIBE_STORE', {})
    store[sess.session_id] = sess


@bp.route('/session', methods=['POST'])
def create_session():
    """Start a new scribe session.
    Body JSON: { patient_id: str }
    Returns: { session_id }
    """
    try:
        data = request.get_json(silent=True) or {}
        patient_id = str(data.get('patient_id') or '').strip()
        if not patient_id:
            return jsonify({ 'error': 'patient_id required' }), 400
        user_id = _get_user_id()
        session_id = uuid.uuid4().hex
        sess = ScribeSession(
            session_id=session_id,
            patient_id=patient_id,
            user_id=user_id,
            created_at=time.time(),
            meta={}
        )
        _save_session(sess)
        return jsonify({ 'session_id': session_id })
    except Exception as e:
        return jsonify({ 'error': f'failed to create session: {e}' }), 500


@bp.route('/stream', methods=['POST'])
def upload_chunk():
    """Upload an audio chunk for transcription.
    Query: ?session_id=...&seq=N
    Headers: x-patient-id, x-patient-generation (optional), Content-Type: audio/*
    Body: binary audio
    Returns: 200 OK, optional JSON { transcript_delta }
    """
    try:
        session_id = (request.args.get('session_id') or '').strip()
        if not session_id:
            return jsonify({ 'error': 'session_id missing' }), 400
        seq_raw = request.args.get('seq')
        try:
            seq = int(seq_raw)
            if seq < 0: raise ValueError
        except Exception:
            return jsonify({ 'error': 'seq must be a non-negative integer' }), 400

        sess = _load_session(session_id)
        if not sess:
            return jsonify({ 'error': 'unknown session_id' }), 404
        if sess.status != 'active':
            return jsonify({ 'error': 'session not active' }), 409

        # Patient guard
        hdr_pid = (request.headers.get('x-patient-id') or '').strip()
        if not hdr_pid:
            return jsonify({ 'error': 'x-patient-id header required' }), 400
        if hdr_pid != sess.patient_id:
            return jsonify({ 'error': 'patient mismatch' }), 409

        # CSRF is enforced globally by middleware; we only do app-level guards here.

        # Idempotency: ignore if already processed
        if seq <= sess.last_seq:
            return jsonify({ 'ok': True, 'skipped': True, 'last_seq': sess.last_seq })

        # Read body (binary audio)
        content_type = request.headers.get('Content-Type','application/octet-stream')
        audio_bytes = request.get_data(cache=False, as_text=False) or b''

        # Call provider (pluggable; Azure when configured)
        provider = get_transcription_provider()
        provider_name = getattr(provider, 'name', provider.__class__.__name__)
        lang = os.getenv('SCRIBE_LANG', 'en-US')
        result: TranscriptionResult
        try:
            result = provider.transcribe_chunk(audio_bytes, content_type, language=lang)
            delta_text = result.text or ''
        except Exception as e:
            # Fallback to a simple marker if provider fails
            delta_text = ''
        used_fallback = False

        if not delta_text:
            # Do not clutter transcript on silence or no-text; just mark fallback for telemetry
            used_fallback = True

        sess.transcript = (sess.transcript or '') + delta_text
        sess.last_seq = seq
        _save_session(sess)

        return jsonify({ 'ok': True, 'last_seq': sess.last_seq, 'transcript_delta': delta_text, 'provider': provider_name, 'fallback': used_fallback })
    except Exception as e:
        return jsonify({ 'error': f'upload failed: {e}' }), 500


@bp.route('/status', methods=['GET'])
def status():
    session_id = (request.args.get('session_id') or '').strip()
    if not session_id:
        return jsonify({ 'error': 'session_id missing' }), 400
    sess = _load_session(session_id)
    if not sess:
        return jsonify({ 'error': 'unknown session_id' }), 404
    return jsonify({
        'session_id': sess.session_id,
        'patient_id': sess.patient_id,
        'status': sess.status,
        'last_seq': sess.last_seq,
        'transcript': sess.transcript or ''
    })


@bp.route('/stop', methods=['POST'])
def stop():
    try:
        session_id = (request.args.get('session_id') or '').strip()
        if not session_id:
            return jsonify({ 'error': 'session_id missing' }), 400
        sess = _load_session(session_id)
        if not sess:
            return jsonify({ 'error': 'unknown session_id' }), 404
        # Patient guard (optional): ensure header patient matches
        hdr_pid = (request.headers.get('x-patient-id') or '').strip()
        if hdr_pid and hdr_pid != sess.patient_id:
            return jsonify({ 'error': 'patient mismatch' }), 409
        sess.status = 'stopped'
        _save_session(sess)
        return jsonify({ 'ok': True, 'status': sess.status, 'last_seq': sess.last_seq })
    except Exception as e:
        return jsonify({ 'error': f'failed to stop: {e}' }), 500
