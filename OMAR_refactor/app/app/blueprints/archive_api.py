from __future__ import annotations
import json
import os
import time
import uuid
from typing import Any, Dict, List

from flask import Blueprint, request, jsonify, current_app

bp = Blueprint('archive_api', __name__)


def _redis():
    return current_app.config.get('SESSION_REDIS')


def _get_user_id() -> str:
    try:
        from flask import session as flask_session
        uid = flask_session.get('user_id')
        if uid:
            return str(uid)
    except Exception:
        pass
    return 'dev-user'


def _archives_dir() -> str:
    # Store under project root's archives folder
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    d = os.path.join(root, 'archives')
    os.makedirs(d, exist_ok=True)
    return d


def _archive_path(archive_id: str) -> str:
    return os.path.join(_archives_dir(), f"{archive_id}.json")


def _user_pref_key(user_id: str, name: str) -> str:
    return f"user:prefs:{user_id}:{name}"


@bp.route('/start', methods=['POST'])
def start_archive():
    """Create a new archive record and return its id.
    Body: { patient_id }
    """
    data = request.get_json(silent=True) or {}
    pid = str(data.get('patient_id') or '').strip()
    if not pid:
        return jsonify({'error': 'patient_id required'}), 400
    uid = _get_user_id()
    archive_id = uuid.uuid4().hex
    content = {
        'archive_id': archive_id,
        'user_id': uid,
        'patient_id': pid,
        'created_at': time.time(),
        'updated_at': time.time(),
        'state': data.get('state') or {}
    }
    with open(_archive_path(archive_id), 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False)
    # Remember current open archive id for this user+patient in Redis for convenience
    r = _redis()
    if r is not None:
        r.setex(f"archive:open:{uid}:{pid}", int(current_app.config.get('EPHEMERAL_STATE_TTL', 1800)), archive_id)
    return jsonify({'ok': True, 'archive_id': archive_id})


@bp.route('/save', methods=['POST'])
def save_archive():
    """Save a snapshot of state to an archive file.
    Body: { patient_id, archive_id?, state }
    If archive_id missing, uses remembered open id or creates a new one.
    """
    data = request.get_json(silent=True) or {}
    pid = str(data.get('patient_id') or '').strip()
    if not pid:
        return jsonify({'error': 'patient_id required'}), 400
    uid = _get_user_id()
    arch_id = (data.get('archive_id') or '').strip()
    r = _redis()
    if not arch_id and r is not None:
        arch_id = (r.get(f"archive:open:{uid}:{pid}") or b'').decode('utf-8')
    if not arch_id:
        arch_id = uuid.uuid4().hex
    path = _archive_path(arch_id)
    doc = {
        'archive_id': arch_id,
        'user_id': uid,
        'patient_id': pid,
        'created_at': time.time(),
        'updated_at': time.time(),
        'state': data.get('state') or {}
    }
    # If file exists, preserve created_at
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                prior = json.load(f)
                doc['created_at'] = prior.get('created_at', doc['created_at'])
        except Exception:
            pass
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False)
    # remember open id
    if r is not None:
        r.setex(f"archive:open:{uid}:{pid}", int(current_app.config.get('EPHEMERAL_STATE_TTL', 1800)), arch_id)
    return jsonify({'ok': True, 'archive_id': arch_id})


@bp.route('/list', methods=['GET'])
def list_archives():
    """List archive records for current user and patient.
    Query: ?patient_id=...
    """
    pid = (request.args.get('patient_id') or '').strip()
    if not pid:
        return jsonify({'error': 'patient_id required'}), 400
    uid = _get_user_id()
    items: List[Dict[str, Any]] = []
    for name in os.listdir(_archives_dir()):
        if not name.endswith('.json'):
            continue
        path = os.path.join(_archives_dir(), name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                doc = json.load(f)
            if doc.get('user_id') == uid and doc.get('patient_id') == pid:
                items.append({
                    'archive_id': doc.get('archive_id'),
                    'created_at': doc.get('created_at'),
                    'updated_at': doc.get('updated_at'),
                })
        except Exception:
            continue
    items.sort(key=lambda x: x.get('updated_at') or 0, reverse=True)
    return jsonify({'ok': True, 'items': items})


@bp.route('/load', methods=['GET'])
def load_archive():
    """Load an archive snapshot by id.
    Query: ?id=...
    """
    arch_id = (request.args.get('id') or '').strip()
    if not arch_id:
        return jsonify({'error': 'id required'}), 400
    path = _archive_path(arch_id)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        return jsonify({'ok': True, 'archive': doc})
    except Exception as e:
        return jsonify({'error': f'failed to load: {e}'}), 500


@bp.route('/auto-archive/toggle', methods=['POST'])
def toggle_auto_archive():
    """Set per-user auto-archive preference.
    Body: { enabled: bool }
    """
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled'))
    uid = _get_user_id()
    r = _redis()
    if r is None:
        store = current_app.config.setdefault('_USER_PREFS', {})
        store[_user_pref_key(uid, 'auto_archive')] = '1' if enabled else '0'
    else:
        r.set(_user_pref_key(uid, 'auto_archive'), '1' if enabled else '0')
    return jsonify({'ok': True, 'enabled': enabled})


@bp.route('/auto-archive/status', methods=['GET'])
def get_auto_archive_status():
    """Return effective auto-archive setting for the user (pref or server default)."""
    uid = _get_user_id()
    default_on = bool(current_app.config.get('AUTO_ARCHIVE_DEFAULT', True))
    r = _redis()
    val = None
    if r is None:
        store = current_app.config.get('_USER_PREFS', {})
        val = store.get(_user_pref_key(uid, 'auto_archive'))
    else:
        v = r.get(_user_pref_key(uid, 'auto_archive'))
        val = v.decode('utf-8') if v else None
    if val is None:
        enabled = default_on
    else:
        enabled = (str(val).strip() == '1')
    return jsonify({'ok': True, 'enabled': enabled, 'default': default_on})


@bp.route('/delete', methods=['DELETE', 'POST'])
def delete_archive():
    """Delete an archive by id if it belongs to the current user.
    Accepts id in query (?id=..) or JSON body { id: ... } for POST fallback.
    """
    arch_id = (request.args.get('id') or '').strip()
    if not arch_id and request.method == 'POST':
        data = request.get_json(silent=True) or {}
        arch_id = str(data.get('id') or '').strip()
    if not arch_id:
        return jsonify({'error': 'id required'}), 400
    path = _archive_path(arch_id)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    # Ensure ownership
    try:
        with open(path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        uid = _get_user_id()
        if doc.get('user_id') != uid:
            return jsonify({'error': 'forbidden'}), 403
    except Exception as e:
        return jsonify({'error': f'failed to verify: {e}'}), 500
    try:
        os.remove(path)
        # Also clear open-id cache if it matched this archive
        r = _redis()
        if r is not None:
            try:
                key = f"archive:open:{uid}:{doc.get('patient_id','')}"
                cur = r.get(key)
                if cur and cur.decode('utf-8') == arch_id:
                    r.delete(key)
            except Exception:
                pass
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': f'failed to delete: {e}'}), 500
