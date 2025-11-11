from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import g, session as flask_session, request


def _clean_str(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        return text or None
    except Exception:
        return None


def build_context(*, dfn: Optional[Any] = None, duz: Optional[Any] = None,
                  session_id: Optional[Any] = None, session_order: Optional[Any] = None,
                  client_session_id: Optional[Any] = None, user_id: Optional[Any] = None) -> Dict[str, Any]:
    """Assemble a per-response context payload capturing patient/session identity.

    Values are sourced in priority order:
    1. Explicit keyword arguments supplied to the helper.
    2. ``g.gateway_context`` (populated by the socket gateway factory).
    3. Flask session defaults (DUZ fallback).

    Missing entries are omitted from the resulting dict. ``issuedAt`` is always
    included to support freshness checks on the client. When the browser sends
    ``X-OMAR-Session-Id`` or ``X-OMAR-Session-Order`` headers they are surfaced
    as ``clientSessionId`` and ``sessionOrder`` respectively.
    """
    source_ctx = getattr(g, 'gateway_context', {}) or {}
    header_client_session: Optional[str] = None
    header_session_order: Optional[int] = None
    try:
        raw_client = request.headers.get('X-OMAR-Session-Id', '').strip()
        header_client_session = _clean_str(raw_client)
        raw_order = request.headers.get('X-OMAR-Session-Order', '').strip()
        if raw_order:
            candidate = int(raw_order)
            if candidate > 0:
                header_session_order = candidate
    except (RuntimeError, ValueError, TypeError):
        header_client_session = None
        header_session_order = None
    context: Dict[str, Any] = {}

    resolved_dfn = _clean_str(dfn) or _clean_str(source_ctx.get('dfn'))
    resolved_duz = _clean_str(duz) or _clean_str(source_ctx.get('duz'))
    resolved_session = _clean_str(session_id) or _clean_str(source_ctx.get('session_id'))
    if not resolved_session:
        resolved_session = _clean_str(flask_session.get('gateway_session_id'))
    resolved_client_session = (
        _clean_str(client_session_id)
        or _clean_str(source_ctx.get('client_session_id'))
        or header_client_session
    )
    resolved_user = _clean_str(user_id) or _clean_str(source_ctx.get('user_id'))

    if resolved_dfn:
        context['dfn'] = resolved_dfn
    if resolved_duz:
        context['duz'] = resolved_duz

    if not resolved_duz:
        session_duz = _clean_str(flask_session.get('duz'))
        if session_duz:
            context['duz'] = session_duz

    if resolved_session:
        context['sessionId'] = resolved_session

    resolved_order: Optional[int] = None
    if session_order is not None:
        try:
            resolved_order = int(session_order)
        except Exception:
            resolved_order = None
    elif source_ctx.get('session_order') is not None:
        try:
            resolved_order = int(source_ctx['session_order'])
        except Exception:
            resolved_order = None
    elif header_session_order is not None:
        resolved_order = header_session_order
    elif flask_session.get('gateway_session_order') is not None:
        try:
            session_order = flask_session.get('gateway_session_order')
            resolved_order = int(session_order) if session_order is not None else None
        except Exception:
            resolved_order = None
    if resolved_order is not None:
        context['sessionOrder'] = resolved_order

    if resolved_client_session:
        context['clientSessionId'] = resolved_client_session

    if resolved_user:
        context['userId'] = resolved_user
    else:
        session_user = _clean_str(flask_session.get('user_id'))
        if session_user:
            context['userId'] = session_user

    issued_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    context['issuedAt'] = issued_at
    return context


def merge_context(payload: Any, *, dfn: Optional[Any] = None, **overrides: Any) -> Any:
    """Attach the context block to an existing response payload.

    ``payload`` is returned unchanged when the context dict is empty or the
    payload already contains a top-level ``context`` key.
    """
    context = build_context(dfn=dfn, **overrides)
    if not context:
        return payload
    if isinstance(payload, dict):
        if 'context' not in payload:
            payload = dict(payload)
            payload['context'] = context
        return payload
    return {
        'result': payload,
        'context': context,
    }
