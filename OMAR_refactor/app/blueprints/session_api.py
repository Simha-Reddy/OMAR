from __future__ import annotations
import json
import time
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app

bp = Blueprint('session_api', __name__)


def _redis():
	return current_app.config.get('SESSION_REDIS')


def _truthy(v: Any) -> bool:
	return str(v).strip().lower() in ('1', 'true', 'yes', 'on') if v is not None else False


def _get_user_id() -> str:
	try:
		from flask import session as flask_session
		uid = flask_session.get('user_id')
		if uid:
			return str(uid)
	except Exception:
		pass
	return 'dev-user'


def _state_key(user_id: str, patient_id: str) -> str:
	return f"ephemeral:state:{user_id}:{patient_id}"


def _load_state(user_id: str, patient_id: str) -> Dict[str, Any]:
	r = _redis()
	if r is None:
		store = current_app.config.setdefault('_EPHEMERAL_STATE', {})
		return store.get((user_id, patient_id), {})
	raw = r.get(_state_key(user_id, patient_id))
	if not raw:
		return {}
	try:
		return json.loads(raw.decode('utf-8'))
	except Exception:
		return {}


def _save_state(user_id: str, patient_id: str, state: Dict[str, Any]):
	# ensure basic shape
	state = state or {}
	state.setdefault('updated_at', time.time())
	ttl = int(current_app.config.get('EPHEMERAL_STATE_TTL', 1800))
	r = _redis()
	if r is None:
		store = current_app.config.setdefault('_EPHEMERAL_STATE', {})
		store[(user_id, patient_id)] = state
		return
	r.setex(_state_key(user_id, patient_id), ttl, json.dumps(state, ensure_ascii=False).encode('utf-8'))


def _merge_state(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
	if not existing:
		existing = {}
	out = dict(existing)
	# Replace known fields when provided; for lists we append if special flag set
	for field in ('transcript', 'draftNote', 'patientInstructions'):
		if field in patch:
			out[field] = patch.get(field)
	if 'to_dos' in patch:
		out['to_dos'] = patch.get('to_dos') or []
	if 'heyOmarQueries' in patch:
		incoming = patch.get('heyOmarQueries') or []
		if patch.get('appendQueries', True):
			prior = out.get('heyOmarQueries') or []
			out['heyOmarQueries'] = (prior + incoming)[-200:]
		else:
			out['heyOmarQueries'] = incoming
	# carry forward created_at
	out.setdefault('created_at', existing.get('created_at') or time.time())
	out['updated_at'] = time.time()
	return out


@bp.route('/state', methods=['GET'])
def get_state():
	"""Return full ephemeral session state for a user + patient.
	Query: ?patient_id=...
	Response: JSON state object (may be empty)
	"""
	pid = (request.args.get('patient_id') or '').strip()
	if not pid:
		return jsonify({'error': 'patient_id required'}), 400
	uid = _get_user_id()
	state = _load_state(uid, pid)
	return jsonify({'ok': True, 'state': state})


@bp.route('/state', methods=['POST'])
def post_state():
	"""Upsert partial ephemeral session state.
	Body JSON: { patient_id, transcript?, draftNote?, to_dos?, patientInstructions?, heyOmarQueries?, appendQueries? }
	"""
	data = request.get_json(silent=True) or {}
	pid = str(data.get('patient_id') or '').strip()
	if not pid:
		return jsonify({'error': 'patient_id required'}), 400
	uid = _get_user_id()
	current = _load_state(uid, pid)
	merged = _merge_state(current, data)
	_save_state(uid, pid, merged)
	return jsonify({'ok': True, 'state': merged})


@bp.route('/purge', methods=['POST'])
def purge_state():
	"""Delete ephemeral session state for a patient.
	Body JSON: { patient_id }
	"""
	data = request.get_json(silent=True) or {}
	pid = str(data.get('patient_id') or '').strip()
	if not pid:
		return jsonify({'error': 'patient_id required'}), 400
	uid = _get_user_id()
	r = _redis()
	if r is None:
		store = current_app.config.setdefault('_EPHEMERAL_STATE', {})
		store.pop((uid, pid), None)
	else:
		r.delete(_state_key(uid, pid))
	return jsonify({'ok': True})

