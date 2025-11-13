from __future__ import annotations
from typing import Any, Dict, Optional
import re
from flask import Blueprint, jsonify, request, session as flask_session
from ..gateways.factory import set_mode_demo, set_mode_socket, logout_socket, get_gateway

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


_STATION_RE = re.compile(r"\b(\d{3,4})\b")


def _extract_station_hint(*candidates: Any) -> Optional[str]:
    for candidate in candidates:
        if not candidate:
            continue
        try:
            match = _STATION_RE.search(str(candidate))
        except Exception:
            match = None
        if match:
            value = match.group(1)
            if value:
                return value
    return None


def _list_sites_from_env() -> Dict[str, Dict[str, Any]]:
    import os
    sites: Dict[str, Dict[str, Any]] = {}
    raw = os.getenv('OMAR_SITES', '')
    if raw:
        for ent in [p.strip() for p in raw.split(';') if p.strip()]:
            toks = [t.strip() for t in _re_split_multi(ent, ['|', ',']) if t.strip()]
            if len(toks) >= 3:
                name, host, port_str = toks[0], toks[1], toks[2]
                station_hint = toks[3] if len(toks) >= 4 else None
                try:
                    port = int(port_str)
                except Exception:
                    continue
                key = _slugify(name)
                entry = { 'key': key, 'name': name, 'host': host, 'port': port }
                station = _extract_station_hint(station_hint, name)
                if station:
                    entry['station'] = station
                sites[key] = entry
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
        entry = { 'key': key, 'name': name, 'host': host, 'port': port }
        station_env = os.getenv(f'SITE_{i}_STATION')
        station = _extract_station_hint(station_env, name)
        if station:
            entry['station'] = station
        sites[key] = entry
    return sites


@bp.get('/api/sites')
def list_sites():
    sites = _list_sites_from_env()
    # Add DEMO entry for vista-api-x
    out = [{ 'key': 'demo', 'name': 'DEMO (vista-api-x)', 'mode': 'demo', 'station': 'demo' }]
    # Append socket sites
    for k, s in sites.items():
        rec = dict(s)
        rec['mode'] = 'socket'
        out.append(rec)
    return jsonify({ 'sites': out })


def _parse_user_identity(raw: Any) -> Dict[str, str]:
    info: Dict[str, str] = {}
    try:
        text = str(raw or '').strip()
    except Exception:
        return info
    if not text:
        return info
    normalized = text.replace('\r', '\n')
    lines = [line.strip() for line in normalized.split('\n') if line.strip()]
    if not lines:
        return info
    first = lines[0]
    fields = [segment.strip() for segment in first.split('^')] if '^' in first else [first]
    # DUZ: prefer first numeric field
    for segment in fields + lines:
        if segment and segment.strip().isdigit():
            info['duz'] = segment.strip()
            break
    # User name: typically second caret field or second line
    if len(fields) >= 2 and fields[1]:
        info['user_name'] = fields[1]
    elif len(lines) >= 2 and lines[1] and not lines[1].isdigit():
        info['user_name'] = lines[1]
    # Station hint: look for 3-4 digit code distinct from DUZ
    duz_val = info.get('duz')
    for segment in fields + lines:
        match = _STATION_RE.search(segment)
        if match:
            candidate = match.group(1)
            if candidate and candidate != duz_val:
                info['station'] = candidate
                break
    return info


def _capture_user_identity(site: Dict[str, Any]) -> Dict[str, str]:
    identity: Dict[str, str] = {}
    try:
        gw = get_gateway()
        if getattr(gw, 'connect', None):
            try:
                gw.connect()  # type: ignore[attr-defined]
            except Exception:
                pass
        if getattr(gw, 'call_rpc', None):
            raw = gw.call_rpc(  # type: ignore[attr-defined]
                context=getattr(gw, 'default_context', '') or '',
                rpc='XUS GET USER INFO',
                parameters=[]
            )
            identity = _parse_user_identity(raw)
    except Exception:
        identity = {}

    # Persist to session for downstream context merges
    duz = identity.get('duz')
    if duz:
        flask_session['duz'] = str(duz)
    station = identity.get('station') or site.get('station') or site.get('key')
    if station:
        flask_session['station'] = str(station)
    name = identity.get('user_name')
    if name:
        flask_session['user_name'] = name
    return identity


@bp.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    site_key = (data.get('siteKey') or '').strip().lower()
    if not site_key:
        return jsonify({ 'error': 'siteKey required' }), 400
    if site_key == 'demo':
        set_mode_demo()
        flask_session['station'] = 'demo'
        flask_session['duz'] = '0'
        flask_session['user_name'] = 'Demo User'
        flask_session.modified = True
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
        identity = _capture_user_identity(site)
        flask_session.modified = True
        response_payload = {
            'ok': True,
            'mode': 'socket',
            'site': {
                'key': site.get('key'),
                'name': site.get('name'),
                'host': site.get('host'),
                'port': site.get('port'),
                'station': site.get('station') or identity.get('station')
            }
        }
        if identity:
            response_payload['user'] = identity
        return jsonify(response_payload)
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500


@bp.post('/api/logout')
def logout():
    try:
        logout_socket()
        return jsonify({ 'ok': True })
    except Exception as e:
        return jsonify({ 'error': str(e) }), 500
