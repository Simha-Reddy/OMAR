from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from ..gateways.factory import set_mode_demo, set_mode_socket, logout_socket

bp = Blueprint('auth_api', __name__)


def _slugify(name: str) -> str:
    try:
        import re
        s = re.sub(r"[^A-Za-z0-9]+", "-", str(name or '').strip().lower())
        s = re.sub(r"-+", "-", s).strip('-')
        return s or 'default'
    except Exception:
        return 'default'


def _re_split_multi(s: str, seps):
    try:
        import re
        pattern = '|'.join(re.escape(x) for x in seps)
        return [p for p in re.split(pattern, s) if p is not None]
    except Exception:
        return [s]


def _list_sites_from_env() -> Dict[str, Dict[str, Any]]:
    import os
    sites: Dict[str, Dict[str, Any]] = {}
    raw = os.getenv('OMAR_SITES', '')
    if raw:
        for ent in [p.strip() for p in raw.split(';') if p.strip()]:
            toks = [t.strip() for t in _re_split_multi(ent, ['|', ',']) if t.strip()]
            if len(toks) >= 3:
                name, host, port_str = toks[0], toks[1], toks[2]
                try:
                    port = int(port_str)
                except Exception:
                    continue
                key = _slugify(name)
                sites[key] = { 'key': key, 'name': name, 'host': host, 'port': port }
    # Numbered triplets SITE_n_*
    for i in range(1, 21):
        name = os.getenv(f'SITE_{i}_NAME')
        host = os.getenv(f'SITE_{i}_HOST')
        port_str = os.getenv(f'SITE_{i}_PORT')
        if not (name and host and port_str):
            continue
        try:
            port = int(port_str)
        except Exception:
            continue
        key = _slugify(name)
        sites[key] = { 'key': key, 'name': name, 'host': host, 'port': port }
    return sites


@bp.get('/api/sites')
def list_sites():
    sites = _list_sites_from_env()
    # Add DEMO entry for vista-api-x
    out = [{ 'key': 'demo', 'name': 'DEMO (vista-api-x)', 'mode': 'demo' }]
    # Append socket sites
    for k, s in sites.items():
        rec = dict(s)
        rec['mode'] = 'socket'
        out.append(rec)
    return jsonify({ 'sites': out })


@bp.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    site_key = (data.get('siteKey') or '').strip().lower()
    if not site_key:
        return jsonify({ 'error': 'siteKey required' }), 400
    if site_key == 'demo':
        set_mode_demo()
        return jsonify({ 'ok': True, 'mode': 'demo' })
    sites = _list_sites_from_env()
    site = sites.get(site_key)
    if not site:
        return jsonify({ 'error': 'unknown siteKey' }), 400
    access = str(data.get('access') or '')
    verify = str(data.get('verify') or '')
    if not access or not verify:
        return jsonify({ 'error': 'access and verify are required for socket login' }), 400
    default_context = (data.get('context') or '')
    # Store and create gateway; connection is validated lazily by first RPC call
    try:
        set_mode_socket(site, access, verify, default_context or None)
        return jsonify({ 'ok': True, 'mode': 'socket', 'site': { 'key': site['key'], 'name': site['name'] } })
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500


@bp.post('/api/logout')
def logout():
    try:
        logout_socket()
        return jsonify({ 'ok': True })
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500
