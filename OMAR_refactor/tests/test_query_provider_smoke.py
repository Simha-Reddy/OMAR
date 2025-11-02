from app.query.providers.default.provider import provider


def test_provider_smoke_no_patient():
    out = provider.answer({ 'prompt': 'What is the A1c?' })
    assert isinstance(out, dict)
    assert out.get('provider_id') == 'default'
    assert 'answer' in out
