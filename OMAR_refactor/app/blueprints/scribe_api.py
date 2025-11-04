from __future__ import annotations
import io
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
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
    meta: Dict[str, Any] = field(default_factory=dict)

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


def _ephemeral_key(user_id: str, patient_id: str) -> str:
    return f"ephemeral:state:{user_id}:{patient_id}"
def _current_visit_id(user_id: str, patient_id: str) -> Optional[str]:
    """Return the current open archive id for this user+patient, if any.
    This serves as a server-side visit identifier.
    """
    r = _redis()
    if r is None:
        # In dev fallback, we don't persist open archive ids; return None
        return None
    try:
        raw = r.get(f"archive:open:{user_id}:{patient_id}")
        if not raw:
            return None
        return raw.decode('utf-8')
    except Exception:
        return None



def _append_transcript_to_ephemeral(user_id: str, patient_id: str, delta: str, last_seq: Optional[int] = None, session_id: Optional[str] = None, status: Optional[str] = None, visit_id: Optional[str] = None):
    """Append transcript delta and/or update scribe metadata in ephemeral state.
    Important: even when delta is empty (silence or status-only), still update
    last_seq/status/visit_id so clients don't see stale metadata.
    """
    r = _redis()
    ttl = int(current_app.config.get('EPHEMERAL_STATE_TTL', 1800))
    if not visit_id:
        visit_id = _current_visit_id(user_id, patient_id)
    if r is None:
        store = current_app.config.setdefault('_EPHEMERAL_STATE', {})
        st = store.get((user_id, patient_id), {})
        if delta:
            st['transcript'] = (st.get('transcript') or '') + delta
        if last_seq is not None:
            st['last_seq'] = int(last_seq)
        if session_id:
            st['scribe_session_id'] = session_id
        if status:
            st['scribe_status'] = status
        if visit_id:
            st['visit_id'] = visit_id
        st['updated_at'] = time.time()
        st.setdefault('created_at', time.time())
        store[(user_id, patient_id)] = st
        return
    try:
        raw = r.get(_ephemeral_key(user_id, patient_id))
        if raw:
            import json as _json
            st = _json.loads(raw.decode('utf-8'))
        else:
            st = {}
    except Exception:
        st = {}
    if delta:
        st['transcript'] = (st.get('transcript') or '') + delta
    if last_seq is not None:
        st['last_seq'] = int(last_seq)
    if session_id:
        st['scribe_session_id'] = session_id
    if status:
        st['scribe_status'] = status
    if visit_id:
        st['visit_id'] = visit_id
    st['updated_at'] = time.time()
    st.setdefault('created_at', time.time())
    import json as _json
    r.setex(_ephemeral_key(user_id, patient_id), ttl, _json.dumps(st, ensure_ascii=False).encode('utf-8'))


def _load_ephemeral_transcript(user_id: str, patient_id: str) -> Dict[str, Any]:
    r = _redis()
    if r is None:
        store = current_app.config.setdefault('_EPHEMERAL_STATE', {})
        st = store.get((user_id, patient_id), {})
        return {
            'transcript': str(st.get('transcript') or ''),
            'last_seq': int(st.get('last_seq') or -1),
            'scribe_session_id': st.get('scribe_session_id') or '',
            'scribe_status': st.get('scribe_status') or '',
            'visit_id': st.get('visit_id') or ''
        }
    try:
        raw = r.get(_ephemeral_key(user_id, patient_id))
        if not raw:
            return { 'transcript': '', 'last_seq': -1, 'scribe_session_id': '', 'scribe_status': '' }
        import json as _json
        st = _json.loads(raw.decode('utf-8'))
        return {
            'transcript': str(st.get('transcript') or ''),
            'last_seq': int(st.get('last_seq') or -1),
            'scribe_session_id': st.get('scribe_session_id') or '',
            'scribe_status': st.get('scribe_status') or '',
            'visit_id': st.get('visit_id') or ''
        }
    except Exception:
        return { 'transcript': '', 'last_seq': -1, 'scribe_session_id': '', 'scribe_status': '', 'visit_id': '' }


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
            seq = int(seq_raw or -1)
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

        # Phase 1: write-through to ephemeral session state for this user+patient
        try:
            _append_transcript_to_ephemeral(
                sess.user_id,
                sess.patient_id,
                delta_text,
                last_seq=sess.last_seq,
                session_id=sess.session_id,
                status=sess.status,
                visit_id=_current_visit_id(sess.user_id, sess.patient_id)
            )
        except Exception:
            pass

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


@bp.route('/transcript', methods=['GET'])
def transcript():
    """Return the current transcript for either a session or a patient.
    Query: session_id=... OR patient_id=...
    If session_id provided, returns session transcript and metadata.
    Else if patient_id provided, returns transcript from ephemeral state for current user.
    """
    try:
        sid = (request.args.get('session_id') or '').strip()
        pid = (request.args.get('patient_id') or '').strip()
        if sid:
            sess = _load_session(sid)
            if not sess:
                return jsonify({ 'error': 'unknown session_id' }), 404
            return jsonify({
                'source': 'session',
                'session_id': sess.session_id,
                'patient_id': sess.patient_id,
                'status': sess.status,
                'last_seq': sess.last_seq,
                'transcript': sess.transcript or ''
            })
        if pid:
            uid = _get_user_id()
            info = _load_ephemeral_transcript(uid, pid)
            # Optional filter by visit_id if provided
            want_vid = (request.args.get('visit_id') or '').strip()
            if want_vid and info.get('visit_id') and info.get('visit_id') != want_vid:
                return jsonify({ 'error': 'unknown visit_id for this patient' }), 404
            return jsonify({
                'source': 'ephemeral',
                'patient_id': pid,
                'session_id': info.get('scribe_session_id') or None,
                'last_seq': info.get('last_seq'),
                'status': info.get('scribe_status') or None,
                'visit_id': info.get('visit_id') or None,
                'transcript': info.get('transcript') or ''
            })
        return jsonify({ 'error': 'session_id or patient_id required' }), 400
    except Exception as e:
        return jsonify({ 'error': f'failed to load transcript: {e}' }), 500


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
        # Reflect status to ephemeral state for the current user+patient
        try:
            _append_transcript_to_ephemeral(
                sess.user_id,
                sess.patient_id,
                '',
                last_seq=sess.last_seq,
                session_id=sess.session_id,
                status=sess.status,
                visit_id=_current_visit_id(sess.user_id, sess.patient_id)
            )
        except Exception:
            pass
        return jsonify({ 'ok': True, 'status': sess.status, 'last_seq': sess.last_seq })
    except Exception as e:
        return jsonify({ 'error': f'failed to stop: {e}' }), 500
