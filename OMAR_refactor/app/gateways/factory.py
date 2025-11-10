from __future__ import annotations
import os
import uuid
from typing import Optional
from flask import current_app, session as flask_session

from .vista_api_x_gateway import VistaApiXGateway
from .vista_socket_gateway import VistaSocketGateway


def _get_session_key() -> str:
    sid = flask_session.get('gateway_session_id')
    if not sid:
        sid = str(uuid.uuid4())
        flask_session['gateway_session_id'] = sid
    return str(sid)


def _registry() -> dict:
    return current_app.config.setdefault('_SOCKET_GATEWAY_REGISTRY', {})


def set_mode_demo():
    flask_session['gateway_mode'] = 'demo'


def set_mode_socket(site: dict, access: str, verify: str, default_context: Optional[str] = None):
    flask_session['gateway_mode'] = 'socket'
    flask_session['selected_site'] = {
        'name': site.get('name'),
        'host': site.get('host'),
        'port': site.get('port'),
        'key': site.get('key'),
    }
    # Save creds server-side by session id (not in client cookie)
    sid = _get_session_key()
    reg = _registry()
    # Close existing if different
    try:
        prior = reg.get(sid)
        if prior:
            try:
                prior.close()
            except Exception:
                pass
    except Exception:
        pass
    gw = VistaSocketGateway(
        host=str(site.get('host') or ''),
        port=int(str(site.get('port') or '0')),
        access=access,
        verify=verify,
        default_context=default_context or os.getenv('VISTA_DEFAULT_CONTEXT') or 'OR CPRS GUI CHART'
    )
    # Test-connect lazily in endpoints; can also connect here if desired
    reg[sid] = gw


def logout_socket():
    sid = _get_session_key()
    reg = _registry()
    gw = reg.pop(sid, None)
    if gw:
        try:
            gw.close()
        except Exception:
            pass
    flask_session.pop('gateway_mode', None)
    flask_session.pop('selected_site', None)


def get_gateway(station: Optional[str] = None, duz: Optional[str] = None):
    """Return the active DataGateway based on session mode.
    - 'demo' => VistaApiXGateway(station/duz)
    - 'socket' => VistaSocketGateway from registry keyed by session id
    """
    mode = str(flask_session.get('gateway_mode') or 'demo')
    if mode == 'socket':
        gw = _registry().get(_get_session_key())
        if gw:
            return gw
        # Fallback to demo if not logged in properly
    # DEMO / fallback: vista-api-x
    st = str(station or os.getenv('DEFAULT_STATION', '500'))
    uz = str(duz or os.getenv('DEFAULT_DUZ', '983'))
    return VistaApiXGateway(station=st, duz=uz)
