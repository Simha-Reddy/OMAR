from __future__ import annotations
import os
import uuid
from typing import Any, Dict, Optional
from flask import current_app, session as flask_session, g, request

from .vista_api_x_gateway import VistaApiXGateway
from .vista_socket_gateway import VistaSocketGateway


_SESSION_ORDER_KEY = 'gateway_session_order'
_SESSION_ORDER_SEQ_KEY = 'gateway_session_order_seq'


def _reset_session_order() -> None:
    try:
        flask_session.pop(_SESSION_ORDER_KEY, None)
        flask_session.pop(_SESSION_ORDER_SEQ_KEY, None)
    except Exception:
        pass
    try:
        if hasattr(g, '_gateway_session_order'):
            delattr(g, '_gateway_session_order')
    except RuntimeError:
        pass


def _next_session_order() -> int:
    try:
        current = int(flask_session.get(_SESSION_ORDER_SEQ_KEY) or 0)
    except Exception:
        current = 0
    current += 1
    flask_session[_SESSION_ORDER_SEQ_KEY] = current
    return current


def _touch_gateway_context(*, station: Optional[Any] = None, duz: Optional[Any] = None) -> None:
    try:
        ctx: Dict[str, Any] = dict(getattr(g, 'gateway_context', {}) or {})
    except RuntimeError:
        return
    # Capture optional client-supplied identifiers from headers when available.
    client_session_id: Optional[str] = None
    header_order: Optional[int] = None
    try:
        raw_client_id = request.headers.get('X-OMAR-Session-Id', '').strip()
        client_session_id = raw_client_id or None
        raw_order = request.headers.get('X-OMAR-Session-Order', '').strip()
        if raw_order:
            parsed = int(raw_order)
            if parsed > 0:
                header_order = parsed
    except (RuntimeError, ValueError, TypeError):
        client_session_id = client_session_id or None
        header_order = None
    try:
        session_id = _get_session_key()
    except Exception:
        session_id = None
    if session_id:
        ctx['session_id'] = session_id
    if client_session_id:
        ctx['client_session_id'] = client_session_id
    if station is not None:
        ctx['station'] = str(station)
    elif 'station' not in ctx:
        stored_station = flask_session.get('station')
        if stored_station:
            ctx['station'] = str(stored_station)
        else:
            selected_site = flask_session.get('selected_site')
            if isinstance(selected_site, dict):
                site_key = selected_site.get('key') or selected_site.get('station')
                if site_key:
                    ctx['station'] = str(site_key)
    if duz is not None:
        ctx['duz'] = str(duz)
    elif 'duz' not in ctx:
        stored_duz = flask_session.get('duz')
        if stored_duz:
            ctx['duz'] = str(stored_duz)
    try:
        user_id = flask_session.get('user_id')
    except Exception:
        user_id = None
    if user_id:
        ctx['user_id'] = str(user_id)
    try:
        order = getattr(g, '_gateway_session_order')
    except (RuntimeError, AttributeError):
        order = None

    if header_order is not None:
        order = header_order
    if order is None:
        try:
            stored = flask_session.get(_SESSION_ORDER_KEY)
            order = int(stored) if stored is not None else None
        except Exception:
            order = None
    if order is None:
        order = _next_session_order()
    if order is not None:
        try:
            setattr(g, '_gateway_session_order', order)
        except RuntimeError:
            pass
        flask_session[_SESSION_ORDER_KEY] = order
    ctx['session_order'] = order
    g.gateway_context = ctx


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
    _reset_session_order()


def set_mode_socket(site: dict, access: str, verify: str, default_context: Optional[str] = None):
    flask_session['gateway_mode'] = 'socket'
    flask_session['selected_site'] = {
        'name': site.get('name'),
        'host': site.get('host'),
        'port': site.get('port'),
        'key': site.get('key'),
    }
    _reset_session_order()
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
    sid = flask_session.get('gateway_session_id')
    reg = _registry()
    if sid is not None:
        gw = reg.pop(str(sid), None)
        if gw:
            try:
                gw.close()
            except Exception:
                pass
    flask_session.pop('gateway_mode', None)
    flask_session.pop('selected_site', None)
    flask_session.pop('gateway_session_id', None)
    _reset_session_order()


def get_gateway(station: Optional[str] = None, duz: Optional[str] = None):
    """Return the active DataGateway based on session mode.
    - 'demo' => VistaApiXGateway(station/duz)
    - 'socket' => VistaSocketGateway from registry keyed by session id
    """
    mode = str(flask_session.get('gateway_mode') or 'demo')
    if mode == 'socket':
        sid = _get_session_key()
        gw = _registry().get(sid)
        if gw:
            _touch_gateway_context(duz=duz)
            return gw
        # Fallback to demo if not logged in properly
    # DEMO / fallback: vista-api-x
    st = str(station or os.getenv('DEFAULT_STATION', '500'))
    uz = str(duz or os.getenv('DEFAULT_DUZ', '983'))
    _touch_gateway_context(station=st, duz=uz)
    return VistaApiXGateway(station=st, duz=uz)
