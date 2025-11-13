import json
from typing import Any, Dict

import pytest

from app import create_app


class FakeGateway:
    """Minimal gateway stub that returns a small VPR payload for 'document'."""
    def __init__(self, *args, **kwargs):
        pass

    def get_vpr_domain(self, dfn: str, domain: str, params: Dict[str, Any] | None = None):
        # Only 'document' is used by these tests
        if domain != 'document':
            return { 'data': { 'items': [] } }
        # Two simple documents with ids and text content
        items = [
            {
                'id': '101',
                'localId': '101',
                'uid': f'urn:va:document:{dfn}:101',
                'localTitle': 'Cardiology Consult',
                'documentTypeName': 'Progress Note',
                'documentClass': 'PROGRESS NOTES',
                'referenceDateTime': '202401020930',
                'facilityName': 'Test Facility',
                'authorDisplayName': 'Dr. Heart',
                'text': [ { 'content': 'Patient referred to cardiology clinic for cardiac rehab.' } ],
            },
            {
                'id': '202',
                'localId': '202',
                'uid': f'urn:va:document:{dfn}:202',
                'localTitle': 'Dermatology Visit',
                'documentTypeName': 'Progress Note',
                'documentClass': 'PROGRESS NOTES',
                'referenceDateTime': '202312311100',
                'facilityName': 'Test Facility',
                'authorDisplayName': 'Dr. Skin',
                'text': [ { 'content': 'Routine dermatology check, benign nevus noted.' } ],
            },
        ]
        return { 'data': { 'items': items } }


@pytest.fixture()
def app(monkeypatch):
    # Ensure the document search service uses our fake gateway
    from app.services import document_search_service as dss
    dss._REGISTRY.clear()
    monkeypatch.setattr(dss, 'VistaApiXGateway', FakeGateway, raising=True)

    # Also ensure the patient blueprint PatientService path constructs a FakeGateway
    # by monkeypatching the symbol it imports
    import app.blueprints.patient as patient_bp
    monkeypatch.setattr(patient_bp, 'VistaApiXGateway', FakeGateway, raising=True)

    app = create_app()
    app.config.update({ 'TESTING': True })
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def _get_csrf(client) -> str:
    # Prime session and CSRF cookie
    client.get('/')
    for cookie in client.cookie_jar:
        if cookie.name == 'csrf_token':
            return cookie.value
    return ''


def test_documents_search_prefix_and_snippet(client):
    dfn = '123'
    # Query with a prefix that should match 'cardiology' and 'cardiac'
    resp = client.get(f'/api/patient/{dfn}/documents/search?q=card')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    items = data.get('items') or []
    assert len(items) >= 1
    titles = [it.get('title') for it in items]
    assert 'Cardiology Consult' in titles
    # Snippet should include the matching word region
    first = next(it for it in items if it.get('title') == 'Cardiology Consult')
    assert 'card' in (first.get('snippet') or '').lower()


def test_documents_list_sort_and_identifiers(client):
    dfn = '123'
    # Sort by title ascending and ensure docId is present
    resp = client.get(f'/api/patient/{dfn}/list/documents?sort=title:asc')
    assert resp.status_code == 200
    env = resp.get_json()
    assert isinstance(env, dict)
    items = env.get('items') or []
    assert len(items) == 2
    titles = [it.get('title') for it in items]
    assert titles == sorted(titles)
    # Each item should have docId and uid strings for viewer/text-batch
    for it in items:
        assert isinstance(it.get('docId'), str)
        assert isinstance(it.get('uid'), str)
