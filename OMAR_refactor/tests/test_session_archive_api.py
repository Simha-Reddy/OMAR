import json
from typing import Optional

import pytest

from app import create_app


def _get_csrf(client) -> Optional[str]:
    # Prime session and cookie
    client.get('/')
    for cookie in client.cookie_jar:
        if cookie.name == 'csrf_token':
            return cookie.value
    return None


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'EPHEMERAL_STATE_TTL': 5,
    })
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_session_state_roundtrip(client):
    csrf = _get_csrf(client)
    assert csrf
    headers = { 'X-CSRF-Token': csrf }
    # Upsert partial state
    resp = client.post('/api/session/state', data=json.dumps({
        'patient_id': '123',
        'draftNote': 'Hello world',
        'to_dos': ['A','B'],
    }), headers={**headers, 'Content-Type': 'application/json'})
    assert resp.status_code == 200
    got = resp.get_json()
    assert got['ok'] is True
    # Read back
    resp = client.get('/api/session/state?patient_id=123')
    assert resp.status_code == 200
    state = resp.get_json()['state']
    assert state.get('draftNote') == 'Hello world'
    assert state.get('to_dos') == ['A','B']


def test_archive_lifecycle(client):
    csrf = _get_csrf(client)
    assert csrf
    headers = { 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' }
    # Start archive
    resp = client.post('/api/archive/start', data=json.dumps({ 'patient_id': '123' }), headers=headers)
    assert resp.status_code == 200
    arch_id = resp.get_json()['archive_id']
    # Save
    resp = client.post('/api/archive/save', data=json.dumps({
        'patient_id': '123',
        'archive_id': arch_id,
        'state': { 'draftNote': 'Saved once' }
    }), headers=headers)
    assert resp.status_code == 200
    # List
    resp = client.get('/api/archive/list?patient_id=123')
    assert resp.status_code == 200
    items = resp.get_json()['items']
    assert any(i['archive_id'] == arch_id for i in items)
    # Load
    resp = client.get(f'/api/archive/load?id={arch_id}')
    assert resp.status_code == 200
    doc = resp.get_json()['archive']
    assert doc['archive_id'] == arch_id
    assert doc['state'].get('draftNote') == 'Saved once'
